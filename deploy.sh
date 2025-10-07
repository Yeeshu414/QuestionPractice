#!/bin/bash

# MP Patwari MCQ Bot Deployment Script

echo "🚀 MP Patwari MCQ Bot Deployment Helper"
echo "======================================"

echo ""
echo "📋 Before deploying, make sure you have:"
echo "   ✅ OpenAI API Key"
echo "   ✅ Telegram Bot Token (from @BotFather)"
echo "   ✅ Your Chat ID (use /start command)"
echo ""

echo "🌐 Choose your deployment platform:"
echo "1) Railway (Recommended - Free)"
echo "2) Render (Free tier available)"
echo "3) Heroku (Requires credit card)"
echo "4) Show deployment files"
echo ""

read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        echo ""
        echo "🚂 Railway Deployment Steps:"
        echo "1. Go to https://railway.app"
        echo "2. Sign up with GitHub"
        echo "3. Click 'New Project' → 'Deploy from GitHub repo'"
        echo "4. Select your repository"
        echo "5. Set these environment variables:"
        echo "   - OPENAI_API_KEY"
        echo "   - TELEGRAM_BOT_TOKEN" 
        echo "   - YOUR_CHAT_ID"
        echo "6. Deploy!"
        ;;
    2)
        echo ""
        echo "🎨 Render Deployment Steps:"
        echo "1. Go to https://render.com"
        echo "2. Connect your GitHub repository"
        echo "3. Create new Web Service"
        echo "4. Set environment variables in dashboard"
        echo "5. Deploy!"
        ;;
    3)
        echo ""
        echo "🟣 Heroku Deployment Steps:"
        echo "1. Install Heroku CLI"
        echo "2. Run: heroku create your-bot-name"
        echo "3. Set environment variables:"
        echo "   heroku config:set OPENAI_API_KEY=your_key"
        echo "   heroku config:set TELEGRAM_BOT_TOKEN=your_token"
        echo "   heroku config:set YOUR_CHAT_ID=your_id"
        echo "4. Run: git push heroku main"
        ;;
    4)
        echo ""
        echo "📁 Deployment files created:"
        echo "✅ Procfile - Tells platform how to run your app"
        echo "✅ runtime.txt - Python version specification"
        echo "✅ requirements.txt - Python dependencies"
        echo "✅ .gitignore - Excludes sensitive files"
        echo "✅ env_template.txt - Environment variables template"
        echo "✅ README.md - Complete deployment guide"
        ;;
    *)
        echo "Invalid choice. Please run the script again."
        ;;
esac

echo ""
echo "📖 For detailed instructions, see README.md"
echo "🔧 Need help? Check the deployment guide in README.md"
