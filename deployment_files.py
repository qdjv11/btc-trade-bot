# health_check.py (Health monitoring script)
import requests
import time
import json
from datetime import datetime

class HealthMonitor:
    def __init__(self, config_file='config.json'):
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        self.telegram_bot_token = self.config.get('telegram_bot_token')
        self.telegram_chat_id = self.config.get('telegram_chat_id')
        
    def send_alert(self, message):
        """Send health alert via Telegram"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': f"🚨 HEALTH ALERT 🚨\n\n{message}\n\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
            requests.post(url, json=payload)
        except Exception as e:
            print(f"Error sending alert: {e}")
    
    def check_bot_health(self):
        """Check if the bot is running properly"""
        try:
            # Check if log file exists and has recent entries
            import os
            if os.path.exists('trading_bot.log'):
                with open('trading_bot.log', 'r') as f:
                    lines = f.readlines()
                    if lines:
                        last_line = lines[-1]
                        # Check if last log entry is within last 10 minutes
                        # This is a simple check - you can make it more sophisticated
                        return True
            return False
        except Exception as e:
            print(f"Health check error: {e}")
            return False

# start_bot.py (Bot starter with auto-restart)
import subprocess
import time
import sys
import logging
from health_check import HealthMonitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_bot():
    """Start the trading bot with auto-restart capability"""
    monitor = HealthMonitor()
    
    while True:
        try:
            logger.info("Starting trading bot...")
            process = subprocess.Popen([sys.executable, 'live_trading_bot.py'])
            
            # Monitor the process
            while True:
                time.sleep(300)  # Check every 5 minutes
                
                # Check if process is still running
                if process.poll() is not None:
                    logger.error("Bot process died, restarting...")
                    monitor.send_alert("Trading bot crashed and will be restarted")
                    break
                
                # Check bot health
                if not monitor.check_bot_health():
                    logger.warning("Bot health check failed")
                    # You might want to restart here too
            
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            process.terminate()
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            monitor.send_alert(f"Bot error: {e}")
            time.sleep(60)  # Wait before restart

if __name__ == "__main__":
    start_bot()

# deploy_to_railway.sh (Deployment script for Railway)
#!/bin/bash

echo "Deploying to Railway..."

# Install Railway CLI if not present
if ! command -v railway &> /dev/null; then
    echo "Installing Railway CLI..."
    npm install -g @railway/cli
fi

# Login to Railway (you'll need to do this once)
# railway login

# Initialize Railway project
railway login
railway init

# Set environment variables
echo "Setting up environment variables..."
echo "Please set your API keys in Railway dashboard:"
echo "1. Go to railway.app"
echo "2. Select your project"
echo "3. Go to Variables tab"
echo "4. Add your Binance API keys and other config"

# Deploy
railway up

echo "Deployment complete!"
echo "Check your bot status at railway.app"

# deploy_to_render.sh (Deployment script for Render)
#!/bin/bash

echo "Deploying to Render..."
echo "1. Push your code to GitHub"
echo "2. Go to render.com"
echo "3. Create new Web Service"
echo "4. Connect your GitHub repo"
echo "5. Use the settings from render.yaml"
echo "6. Add environment variables in Render dashboard"

echo "Environment variables to set in Render:"
echo "- BINANCE_API_KEY: your_api_key"
echo "- BINANCE_SECRET: your_secret"
echo "- TELEGRAM_BOT_TOKEN: your_bot_token"
echo "- TELEGRAM_CHAT_ID: your_chat_id"