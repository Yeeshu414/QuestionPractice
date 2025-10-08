from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from apscheduler.schedulers.background import BackgroundScheduler
from openai import OpenAI
import random
import asyncio
import datetime
import re
import os
import sqlite3
import json
import base64
import requests
import threading
from dotenv import load_dotenv
from sympy import sympify, latex, symbols, simplify, expand, N
from sympy.parsing.latex import parse_latex

# === Rate Limiting ===
user_last_question_time = {}
user_processing_questions = {}
question_generation_lock = threading.Lock()
QUESTION_COOLDOWN = 5

def can_generate_question(chat_id):
    """Check if user can generate a new question (rate limiting)"""
    current_time = datetime.datetime.now()
    if chat_id not in user_last_question_time:
        user_last_question_time[chat_id] = current_time
        return True
    time_diff = (current_time - user_last_question_time[chat_id]).total_seconds()
    if time_diff >= QUESTION_COOLDOWN:
        user_last_question_time[chat_id] = current_time
        return True
    return False

def get_cooldown_remaining(chat_id):
    """Get remaining cooldown time for user"""
    if chat_id not in user_last_question_time:
        return 0
    current_time = datetime.datetime.now()
    time_diff = (current_time - user_last_question_time[chat_id]).total_seconds()
    return max(0, QUESTION_COOLDOWN - time_diff)

def check_and_set_processing(chat_id):
    """Atomically check if user can process and set processing flag"""
    with question_generation_lock:
        if chat_id in user_processing_questions or not can_generate_question(chat_id):
            return False
        user_processing_questions[chat_id] = True
        return True

def clear_processing(chat_id):
    """Clear user processing status"""
    with question_generation_lock:
        user_processing_questions.pop(chat_id, None)

# === Text Cleaning Functions ===
def clean_mathematical_text(text):
    """Convert LaTeX mathematical code to plain text"""
    if not text:
        return text
    
    # LaTeX to text replacements
    replacements = [
        (r'\\[()\[\]]', ''), (r'\$\$(.*?)\$\$', r'\1'), (r'\$(.*?)\$', r'\1'),
        (r'\\frac\{([^}]*)\}\{([^}]*)\}', r'(\1)/(\2)'), (r'\\sqrt\{([^}]*)\}', r'sqrt(\1)'),
        (r'\\times|\\cdot', '*'), (r'\\div', '/'), (r'\\pi', 'pi'), (r'\\alpha', 'alpha'),
        (r'\\beta', 'beta'), (r'\\gamma', 'gamma'), (r'\\delta', 'delta'), (r'\\log|\\ln', 'log'),
        (r'\\sin', 'sin'), (r'\\cos', 'cos'), (r'\\tan', 'tan'), (r'\\exp', 'exp'),
        (r'\{([^}]*)\}', r'\1'), (r'\^{([^}]*)}', r'^(\1)'), (r'\^([a-zA-Z0-9])', r'^\1'),
        (r'_{([^}]*)}', r'_(\1)'), (r'_([a-zA-Z0-9])', r'_\1'),
        ('²', '^2'), ('³', '^3'), ('¹', '^1'), ('⁴', '^4'), ('⁵', '^5'),
        (r'\(\)', ''), (r'\/\/+', '/'), (r'\s+', ' '), (r'\\[a-zA-Z]+', '')
    ]
    
    try:
        cleaned_text = text
        for pattern, replacement in replacements:
            cleaned_text = re.sub(pattern, replacement, cleaned_text)
        
        # Try SymPy parsing for mathematical expressions
        if any(op in cleaned_text for op in ['+', '-', '*', '/', '^', '=', '(', ')']):
            try:
                expr = sympify(cleaned_text, transformations='all')
                return str(expr).replace('**', '^').replace(' ', '')
            except:
                pass
        
        return cleaned_text.strip()
    except:
        return re.sub(r'\\[a-zA-Z]+', '', text.strip())

# === Image Generation Functions ===
def needs_visual_representation(topic, math_subtopic=None):
    """Determine if a question topic would benefit from visual representation"""
    visual_topics = [
        "Mensuration", "Data Interpretation", "Quadratic Equations",
        "Probability", "Permutation and Combination", "Geometry",
        "Charts and Graphs", "Shapes and Figures"
    ]
    
    # Check if the main topic needs visuals
    if topic in ["Basic Mathematics", "Science", "Geography", "History"]:
        if math_subtopic and math_subtopic in visual_topics:
            return True
        return topic in ["Science", "Geography", "History"]
    
    return topic in visual_topics

def generate_question_image(topic, math_subtopic=None, question_text="", options_text="", question_type="MCQ"):
    """Generate a contextually relevant image for the specific question using DALL-E"""
    try:
        question_content = f"{question_text} {options_text}".lower()
        prompt = create_image_prompt(topic, math_subtopic, question_content)
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1
        )
        
        return response.data[0].url
    except Exception as e:
        print(f"Error generating image: {e}")
        return None

def create_image_prompt(topic, math_subtopic, question_content):
    """Create contextually relevant image prompts based on question content"""
    numbers = re.findall(r'-?\d+', question_content)
    
    if topic == "Basic Mathematics" and math_subtopic:
        if "mensuration" in math_subtopic.lower():
            if "rectangle" in question_content or "आयत" in question_content:
                if len(numbers) >= 2:
                    return f"Educational diagram of rectangle with length {numbers[0]} cm and width {numbers[1]} cm. Clear labels, white background, black lines."
            elif "triangle" in question_content or "त्रिभुज" in question_content:
                if len(numbers) >= 2:
                    return f"Educational diagram of triangle with base {numbers[0]} cm and height {numbers[1]} cm. Clear labels, white background, black lines."
            elif "circle" in question_content or "वृत्त" in question_content:
                if numbers:
                    return f"Educational diagram of circle with radius {numbers[0]} cm. Clear labels, white background, black lines."
            return "Educational diagram showing geometric shapes with labeled dimensions. Clear mathematical figures, white background, black lines."
        
        elif "data interpretation" in math_subtopic.lower():
            data_values = ', '.join(numbers[:4]) if numbers else 'sample data'
            if "bar chart" in question_content or "बार चार्ट" in question_content:
                return f"Professional bar chart showing data: {data_values}. Clear labels, different colored bars, educational style."
            elif "pie chart" in question_content or "पाई चार्ट" in question_content:
                return f"Professional pie chart with segments: {data_values}. Clear labels, different colors, educational style."
            return "Professional data visualization chart with clear labels and values. Educational style."
        
        elif "quadratic equations" in math_subtopic.lower():
            if len(numbers) >= 3:
                return f"Mathematical graph of y = {numbers[0]}x² + {numbers[1]}x + {numbers[2]}. Parabolic curve with labeled axes, grid lines."
            return "Mathematical graph of quadratic equation showing parabolic curve with labeled axes, grid lines."
        
        elif "probability" in math_subtopic.lower():
            if "coin" in question_content or "सिक्का" in question_content:
                return "Educational diagram showing coin toss probability with heads and tails labeled. Simple, clean design."
            elif "dice" in question_content or "पासा" in question_content:
                return "Educational diagram showing dice with numbered faces (1-6). Simple, clean design."
            elif "venn diagram" in question_content:
                return "Educational Venn diagram showing overlapping circles for set theory. Clear labels and intersections."
            return "Educational probability diagram showing coins, dice, or Venn diagram. Clean, simple design."
        
        elif "permutation" in math_subtopic.lower() or "combination" in math_subtopic.lower():
            return "Educational diagram showing arrangement of objects in different combinations. Clean, organized layout."
        
        return f"Educational mathematical diagram for {math_subtopic} with clear labels and measurements."
    
    # Topic-specific prompts
    topic_prompts = {
        "Science": {
            "biology": "Educational biological diagram showing anatomical structures, cells, or biological processes. Clean, scientific illustration.",
            "chemistry": "Educational chemistry diagram showing molecular structures, chemical reactions, or laboratory equipment. Clean, scientific illustration.",
            "physics": "Educational physics diagram showing mechanical systems, electrical circuits, or physical phenomena. Clean, scientific illustration.",
            "default": "Educational scientific diagram with laboratory equipment, biological structures, or chemical processes. Clean, scientific illustration."
        },
        "Geography": {
            "map": "Educational geographic map showing countries, states, or regions with clear boundaries and labels. Clean, simple map style.",
            "climate": "Educational diagram showing climate zones, weather patterns, or temperature maps. Clean, simple geographic illustration.",
            "default": "Educational geographic illustration showing landforms, maps, or geographic features. Clean, simple geographic style."
        },
        "History": {
            "monument": "Educational illustration of historical monuments or architectural structures. Clean, historical illustration style.",
            "battle": "Educational illustration of historical battles or military events. Clean, historical illustration style.",
            "default": "Educational historical illustration showing artifacts, monuments, or historical events. Clean, historical illustration style."
        }
    }
    
    if topic in topic_prompts:
        for keyword, prompt in topic_prompts[topic].items():
            if keyword != "default" and (keyword in question_content or any(hindi in question_content for hindi in ["नक्शा", "जलवायु", "स्मारक", "युद्ध", "जीव विज्ञान", "रसायन विज्ञान", "भौतिक विज्ञान"])):
                return prompt
        return topic_prompts[topic]["default"]
    
    return f"Educational diagram or illustration relevant to {topic} with clear labels and professional appearance. Clean, educational style."

def download_image(image_url, filename="temp_image.png"):
    """Download image from URL and save locally"""
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        
        with open(filename, 'wb') as f:
            f.write(response.content)
        
        return filename
    except Exception as e:
        print(f"Error downloading image: {e}")
        return None

# Load environment variables
load_dotenv()

# === CONFIGURATION ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Validate required environment variables
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

client = OpenAI(api_key=OPENAI_API_KEY)

# === DATABASE SETUP ===
def init_database():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect('mcq_bot.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # User preferences table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            chat_id INTEGER,
            topic TEXT DEFAULT 'Random',
            difficulty TEXT DEFAULT 'Medium',
            math_subtopic TEXT,
            language TEXT DEFAULT 'English',
            FOREIGN KEY (chat_id) REFERENCES users (chat_id),
            PRIMARY KEY (chat_id)
        )
    ''')
    
    # User stats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            topic TEXT,
            difficulty TEXT,
            is_correct BOOLEAN,
            question_id TEXT,
            answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )
    ''')
    
    # Questions table for tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            difficulty TEXT,
            subtopic TEXT,
            question_text TEXT,
            correct_answer TEXT,
            explanation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database
init_database()

topics = [
    "General Science",
    "General Hindi", 
    "General English",
    "Basic Mathematics",
    "General Knowledge",
    "Computer Knowledge",
    "Reasoning Ability",
    "General Management with MP GK"
]

difficulties = ["Easy", "Medium", "Hard"]

# Mathematics subtopics based on MP Patwari syllabus
math_subtopics = [
    "Decimals and Fractions",
    "Square Root and Cube Root", 
    "Simplification",
    "L.S. and M.S.",
    "Time, Speed, and Distance",
    "Mensuration",
    "Number System",
    "Simple and Compound Interest",
    "Ratio and Proportion",
    "Partnership",
    "Number Series",
    "Data Interpretation",
    "Quadratic Equations",
    "Data Sufficiency",
    "Discounts",
    "Averages",
    "Mixtures",
    "Percentages",
    "Profit and Loss",
    "Work",
    "Rate of Interest",
    "Probability",
    "Permutation and Combination"
]

# Language-specific text dictionaries
interface_texts = {
    "English": {
        "welcome": "🎉 *Welcome to MP Patwari MCQ Practice Bot!*\n\nI'll help you prepare for your exam with personalized MCQs. Let's start your practice journey!",
        "question_ready": "🧠 *MP Patwari Practice MCQ:*", "topic": "📚 Topic:", "difficulty": "🎯 Difficulty:", "question": "*Question:*",
        "reply_instruction": "💭 Reply with A, B, C, or D to answer!", "correct": "✅ *Correct!*", "incorrect": "❌ *Incorrect!*",
        "correct_answer": "Correct Answer:", "explanation": "Explanation:", "stats": "📊 *Your Statistics:*",
        "total_questions": "Total Questions:", "correct_answers": "Correct Answers:", "accuracy": "Accuracy:",
        "topic_selected": "Topic set to:", "difficulty_selected": "Difficulty set to:", "language_selected": "Language set to:",
        "settings": "*Your Settings:*", "reset_stats": "🔄 Reset Stats", "back_to_topics": "⬅️ Back to Topics",
        "random_subtopic": "🎲 Random Subtopic", "use_question_command": "Use /question to get MCQs from this topic!",
        "use_question_command_math": "Use /question to get MCQs from this specific mathematics area!",
        "use_topics_difficulty_commands": "Use /topics, /difficulty, and /language to change your preferences!",
        "basic_math_selected": "*Basic Mathematics Selected!*", "choose_math_area": "Choose a specific area of mathematics to focus on:",
        "reset_confirmation": "✅ All your statistics have been reset successfully!",
        "help_text": """📚 *Available Commands:*\n/start - Start the bot and register\n/question - Get a practice MCQ\n/topics - Choose your preferred topic\n/difficulty - Set difficulty level (Easy/Medium/Hard)\n/language - Choose language (English/Hindi)\n/math_subtopics - Choose mathematics subtopic\n/stats - View your performance statistics\n/settings - View current preferences\n/help - Show this help message\n\n🎯 *Features:*\n• Personalized MCQs based on your preferences\n• Multiple difficulty levels\n• Statistics tracking\n• Bilingual support (English/Hindi)\n• Visual questions with diagrams\n• Mathematics subtopic selection\n• Rate limiting to prevent spam (5 second cooldown)""",
        "error_message": "❌ Error occurred. Please try again.", "no_active_question": "No active question found. Use /question to get a new MCQ!",
        "cooldown_message": "⏰ Please wait {remaining:.1f} seconds.\n\nYou're requesting questions too quickly.",
        "rate_limit_info": "Rate Limit: 1 question per 5 seconds"
    },
    "Hindi": {
        "welcome": "🎉 *MP पटवारी MCQ अभ्यास बॉट में आपका स्वागत है!*\n\nमैं आपकी परीक्षा की तैयारी में व्यक्तिगत MCQ के साथ मदद करूंगा। आइए अपनी अभ्यास यात्रा शुरू करें!",
        "question_ready": "🧠 *MP पटवारी अभ्यास MCQ:*", "topic": "📚 विषय:", "difficulty": "🎯 कठिनाई:", "question": "*प्रश्न:*",
        "reply_instruction": "💭 जवाब देने के लिए A, B, C, या D भेजें!", "correct": "✅ *सही!*", "incorrect": "❌ *गलत!*",
        "correct_answer": "सही उत्तर:", "explanation": "व्याख्या:", "stats": "📊 *आपके आंकड़े:*",
        "total_questions": "कुल प्रश्न:", "correct_answers": "सही उत्तर:", "accuracy": "सटीकता:",
        "topic_selected": "विषय सेट किया गया:", "difficulty_selected": "कठिनाई सेट की गई:", "language_selected": "भाषा सेट की गई:",
        "settings": "*आपकी सेटिंग्स:*", "reset_stats": "🔄 आंकड़े रीसेट करें", "back_to_topics": "⬅️ विषयों पर वापस जाएं",
        "random_subtopic": "🎲 यादृच्छिक उप-विषय", "use_question_command": "इस विषय से MCQ प्राप्त करने के लिए /question का उपयोग करें!",
        "use_question_command_math": "इस विशिष्ट गणित क्षेत्र से MCQ प्राप्त करने के लिए /question का उपयोग करें!",
        "use_topics_difficulty_commands": "अपनी प्राथमिकताएं बदलने के लिए /topics, /difficulty, और /language का उपयोग करें!",
        "basic_math_selected": "*बेसिक गणित चुना गया!*", "choose_math_area": "फोकस करने के लिए गणित का एक विशिष्ट क्षेत्र चुनें:",
        "reset_confirmation": "✅ आपके सभी आंकड़े सफलतापूर्वक रीसेट कर दिए गए हैं!",
        "help_text": """📚 *उपलब्ध कमांड:*\n/start - बॉट शुरू करें और पंजीकरण करें\n/question - अभ्यास MCQ प्राप्त करें\n/topics - अपना पसंदीदा विषय चुनें\n/difficulty - कठिनाई स्तर सेट करें (आसान/मध्यम/कठिन)\n/language - भाषा चुनें (अंग्रेजी/हिंदी)\n/math_subtopics - गणित उप-विषय चुनें\n/stats - अपने प्रदर्शन आंकड़े देखें\n/settings - वर्तमान प्राथमिकताएं देखें\n/help - यह मदद संदेश दिखाएं\n\n🎯 *विशेषताएं:*\n• आपकी प्राथमिकताओं के आधार पर व्यक्तिगत MCQ\n• कई कठिनाई स्तर\n• आंकड़े ट्रैकिंग\n• द्विभाषी सहायता (अंग्रेजी/हिंदी)\n• आरेखों के साथ दृश्य प्रश्न\n• गणित उप-विषय चयन\n• स्पैम रोकने के लिए दर सीमित (5 सेकंड का शीतलन)""",
        "error_message": "❌ त्रुटि हुई। कृपया फिर से कोशिश करें।", "no_active_question": "कोई सक्रिय प्रश्न नहीं मिला। नया MCQ प्राप्त करने के लिए /question का उपयोग करें!",
        "cooldown_message": "⏰ कृपया {remaining:.1f} सेकंड प्रतीक्षा करें।\n\nबहुत तेज़ी से प्रश्न मांग रहे हैं।",
        "rate_limit_info": "दर सीमा: प्रति 5 सेकंड में 1 प्रश्न"
    }
}

# Hindi translations for math subtopics
math_subtopics_hindi = [
    "दशमलव और भिन्न",
    "वर्गमूल और घनमूल",
    "सरलीकरण",
    "L.S. और M.S.",
    "समय, गति और दूरी",
    "क्षेत्रमिति",
    "संख्या प्रणाली",
    "साधारण और चक्रवृद्धि ब्याज",
    "अनुपात और समानुपात",
    "साझेदारी",
    "संख्या श्रृंखला",
    "डेटा व्याख्या",
    "द्विघात समीकरण",
    "डेटा पर्याप्तता",
    "छूट",
    "औसत",
    "मिश्रण",
    "प्रतिशत",
    "लाभ और हानि",
    "कार्य",
    "ब्याज दर",
    "संभावना",
    "क्रमचय और संयोजन"
]

# Database helper functions
def db_execute(query, params=None, fetch=False):
    """Execute database query with connection management"""
    conn = sqlite3.connect('mcq_bot.db')
    cursor = conn.cursor()
    try:
        cursor.execute(query, params or ())
        if fetch:
            result = cursor.fetchone()
        else:
            conn.commit()
            result = None
        return result
    finally:
        conn.close()

def get_user_preferences(chat_id):
    """Get user preferences from database"""
    result = db_execute('SELECT topic, difficulty, math_subtopic, language FROM user_preferences WHERE chat_id = ?', (chat_id,), fetch=True)
    if result:
        return {"topic": result[0], "difficulty": result[1], "math_subtopic": result[2], "language": result[3]}
    return {"topic": "Random", "difficulty": "Medium", "math_subtopic": None, "language": "English"}

def update_user_preferences(chat_id, topic=None, difficulty=None, math_subtopic=None, language=None):
    """Update user preferences in database"""
    current = get_user_preferences(chat_id)
    new_values = (
        chat_id,
        topic or current["topic"],
        difficulty or current["difficulty"],
        math_subtopic if math_subtopic is not None else current["math_subtopic"],
        language or current["language"]
    )
    db_execute('INSERT OR REPLACE INTO user_preferences (chat_id, topic, difficulty, math_subtopic, language) VALUES (?, ?, ?, ?, ?)', new_values)

def register_user(chat_id, username=None, first_name=None, last_name=None):
    """Register a new user in the database"""
    db_execute('INSERT OR IGNORE INTO users (chat_id, username, first_name, last_name) VALUES (?, ?, ?, ?)', (chat_id, username, first_name, last_name))
    db_execute('INSERT OR IGNORE INTO user_preferences (chat_id, topic, difficulty) VALUES (?, ?, ?)', (chat_id, 'Random', 'Medium'))

def save_user_answer(chat_id, topic, difficulty, is_correct, question_id=None):
    """Save user's answer to database"""
    db_execute('INSERT INTO user_stats (chat_id, topic, difficulty, is_correct, question_id) VALUES (?, ?, ?, ?, ?)', (chat_id, topic, difficulty, is_correct, question_id))

def save_question_to_db(topic, difficulty, question_text, correct_answer, explanation, subtopic=None):
    """Save generated question to database for tracking"""
    db_execute('INSERT INTO questions (topic, difficulty, subtopic, question_text, correct_answer, explanation) VALUES (?, ?, ?, ?, ?, ?)', (topic, difficulty, subtopic, question_text, correct_answer, explanation))

def reset_user_stats(chat_id):
    """Reset all statistics for a user"""
    db_execute('DELETE FROM user_stats WHERE chat_id = ?', (chat_id,))

def get_user_stats(chat_id):
    """Get user statistics from database"""
    topic_stats = db_execute('''
        SELECT COUNT(*) as total_questions, SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_answers, topic, difficulty
        FROM user_stats WHERE chat_id = ? GROUP BY topic, difficulty ORDER BY total_questions DESC
    ''', (chat_id,), fetch=False)
    
    overall = db_execute('SELECT COUNT(*) as total, SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct FROM user_stats WHERE chat_id = ?', (chat_id,), fetch=True)
    
    return {
        "overall": {"total": overall[0] if overall and overall[0] else 0, "correct": overall[1] if overall and overall[1] else 0},
        "by_topic": topic_stats or []
    }

def get_all_active_users():
    """Get all active users for scheduled questions"""
    conn = sqlite3.connect('mcq_bot.db')
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT chat_id FROM users WHERE is_active = 1')
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

def get_recent_questions(topic, difficulty, limit=10):
    """Get recent questions to avoid repetition"""
    conn = sqlite3.connect('mcq_bot.db')
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT question_text FROM questions WHERE topic = ? AND difficulty = ? ORDER BY created_at DESC LIMIT ?', (topic, difficulty, limit))
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

active_questions = {}  # Store active questions by chat_id

# === AI Question Generator ===
def generate_mcq(selected_topic=None, difficulty="Medium", chat_id=None, language="English"):
    if selected_topic and selected_topic != "Random":
        topic = selected_topic
    else:
        topic = random.choice(topics)
    
    # Add some randomization to reduce patterns
    random_seed = random.randint(1, 1000)
    
    # For Basic Mathematics, get user's preferred subtopic or random
    math_subtopic = ""
    if topic == "Basic Mathematics":
        if chat_id:
            preferences = get_user_preferences(chat_id)
            user_math_subtopic = preferences.get("math_subtopic")
            if user_math_subtopic and user_math_subtopic != "Random":
                math_subtopic = user_math_subtopic
            else:
                math_subtopic = random.choice(math_subtopics)
        else:
            math_subtopic = random.choice(math_subtopics)
    
    # Get recent questions to avoid repetition
    recent_questions = get_recent_questions(topic, difficulty, 5)
    avoid_text = ""
    if recent_questions:
        avoid_text = f"\n\nAVOID these recent questions: {', '.join(recent_questions[:3])}"
    
    # Difficulty-specific prompts with math-specific instructions
    math_instructions = ""
    if topic == "Basic Mathematics":
        math_instructions = f"""
        MATHEMATICS SPECIFIC INSTRUCTIONS:
        - FOCUS ON SPECIFIC SUBTOPIC: {math_subtopic}
        - Use clear and precise mathematical language
        - Create practical problems relevant to MP Patwari exam
        - Ensure question tests understanding of {math_subtopic} specifically
        - Make calculations straightforward and educational
        - Use appropriate mathematical notation for clarity
        - Keep numbers simple (1-1000) and use basic operations: +, -, *, / only"""
    
    # Add subtopic info to topic name for mathematics
    topic_display = topic
    if topic == "Basic Mathematics" and math_subtopic:
        if language == "Hindi":
            # Get Hindi translation for math subtopic
            try:
                subtopic_index = math_subtopics.index(math_subtopic)
                hindi_subtopic = math_subtopics_hindi[subtopic_index]
                topic_display = f"बेसिक गणित - {hindi_subtopic}"
            except (ValueError, IndexError):
                topic_display = f"बेसिक गणित - {math_subtopic}"
        else:
            topic_display = f"{topic} - {math_subtopic}"
    
    # Language-specific instructions
    language_instructions = ""
    if language == "Hindi":
        language_instructions = """
        LANGUAGE REQUIREMENTS:
        - Generate the ENTIRE question in HINDI (Devanagari script)
        - Use proper Hindi mathematical terminology
        - Keep Hindi grammar and sentence structure correct
        - Use English numerals (1, 2, 3, etc.) for all numbers, not Hindi numerals
        - Keep mathematical expressions in standard English format (1, 2, 3, etc.)
        - Use common Hindi words that MP Patwari aspirants would understand
        - Maintain professional and educational tone in Hindi"""
    else:
        language_instructions = """
        LANGUAGE REQUIREMENTS:
        - Generate the ENTIRE question in ENGLISH
        - Use clear and simple English appropriate for exam preparation
        - Use proper English grammar and sentence structure
        - Maintain professional and educational tone"""
    
    difficulty_prompts = {
        "Easy": f"""Generate a SHORT and EASY MP Patwari exam MCQ from {topic_display}. 
        
        EASY LEVEL REQUIREMENTS:
        - Use ONLY basic, fundamental concepts
        - Questions should be straightforward and obvious
        - Options should be clearly distinguishable
        - Answer should be obvious to anyone with basic knowledge
        - Use simple language and common terms only
        - Keep question and options short (1-2 lines each){math_instructions}{language_instructions}""",
        
        "Medium": f"""Generate a SHORT MEDIUM difficulty MP Patwari exam MCQ from {topic_display}.
        
        MEDIUM LEVEL REQUIREMENTS:
        - Use intermediate concepts that require some thinking
        - Include moderately challenging scenarios
        - Options should require some analysis to distinguish
        - Answer should require understanding, not just memorization
        - May include some application of concepts
        - Keep question and options concise (2-3 lines each){math_instructions}{language_instructions}""",
        
        "Hard": f"""Generate a SHORT DIFFICULT MP Patwari exam MCQ from {topic_display}.
        
        HARD LEVEL REQUIREMENTS:
        - Use advanced, complex concepts
        - Include challenging scenarios and deep analysis
        - Options should be sophisticated and require critical thinking
        - Answer should require deep understanding and reasoning
        - May include complex applications or synthesis of concepts
        - Test advanced knowledge and problem-solving skills
        - Keep question and options concise (2-3 lines each){math_instructions}{language_instructions}"""
    }
    
    base_prompt = difficulty_prompts.get(difficulty, difficulty_prompts["Medium"])
    
    # Check if this topic needs visual representation
    needs_image = needs_visual_representation(topic, math_subtopic)
    
    image_instruction = ""
    if needs_image:
        image_instruction = f"""
    
    VISUAL INSTRUCTION:
    This question will be accompanied by a contextually relevant diagram/chart/image with correct data and parameters.
    - Include specific measurements, dimensions, or data values in your question
    - Reference the image naturally (e.g., "Based on the diagram above", "Looking at the chart", "From the figure shown")
    - Use exact numbers and parameters that will be displayed in the accompanying image
    - Make your question directly related to the visual content with specific calculations or interpretations
    - Ensure the image data matches your question requirements perfectly"""

    prompt = f"""{base_prompt}{image_instruction}

RANDOMIZATION SEED: {random_seed} (use this to create variety)

CRITICAL: Follow this EXACT format:

Question: [Short question here - reference image if applicable]
A) [Short option A]
B) [Short option B] 
C) [Short option C]
D) [Short option D]

Correct Answer: [ONLY A, B, C, or D - no other text]
Explanation: [ONE sentence explaining why the correct answer is right - keep it short]

IMPORTANT:
- For mathematics: Use simple numbers and basic operations only
- Avoid complex symbols, fractions, or special characters
- Keep all text plain and simple
- Do not use parentheses, slashes, or special formatting in options
- Use only standard mathematical notation: +, -, ×, ÷, =
- Write in PLAIN TEXT format - NO LaTeX code or mathematical formatting
- Use simple text for mathematical expressions (e.g., "2 + 3 = 5" not "2+3=5")
- Create a UNIQUE question different from recent ones
- Use the randomization seed to create variety{avoid_text}"""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    full_response = response.choices[0].message.content.strip()
    return full_response, topic, math_subtopic, needs_image

# === Auto-save Questions to File ===
def save_question_to_file(question_text, topic, correct_answer=None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = "mp_patwari_questions.txt"
    
    with open(filename, "a", encoding="utf-8") as file:
        file.write(f"\n{'='*50}\n")
        file.write(f"Date: {timestamp}\n")
        file.write(f"Topic: {topic}\n")
        file.write(f"Question:\n{question_text}\n")
        if correct_answer:
            file.write(f"Correct Answer: {correct_answer}\n")
        file.write(f"{'='*50}\n")

# === Parse Question Components ===
def parse_question(full_response):
    """Parse MCQ response and extract question, options, answer, and explanation"""
    # Clean and convert LaTeX to plain text
    full_response = clean_mathematical_text(full_response.replace('\n\n', '\n').replace('  ', ' ').strip())
    
    # Extract question
    question_match = re.search(r'Question:\s*(.*?)(?=A\))', full_response, re.DOTALL | re.IGNORECASE)
    question_text = clean_mathematical_text(question_match.group(1).strip()) if question_match else "Question not found"
    
    # Extract options
    options_text = ""
    for option in ['A', 'B', 'C', 'D']:
        pattern = f'{option}\)\s*(.*?)(?=[A-D]\)|Correct Answer|Answer:|$)'
        option_match = re.search(pattern, full_response, re.DOTALL | re.IGNORECASE)
        if option_match:
            option_text = clean_mathematical_text(option_match.group(1).strip())
            options_text += f"{option}) {option_text}\n"
    
    if not options_text:
        options_text = "Options not found"
    
    # Extract correct answer
    answer_patterns = [r'Correct Answer:\s*([A-D])\)?', r'Answer:\s*([A-D])\)?', r'\(([A-D])\)']
    correct_answer = None
    for pattern in answer_patterns:
        answer_match = re.search(pattern, full_response, re.IGNORECASE)
        if answer_match:
            correct_answer = answer_match.group(1).upper()
            break
    
    # Fallback: find any A-D in last lines
    if not correct_answer:
        for line in reversed(full_response.split('\n')):
            if re.search(r'([A-D])', line):
                correct_answer = re.search(r'([A-D])', line).group(1).upper()
                break
    
    # Extract explanation
    explanation_match = re.search(r'Explanation:\s*(.*?)(?:\n|$)', full_response, re.DOTALL | re.IGNORECASE)
    if explanation_match:
        explanation = clean_mathematical_text(explanation_match.group(1).strip())
        if '.' in explanation:
            explanation = explanation.split('.')[0] + '.'
        elif len(explanation) > 80:
            explanation = explanation[:80] + '...'
    else:
        explanation = "Correct answer provided."
    
    return question_text, options_text, correct_answer, explanation


# === Telegram Command Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Register user in database
    register_user(chat_id, user.username, user.first_name, user.last_name)
    
    # Get user language preference (default to English for new users)
    preferences = get_user_preferences(chat_id)
    language = preferences.get("language", "English")
    texts = interface_texts.get(language, interface_texts["English"])
    
    # Send welcome message without markdown to avoid parsing issues
    welcome_msg = texts["welcome"] + "\n\n" + texts["help_text"]
    await update.message.reply_text(welcome_msg)

async def send_question(context, chat_id=None):
    if chat_id:
        # Send to specific user
        await send_question_to_user(context, chat_id)
    else:
        # Send to all active users
        active_users = get_all_active_users()
        for user_chat_id in active_users:
            try:
                await send_question_to_user(context, user_chat_id)
                await asyncio.sleep(0.1)  # Small delay between users
            except Exception as e:
                print(f"Error sending question to user {user_chat_id}: {e}")

async def send_question_to_user(context, chat_id):
    """Send a personalized question to a specific user"""
    # Atomically check if user can process and set processing flag
    if not check_and_set_processing(chat_id):
        print(f"Skipping scheduled question for user {chat_id} - already processing or in cooldown")
        return
    
    preferences = get_user_preferences(chat_id)
    selected_topic = preferences["topic"]
    difficulty = preferences["difficulty"]
    language = preferences["language"]
    
    # Generate question with validation
    max_attempts = 3
    for attempt in range(max_attempts):
        full_response, topic, math_subtopic, needs_image = generate_mcq(selected_topic, difficulty, chat_id, language)
        question_text, options_text, correct_answer, explanation = parse_question(full_response)
        
        # Validate that we have a correct answer
        if correct_answer and correct_answer in ['A', 'B', 'C', 'D']:
            break
        elif attempt == max_attempts - 1:
            # Fallback: assign a random answer if parsing fails
            correct_answer = random.choice(['A', 'B', 'C', 'D'])
            explanation = "Answer assigned randomly due to parsing issue."
    
    # Store active question
    active_questions[chat_id] = {
        'question_text': question_text,
        'options_text': options_text,
        'correct_answer': correct_answer,
        'explanation': explanation,
        'topic': topic,
        'difficulty': difficulty,
        'full_response': full_response
    }
    
    # Save question to file and database
    save_question_to_file(full_response, topic, correct_answer)
    save_question_to_db(topic, difficulty, question_text, correct_answer, explanation, math_subtopic if topic == "Basic Mathematics" else None)
    
    # Generate and send image if needed
    if needs_image:
        try:
            print(f"Generating image for topic: {topic}, math_subtopic: {math_subtopic}")
            image_url = generate_question_image(topic, math_subtopic, question_text, options_text)
            if image_url:
                # Download and send image with question
                image_filename = f"temp_question_{chat_id}.png"
                if download_image(image_url, image_filename):
                    # Get language-specific texts
                    texts = interface_texts.get(language, interface_texts["English"])
                    difficulty_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}
                    question_message = f"{texts['question_ready']}\n{texts['topic']} {topic}\n{texts['difficulty']} {difficulty_emoji.get(difficulty, '🟡')} {difficulty}\n\n{texts['question']} {question_text}\n\n{options_text}\n\n{texts['reply_instruction']}"
    
    if context and hasattr(context, 'bot'):
                        with open(image_filename, 'rb') as photo:
                            await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=question_message, parse_mode="Markdown")
    else:
                        with open(image_filename, 'rb') as photo:
                            await app.bot.send_photo(chat_id=chat_id, photo=photo, caption=question_message, parse_mode="Markdown")
                    
                    # Clean up temporary file
                    try:
                        os.remove(image_filename)
                    except:
                        pass
                    
                    # Clear processing flag
                    clear_processing(chat_id)
                    return
        except Exception as e:
            print(f"Error generating/sending image: {e}")
            # Clear processing flag on error
            clear_processing(chat_id)
            # Fall through to text-only message
    
    # Send question without image (fallback or non-visual topics)
    # Get language-specific texts
    texts = interface_texts.get(language, interface_texts["English"])
    difficulty_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}
    question_message = f"{texts['question_ready']}\n{texts['topic']} {topic}\n{texts['difficulty']} {difficulty_emoji.get(difficulty, '🟡')} {difficulty}\n\n{texts['question']} {question_text}\n\n{options_text}\n\n{texts['reply_instruction']}"
    
    if context and hasattr(context, 'bot'):
        await context.bot.send_message(chat_id=chat_id, text=question_message, parse_mode="Markdown")
    else:
        await app.bot.send_message(chat_id=chat_id, text=question_message, parse_mode="Markdown")
    
    # Clear processing flag
    clear_processing(chat_id)

async def manual_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Atomically check if user can process and set processing flag
    if not check_and_set_processing(chat_id):
        # Get user language for message
        preferences = get_user_preferences(chat_id)
        language = preferences.get("language", "English")
        
        remaining_time = get_cooldown_remaining(chat_id)
        if remaining_time > 0:
            texts = interface_texts.get(language, interface_texts["English"])
            cooldown_message = texts["cooldown_message"].format(remaining=remaining_time)
            await update.message.reply_text(cooldown_message)
        else:
            if language == "Hindi":
                processing_message = "⏳ आपका प्रश्न तैयार हो रहा है... कृपया प्रतीक्षा करें।"
            else:
                processing_message = "⏳ Your question is being prepared... Please wait."
            await update.message.reply_text(processing_message)
        return
    
    # Register user if not already registered
    user = update.effective_user
    register_user(chat_id, user.username, user.first_name, user.last_name)
    
    # Get user preferences
    preferences = get_user_preferences(chat_id)
    selected_topic = preferences["topic"]
    difficulty = preferences["difficulty"]
    language = preferences["language"]
    
    # Generate question with validation
    max_attempts = 3
    for attempt in range(max_attempts):
        full_response, topic, math_subtopic, needs_image = generate_mcq(selected_topic, difficulty, chat_id, language)
        question_text, options_text, correct_answer, explanation = parse_question(full_response)
        
        # Validate that we have a correct answer
        if correct_answer and correct_answer in ['A', 'B', 'C', 'D']:
            break
        elif attempt == max_attempts - 1:
            # Fallback: assign a random answer if parsing fails
            correct_answer = random.choice(['A', 'B', 'C', 'D'])
            explanation = "Answer assigned randomly due to parsing issue."
    
    # Store active question
    active_questions[chat_id] = {
        'question_text': question_text,
        'options_text': options_text,
        'correct_answer': correct_answer,
        'explanation': explanation,
        'topic': topic,
        'difficulty': difficulty,
        'full_response': full_response
    }
    
    # Save question to file and database
    save_question_to_file(full_response, topic, correct_answer)
    save_question_to_db(topic, difficulty, question_text, correct_answer, explanation, math_subtopic if topic == "Basic Mathematics" else None)
    
    # Generate and send image if needed
    if needs_image:
        try:
            print(f"Generating image for manual question - topic: {topic}, math_subtopic: {math_subtopic}")
            image_url = generate_question_image(topic, math_subtopic, question_text, options_text)
            if image_url:
                # Download and send image with question
                image_filename = f"temp_manual_{chat_id}.png"
                if download_image(image_url, image_filename):
                    difficulty_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}
                    question_message = f"🧠 *MCQ:*\n📚 Topic: {topic}\n🎯 Difficulty: {difficulty_emoji.get(difficulty, '🟡')} {difficulty}\n\n*Question:* {question_text}\n\n{options_text}\n\n💭 Reply with A, B, C, or D to answer!"
                    
                    with open(image_filename, 'rb') as photo:
                        await update.message.reply_photo(photo=photo, caption=question_message, parse_mode="Markdown")
                    
                    # Clean up temporary file
                    try:
                        os.remove(image_filename)
                    except:
                        pass
                    
                    # Clear processing flag
                    clear_processing(chat_id)
                    return
        except Exception as e:
            print(f"Error generating/sending image for manual question: {e}")
            # Clear processing flag on error
            clear_processing(chat_id)
            # Fall through to text-only message
    
    # Send question without image (fallback or non-visual topics)
    difficulty_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}
    question_message = f"🧠 *MCQ:*\n📚 Topic: {topic}\n🎯 Difficulty: {difficulty_emoji.get(difficulty, '🟡')} {difficulty}\n\n*Question:* {question_text}\n\n{options_text}\n\n💭 Reply with A, B, C, or D to answer!"
    await update.message.reply_text(question_message, parse_mode="Markdown")
    
    # Clear processing flag
    clear_processing(chat_id)

# === Answer Handler ===
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_answer = update.message.text.strip().upper()
    
    # Check if user has an active question
    if chat_id not in active_questions:
        await update.message.reply_text("❌ No active question found. Use /question to get a new MCQ!")
        return
    
    # Validate answer format
    if user_answer not in ['A', 'B', 'C', 'D']:
        await update.message.reply_text("❌ Please reply with A, B, C, or D only!")
        return
    
    question_data = active_questions[chat_id]
    correct_answer = question_data['correct_answer']
    explanation = question_data['explanation']
    topic = question_data['topic']
    difficulty = question_data['difficulty']
    
    # Check if answer is correct
    is_correct = user_answer == correct_answer
    
    if is_correct:
        feedback = "✅ **Correct!**"
    else:
        feedback = f"❌ **Wrong!** Correct answer is **{correct_answer}**"
    
    # Save answer to database
    save_user_answer(chat_id, topic, difficulty, is_correct)
    
    # Get updated stats for this user
    stats = get_user_stats(chat_id)
    overall_stats = stats["overall"]
    accuracy = (overall_stats["correct"] / overall_stats["total"] * 100) if overall_stats["total"] > 0 else 0
    
    # Send short feedback with stats
    feedback_message = f"{feedback}\n\n💡 {explanation}\n\n📊 Stats: {overall_stats['correct']}/{overall_stats['total']} ({accuracy:.1f}%)\n\n🎯 /question for more!"
    await update.message.reply_text(feedback_message, parse_mode="Markdown")
    
    # Remove the active question
    del active_questions[chat_id]

# === Topic Selection Commands ===
async def set_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Register user if not already registered
    user = update.effective_user
    register_user(chat_id, user.username, user.first_name, user.last_name)
    
    if not context.args:
        topics_list = "\n".join([f"• {topic}" for topic in topics])
        await update.message.reply_text(
            f"📚 Please specify a topic!\n\n"
            f"Available topics:\n{topics_list}\n\n"
            f"Usage: /topic Basic Mathematics"
        )
        return
    
    topic_input = " ".join(context.args).title()
    
    if topic_input in topics:
        update_user_preferences(chat_id, topic=topic_input)
        await update.message.reply_text(f"✅ Topic set to: **{topic_input}**\n\nUse /question to get MCQs from this topic!", parse_mode="Markdown")
    else:
        topics_list = "\n".join([f"• {topic}" for topic in topics])
        await update.message.reply_text(
            f"❌ Topic '{topic_input}' not found!\n\n"
            f"Available topics:\n{topics_list}"
        )

async def show_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Register user if not already registered
    user = update.effective_user
    register_user(chat_id, user.username, user.first_name, user.last_name)
    
    keyboard = []
    # Create buttons in rows of 2
    for i in range(0, len(topics), 2):
        row = []
        for j in range(2):
            if i + j < len(topics):
                topic = topics[i + j]
                row.append(InlineKeyboardButton(topic, callback_data=f"topic_{topic}"))
        keyboard.append(row)
    
    # Add a "Random Topic" button
    keyboard.append([InlineKeyboardButton("🎲 Random Topic", callback_data="topic_random")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📚 **Select a Topic for MCQs:**\n\nChoose from the buttons below or use /topic <name> command:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def show_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show language selection interface"""
    chat_id = update.effective_chat.id
    
    # Register user if not already registered
    user = update.effective_user
    register_user(chat_id, user.username, user.first_name, user.last_name)
    
    # Get current language preference
    preferences = get_user_preferences(chat_id)
    current_language = preferences.get("language", "English")
    
    # Create keyboard with language options
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="language_English")],
        [InlineKeyboardButton("🇮🇳 हिंदी (Hindi)", callback_data="language_Hindi")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Get appropriate text based on current language
    texts = interface_texts.get(current_language, interface_texts["English"])
    message = f"🌐 **Select Language / भाषा चुनें:**\n\n"
    message += f"Current Language / वर्तमान भाषा: **{current_language}**\n\n"
    message += "Choose your preferred language for questions and interface:"
    
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Get user language preference
    preferences = get_user_preferences(chat_id)
    language = preferences.get("language", "English")
    texts = interface_texts.get(language, interface_texts["English"])
    
    await update.message.reply_text(texts["help_text"])

# === New Commands ===
async def show_difficulty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Register user if not already registered
    user = update.effective_user
    register_user(chat_id, user.username, user.first_name, user.last_name)
    
    keyboard = []
    # Create buttons for each difficulty level
    for difficulty in difficulties:
        emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}
        keyboard.append([InlineKeyboardButton(
            f"{emoji.get(difficulty, '🟡')} {difficulty}", 
            callback_data=f"difficulty_{difficulty}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎯 **Select Difficulty Level:**\n\nChoose your preferred difficulty:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def show_math_subtopics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show mathematics subtopic selection menu"""
    chat_id = update.effective_chat.id
    
    # Register user if not already registered
    user = update.effective_user
    register_user(chat_id, user.username, user.first_name, user.last_name)
    
    message = "📚 *Select Mathematics Subtopic:*\n\n"
    message += "Choose a specific area of mathematics to focus on:\n\n"
    
    # Create keyboard with subtopics in rows of 2
    keyboard = []
    for i in range(0, len(math_subtopics), 2):
        row = []
        row.append(InlineKeyboardButton(math_subtopics[i], callback_data=f"math_subtopic_{math_subtopics[i]}"))
        if i + 1 < len(math_subtopics):
            row.append(InlineKeyboardButton(math_subtopics[i + 1], callback_data=f"math_subtopic_{math_subtopics[i + 1]}"))
        keyboard.append(row)
    
    # Add "Random" option
    keyboard.append([InlineKeyboardButton("🎲 Random Subtopic", callback_data="math_subtopic_Random")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Register user if not already registered
    user = update.effective_user
    register_user(chat_id, user.username, user.first_name, user.last_name)
    
    stats = get_user_stats(chat_id)
    overall_stats = stats["overall"]
    topic_stats = stats["by_topic"]
    
    if overall_stats["total"] == 0:
        await update.message.reply_text(
            "📊 **Your Statistics:**\n\n"
            "No questions answered yet!\n"
            "Use /question to start practicing and track your progress."
        )
        return
    
    accuracy = (overall_stats["correct"] / overall_stats["total"] * 100)
    
    stats_message = f"📊 **Your Statistics:**\n\n"
    stats_message += f"🎯 **Overall Performance:**\n"
    stats_message += f"• Total Questions: {overall_stats['total']}\n"
    stats_message += f"• Correct Answers: {overall_stats['correct']}\n"
    stats_message += f"• Accuracy: {accuracy:.1f}%\n\n"
    
    if topic_stats:
        stats_message += f"📚 **By Topic & Difficulty:**\n"
        for stat in topic_stats[:5]:  # Show top 5
            total, correct, topic, difficulty = stat
            topic_accuracy = (correct / total * 100) if total > 0 else 0
            emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}
            stats_message += f"• {topic} ({emoji.get(difficulty, '🟡')}): {correct}/{total} ({topic_accuracy:.1f}%)\n"
    
    stats_message += f"\n🎮 Keep practicing to improve your scores!"
    
    # Create keyboard with reset button
    keyboard = [[InlineKeyboardButton("🔄 Reset Stats", callback_data="reset_stats")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(stats_message, parse_mode="Markdown", reply_markup=reply_markup)

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Register user if not already registered
    user = update.effective_user
    register_user(chat_id, user.username, user.first_name, user.last_name)
    
    preferences = get_user_preferences(chat_id)
    topic = preferences["topic"]
    difficulty = preferences["difficulty"]
    math_subtopic = preferences.get("math_subtopic", "Random")
    language = preferences.get("language", "English")
    
    # Get language-specific texts
    texts = interface_texts.get(language, interface_texts["English"])
    
    difficulty_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}
    language_emoji = {"English": "🇬🇧", "Hindi": "🇮🇳"}
    
    settings_message = f"⚙️ **{texts['settings']}**\n\n"
    settings_message += f"📚 {texts['topic']} **{topic}**\n"
    settings_message += f"🎯 {texts['difficulty']} {difficulty_emoji.get(difficulty, '🟡')} **{difficulty}**\n"
    settings_message += f"🌐 Language: {language_emoji.get(language, '🌐')} **{language}**\n"
    if topic == "Basic Mathematics":
        settings_message += f"🔢 Math Subtopic: **{math_subtopic}**\n"
    settings_message += f"\n"
    settings_message += f"{texts['use_topics_difficulty_commands']}"
    
    # Create interactive keyboard with quick setting buttons
    keyboard = [
        [InlineKeyboardButton("📚 Change Topic", callback_data="settings_topic")],
        [InlineKeyboardButton("🎯 Change Difficulty", callback_data="settings_difficulty")],
        [InlineKeyboardButton("🌐 Change Language", callback_data="settings_language")],
    ]
    
    if topic == "Basic Mathematics":
        keyboard.append([InlineKeyboardButton("🔢 Change Math Subtopic", callback_data="settings_math_subtopic")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(settings_message, parse_mode="Markdown", reply_markup=reply_markup)

# === Callback Handlers ===
async def topic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = query.from_user.id
    callback_data = query.data
    
    print(f"DEBUG: topic_callback called with data: {callback_data}")
    
    # Register user if not already registered
    register_user(chat_id, query.from_user.username, query.from_user.first_name, query.from_user.last_name)
    
    if callback_data == "topic_random":
        update_user_preferences(chat_id, topic="Random")
        await query.edit_message_text("✅ Topic set to: **Random**\n\nUse /question to get MCQs from any topic!")
    else:
        # Extract topic name from callback_data
        topic_name = callback_data.replace("topic_", "")
        
        print(f"DEBUG: Extracted topic_name: {topic_name}")
    
        # If Basic Mathematics is selected, show subtopic selection
        if topic_name == "Basic Mathematics":
            print("DEBUG: Showing math subtopics from topic")
            await show_math_subtopics_from_topic(query)
        else:
            update_user_preferences(chat_id, topic=topic_name)
        await query.edit_message_text(f"✅ Topic set to: **{topic_name}**\n\nUse /question to get MCQs from this topic!", parse_mode="Markdown")

async def show_math_subtopics_from_topic(query):
    """Show mathematics subtopic selection when Basic Mathematics is chosen from topics"""
    message = "📚 *Basic Mathematics Selected!*\n\n"
    message += "Choose a specific area of mathematics to focus on:\n\n"
    
    # Create keyboard with subtopics in rows of 2
    keyboard = []
    for i in range(0, len(math_subtopics), 2):
        row = []
        row.append(InlineKeyboardButton(math_subtopics[i], callback_data=f"topic_math_subtopic_{math_subtopics[i]}"))
        if i + 1 < len(math_subtopics):
            row.append(InlineKeyboardButton(math_subtopics[i + 1], callback_data=f"topic_math_subtopic_{math_subtopics[i + 1]}"))
        keyboard.append(row)
    
    # Add "Random" option
    keyboard.append([InlineKeyboardButton("🎲 Random Subtopic", callback_data="topic_math_subtopic_Random")])
    
    # Add back button
    keyboard.append([InlineKeyboardButton("⬅️ Back to Topics", callback_data="back_to_topics")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)

async def difficulty_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = query.from_user.id
    callback_data = query.data
    
    # Register user if not already registered
    register_user(chat_id, query.from_user.username, query.from_user.first_name, query.from_user.last_name)
    
    # Extract difficulty from callback_data
    difficulty = callback_data.replace("difficulty_", "")
    update_user_preferences(chat_id, difficulty=difficulty)
    
    emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}
    await query.edit_message_text(f"✅ Difficulty set to: **{emoji.get(difficulty, '🟡')} {difficulty}**\n\nUse /question to get MCQs with this difficulty level!", parse_mode="Markdown")

async def math_subtopic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle math subtopic selection"""
    query = update.callback_query
    await query.answer()
    
    chat_id = query.from_user.id
    subtopic = query.data.replace("math_subtopic_", "")
    
    # Register user if not already registered
    register_user(chat_id, query.from_user.username, query.from_user.first_name, query.from_user.last_name)
    
    # Update user preferences with math subtopic
    update_user_preferences(chat_id, math_subtopic=subtopic)
    
    if subtopic == "Random":
        message = "🎲 Mathematics subtopic set to: **Random** (Balanced selection)"
    else:
        message = f"📚 Mathematics subtopic set to: **{subtopic}**"
    
    message += "\n\nUse /question to get MCQs from this specific mathematics area!"
    await query.edit_message_text(message, parse_mode="Markdown")

async def topic_math_subtopic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle math subtopic selection from topic menu"""
    try:
        query = update.callback_query
        await query.answer()
        
        chat_id = query.from_user.id
        callback_data = query.data
        
        print(f"DEBUG: topic_math_subtopic_callback called with data: {callback_data}")
        
        # Register user if not already registered
        register_user(chat_id, query.from_user.username, query.from_user.first_name, query.from_user.last_name)
        
        # Extract subtopic from callback_data
        subtopic = callback_data.replace("topic_math_subtopic_", "")
        
        print(f"DEBUG: Extracted subtopic: {subtopic}")
        
        # Set both topic and subtopic
        update_user_preferences(chat_id, topic="Basic Mathematics", math_subtopic=subtopic)
        
        if subtopic == "Random":
            message = "✅ **Basic Mathematics** with **Random** subtopic selected!\n\nUse /question to get MCQs from any mathematics area!"
        else:
            message = f"✅ **Basic Mathematics** with **{subtopic}** subtopic selected!\n\nUse /question to get MCQs from this specific mathematics area!"
        
        await query.edit_message_text(message, parse_mode="Markdown")
        
    except Exception as e:
        print(f"ERROR in topic_math_subtopic_callback: {e}")
        # Fallback message
        try:
            await query.edit_message_text("❌ Error occurred. Please try again with /topics")
        except:
            pass

async def back_to_topics_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back to topics button"""
    query = update.callback_query
    await query.answer()
    
    # Show the topics menu again
    await show_topics_from_callback(query)

async def show_topics_from_callback(query):
    """Show topics menu from callback"""
    message = "📚 **Select Topic:**\n\nChoose a topic for your MCQs:"
    
    keyboard = []
    for i in range(0, len(topics), 2):
        row = []
        row.append(InlineKeyboardButton(topics[i], callback_data=f"topic_{topics[i]}"))
        if i + 1 < len(topics):
            row.append(InlineKeyboardButton(topics[i + 1], callback_data=f"topic_{topics[i + 1]}"))
        keyboard.append(row)
    
    # Add Random option
    keyboard.append([InlineKeyboardButton("🎲 Random Topic", callback_data="topic_random")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)

async def reset_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = query.from_user.id
    
    # Register user if not already registered
    register_user(chat_id, query.from_user.username, query.from_user.first_name, query.from_user.last_name)
    
    # Reset user statistics
    reset_user_stats(chat_id)
    
    # Get user language preference for confirmation message
    preferences = get_user_preferences(chat_id)
    language = preferences.get("language", "English")
    texts = interface_texts.get(language, interface_texts["English"])
    
    await query.edit_message_text(
        texts["reset_confirmation"],
        parse_mode="Markdown"
    )

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection"""
    query = update.callback_query
    await query.answer()
    
    chat_id = query.from_user.id
    callback_data = query.data
    
    # Register user if not already registered
    register_user(chat_id, query.from_user.username, query.from_user.first_name, query.from_user.last_name)
    
    # Extract language from callback_data
    language = callback_data.replace("language_", "")
    update_user_preferences(chat_id, language=language)
    
    # Get appropriate text for confirmation
    texts = interface_texts.get(language, interface_texts["English"])
    
    emoji = {"English": "🇬🇧", "Hindi": "🇮🇳"}
    message = f"{emoji.get(language, '🌐')} **{texts['language_selected']} {language}**\n\n"
    
    if language == "Hindi":
        message += "अब आपको हिंदी में प्रश्न और इंटरफेस मिलेगा।\n"
        message += "Use /question to get MCQs in Hindi!"
    else:
        message += "Now you'll receive questions and interface in English.\n"
        message += "Use /question to get MCQs in English!"
    
    await query.edit_message_text(message, parse_mode="Markdown")

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle settings menu callbacks"""
    query = update.callback_query
    await query.answer()
    
    chat_id = query.from_user.id
    callback_data = query.data
    
    # Register user if not already registered
    register_user(chat_id, query.from_user.username, query.from_user.first_name, query.from_user.last_name)
    
    # Get current language for interface
    preferences = get_user_preferences(chat_id)
    language = preferences.get("language", "English")
    texts = interface_texts.get(language, interface_texts["English"])
    
    if callback_data == "settings_topic":
        # Show topic selection
        await show_topics_from_callback(query)
    elif callback_data == "settings_difficulty":
        # Show difficulty selection
        await show_difficulty_from_callback(query)
    elif callback_data == "settings_language":
        # Show language selection
        await show_language_from_callback(query)
    elif callback_data == "settings_math_subtopic":
        # Show math subtopic selection
        await show_math_subtopics_from_callback(query)
    else:
        await query.edit_message_text(texts["error_message"])

async def show_language_from_callback(query):
    """Show language selection from settings callback"""
    chat_id = query.from_user.id
    preferences = get_user_preferences(chat_id)
    current_language = preferences.get("language", "English")
    
    # Create keyboard with language options
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="language_English")],
        [InlineKeyboardButton("🇮🇳 हिंदी (Hindi)", callback_data="language_Hindi")],
        [InlineKeyboardButton("⬅️ Back to Settings", callback_data="back_to_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Get appropriate text based on current language
    texts = interface_texts.get(current_language, interface_texts["English"])
    message = f"🌐 **Select Language / भाषा चुनें:**\n\n"
    message += f"Current Language / वर्तमान भाषा: **{current_language}**\n\n"
    message += "Choose your preferred language for questions and interface:"
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")

async def show_difficulty_from_callback(query):
    """Show difficulty selection from settings callback"""
    chat_id = query.from_user.id
    preferences = get_user_preferences(chat_id)
    current_language = preferences.get("language", "English")
    
    # Create keyboard with difficulty options
    keyboard = [
        [InlineKeyboardButton("🟢 Easy", callback_data="difficulty_Easy")],
        [InlineKeyboardButton("🟡 Medium", callback_data="difficulty_Medium")],
        [InlineKeyboardButton("🔴 Hard", callback_data="difficulty_Hard")],
        [InlineKeyboardButton("⬅️ Back to Settings", callback_data="back_to_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Get appropriate text based on current language
    texts = interface_texts.get(current_language, interface_texts["English"])
    message = f"🎯 **Select Difficulty Level:**\n\n"
    message += "Choose your preferred difficulty level for MCQs:"
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")

async def show_math_subtopics_from_callback(query):
    """Show math subtopic selection from settings callback"""
    chat_id = query.from_user.id
    preferences = get_user_preferences(chat_id)
    current_language = preferences.get("language", "English")
    
    # Get appropriate text based on current language
    texts = interface_texts.get(current_language, interface_texts["English"])
    message = f"🔢 **Select Mathematics Subtopic:**\n\n"
    message += "Choose a specific area of mathematics to focus on:"
    
    # Create keyboard with subtopics in rows of 2
    keyboard = []
    for i in range(0, len(math_subtopics), 2):
        row = []
        row.append(InlineKeyboardButton(math_subtopics[i], callback_data=f"math_subtopic_{math_subtopics[i]}"))
        if i + 1 < len(math_subtopics):
            row.append(InlineKeyboardButton(math_subtopics[i + 1], callback_data=f"math_subtopic_{math_subtopics[i + 1]}"))
        keyboard.append(row)
    
    # Add "Random" option and back button
    keyboard.append([InlineKeyboardButton("🎲 Random Subtopic", callback_data="math_subtopic_Random")])
    keyboard.append([InlineKeyboardButton("⬅️ Back to Settings", callback_data="back_to_settings")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)

async def show_topics_from_callback(query):
    """Show topic selection from settings callback"""
    chat_id = query.from_user.id
    preferences = get_user_preferences(chat_id)
    current_language = preferences.get("language", "English")
    
    # Get appropriate text based on current language
    texts = interface_texts.get(current_language, interface_texts["English"])
    message = f"📚 **Select Topic:**\n\n"
    message += "Choose your preferred topic for MCQs:"
    
    # Create keyboard with topics in rows of 2
    keyboard = []
    for i in range(0, len(topics), 2):
        row = []
        row.append(InlineKeyboardButton(topics[i], callback_data=f"topic_{topics[i]}"))
        if i + 1 < len(topics):
            row.append(InlineKeyboardButton(topics[i + 1], callback_data=f"topic_{topics[i + 1]}"))
        keyboard.append(row)
    
    # Add "Random" option and back button
    keyboard.append([InlineKeyboardButton("🎲 Random Topic", callback_data="topic_random")])
    keyboard.append([InlineKeyboardButton("⬅️ Back to Settings", callback_data="back_to_settings")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)

async def back_to_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back to settings button"""
    query = update.callback_query
    await query.answer()
    
    chat_id = query.from_user.id
    
    # Register user if not already registered
    register_user(chat_id, query.from_user.username, query.from_user.first_name, query.from_user.last_name)
    
    preferences = get_user_preferences(chat_id)
    topic = preferences["topic"]
    difficulty = preferences["difficulty"]
    math_subtopic = preferences.get("math_subtopic", "Random")
    language = preferences.get("language", "English")
    
    # Get language-specific texts
    texts = interface_texts.get(language, interface_texts["English"])
    
    difficulty_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}
    language_emoji = {"English": "🇬🇧", "Hindi": "🇮🇳"}
    
    settings_message = f"⚙️ **{texts['settings']}**\n\n"
    settings_message += f"📚 {texts['topic']} **{topic}**\n"
    settings_message += f"🎯 {texts['difficulty']} {difficulty_emoji.get(difficulty, '🟡')} **{difficulty}**\n"
    settings_message += f"🌐 Language: {language_emoji.get(language, '🌐')} **{language}**\n"
    if topic == "Basic Mathematics":
        settings_message += f"🔢 Math Subtopic: **{math_subtopic}**\n"
    settings_message += f"\n"
    settings_message += f"{texts['use_topics_difficulty_commands']}"
    
    # Create interactive keyboard with quick setting buttons
    keyboard = [
        [InlineKeyboardButton("📚 Change Topic", callback_data="settings_topic")],
        [InlineKeyboardButton("🎯 Change Difficulty", callback_data="settings_difficulty")],
        [InlineKeyboardButton("🌐 Change Language", callback_data="settings_language")],
    ]
    
    if topic == "Basic Mathematics":
        keyboard.append([InlineKeyboardButton("🔢 Change Math Subtopic", callback_data="settings_math_subtopic")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(settings_message, parse_mode="Markdown", reply_markup=reply_markup)

# === MAIN BOT SETUP ===
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

# Command handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("question", manual_question))
app.add_handler(CommandHandler("topic", set_topic))
app.add_handler(CommandHandler("topics", show_topics))
app.add_handler(CommandHandler("difficulty", show_difficulty))
app.add_handler(CommandHandler("language", show_language))
app.add_handler(CommandHandler("math_subtopics", show_math_subtopics))
app.add_handler(CommandHandler("stats", show_stats))
app.add_handler(CommandHandler("settings", show_settings))
app.add_handler(CommandHandler("help", help_command))

# Callback query handlers (order matters - more specific patterns first)
app.add_handler(CallbackQueryHandler(topic_math_subtopic_callback, pattern="^topic_math_subtopic_"))
app.add_handler(CallbackQueryHandler(back_to_topics_callback, pattern="^back_to_topics$"))
app.add_handler(CallbackQueryHandler(back_to_settings_callback, pattern="^back_to_settings$"))
app.add_handler(CallbackQueryHandler(settings_callback, pattern="^settings_"))
app.add_handler(CallbackQueryHandler(topic_callback, pattern="^topic_"))
app.add_handler(CallbackQueryHandler(difficulty_callback, pattern="^difficulty_"))
app.add_handler(CallbackQueryHandler(language_callback, pattern="^language_"))
app.add_handler(CallbackQueryHandler(math_subtopic_callback, pattern="^math_subtopic_"))
app.add_handler(CallbackQueryHandler(reset_stats_callback, pattern="^reset_stats$"))

# Message handler for answers
app.add_handler(MessageHandler(filters.Regex(r'^[A-D]$'), handle_answer))

# Scheduler setup - now sends to all active users
scheduler = BackgroundScheduler()
scheduler.add_job(lambda: asyncio.run(send_question(None)), 'interval', minutes=30)
scheduler.start()

print("🤖 Enhanced MCQ Bot is running with multi-user support!")
print("📊 Features: Database, Stats, Difficulty levels, Multi-user scheduling")

app.run_polling()