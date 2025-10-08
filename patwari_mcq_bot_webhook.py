from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# === CONFIGURATION ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # For platforms like Railway
PORT = int(os.getenv("PORT", 8000))

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

# Database helper functions (same as main file)
def get_user_preferences(chat_id):
    """Get user preferences from database"""
    conn = sqlite3.connect('mcq_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT topic, difficulty FROM user_preferences WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {"topic": result[0], "difficulty": result[1]}
    else:
        return {"topic": "Random", "difficulty": "Medium"}

def update_user_preferences(chat_id, topic=None, difficulty=None):
    """Update user preferences in database"""
    conn = sqlite3.connect('mcq_bot.db')
    cursor = conn.cursor()
    
    current = get_user_preferences(chat_id)
    new_topic = topic if topic else current["topic"]
    new_difficulty = difficulty if difficulty else current["difficulty"]
    
    cursor.execute('''
        INSERT OR REPLACE INTO user_preferences (chat_id, topic, difficulty)
        VALUES (?, ?, ?)
    ''', (chat_id, new_topic, new_difficulty))
    
    conn.commit()
    conn.close()

def register_user(chat_id, username=None, first_name=None, last_name=None):
    """Register a new user in the database"""
    conn = sqlite3.connect('mcq_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR IGNORE INTO users (chat_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
    ''', (chat_id, username, first_name, last_name))
    
    # Set default preferences
    cursor.execute('''
        INSERT OR IGNORE INTO user_preferences (chat_id, topic, difficulty)
        VALUES (?, 'Random', 'Medium')
    ''', (chat_id,))
    
    conn.commit()
    conn.close()

def save_user_answer(chat_id, topic, difficulty, is_correct, question_id=None):
    """Save user's answer to database"""
    conn = sqlite3.connect('mcq_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO user_stats (chat_id, topic, difficulty, is_correct, question_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (chat_id, topic, difficulty, is_correct, question_id))
    
    conn.commit()
    conn.close()

def get_user_stats(chat_id):
    """Get user statistics from database"""
    conn = sqlite3.connect('mcq_bot.db')
    cursor = conn.cursor()
    
    # Overall stats
    cursor.execute('''
        SELECT 
            COUNT(*) as total_questions,
            SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_answers,
            topic,
            difficulty
        FROM user_stats 
        WHERE chat_id = ?
        GROUP BY topic, difficulty
        ORDER BY total_questions DESC
    ''', (chat_id,))
    
    topic_stats = cursor.fetchall()
    
    # Overall summary
    cursor.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct
        FROM user_stats 
        WHERE chat_id = ?
    ''', (chat_id,))
    
    overall = cursor.fetchone()
    conn.close()
    
    return {
        "overall": {"total": overall[0] if overall[0] else 0, "correct": overall[1] if overall[1] else 0},
        "by_topic": topic_stats
    }

def get_all_active_users():
    """Get all active users for scheduled questions"""
    conn = sqlite3.connect('mcq_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT chat_id FROM users WHERE is_active = 1')
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return users

active_questions = {}  # Store active questions by chat_id

# Include all the same functions from the main file...
# (generate_mcq, parse_question, save_question_to_file, etc.)
# For brevity, I'm including just the key differences for webhook mode

# === WEBHOOK-SPECIFIC SETUP ===
async def post_init(application):
    """Initialize the application after startup"""
    if WEBHOOK_URL:
        await application.bot.set_webhook(url=WEBHOOK_URL)

async def send_question_to_all_users():
    """Send questions to all active users"""
    active_users = get_all_active_users()
    for user_chat_id in active_users:
        try:
            await send_question_to_user(None, user_chat_id)
            await asyncio.sleep(0.1)  # Small delay between users
        except Exception as e:
            print(f"Error sending question to user {user_chat_id}: {e}")

# Include all the command handlers from the main file...
# (start, manual_question, handle_answer, etc.)

# === MAIN APPLICATION ===
def main():
    # Create application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    
    # Add all handlers (same as main file)
    # ... (include all handlers)
    
    # Start scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_question_to_all_users, 'interval', minutes=30)
    scheduler.start()
    
    print("🤖 Enhanced MCQ Bot is running with webhook support!")
    
    if WEBHOOK_URL:
        # Webhook mode
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL
        )
    else:
        # Polling mode (fallback)
        application.run_polling()

if __name__ == '__main__':
    main()
