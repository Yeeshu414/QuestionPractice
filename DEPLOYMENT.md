# Railway Deployment Guide

## 🚀 Quick Deploy to Railway

### 1. Prerequisites
- GitHub repository with your code
- Railway account
- Telegram Bot Token from @BotFather
- OpenAI API Key

### 2. Deploy Steps

1. **Connect to Railway:**
   - Go to [railway.app](https://railway.app)
   - Sign in with GitHub
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

2. **Configure Environment Variables:**
   - Go to your project settings
   - Add these variables:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   OPENAI_API_KEY=your_openai_key_here
   ```

3. **Deploy:**
   - Railway will automatically detect the `railway.json` configuration
   - The bot will start automatically with `python patwari_mcq_bot.py`

### 3. Files Included
- ✅ `patwari_mcq_bot.py` - Main bot file
- ✅ `requirements.txt` - Python dependencies
- ✅ `railway.json` - Railway configuration
- ✅ `mcq_bot.db` - SQLite database (will be recreated if needed)

### 4. Features
- 🤖 MCQ Practice Bot with multi-user support
- 📊 Statistics tracking
- 🌐 Bilingual support (English/Hindi)
- 🎯 Difficulty levels and topic selection
- 🖼️ Smart image generation for math questions
- ⏱️ Rate limiting and anti-spam protection

### 5. Bot Commands
- `/start` - Initialize the bot
- `/question` - Get a manual question
- `/settings` - Configure preferences
- `/stats` - View statistics
- `/language` - Change language

### 6. Troubleshooting
- Check Railway logs if bot doesn't start
- Ensure all environment variables are set
- Verify bot token is valid
- Check OpenAI API key permissions

---
**Ready to deploy!** 🎉
