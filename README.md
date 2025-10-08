# MP Patwari MCQ Bot 🤖

An intelligent Telegram bot that provides MP Patwari exam MCQs with interactive quiz functionality, multi-user support, and advanced features.

## ✨ Features

- 🎮 **Interactive Quiz Mode** - Answer questions and get instant feedback
- 📚 **8 MP Patwari Topics** - Complete syllabus coverage
- 🎯 **Topic Selection** - Choose specific subjects or random
- ⚡ **Difficulty Levels** - Easy, Medium, Hard with different AI prompts
- 👥 **Multi-User Support** - Personalized experience for each user
- 📊 **Statistics Tracking** - Track performance by topic and difficulty
- 💾 **Database Storage** - SQLite database for user data and progress
- ⏰ **24/7 Scheduled MCQs** - Automatic questions every 30 minutes to all users
- 💡 **Enhanced AI Explanations** - Detailed explanations with examples
- 📄 **Auto-save** - All questions saved to text file
- 🔄 **Real-time Feedback** - Know immediately if correct with stats

## Topics Covered

1. General Science
2. General Hindi
3. General English
4. Basic Mathematics
5. General Knowledge
6. Computer Knowledge
7. Reasoning Ability
8. General Management with MP GK

## 📱 Bot Commands

- `/start` - Welcome message and user registration
- `/question` - Get instant MCQ
- `/topics` - Interactive topic selection with buttons
- `/difficulty` - Select difficulty level (Easy/Medium/Hard)
- `/stats` - View your performance statistics
- `/settings` - View current preferences
- `/topic <name>` - Set topic via command
- `/help` - Show help message

## 🎯 Difficulty Levels

- **🟢 Easy**: Basic concepts, straightforward questions
- **🟡 Medium**: Intermediate concepts, moderate challenge
- **🔴 Hard**: Advanced concepts, complex scenarios

## 🌐 Deployment Options

### Option 1: Render (Recommended - Free Tier Available)

1. **Fork this repository** to your GitHub account
2. **Go to [Render.com](https://render.com)** and sign up with GitHub
3. **Create new Web Service**
4. **Connect your repository**
5. **Set Environment Variables**:
   ```
   OPENAI_API_KEY=your_openai_api_key
   TELEGRAM_BOT_TOKEN=your_bot_token
   ```
6. **Deploy** - Render will automatically deploy your bot

**Note:** Render's free tier may sleep after inactivity. Consider upgrading for 24/7 operation.

### Option 2: Railway (Free Tier Available)

1. **Fork this repository** to your GitHub account
2. **Go to [Railway.app](https://railway.app)** and sign up with GitHub
3. **Click "New Project"** → "Deploy from GitHub repo"
4. **Select your forked repository**
5. **Set Environment Variables**:
   ```
   OPENAI_API_KEY=your_openai_api_key
   TELEGRAM_BOT_TOKEN=your_bot_token
   ```
6. **Deploy** - Railway will automatically deploy your bot

### Option 3: Oracle Cloud (Always Free - 24/7)

1. **Create Oracle Cloud Free Tier account**
2. **Launch Always Free Compute Instance**
3. **Follow detailed setup in `oracle_cloud_setup.md`**
4. **Use systemd for automatic startup**

### Option 4: Replit (Great for Development)

1. **Go to [Replit.com](https://replit.com)** and sign up
2. **Create new Python Repl**
3. **Upload files or clone from GitHub**
4. **Set environment variables in Secrets tab**
5. **Run the bot**

**Detailed deployment guides available in `DEPLOYMENT.md`**

## Local Setup

1. **Clone repository**:

   ```bash
   git clone <your-repo-url>
   cd patwari-mcq-bot
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Create .env file** (copy from env_template.txt):

   ```
   OPENAI_API_KEY=your_openai_api_key
   TELEGRAM_BOT_TOKEN=your_bot_token
   ```

4. **Run bot**:
   ```bash
   python patwari_mcq_bot.py
   ```

## Getting API Keys

### OpenAI API Key

1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create account and get API key
3. Add credits to your account

### Telegram Bot Token

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` and follow instructions
3. Get your bot token

### Chat ID (No longer needed!)

The bot now supports multiple users automatically! Each user who starts the bot will be registered in the database.

## 📁 File Structure

```
├── patwari_mcq_bot.py              # Main bot code with multi-user support
├── patwari_mcq_bot_webhook.py      # Webhook version for deployment
├── requirements.txt                # Python dependencies
├── render.yaml                     # Render deployment configuration
├── replit.nix                      # Replit configuration
├── .replit                         # Replit settings
├── oracle_cloud_setup.md           # Oracle Cloud deployment guide
├── DEPLOYMENT.md                   # Comprehensive deployment guide
├── Procfile                        # Railway deployment configuration
├── runtime.txt                     # Python version
├── .gitignore                      # Git ignore rules
├── env_template.txt                # Environment variables template
├── mcq_bot.db                      # SQLite database (created automatically)
├── mp_patwari_questions.txt        # Auto-saved questions
└── README.md                       # This file
```

## Support

For issues or questions, please create an issue in the repository.

## License

This project is open source and available under the MIT License.

# QuestionPractice
