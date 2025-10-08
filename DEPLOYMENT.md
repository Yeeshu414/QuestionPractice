# Deployment Guide for MP Patwari MCQ Bot

This guide covers deployment options for the enhanced MCQ bot with multi-user support, database, and statistics tracking.

## 🌐 Deployment Options

### 1. Render (Recommended for beginners)

**Pros:** Easy setup, automatic deployments, free tier available
**Cons:** Limited free tier resources

#### Steps:

1. Fork this repository to your GitHub account
2. Go to [Render.com](https://render.com) and sign up
3. Connect your GitHub account
4. Create a new Web Service
5. Select your repository
6. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python patwari_mcq_bot.py`
   - **Environment Variables:**
     - `OPENAI_API_KEY`: Your OpenAI API key
     - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
7. Deploy!

**Note:** Render's free tier may sleep after 15 minutes of inactivity. Consider upgrading for 24/7 operation.

### 2. Replit (Great for development)

**Pros:** Online IDE, instant deployment, collaborative features
**Cons:** Limited resources on free tier

#### Steps:

1. Go to [Replit.com](https://replit.com) and sign up
2. Create a new Python Repl
3. Upload your files or clone from GitHub
4. Install dependencies in the Shell:
   ```bash
   pip install -r requirements.txt
   ```
5. Set environment variables in the Secrets tab:
   - `OPENAI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
6. Run the bot using the Run button

### 3. Oracle Cloud (Best for 24/7 hosting)

**Pros:** Always Free tier, 24/7 uptime, full control
**Cons:** More complex setup

#### Detailed Setup:

See `oracle_cloud_setup.md` for complete instructions.

**Quick Setup:**

1. Create Oracle Cloud Free Tier account
2. Launch Always Free Compute Instance
3. SSH into instance and follow Oracle Cloud setup guide
4. Use systemd for automatic startup

### 4. Railway (Alternative to Render)

**Pros:** Easy deployment, good free tier, GitHub integration
**Cons:** Limited free tier hours

#### Steps:

1. Go to [Railway.app](https://railway.app)
2. Connect GitHub account
3. Deploy from repository
4. Add environment variables
5. Deploy!

## 🔧 Environment Variables

All deployment methods require these environment variables:

```bash
OPENAI_API_KEY=your_openai_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```

## 📊 Database Considerations

### SQLite Database

- **File Location:** `mcq_bot.db` in the application directory
- **Persistence:** File-based, survives restarts
- **Backup:** Copy the `.db` file regularly

### For Production (Optional Upgrade)

Consider upgrading to PostgreSQL for better performance:

1. Modify database connection in code
2. Use cloud database services (Railway PostgreSQL, Supabase, etc.)

## 🚀 Features Included

✅ **Multi-user Support:** Each user gets personalized experience  
✅ **Database Storage:** SQLite database for user data and statistics  
✅ **Difficulty Levels:** Easy, Medium, Hard with different AI prompts  
✅ **Statistics Tracking:** Per-user and per-topic performance tracking  
✅ **24/7 Scheduling:** Automatic question delivery every 30 minutes  
✅ **Interactive Commands:** Topic selection, difficulty selection, stats viewing  
✅ **Enhanced AI:** Better explanations and difficulty-based questions

## 📱 Bot Commands

- `/start` - Welcome message and user registration
- `/question` - Get instant MCQ
- `/topics` - Select topic with interactive buttons
- `/difficulty` - Select difficulty level (Easy/Medium/Hard)
- `/stats` - View performance statistics
- `/settings` - View current preferences
- `/help` - Show help message

## 🔄 Updates and Maintenance

### Code Updates

1. Update code in your repository
2. For Render/Railway: Automatic deployment on push
3. For Oracle Cloud: SSH and run `git pull && sudo systemctl restart mcq-bot`

### Database Backup

```bash
# For Oracle Cloud
cp mcq_bot.db backup_$(date +%Y%m%d).db

# For other platforms, download the database file
```

### Monitoring

- Check bot logs regularly
- Monitor API usage (OpenAI tokens)
- Verify scheduled questions are being sent

## 🆘 Troubleshooting

### Common Issues:

1. **Bot not responding:**

   - Check environment variables
   - Verify bot token is correct
   - Check logs for errors

2. **Database errors:**

   - Ensure write permissions
   - Check disk space
   - Verify SQLite installation

3. **Scheduler not working:**

   - Check if the platform supports background processes
   - Verify APScheduler is working
   - Check system time/timezone

4. **OpenAI API errors:**
   - Verify API key is valid
   - Check API quota/billing
   - Monitor rate limits

## 📈 Scaling Considerations

For high user loads:

1. Upgrade to paid hosting plans
2. Consider PostgreSQL database
3. Implement rate limiting
4. Add user management features
5. Consider Redis for session management

## 🔒 Security Notes

- Keep environment variables secure
- Use HTTPS for webhooks (if applicable)
- Regularly update dependencies
- Monitor for suspicious activity
- Backup database regularly

## 📞 Support

For issues or questions:

1. Check the logs first
2. Verify environment variables
3. Test with a simple question manually
4. Check platform-specific documentation
