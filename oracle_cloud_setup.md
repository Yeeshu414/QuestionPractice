# Oracle Cloud Deployment Guide

## Prerequisites

1. Oracle Cloud Free Tier account
2. Compute Instance (Always Free eligible)

## Setup Steps

### 1. Create Compute Instance

1. Go to Oracle Cloud Console
2. Navigate to Compute > Instances
3. Create Instance with:
   - Image: Oracle Linux 8
   - Shape: VM.Standard.E2.1.Micro (Always Free)
   - Networking: Public subnet
   - SSH Key: Generate or upload your key

### 2. Connect to Instance

```bash
ssh -i your-key.pem opc@your-instance-ip
```

### 3. Install Dependencies

```bash
# Update system
sudo dnf update -y

# Install Python 3.11
sudo dnf install python3.11 python3.11-pip -y

# Install git
sudo dnf install git -y
```

### 4. Deploy Application

```bash
# Clone your repository
git clone https://github.com/yourusername/mp-patwari-mcq-bot.git
cd mp-patwari-mcq-bot

# Install Python dependencies
python3.11 -m pip install -r requirements.txt

# Create environment file
nano .env
```

### 5. Environment Variables

Create `.env` file with:

```
OPENAI_API_KEY=your_openai_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

### 6. Run with Systemd Service

Create service file:

```bash
sudo nano /etc/systemd/system/mcq-bot.service
```

Content:

```ini
[Unit]
Description=MP Patwari MCQ Bot
After=network.target

[Service]
Type=simple
User=opc
WorkingDirectory=/home/opc/mp-patwari-mcq-bot
Environment=PATH=/usr/bin:/usr/local/bin
ExecStart=/usr/bin/python3.11 patwari_mcq_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 7. Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable mcq-bot.service

# Start service
sudo systemctl start mcq-bot.service

# Check status
sudo systemctl status mcq-bot.service
```

### 8. Firewall Configuration

```bash
# Allow SSH (if not already allowed)
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload
```

### 9. Monitoring

```bash
# View logs
sudo journalctl -u mcq-bot.service -f

# Restart service
sudo systemctl restart mcq-bot.service
```

## Database Persistence

The SQLite database will be stored in the application directory and will persist across reboots.

## Backup

```bash
# Create backup script
nano backup.sh
```

Content:

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
cp /home/opc/mp-patwari-mcq-bot/mcq_bot.db /home/opc/backups/mcq_bot_$DATE.db
```

## Updates

To update the application:

```bash
cd /home/opc/mp-patwari-mcq-bot
git pull
sudo systemctl restart mcq-bot.service
```
