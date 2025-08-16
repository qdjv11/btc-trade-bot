# railway_deploy.py - Railway deployment script
import os
import json
import subprocess
import sys

def create_railway_files():
    """Railway için gerekli dosyaları oluştur"""
    
    # 1. requirements.txt
    requirements = """pandas==2.0.3
numpy==1.24.3
ccxt==4.0.77
TA-Lib==0.4.28
python-telegram-bot==20.7
requests==2.31.0
asyncio"""
    
    with open('requirements.txt', 'w') as f:
        f.write(requirements)
    print("✅ requirements.txt oluşturuldu")
    
    # 2. Procfile (Railway için)
    procfile = "web: python original_strategy_telegram_bot.py"
    
    with open('Procfile', 'w') as f:
        f.write(procfile)
    print("✅ Procfile oluşturuldu")
    
    # 3. railway.toml
    railway_config = """[build]
builder = "nixpacks"

[deploy]
startCommand = "python original_strategy_telegram_bot.py"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10

[[services]]
name = "btc-trading-bot"
"""
    
    with open('railway.toml', 'w') as f:
        f.write(railway_config)
    print("✅ railway.toml oluşturuldu")
    
    # 4. nixpacks.toml (TA-Lib için)
    nixpacks_config = """[providers]
python = "3.11"

[phases.setup]
cmds = [
    "apt-get update",
    "apt-get install -y wget build-essential",
    "wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz",
    "tar -xzf ta-lib-0.4.0-src.tar.gz",
    "cd ta-lib && ./configure --prefix=/usr && make && make install"
]

[phases.install]
cmds = ["pip install -r requirements.txt"]

[start]
cmd = "python original_strategy_telegram_bot.py"
"""
    
    with open('nixpacks.toml', 'w') as f:
        f.write(nixpacks_config)
    print("✅ nixpacks.toml oluşturuldu")

def setup_git():
    """Git repository ayarla"""
    print("\n📂 Git repository kuruluyor...")
    
    try:
        # Git init
        subprocess.run(['git', 'init'], check=True)
        
        # .gitignore oluştur
        gitignore = """__pycache__/
*.pyc
*.db
*.log
trading_settings.json
.env
"""
        with open('.gitignore', 'w') as f:
            f.write(gitignore)
        
        # Dosyaları ekle
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit - BTC Trading Bot'], check=True)
        
        print("✅ Git repository hazır")
        return True
        
    except subprocess.CalledProcessError:
        print("❌ Git kurulu değil veya hata oluştu")
        return False

def create_env_template():
    """Environment variables template oluştur"""
    env_template = """# Railway Environment Variables
# Bu değerleri Railway dashboard'da ayarlayın

BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET=your_secret_here
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
SANDBOX=true
"""
    
    with open('.env.example', 'w') as f:
        f.write(env_template)
    print("✅ .env.example oluşturuldu")

def update_config_for_deployment():
    """Config'i environment variables kullanacak şekilde güncelle"""
    
    config_code = '''# config_loader.py - Environment variables desteği
import os
import json

def load_config():
    """Config'i environment variables veya dosyadan yükle"""
    
    # Railway'de environment variables kullan
    if os.getenv('RAILWAY_ENVIRONMENT'):
        return {
            "api_key": os.getenv('BINANCE_API_KEY'),
            "secret": os.getenv('BINANCE_SECRET'),
            "sandbox": os.getenv('SANDBOX', 'true').lower() == 'true',
            "symbol": "BTC/USDT",
            "timeframe": "15m",
            "donchian_period": 20,
            "ema_period": 200,
            "telegram_bot_token": os.getenv('TELEGRAM_BOT_TOKEN'),
            "telegram_chat_id": os.getenv('TELEGRAM_CHAT_ID')
        }
    
    # Local'de config.json kullan
    else:
        try:
            with open('config.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("❌ config.json bulunamadı ve environment variables ayarlanmamış!")
            return None

# Bot dosyasının başında bu import'u ekleyin:
# from config_loader import load_config
# self.config = load_config()
'''
    
    with open('config_loader.py', 'w') as f:
        f.write(config_code)
    print("✅ config_loader.py oluşturuldu")

def main():
    print("🚀 RAILWAY DEPLOYMENT HAZIRLIĞI")
    print("=" * 50)
    
    # 1. Railway dosyalarını oluştur
    create_railway_files()
    
    # 2. Environment variables template
    create_env_template()
    
    # 3. Config loader
    update_config_for_deployment()
    
    # 4. Git setup
    git_ready = setup_git()
    
    print("\n✅ Railway deployment dosyaları hazır!")
    print("\n📋 SONRAKI ADIMLAR:")
    print("=" * 30)
    print("1. https://railway.app adresine gidin")
    print("2. GitHub ile giriş yapın")
    print("3. 'New Project' → 'Deploy from GitHub repo'")
    print("4. Bu repository'yi seçin")
    print("5. Environment Variables ekleyin:")
    print("   - BINANCE_API_KEY")
    print("   - BINANCE_SECRET") 
    print("   - TELEGRAM_BOT_TOKEN")
    print("   - TELEGRAM_CHAT_ID")
    print("   - SANDBOX=true")
    print("6. Deploy edin!")
    
    if not git_ready:
        print("\n⚠️  Git kurulumu gerekli:")
        print("   - Git'i yükleyin: https://git-scm.com/")
        print("   - Bu scripti tekrar çalıştırın")

if __name__ == "__main__":
    main()

# render_deploy.py - Render deployment alternatifi
def create_render_files():
    """Render için deployment dosyaları"""
    
    # render.yaml
    render_config = """services:
  - type: web
    name: btc-trading-bot
    env: python
    region: oregon
    plan: free
    buildCommand: |
      apt-get update && apt-get install -y wget build-essential
      wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
      tar -xzf ta-lib-0.4.0-src.tar.gz
      cd ta-lib/
      ./configure --prefix=/usr
      make && make install
      cd ..
      rm -rf ta-lib ta-lib-0.4.0-src.tar.gz
      pip install -r requirements.txt
    startCommand: python original_strategy_telegram_bot.py
    envVars:
      - key: BINANCE_API_KEY
        value: your_api_key
      - key: BINANCE_SECRET
        value: your_secret
      - key: TELEGRAM_BOT_TOKEN
        value: your_bot_token
      - key: TELEGRAM_CHAT_ID
        value: your_chat_id
      - key: SANDBOX
        value: "true"
"""
    
    with open('render.yaml', 'w') as f:
        f.write(render_config)
    print("✅ render.yaml oluşturuldu")

# vps_setup.py - VPS kurulum scripti
def create_vps_setup():
    """VPS için kurulum scripti"""
    
    vps_script = """#!/bin/bash
# vps_setup.sh - VPS kurulum scripti

echo "🚀 BTC Trading Bot VPS Kurulumu"
echo "================================"

# System update
sudo apt update && sudo apt upgrade -y

# Python ve pip
sudo apt install -y python3 python3-pip git wget build-essential

# TA-Lib kurulumu
cd /tmp
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
cd ~

# Bot klasörü oluştur
mkdir -p ~/btc-trading-bot
cd ~/btc-trading-bot

# Python paketleri
pip3 install pandas numpy ccxt TA-Lib python-telegram-bot requests

# Systemd service oluştur
sudo tee /etc/systemd/system/btc-bot.service > /dev/null <<EOF
[Unit]
Description=BTC Trading Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/btc-trading-bot
ExecStart=/usr/bin/python3 original_strategy_telegram_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Service'i etkinleştir
sudo systemctl daemon-reload
sudo systemctl enable btc-bot

echo "✅ VPS kurulumu tamamlandı!"
echo "📋 Sonraki adımlar:"
echo "1. Bot dosyalarını kopyalayın"
echo "2. config.json dosyasını düzenleyin"
echo "3. sudo systemctl start btc-bot"
echo "4. sudo systemctl status btc-bot"
"""
    
    with open('vps_setup.sh', 'w') as f:
        f.write(vps_script)
    
    # Executable yap
    os.chmod('vps_setup.sh', 0o755)
    print("✅ vps_setup.sh oluşturuldu")

if __name__ == "__main__":
    # Railway deployment hazırlığı
    main()
    
    print("\n" + "="*50)
    print("🎯 ALTERNATIF SEÇENEKLER:")
    print("="*50)
    
    choice = input("Render.com dosyalarını da oluşturmak ister misiniz? (e/h): ")
    if choice.lower() == 'e':
        create_render_files()
    
    choice = input("VPS kurulum scriptini oluşturmak ister misiniz? (e/h): ")
    if choice.lower() == 'e':
        create_vps_setup()
    
    print("\n🎉 Tüm deployment dosyaları hazır!")
