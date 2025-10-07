from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from apscheduler.schedulers.background import BackgroundScheduler
from openai import OpenAI
import random
import asyncio
import datetime
import re
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# === CONFIGURATION ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUR_CHAT_ID = os.getenv("YOUR_CHAT_ID")

# Validate required environment variables
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
if not YOUR_CHAT_ID:
    raise ValueError("YOUR_CHAT_ID environment variable is required")

client = OpenAI(api_key=OPENAI_API_KEY)

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
user_selected_topics = {}  # Store user's topic preferences by chat_id
active_questions = {}  # Store active questions by chat_id: {question_text, correct_answer, explanation, topic}

# === AI Question Generator ===
def generate_mcq(selected_topic=None):
    if selected_topic:
        topic = selected_topic
    else:
        topic = random.choice(topics)
    
    prompt = f"""Generate one MP Patwari exam MCQ from {topic}. 

Format:
Question: [Your question here]
A) [Option A]
B) [Option B] 
C) [Option C]
D) [Option D]

Correct Answer: [A/B/C/D]
Explanation: [Brief explanation of why this answer is correct]"""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    full_response = response.choices[0].message.content.strip()
    return full_response, topic

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
    # Extract question without answer
    question_match = re.search(r'Question:\s*(.*?)(?=A\))', full_response, re.DOTALL | re.IGNORECASE)
    question_text = question_match.group(1).strip() if question_match else "Question not found"
    
    # Extract options
    options_match = re.search(r'(A\)\s*.*?B\)\s*.*?C\)\s*.*?D\)\s*.*?)(?=Correct Answer)', full_response, re.DOTALL | re.IGNORECASE)
    options_text = options_match.group(1).strip() if options_match else "Options not found"
    
    # Extract correct answer
    answer_match = re.search(r'Correct Answer:\s*([A-D])', full_response, re.IGNORECASE)
    correct_answer = answer_match.group(1).upper() if answer_match else None
    
    # Extract explanation
    explanation_match = re.search(r'Explanation:\s*(.*)', full_response, re.DOTALL | re.IGNORECASE)
    explanation = explanation_match.group(1).strip() if explanation_match else "No explanation provided"
    
    return question_text, options_text, correct_answer, explanation

# === Extract Correct Answer from Question (legacy support) ===
def extract_correct_answer(question_text):
    # Look for patterns like "Correct Answer: A", "Answer: B", etc.
    patterns = [
        r"correct answer[:\s]+([A-D])",
        r"answer[:\s]+([A-D])",
        r"\(correct\)[:\s]*([A-D])",
        r"✅[:\s]*([A-D])"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, question_text.lower())
        if match:
            return match.group(1).upper()
    
    return None

# === Telegram Command Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        "👋 Hi! I'll send you a new MP Patwari MCQ every 30 minutes.\n\n"
        "📋 Available commands:\n"
        "• /question - Get instant MCQ\n"
        "• /topics - Select topic with interactive buttons\n"
        "• /topic <name> - Set topic via command\n"
        "• /help - Show this help message\n\n"
        "🎮 **Interactive Quiz Mode:**\n"
        "• Questions show without answers\n"
        "• Reply with A, B, C, or D to answer\n"
        "• Get instant feedback + explanation\n\n"
        "📄 All questions are auto-saved to mp_patwari_questions.txt\n"
        "🎯 Try /topics for easy topic selection!"
    )
    print(f"User Chat ID: {chat_id} (save this in YOUR_CHAT_ID in code)")

async def send_question(context, chat_id=None):
    target_chat_id = chat_id or YOUR_CHAT_ID
    selected_topic = user_selected_topics.get(target_chat_id)
    
    full_response, topic = generate_mcq(selected_topic)
    question_text, options_text, correct_answer, explanation = parse_question(full_response)
    
    # Store active question
    active_questions[target_chat_id] = {
        'question_text': question_text,
        'options_text': options_text,
        'correct_answer': correct_answer,
        'explanation': explanation,
        'topic': topic,
        'full_response': full_response
    }
    
    # Save question to file
    save_question_to_file(full_response, topic, correct_answer)
    
    # Send question without answer
    question_message = f"🧠 *MP Patwari Practice MCQ:*\n📚 Topic: {topic}\n\n*Question:* {question_text}\n\n{options_text}\n\n💭 Reply with A, B, C, or D to answer!"
    
    if context and hasattr(context, 'bot'):
        await context.bot.send_message(chat_id=target_chat_id, text=question_message, parse_mode="Markdown")
    else:
        await app.bot.send_message(chat_id=target_chat_id, text=question_message, parse_mode="Markdown")

async def manual_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    selected_topic = user_selected_topics.get(chat_id)
    
    full_response, topic = generate_mcq(selected_topic)
    question_text, options_text, correct_answer, explanation = parse_question(full_response)
    
    # Store active question
    active_questions[chat_id] = {
        'question_text': question_text,
        'options_text': options_text,
        'correct_answer': correct_answer,
        'explanation': explanation,
        'topic': topic,
        'full_response': full_response
    }
    
    # Save question to file
    save_question_to_file(full_response, topic, correct_answer)
    
    # Send question without answer
    question_message = f"🧠 *MCQ:*\n📚 Topic: {topic}\n\n*Question:* {question_text}\n\n{options_text}\n\n💭 Reply with A, B, C, or D to answer!"
    await update.message.reply_text(question_message, parse_mode="Markdown")

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
    
    # Check if answer is correct
    if user_answer == correct_answer:
        feedback = "✅ **Correct!**"
    else:
        feedback = f"❌ **Wrong!** Correct answer is **{correct_answer})**"
    
    # Send feedback
    feedback_message = f"{feedback}\n\n💡 *Explanation:* {explanation}\n\n🎯 Use /question for more MCQs!"
    await update.message.reply_text(feedback_message, parse_mode="Markdown")
    
    # Remove the active question
    del active_questions[chat_id]

# === Topic Selection Commands ===
async def set_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
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
        user_selected_topics[chat_id] = topic_input
        await update.message.reply_text(f"✅ Topic set to: **{topic_input}**\n\nUse /question to get MCQs from this topic!", parse_mode="Markdown")
    else:
        topics_list = "\n".join([f"• {topic}" for topic in topics])
        await update.message.reply_text(
            f"❌ Topic '{topic_input}' not found!\n\n"
            f"Available topics:\n{topics_list}"
        )

async def show_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# === Callback Handler for Topic Selection ===
async def topic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = query.from_user.id
    callback_data = query.data
    
    if callback_data == "topic_random":
        # Remove any selected topic preference
        if chat_id in user_selected_topics:
            del user_selected_topics[chat_id]
        await query.edit_message_text("✅ Topic set to: **Random**\n\nUse /question to get MCQs from any topic!")
    else:
        # Extract topic name from callback_data
        topic_name = callback_data.replace("topic_", "")
        user_selected_topics[chat_id] = topic_name
        await query.edit_message_text(f"✅ Topic set to: **{topic_name}**\n\nUse /question to get MCQs from this topic!", parse_mode="Markdown")

# === MAIN BOT SETUP ===
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("question", manual_question))
app.add_handler(CommandHandler("topic", set_topic))
app.add_handler(CommandHandler("topics", show_topics))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CallbackQueryHandler(topic_callback, pattern="^topic_"))
app.add_handler(MessageHandler(filters.Regex(r'^[A-D]$'), handle_answer))

scheduler = BackgroundScheduler()
scheduler.add_job(lambda: asyncio.run(send_question(None)), 'interval', minutes=30)
scheduler.start()

print("🤖 Bot is running...")

app.run_polling()
