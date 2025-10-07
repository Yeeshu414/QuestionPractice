# 🚂 Railway.app Deployment Guide for MP Patwari MCQ Bot

## 🎯 **Why Railway is Perfect for Telegram Bots**

- ✅ **Free webhook support** - No pro features needed
- ✅ **Always-on service** - No cold starts like Vercel
- ✅ **Background tasks** - Scheduled MCQs work perfectly
- ✅ **Persistent storage** - User preferences saved
- ✅ **Simple deployment** - Just connect GitHub repo
- ✅ **Free tier** - $5 credit monthly, perfect for bots

## 📋 **Step-by-Step Deployment**

### **Step 1: Prepare Your Repository**

1. **Ensure all files are committed:**
   ```bash
   git add .
   git commit -m "Ready for Railway deployment"
   git push origin main
   ```

### **Step 2: Deploy to Railway**

1. **Go to [railway.app](https://railway.app)**
2. **Sign up** with your GitHub account
3. **Click "New Project"**
4. **Select "Deploy from GitHub repo"**
5. **Choose your repository:** `Yeeshu414/QuestionPractice`
6. **Railway will automatically detect it's a Python project**

### **Step 3: Set Environment Variables**

In Railway dashboard, go to your project → **Variables** tab and add:

```bash
OPENAI_API_KEY=your_openai_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
YOUR_CHAT_ID=your_telegram_chat_id_here
```

### **Step 4: Deploy**

1. **Click "Deploy"**
2. **Railway will automatically:**
   - Install Python dependencies from `requirements.txt`
   - Run your bot with `python patwari_mcq_bot.py`
   - Keep it running 24/7

### **Step 5: Get Your Bot URL**

After deployment, Railway gives you a URL like:

```
https://your-app-name-production.up.railway.app
```

## 🔧 **Configuration Details**

### **Railway.json Configuration**

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python patwari_mcq_bot.py",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### **Required Files**

- ✅ `patwari_mcq_bot.py` - Main bot file
- ✅ `requirements.txt` - Python dependencies
- ✅ `railway.json` - Railway configuration
- ✅ `.env` - Environment variables (local only)

## 🎮 **Bot Features (All Working on Railway)**

### **Commands**

- `/start` - Welcome message
- `/question` - Get instant MCQ
- `/topics` - Interactive topic selection
- `/help` - Help information

### **Interactive Features**

- 🎯 **Topic Selection** - Click buttons to choose topics
- 🧠 **Quiz Mode** - Answer A/B/C/D, get instant feedback
- 📄 **Auto-save** - All questions saved to file
- ⏰ **Scheduled Questions** - Every 30 minutes (if enabled)

### **Topics Available**

1. General Science
2. General Hindi
3. General English
4. Basic Mathematics
5. General Knowledge
6. Computer Knowledge
7. Reasoning Ability
8. General Management with MP GK

## 🚀 **Advantages Over Vercel**

| Feature          | Railway     | Vercel        |
| ---------------- | ----------- | ------------- |
| Webhooks         | ✅ Free     | ❌ Pro only   |
| Always-on        | ✅ Yes      | ❌ Serverless |
| Background tasks | ✅ Yes      | ❌ Limited    |
| Cold starts      | ❌ None     | ❌ Yes        |
| Free tier        | ✅ $5/month | ✅ Limited    |
| Bot support      | ✅ Perfect  | ❌ Complex    |

## 🔍 **Monitoring & Logs**

### **View Logs**

1. Go to Railway dashboard
2. Click your project
3. Go to **Deployments** tab
4. Click on latest deployment
5. View **Logs** tab

### **Common Log Messages**

```
🤖 Bot is running...
OpenAI client initialized successfully
Bot initialized with 8 topics
```

## 🛠 **Troubleshooting**

### **Bot Not Responding**

1. Check Railway logs for errors
2. Verify environment variables are set
3. Ensure Telegram bot token is correct

### **Environment Variables Not Working**

1. Go to Railway → Variables tab
2. Add each variable manually
3. Redeploy the project

### **Dependencies Issues**

1. Check `requirements.txt` is complete
2. Railway auto-installs from requirements.txt
3. Check logs for import errors

## 📱 **Testing Your Bot**

1. **Find your bot** on Telegram: `@your_bot_username`
2. **Send `/start`** - Should get welcome message
3. **Send `/question`** - Should get MCQ
4. **Click `/topics`** - Should show topic buttons
5. **Test interactive quiz** - Reply A/B/C/D

## 💰 **Pricing**

### **Free Tier**

- $5 credit monthly
- Perfect for small bots
- 512MB RAM
- 1GB storage

### **Pro Tier** (if needed later)

- $5/month per service
- More resources
- Custom domains

## 🎉 **Success!**

Once deployed, your bot will:

- ✅ Run 24/7 on Railway
- ✅ Respond to all Telegram commands
- ✅ Generate MCQs using OpenAI
- ✅ Save questions automatically
- ✅ Support interactive features

## 📞 **Support**

- **Railway Docs:** [docs.railway.app](https://docs.railway.app)
- **Railway Discord:** [discord.gg/railway](https://discord.gg/railway)
- **GitHub Issues:** Create issue in your repo

---

**🎯 Your MP Patwari MCQ Bot is now ready to help students prepare for their exams!**
