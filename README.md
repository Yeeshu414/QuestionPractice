# MP Patwari MCQ Bot

An intelligent Telegram bot that provides MP Patwari exam MCQs with interactive quiz functionality.

## Features

- 🎮 **Interactive Quiz Mode** - Answer questions and get instant feedback
- 📚 **8 MP Patwari Topics** - Complete syllabus coverage
- 🎯 **Topic Selection** - Choose specific subjects or random
- ⏰ **Scheduled MCQs** - Automatic questions every 30 minutes
- 💡 **Explanations** - Learn from each answer
- 📄 **Auto-save** - All questions saved to text file
- 🔄 **Real-time Feedback** - Know immediately if correct

## Topics Covered

1. General Science
2. General Hindi
3. General English
4. Basic Mathematics
5. General Knowledge
6. Computer Knowledge
7. Reasoning Ability
8. General Management with MP GK

## Commands

- `/start` - Welcome message and help
- `/question` - Get instant MCQ
- `/topics` - Interactive topic selection
- `/topic <name>` - Set topic via command
- `/help` - Show help message

## Deployment Options

### Option 1: Railway (Recommended - Free)

1. **Fork this repository** to your GitHub account
2. **Go to [Railway.app](https://railway.app)** and sign up with GitHub
3. **Click "New Project"** → "Deploy from GitHub repo"
4. **Select your forked repository**
5. **Set Environment Variables** in Railway dashboard:
   ```
   OPENAI_API_KEY=your_openai_api_key
   TELEGRAM_BOT_TOKEN=your_bot_token
   YOUR_CHAT_ID=your_chat_id
   ```
6. **Deploy** - Railway will automatically deploy your bot

### Option 2: Render (Free Tier Available)

1. **Connect GitHub repository** to Render
2. **Create new Web Service**
3. **Set Environment Variables**:
   ```
   OPENAI_API_KEY=your_openai_api_key
   TELEGRAM_BOT_TOKEN=your_bot_token
   YOUR_CHAT_ID=your_chat_id
   ```
4. **Deploy**

### Option 3: Heroku

1. **Install Heroku CLI** and login
2. **Create Heroku app**: `heroku create your-bot-name`
3. **Set environment variables**:
   ```bash
   heroku config:set OPENAI_API_KEY=your_key
   heroku config:set TELEGRAM_BOT_TOKEN=your_token
   heroku config:set YOUR_CHAT_ID=your_id
   ```
4. **Deploy**: `git push heroku main`

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
   YOUR_CHAT_ID=your_chat_id
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

### Chat ID

1. Start your bot with `/start`
2. Check bot logs to see your Chat ID
3. Use this ID in environment variables

## File Structure

```
├── patwari_mcq_bot.py    # Main bot code
├── requirements.txt      # Python dependencies
├── Procfile             # Deployment configuration
├── runtime.txt          # Python version
├── .gitignore          # Git ignore rules
├── env_template.txt    # Environment variables template
└── README.md           # This file
```

## Support

For issues or questions, please create an issue in the repository.

## License

This project is open source and available under the MIT License.

# QuestionPractice
