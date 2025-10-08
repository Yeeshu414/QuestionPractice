import os
import asyncio
import sqlite3
import datetime
import random
import re
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import OpenAI
from dotenv import load_dotenv
from sympy import sympify
import requests

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Rate limiting and processing flags
user_last_question_time = {}
user_processing_questions = {}
question_generation_lock = threading.Lock()
QUESTION_COOLDOWN = 5

def can_generate_question(chat_id):
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
    if chat_id not in user_last_question_time:
        return 0
    current_time = datetime.datetime.now()
    time_diff = (current_time - user_last_question_time[chat_id]).total_seconds()
    return max(0, QUESTION_COOLDOWN - time_diff)

def check_and_set_processing(chat_id):
    with question_generation_lock:
        if chat_id in user_processing_questions or not can_generate_question(chat_id):
            return False
        user_processing_questions[chat_id] = True
        return True

def clear_processing(chat_id):
    with question_generation_lock:
        user_processing_questions.pop(chat_id, None)

# Database functions
def db_execute(query, params=None, fetch=False):
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

def init_database():
    conn = sqlite3.connect('mcq_bot.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')
    
    # User preferences table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            chat_id INTEGER PRIMARY KEY,
            topic TEXT DEFAULT 'General Knowledge',
            difficulty TEXT DEFAULT 'Medium',
            language TEXT DEFAULT 'English',
            math_subtopic TEXT DEFAULT NULL,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )
    ''')
    
    # User statistics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_stats (
            chat_id INTEGER PRIMARY KEY,
            total_questions INTEGER DEFAULT 0,
            correct_answers INTEGER DEFAULT 0,
            wrong_answers INTEGER DEFAULT 0,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )
    ''')
    
    # Questions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            difficulty TEXT,
            question_text TEXT,
            correct_answer TEXT,
            explanation TEXT,
            math_subtopic TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def register_user(chat_id, username, first_name, last_name):
    query = "INSERT OR REPLACE INTO users (chat_id, username, first_name, last_name, is_active) VALUES (?, ?, ?, ?, TRUE)"
    db_execute(query, (chat_id, username, first_name, last_name))
    
    # Initialize preferences if not exists
    query = "INSERT OR IGNORE INTO user_preferences (chat_id) VALUES (?)"
    db_execute(query, (chat_id,))
    
    # Initialize stats if not exists
    query = "INSERT OR IGNORE INTO user_stats (chat_id) VALUES (?)"
    db_execute(query, (chat_id,))

def get_user_preferences(chat_id):
    query = "SELECT topic, difficulty, language, math_subtopic FROM user_preferences WHERE chat_id = ?"
    result = db_execute(query, (chat_id,), fetch=True)
    
    if result:
        return {
            "topic": result[0],
            "difficulty": result[1],
            "language": result[2],
            "math_subtopic": result[3]
        }
    else:
        # Default preferences
        return {
            "topic": "General Knowledge",
            "difficulty": "Medium",
            "language": "English",
            "math_subtopic": None
        }

def update_user_preferences(chat_id, **kwargs):
    if not kwargs:
        return
    
    set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
    query = f"UPDATE user_preferences SET {set_clause} WHERE chat_id = ?"
    params = list(kwargs.values()) + [chat_id]
    db_execute(query, params)

def save_user_answer(chat_id, is_correct):
    query = "UPDATE user_stats SET total_questions = total_questions + 1, correct_answers = correct_answers + ?, wrong_answers = wrong_answers + ? WHERE chat_id = ?"
    db_execute(query, (1 if is_correct else 0, 0 if is_correct else 1, chat_id))

def save_question_to_db(topic, difficulty, question_text, correct_answer, explanation, math_subtopic=None):
    query = "INSERT INTO questions (topic, difficulty, question_text, correct_answer, explanation, math_subtopic) VALUES (?, ?, ?, ?, ?, ?)"
    db_execute(query, (topic, difficulty, question_text, correct_answer, explanation, math_subtopic))

def reset_user_stats(chat_id):
    query = "UPDATE user_stats SET total_questions = 0, correct_answers = 0, wrong_answers = 0 WHERE chat_id = ?"
    db_execute(query, (chat_id,))

def get_user_stats(chat_id):
    query = "SELECT total_questions, correct_answers, wrong_answers FROM user_stats WHERE chat_id = ?"
    result = db_execute(query, (chat_id,), fetch=True)
    return result if result else (0, 0, 0)

def get_all_active_users():
    query = "SELECT chat_id FROM users WHERE is_active = TRUE"
    conn = sqlite3.connect('mcq_bot.db')
    cursor = conn.cursor()
    cursor.execute(query)
    result = [row[0] for row in cursor.fetchall()]
    conn.close()
    return result

def get_recent_questions(limit=5):
    query = "SELECT question_text FROM questions ORDER BY created_at DESC LIMIT ?"
    conn = sqlite3.connect('mcq_bot.db')
    cursor = conn.cursor()
    cursor.execute(query, (limit,))
    result = [row[0] for row in cursor.fetchall()]
    conn.close()
    return result

# Text cleaning function
def clean_mathematical_text(text):
    if not text:
        return text
    
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
        
        if any(op in cleaned_text for op in ['+', '-', '*', '/', '^', '=', '(', ')']):
            try:
                expr = sympify(cleaned_text, transformations='all')
                return str(expr).replace('**', '^').replace(' ', '')
            except:
                pass
        
        return cleaned_text.strip()
    except:
        return re.sub(r'\\[a-zA-Z]+', '', text.strip())

# Question parsing function
def parse_question(full_response):
    full_response = clean_mathematical_text(full_response.replace('\n\n', '\n').replace('  ', ' ').strip())
    
    question_match = re.search(r'Question:\s*(.*?)(?=A\))', full_response, re.DOTALL | re.IGNORECASE)
    question_text = clean_mathematical_text(question_match.group(1).strip()) if question_match else "Question not found"
    
    options_text = ""
    for option in ['A', 'B', 'C', 'D']:
        pattern = f'{option}\)\s*(.*?)(?=[A-D]\)|Correct Answer|Answer:|$)'
        option_match = re.search(pattern, full_response, re.DOTALL | re.IGNORECASE)
        if option_match:
            option_text = clean_mathematical_text(option_match.group(1).strip())
            options_text += f"{option}) {option_text}\n"
    
    if not options_text:
        options_text = "Options not found"
    
    answer_patterns = [r'Correct Answer:\s*([A-D])\)?', r'Answer:\s*([A-D])\)?', r'\(([A-D])\)']
    correct_answer = None
    for pattern in answer_patterns:
        answer_match = re.search(pattern, full_response, re.IGNORECASE)
        if answer_match:
            correct_answer = answer_match.group(1).upper()
            break
    
    if not correct_answer:
        for line in reversed(full_response.split('\n')):
            if re.search(r'([A-D])', line):
                correct_answer = re.search(r'([A-D])', line).group(1).upper()
                break
    
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

# Image generation functions
def download_image(url, filename):
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"Error downloading image: {e}")
        return False

def create_image_prompt(topic, math_subtopic, question_content):
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
        
        elif "data interpretation" in math_subtopic.lower() or "data sufficiency" in math_subtopic.lower():
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
        
        elif "arithmetic" in math_subtopic.lower():
            if numbers:
                return f"Educational arithmetic diagram showing numbers {', '.join(numbers[:3])} with basic operations. Clean, simple layout."
            return "Educational arithmetic diagram showing basic mathematical operations. Clean, simple layout."
        
        elif "geometry" in math_subtopic.lower():
            if "triangle" in question_content or "त्रिभुज" in question_content:
                return "Educational geometric diagram showing triangles with angles and sides labeled. Clean, mathematical illustration."
            elif "circle" in question_content or "वृत्त" in question_content:
                return "Educational geometric diagram showing circles with radius and diameter labeled. Clean, mathematical illustration."
            return "Educational geometric diagram showing various shapes with measurements. Clean, mathematical illustration."
        
        elif "algebra" in math_subtopic.lower():
            if numbers:
                return f"Educational algebraic diagram showing equations with variables and numbers {', '.join(numbers[:3])}. Clean, mathematical layout."
            return "Educational algebraic diagram showing equations and variables. Clean, mathematical layout."
        
        elif "number system" in math_subtopic.lower():
            if numbers:
                return f"Educational number system diagram showing numbers {', '.join(numbers[:4])} with place values. Clean, organized layout."
            return "Educational number system diagram showing place values and number properties. Clean, organized layout."
        
        elif "trigonometry" in math_subtopic.lower():
            return "Educational trigonometric diagram showing right triangles with angles and ratios labeled. Clean, mathematical illustration."
        
        elif "percentage" in math_subtopic.lower() or "ratio" in math_subtopic.lower():
            if numbers:
                return f"Educational percentage/ratio diagram showing {', '.join(numbers[:3])} with calculations. Clean, organized layout."
            return "Educational percentage and ratio diagram showing calculations and comparisons. Clean, organized layout."
        
        elif "time" in math_subtopic.lower() or "work" in math_subtopic.lower():
            return "Educational time and work diagram showing workers, time calculations, and efficiency. Clean, organized layout."
        
        elif "profit" in math_subtopic.lower() or "loss" in math_subtopic.lower():
            if numbers:
                return f"Educational profit/loss diagram showing cost price, selling price, and calculations with {', '.join(numbers[:3])}. Clean, business illustration."
            return "Educational profit and loss diagram showing business calculations. Clean, business illustration."
        
        elif "interest" in math_subtopic.lower() or "rate of interest" in math_subtopic.lower():
            if numbers:
                return f"Educational interest calculation diagram showing principal, rate, time with {', '.join(numbers[:3])}. Clean, financial illustration."
            return "Educational interest calculation diagram showing financial formulas. Clean, financial illustration."
        
        elif "decimals" in math_subtopic.lower() or "fractions" in math_subtopic.lower():
            if numbers:
                return f"Educational diagram showing decimal and fraction conversions with {', '.join(numbers[:3])}. Clean, mathematical layout."
            return "Educational diagram showing decimal and fraction concepts. Clean, mathematical layout."
        
        elif "square root" in math_subtopic.lower() or "cube root" in math_subtopic.lower():
            if numbers:
                return f"Educational diagram showing square root and cube root calculations with {', '.join(numbers[:3])}. Clean, mathematical layout."
            return "Educational diagram showing square root and cube root concepts. Clean, mathematical layout."
        
        elif "simplification" in math_subtopic.lower():
            if numbers:
                return f"Educational simplification diagram showing step-by-step calculations with {', '.join(numbers[:3])}. Clean, organized layout."
            return "Educational diagram showing mathematical simplification steps. Clean, organized layout."
        
        elif "l.s." in math_subtopic.lower() or "m.s." in math_subtopic.lower():
            return "Educational diagram showing Least Square and Most Square concepts with mathematical calculations. Clean, statistical layout."
        
        elif "time" in math_subtopic.lower() and "speed" in math_subtopic.lower() and "distance" in math_subtopic.lower():
            if numbers:
                return f"Educational time-speed-distance diagram showing calculations with {', '.join(numbers[:3])}. Clean, physics illustration."
            return "Educational diagram showing time, speed, and distance relationships. Clean, physics illustration."
        
        elif "ratio" in math_subtopic.lower() and "proportion" in math_subtopic.lower():
            if numbers:
                return f"Educational ratio and proportion diagram showing calculations with {', '.join(numbers[:3])}. Clean, mathematical layout."
            return "Educational diagram showing ratio and proportion concepts. Clean, mathematical layout."
        
        elif "partnership" in math_subtopic.lower():
            if numbers:
                return f"Educational partnership diagram showing profit/loss sharing with {', '.join(numbers[:3])}. Clean, business illustration."
            return "Educational diagram showing partnership calculations and profit sharing. Clean, business illustration."
        
        elif "number series" in math_subtopic.lower():
            if numbers:
                return f"Educational number series diagram showing pattern with {', '.join(numbers[:5])}. Clean, organized layout."
            return "Educational diagram showing number series patterns and sequences. Clean, organized layout."
        
        elif "discounts" in math_subtopic.lower():
            if numbers:
                return f"Educational discount calculation diagram showing price reductions with {', '.join(numbers[:3])}. Clean, business illustration."
            return "Educational diagram showing discount calculations and pricing. Clean, business illustration."
        
        elif "averages" in math_subtopic.lower():
            if numbers:
                return f"Educational average calculation diagram showing data points {', '.join(numbers[:4])}. Clean, statistical layout."
            return "Educational diagram showing average calculations and statistical concepts. Clean, statistical layout."
        
        elif "mixtures" in math_subtopic.lower():
            if numbers:
                return f"Educational mixture diagram showing different components with ratios {', '.join(numbers[:3])}. Clean, chemistry-style illustration."
            return "Educational diagram showing mixture calculations and component ratios. Clean, chemistry-style illustration."
        
        elif "percentages" in math_subtopic.lower():
            if numbers:
                return f"Educational percentage calculation diagram showing {', '.join(numbers[:3])} with percentage calculations. Clean, mathematical layout."
            return "Educational diagram showing percentage calculations and conversions. Clean, mathematical layout."
        
        elif "work" in math_subtopic.lower():
            if numbers:
                return f"Educational work calculation diagram showing workers and time with {', '.join(numbers[:3])}. Clean, organized layout."
            return "Educational diagram showing work and time calculations. Clean, organized layout."
        
        return f"Educational mathematical diagram for {math_subtopic} with clear labels and measurements."
    
    topic_prompts = {
        "General Science": {
            "biology": "Educational biological diagram showing anatomical structures, cells, or biological processes. Clean, scientific illustration.",
            "chemistry": "Educational chemistry diagram showing molecular structures, chemical reactions, or laboratory equipment. Clean, scientific illustration.",
            "physics": "Educational physics diagram showing mechanical systems, electrical circuits, or physical phenomena. Clean, scientific illustration.",
            "default": "Educational scientific diagram with laboratory equipment, biological structures, or chemical processes. Clean, scientific illustration."
        },
        "General Hindi": {
            "grammar": "Educational diagram showing Hindi grammar rules, sentence structure, or language concepts. Clean, educational illustration.",
            "literature": "Educational illustration showing Hindi literary figures, books, or cultural elements. Clean, cultural illustration style.",
            "default": "Educational Hindi language diagram showing grammar, vocabulary, or literary concepts. Clean, educational illustration."
        },
        "General English": {
            "grammar": "Educational diagram showing English grammar rules, sentence structure, or language concepts. Clean, educational illustration.",
            "literature": "Educational illustration showing English literary figures, books, or cultural elements. Clean, cultural illustration style.",
            "default": "Educational English language diagram showing grammar, vocabulary, or literary concepts. Clean, educational illustration."
        },
        "General Knowledge": {
            "awards": "Educational illustration showing awards, medals, or recognition symbols. Clean, prestigious illustration.",
            "sports": "Educational sports illustration showing various sports, equipment, or athletic achievements. Clean, dynamic illustration.",
            "default": "Educational general knowledge illustration showing various topics, symbols, or informative elements. Clean, educational illustration."
        },
        "Computer Knowledge": {
            "hardware": "Educational diagram showing computer hardware components, CPU, motherboard, or peripheral devices. Clean, technical illustration.",
            "software": "Educational illustration showing software interfaces, applications, or programming concepts. Clean, modern illustration.",
            "default": "Educational computer diagram showing hardware, software, or IT concepts. Clean, technical illustration."
        },
        "Reasoning Ability": {
            "puzzle": "Educational diagram showing logical puzzles, patterns, or reasoning problems. Clean, organized layout.",
            "series": "Educational illustration showing number series, pattern recognition, or sequence problems. Clean, mathematical layout.",
            "default": "Educational reasoning diagram showing logical problems, patterns, or analytical concepts. Clean, organized illustration."
        },
        "General Management with MP GK": {
            "management": "Educational diagram showing management principles, organizational structure, or business concepts. Clean, professional illustration.",
            "mp_map": "Educational map of Madhya Pradesh showing districts, cities, or geographical features. Clean, simple map style.",
            "government": "Educational illustration showing MP government buildings, symbols, or administrative structure. Clean, official illustration.",
            "default": "Educational MP management diagram showing administrative concepts, geography, or government structure. Clean, official illustration."
        }
    }
    
    if topic in topic_prompts:
        for keyword, prompt in topic_prompts[topic].items():
            if keyword != "default" and (keyword in question_content or any(hindi in question_content for hindi in ["नक्शा", "जलवायु", "स्मारक", "युद्ध", "जीव विज्ञान", "रसायन विज्ञान", "भौतिक विज्ञान"])):
                return prompt
        return topic_prompts[topic]["default"]
    
    return f"Educational diagram or illustration relevant to {topic} with clear labels and professional appearance. Clean, educational style."

def generate_question_image(topic, math_subtopic=None, question_text="", options_text="", question_type="MCQ"):
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

# Question generation function
def generate_mcq(topic, difficulty, chat_id, language="English", math_subtopic=None):
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    # Get recent questions to avoid repetition
    recent_questions = get_recent_questions(5)
    avoid_text = "\n".join([f"- {q}" for q in recent_questions]) if recent_questions else "No recent questions"
    
    # Language instructions
    language_instructions = {
        "English": "Generate the question and all content in English. Use English numerals (1, 2, 3, etc.) for all numbers.",
        "Hindi": "Generate the question and all content in Hindi. Use English numerals (1, 2, 3, etc.) for all numbers, not Hindi numerals. Keep mathematical expressions in standard English format (1, 2, 3, etc.)."
    }
    
    # Difficulty prompts
    difficulty_prompts = {
        "Easy": "Create a simple, straightforward question that tests basic understanding. Use simple language and basic concepts.",
        "Medium": "Create a moderately challenging question that requires some analysis or application of concepts.",
        "Hard": "Create a complex question that tests deep understanding, requires multiple steps, or involves advanced concepts."
    }
    
    # Topic-specific instructions
    topic_instructions = {
        "Basic Mathematics": f"""
        MATHEMATICS SPECIFIC INSTRUCTIONS:
        - Use simple numbers and basic operations (+, -, *, /)
        - Avoid fractions, decimals, percentages unless necessary
        - Keep mathematical expressions simple and clear
        - For geometry questions, include specific measurements
        - Use plain text format - NO LaTeX code or mathematical formatting
        - Use simple text for mathematical expressions
        """,
        "General Science": "Focus on basic science concepts from Biology, Chemistry, and Physics. Include practical applications, scientific phenomena, and fundamental principles. Keep questions relevant to competitive exam level.",
        "General Hindi": "Focus on Hindi grammar, literature, vocabulary, and language skills. Include questions about Hindi poets, writers, literary works, grammar rules, and language usage. Use proper Hindi terminology.",
        "General English": "Focus on English grammar, vocabulary, comprehension, and language skills. Include questions about grammar rules, synonyms, antonyms, idioms, and English literature basics.",
        "General Knowledge": "Create questions covering current affairs, history, geography, sports, awards, books, authors, and general awareness topics relevant to competitive exams.",
        "Computer Knowledge": "Focus on basic computer concepts, hardware, software, internet, MS Office, computer terminology, and fundamental IT knowledge relevant to competitive exams.",
        "Reasoning Ability": "Focus on logical reasoning, analytical ability, verbal reasoning, non-verbal reasoning, puzzles, series, coding-decoding, and problem-solving skills.",
        "General Management with MP GK": "Focus on management principles, Madhya Pradesh specific knowledge including geography, history, culture, current affairs, government schemes, and administrative aspects of MP."
    }
    
    # Math subtopic handling
    math_subtopic_text = ""
    if topic == "Basic Mathematics" and math_subtopic:
        math_subtopic_text = f"Focus specifically on: {math_subtopic}"
    
    prompt = f"""
    Generate a SHORT MCQ question for {topic} at {difficulty} difficulty level.
    
    {language_instructions.get(language, language_instructions["English"])}
    {difficulty_prompts.get(difficulty, difficulty_prompts["Medium"])}
    {topic_instructions.get(topic, "")}
    {math_subtopic_text}
    
    REQUIREMENTS:
    - Make the question SHORT and concise
    - Provide 4 options (A, B, C, D)
    - Clearly indicate the correct answer
    - Provide ONE sentence explaining why the correct answer is right - keep it short
    - Do not describe why wrong options are wrong
    - Use simple language and avoid complex jargon
    - Make sure the question is educational and appropriate
    
    AVOID THESE RECENT QUESTIONS:
    {avoid_text}
    
    Random seed: {random.randint(1000, 9999)}
    
    Format your response as:
    Question: [Your question here]
    A) [Option A]
    B) [Option B]
    C) [Option C]
    D) [Option D]
    Correct Answer: [A/B/C/D]
    Explanation: [One sentence explanation]
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7
        )
        
        full_response = response.choices[0].message.content.strip()
        
        # Determine if image is needed
        needs_image = False
        if topic == "Basic Mathematics" and math_subtopic:
            image_topics = ["mensuration", "data interpretation", "quadratic equations", "probability", "permutation", "combination", "geometry", "trigonometry", "statistics", "square root", "cube root", "simplification", "time", "speed", "distance", "number series", "data sufficiency", "averages", "mixtures", "percentages", "profit", "loss", "work", "rate of interest"]
            needs_image = any(img_topic in math_subtopic.lower() for img_topic in image_topics)
        elif topic in ["General Science", "General Hindi", "General English", "General Knowledge", "Computer Knowledge", "Reasoning Ability", "General Management with MP GK"]:
            needs_image = True
        
        return full_response, topic, math_subtopic, needs_image
        
    except Exception as e:
        print(f"Error generating MCQ: {e}")
        return "Error generating question", topic, math_subtopic, False

# Interface texts
interface_texts = {
    "English": {
        "welcome": "Welcome to MCQ Practice Bot! 📚\n\nThis bot helps you practice multiple choice questions for various topics.\n\nCommands:\n/start - Start the bot\n/help - Show help\n/question - Get a manual question\n/settings - Configure preferences\n/stats - View your statistics\n/language - Change language",
        "help_text": "MCQ Practice Bot Help 📖\n\nCommands:\n/start - Start the bot\n/help - Show help\n/question - Get a manual question\n/settings - Configure preferences\n/stats - View your statistics\n/language - Change language\n\nRate Limit: 5 seconds between questions",
        "question_ready": "📝 Question Ready!",
        "topic": "Topic:",
        "difficulty": "Difficulty:",
        "question": "Question:",
        "reply_instruction": "Reply with A, B, C, or D to answer.",
        "cooldown_message": "⏰ Please wait {remaining:.1f} seconds before requesting another question.",
        "processing_message": "⏳ Your question is being prepared... Please wait.",
        "correct_answer": "✅ Correct!",
        "wrong_answer": "❌ Incorrect!",
        "correct_option": "The correct answer is:",
        "explanation": "Explanation:",
        "stats_title": "📊 Your Statistics",
        "total_questions": "Total Questions:",
        "correct_answers": "Correct Answers:",
        "wrong_answers": "Wrong Answers:",
        "accuracy": "Accuracy:",
        "reset_stats": "Reset Stats"
    },
    "Hindi": {
        "welcome": "MCQ अभ्यास बॉट में आपका स्वागत है! 📚\n\nयह बॉट विभिन्न विषयों के लिए बहुविकल्पीय प्रश्नों का अभ्यास करने में आपकी मदद करता है।\n\nकमांड:\n/start - बॉट शुरू करें\n/help - सहायता दिखाएं\n/question - मैनुअल प्रश्न प्राप्त करें\n/settings - प्राथमिकताएं कॉन्फ़िगर करें\n/stats - अपने आंकड़े देखें\n/language - भाषा बदलें",
        "help_text": "MCQ अभ्यास बॉट सहायता 📖\n\nकमांड:\n/start - बॉट शुरू करें\n/help - सहायता दिखाएं\n/question - मैनुअल प्रश्न प्राप्त करें\n/settings - प्राथमिकताएं कॉन्फ़िगर करें\n/stats - अपने आंकड़े देखें\n/language - भाषा बदलें\n\nदर सीमा: प्रश्नों के बीच 5 सेकंड",
        "question_ready": "📝 प्रश्न तैयार!",
        "topic": "विषय:",
        "difficulty": "कठिनाई:",
        "question": "प्रश्न:",
        "reply_instruction": "उत्तर देने के लिए A, B, C, या D का उत्तर दें।",
        "cooldown_message": "⏰ कृपया दूसरा प्रश्न मांगने से पहले {remaining:.1f} सेकंड प्रतीक्षा करें।",
        "processing_message": "⏳ आपका प्रश्न तैयार हो रहा है... कृपया प्रतीक्षा करें।",
        "correct_answer": "✅ सही!",
        "wrong_answer": "❌ गलत!",
        "correct_option": "सही उत्तर है:",
        "explanation": "स्पष्टीकरण:",
        "stats_title": "📊 आपके आंकड़े",
        "total_questions": "कुल प्रश्न:",
        "correct_answers": "सही उत्तर:",
        "wrong_answers": "गलत उत्तर:",
        "accuracy": "सटीकता:",
        "reset_stats": "आंकड़े रीसेट करें"
    }
}

# Global variables
active_questions = {}
app = None

# Bot commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    register_user(chat_id, user.username, user.first_name, user.last_name)
    
    texts = interface_texts["English"]
    await update.message.reply_text(texts["welcome"])

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texts = interface_texts["English"]
    await update.message.reply_text(texts["help_text"])

async def manual_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Atomically check if user can process and set processing flag
    if not check_and_set_processing(chat_id):
        preferences = get_user_preferences(chat_id)
        language = preferences.get("language", "English")
        
        remaining_time = get_cooldown_remaining(chat_id)
        if remaining_time > 0:
            texts = interface_texts.get(language, interface_texts["English"])
            cooldown_message = texts["cooldown_message"].format(remaining=remaining_time)
            await update.message.reply_text(cooldown_message)
        else:
            texts = interface_texts.get(language, interface_texts["English"])
            await update.message.reply_text(texts["processing_message"])
        return
    
    try:
        # Register user if not already registered
        user = update.effective_user
        register_user(chat_id, user.username, user.first_name, user.last_name)
        
        # Get user preferences
        preferences = get_user_preferences(chat_id)
        selected_topic = preferences["topic"]
        difficulty = preferences["difficulty"]
        language = preferences["language"]
        math_subtopic = preferences.get("math_subtopic")
        
        # Generate question with validation
        max_attempts = 3
        for attempt in range(max_attempts):
            full_response, topic, math_subtopic, needs_image = generate_mcq(selected_topic, difficulty, chat_id, language, math_subtopic)
            question_text, options_text, correct_answer, explanation = parse_question(full_response)
            
            if correct_answer and correct_answer in ['A', 'B', 'C', 'D']:
                break
            elif attempt == max_attempts - 1:
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
        
        # Save question to database
        save_question_to_db(topic, difficulty, question_text, correct_answer, explanation, math_subtopic if topic == "Basic Mathematics" else None)
        
        # Get language-specific texts
        texts = interface_texts.get(language, interface_texts["English"])
        difficulty_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}
        question_message = f"{texts['question_ready']}\n{texts['topic']} {topic}\n{texts['difficulty']} {difficulty_emoji.get(difficulty, '🟡')} {difficulty}\n\n{texts['question']} {question_text}\n\n{options_text}\n\n{texts['reply_instruction']}"
        
        # Generate and send image if needed
        if needs_image:
            try:
                print(f"Generating image for topic: {topic}, math_subtopic: {math_subtopic}")
                image_url = generate_question_image(topic, math_subtopic, question_text, options_text)
                if image_url:
                    image_filename = f"temp_question_{chat_id}.png"
                    if download_image(image_url, image_filename):
                        with open(image_filename, 'rb') as photo:
                            await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=question_message, parse_mode="Markdown")
                        try:
                            os.remove(image_filename)
                        except:
                            pass
                    else:
                        await update.message.reply_text(question_message, parse_mode="Markdown")
                else:
                    await update.message.reply_text(question_message, parse_mode="Markdown")
            except Exception as e:
                print(f"Error with image generation: {e}")
                await update.message.reply_text(question_message, parse_mode="Markdown")
        else:
            await update.message.reply_text(question_message, parse_mode="Markdown")
            
    except Exception as e:
        print(f"Error in manual_question: {e}")
    finally:
        clear_processing(chat_id)

async def send_question_to_user(context, chat_id):
    """Send a personalized question to a specific user"""
    if not check_and_set_processing(chat_id):
        print(f"Skipping scheduled question for user {chat_id} - already processing or in cooldown")
        return
    
    try:
        preferences = get_user_preferences(chat_id)
        selected_topic = preferences["topic"]
        difficulty = preferences["difficulty"]
        language = preferences["language"]
        math_subtopic = preferences.get("math_subtopic")
        
        # Generate question with validation
        max_attempts = 3
        for attempt in range(max_attempts):
            full_response, topic, math_subtopic, needs_image = generate_mcq(selected_topic, difficulty, chat_id, language, math_subtopic)
            question_text, options_text, correct_answer, explanation = parse_question(full_response)
            
            if correct_answer and correct_answer in ['A', 'B', 'C', 'D']:
                break
            elif attempt == max_attempts - 1:
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
        
        # Save question to database
        save_question_to_db(topic, difficulty, question_text, correct_answer, explanation, math_subtopic if topic == "Basic Mathematics" else None)
        
        # Get language-specific texts
        texts = interface_texts.get(language, interface_texts["English"])
        difficulty_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}
        question_message = f"{texts['question_ready']}\n{texts['topic']} {topic}\n{texts['difficulty']} {difficulty_emoji.get(difficulty, '🟡')} {difficulty}\n\n{texts['question']} {question_text}\n\n{options_text}\n\n{texts['reply_instruction']}"
        
        # Generate and send image if needed
        if needs_image:
            try:
                print(f"Generating image for topic: {topic}, math_subtopic: {math_subtopic}")
                image_url = generate_question_image(topic, math_subtopic, question_text, options_text)
                if image_url:
                    image_filename = f"temp_question_{chat_id}.png"
                    if download_image(image_url, image_filename):
                        with open(image_filename, 'rb') as photo:
                            await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=question_message, parse_mode="Markdown")
                        try:
                            os.remove(image_filename)
                        except:
                            pass
                    else:
                        await context.bot.send_message(chat_id=chat_id, text=question_message, parse_mode="Markdown")
                else:
                    await context.bot.send_message(chat_id=chat_id, text=question_message, parse_mode="Markdown")
            except Exception as e:
                print(f"Error with image generation: {e}")
                await context.bot.send_message(chat_id=chat_id, text=question_message, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text=question_message, parse_mode="Markdown")
            
    except Exception as e:
        print(f"Error in send_question_to_user: {e}")
    finally:
        clear_processing(chat_id)

async def send_scheduled_questions(context: ContextTypes.DEFAULT_TYPE):
    """Send questions to all active users"""
    active_users = get_all_active_users()
    for user_chat_id in active_users:
        try:
            await send_question_to_user(context, user_chat_id)
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Error sending question to user {user_chat_id}: {e}")

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_answer = update.message.text.strip().upper()
    
    if chat_id not in active_questions:
        await update.message.reply_text("No active question found. Please request a new question.")
        return
    
    if user_answer not in ['A', 'B', 'C', 'D']:
        await update.message.reply_text("Please reply with A, B, C, or D.")
        return
    
    question_data = active_questions[chat_id]
    correct_answer = question_data['correct_answer']
    explanation = question_data['explanation']
    
    # Get user language for response
    preferences = get_user_preferences(chat_id)
    language = preferences.get("language", "English")
    texts = interface_texts.get(language, interface_texts["English"])
    
    is_correct = user_answer == correct_answer
    save_user_answer(chat_id, is_correct)
    
    if is_correct:
        response_message = f"{texts['correct_answer']}\n\n{texts['explanation']} {explanation}"
    else:
        response_message = f"{texts['wrong_answer']}\n\n{texts['correct_option']} {correct_answer}\n\n{texts['explanation']} {explanation}"
    
    await update.message.reply_text(response_message)
    del active_questions[chat_id]

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    preferences = get_user_preferences(chat_id)
    language = preferences.get("language", "English")
    texts = interface_texts.get(language, interface_texts["English"])
    
    keyboard = [
        [InlineKeyboardButton("📚 Topic", callback_data="settings_topic")],
        [InlineKeyboardButton("🎯 Difficulty", callback_data="settings_difficulty")],
        [InlineKeyboardButton("🌐 Language", callback_data="settings_language")],
        [InlineKeyboardButton("📊 Stats", callback_data="settings_stats")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    settings_text = f"⚙️ Settings\n\nCurrent Preferences:\n• Topic: {preferences['topic']}\n• Difficulty: {preferences['difficulty']}\n• Language: {language}"
    await update.message.reply_text(settings_text, reply_markup=reply_markup)

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    total, correct, wrong = get_user_stats(chat_id)
    accuracy = (correct / total * 100) if total > 0 else 0
    
    preferences = get_user_preferences(chat_id)
    language = preferences.get("language", "English")
    texts = interface_texts.get(language, interface_texts["English"])
    
    keyboard = [[InlineKeyboardButton(texts["reset_stats"], callback_data="reset_stats")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    stats_text = f"{texts['stats_title']}\n\n{texts['total_questions']} {total}\n{texts['correct_answers']} {correct}\n{texts['wrong_answers']} {wrong}\n{texts['accuracy']} {accuracy:.1f}%"
    await update.message.reply_text(stats_text, reply_markup=reply_markup)

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat_id = query.message.chat_id
    
    if data == "settings_topic":
        keyboard = [
            [InlineKeyboardButton("🔬 General Science", callback_data="topic_General Science")],
            [InlineKeyboardButton("📖 General Hindi", callback_data="topic_General Hindi")],
            [InlineKeyboardButton("🇺🇸 General English", callback_data="topic_General English")],
            [InlineKeyboardButton("🔢 Basic Mathematics", callback_data="topic_Basic Mathematics")],
            [InlineKeyboardButton("📚 General Knowledge", callback_data="topic_General Knowledge")],
            [InlineKeyboardButton("💻 Computer Knowledge", callback_data="topic_Computer Knowledge")],
            [InlineKeyboardButton("🧠 Reasoning Ability", callback_data="topic_Reasoning Ability")],
            [InlineKeyboardButton("🏛️ General Management with MP GK", callback_data="topic_General Management with MP GK")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📚 Select Topic:", reply_markup=reply_markup)
    
    elif data == "settings_difficulty":
        keyboard = [
            [InlineKeyboardButton("🟢 Easy", callback_data="difficulty_Easy")],
            [InlineKeyboardButton("🟡 Medium", callback_data="difficulty_Medium")],
            [InlineKeyboardButton("🔴 Hard", callback_data="difficulty_Hard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🎯 Select Difficulty:", reply_markup=reply_markup)
    
    elif data == "settings_language":
        keyboard = [
            [InlineKeyboardButton("🇺🇸 English", callback_data="language_English")],
            [InlineKeyboardButton("🇮🇳 Hindi", callback_data="language_Hindi")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🌐 Select Language:", reply_markup=reply_markup)
    
    elif data == "settings_stats":
        await show_stats_from_callback(query)

async def topic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    topic = query.data.replace("topic_", "")
    chat_id = query.message.chat_id
    
    if topic == "Basic Mathematics":
        keyboard = [
            [InlineKeyboardButton("🔢 Decimals and Fractions", callback_data="topic_math_subtopic_Decimals and Fractions")],
            [InlineKeyboardButton("√ Square Root and Cube Root", callback_data="topic_math_subtopic_Square Root and Cube Root")],
            [InlineKeyboardButton("🧮 Simplification", callback_data="topic_math_subtopic_Simplification")],
            [InlineKeyboardButton("📏 L.S. and M.S.", callback_data="topic_math_subtopic_L.S. and M.S.")],
            [InlineKeyboardButton("⏰ Time, Speed, and Distance", callback_data="topic_math_subtopic_Time, Speed, and Distance")],
            [InlineKeyboardButton("📊 Mensuration", callback_data="topic_math_subtopic_Mensuration")],
            [InlineKeyboardButton("🔢 Number System", callback_data="topic_math_subtopic_Number System")],
            [InlineKeyboardButton("💰 Simple and Compound Interest", callback_data="topic_math_subtopic_Simple and Compound Interest")],
            [InlineKeyboardButton("📊 Ratio and Proportion", callback_data="topic_math_subtopic_Ratio and Proportion")],
            [InlineKeyboardButton("🤝 Partnership", callback_data="topic_math_subtopic_Partnership")],
            [InlineKeyboardButton("🔢 Number Series", callback_data="topic_math_subtopic_Number Series")],
            [InlineKeyboardButton("📊 Data Interpretation", callback_data="topic_math_subtopic_Data Interpretation")],
            [InlineKeyboardButton("📈 Quadratic Equations", callback_data="topic_math_subtopic_Quadratic Equations")],
            [InlineKeyboardButton("📋 Data Sufficiency", callback_data="topic_math_subtopic_Data Sufficiency")],
            [InlineKeyboardButton("🏷️ Discounts", callback_data="topic_math_subtopic_Discounts")],
            [InlineKeyboardButton("📊 Averages", callback_data="topic_math_subtopic_Averages")],
            [InlineKeyboardButton("🥤 Mixtures", callback_data="topic_math_subtopic_Mixtures")],
            [InlineKeyboardButton("📊 Percentages", callback_data="topic_math_subtopic_Percentages")],
            [InlineKeyboardButton("💰 Profit and Loss", callback_data="topic_math_subtopic_Profit and Loss")],
            [InlineKeyboardButton("⚙️ Work", callback_data="topic_math_subtopic_Work")],
            [InlineKeyboardButton("📈 Rate of Interest", callback_data="topic_math_subtopic_Rate of Interest")],
            [InlineKeyboardButton("🎲 Probability", callback_data="topic_math_subtopic_Probability")],
            [InlineKeyboardButton("🔢 Permutation and Combination", callback_data="topic_math_subtopic_Permutation and Combination")],
            [InlineKeyboardButton("📚 All Mathematics", callback_data="topic_math_subtopic_All Mathematics")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🔢 Select Mathematics Subtopic:", reply_markup=reply_markup)
    else:
        update_user_preferences(chat_id, topic=topic)
        await query.edit_message_text(f"✅ Topic updated to: {topic}")

async def topic_math_subtopic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    math_subtopic = query.data.replace("topic_math_subtopic_", "")
    chat_id = query.message.chat_id
    
    update_user_preferences(chat_id, topic="Basic Mathematics", math_subtopic=math_subtopic)
    await query.edit_message_text(f"✅ Mathematics subtopic updated to: {math_subtopic}")

async def difficulty_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    difficulty = query.data.replace("difficulty_", "")
    chat_id = query.message.chat_id
    
    update_user_preferences(chat_id, difficulty=difficulty)
    await query.edit_message_text(f"✅ Difficulty updated to: {difficulty}")

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    language = query.data.replace("language_", "")
    chat_id = query.message.chat_id
    
    update_user_preferences(chat_id, language=language)
    
    texts = interface_texts.get(language, interface_texts["English"])
    await query.edit_message_text(f"✅ Language updated to: {language}")

async def show_stats_from_callback(query):
    chat_id = query.message.chat_id
    total, correct, wrong = get_user_stats(chat_id)
    accuracy = (correct / total * 100) if total > 0 else 0
    
    preferences = get_user_preferences(chat_id)
    language = preferences.get("language", "English")
    texts = interface_texts.get(language, interface_texts["English"])
    
    keyboard = [[InlineKeyboardButton(texts["reset_stats"], callback_data="reset_stats")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    stats_text = f"{texts['stats_title']}\n\n{texts['total_questions']} {total}\n{texts['correct_answers']} {correct}\n{texts['wrong_answers']} {wrong}\n{texts['accuracy']} {accuracy:.1f}%"
    await query.edit_message_text(stats_text, reply_markup=reply_markup)

async def reset_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat_id
    reset_user_stats(chat_id)
    
    preferences = get_user_preferences(chat_id)
    language = preferences.get("language", "English")
    texts = interface_texts.get(language, interface_texts["English"])
    
    await query.edit_message_text("✅ Statistics reset successfully!")

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇺🇸 English", callback_data="language_English")],
        [InlineKeyboardButton("🇮🇳 Hindi", callback_data="language_Hindi")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🌐 Select Language:", reply_markup=reply_markup)

def main():
    global app
    
    # Initialize database
    init_database()
    
    # Create application
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("question", manual_question))
    app.add_handler(CommandHandler("settings", show_settings))
    app.add_handler(CommandHandler("stats", show_stats))
    app.add_handler(CommandHandler("language", language_command))
    
    # Add callback handlers with proper priority
    app.add_handler(CallbackQueryHandler(topic_math_subtopic_callback, pattern="^topic_math_subtopic_"))
    app.add_handler(CallbackQueryHandler(topic_callback, pattern="^topic_"))
    app.add_handler(CallbackQueryHandler(difficulty_callback, pattern="^difficulty_"))
    app.add_handler(CallbackQueryHandler(language_callback, pattern="^language_"))
    app.add_handler(CallbackQueryHandler(reset_stats_callback, pattern="^reset_stats$"))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern="^settings_"))
    
    # Add message handler for answers
    app.add_handler(MessageHandler(filters=None, callback=handle_answer))
    
    print("Bot started successfully!")
    print("Note: Scheduled questions are disabled for now. Use /question for manual questions.")
    
    # Run the bot
    app.run_polling()

if __name__ == '__main__':
    main()
