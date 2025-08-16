import subprocess
import sys
import os
import json

def install_requirements():
    """Gerekli kütüphaneleri yükle"""
    print("🔄 Gerekli kütüphaneler yükleniyor...")
    
    requirements = [
        "pandas==2.0.3",
        "numpy==1.24.3", 
        "ccxt==4.0.77",
        "requests==2.31.0",
        "matplotlib==3.7.1"
    ]
    
    for package in requirements:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ {package} yüklendi")
        except subprocess.CalledProcessError:
            print(f"❌ {package} yüklenemedi")

def install_talib():
    """TA-Lib kurulumu"""
    print("🔄 TA-Lib yükleniyor...")
    
    try:
        import talib
        print("✅ TA-Lib zaten yüklü")
        return True
    except ImportError:
        pass
    
    print("TA-Lib bulunamadı. Yükleme talimatları:")
    
    if os.name == 'nt':  # Windows
        print("""
Windows için TA-Lib kurulumu:
1. https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib adresinden
2. Python versiyonunuza uygun .whl dosyasını indirin
3. Komut satırında: pip install dosya_adi.whl
        """)
    else:  # Mac/Linux
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "TA-Lib"])
            print("✅ TA-Lib yüklendi")
        except:
            print("❌ TA-Lib otomatik yüklenemedi. Manuel kurulum gerekli.")
    
    return False

def create_config():
    """Config dosyası oluştur"""
    config = {
        "api_key": "YOUR_BINANCE_API_KEY",
        "secret": "YOUR_BINANCE_SECRET", 
        "sandbox": True,
        "symbol": "BTC/USDT",
        "timeframe": "15m",
        "donchian_period": 20,
        "ema_period": 200,
        "risk_per_trade": 0.01,
        "max_position_size": 0.05,
        "max_daily_trades": 3,
        "telegram_bot_token": "",
        "telegram_chat_id": ""
    }
    
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)
    
    print("✅ config.json oluşturuldu")
    print("⚠️  config.json dosyasını düzenleyip API anahtarlarınızı girin!")

def main():
    print("🚀 BTC Trading Bot Kurulumu")
    print("=" * 40)
    
    # Python versiyonu kontrol
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ gerekli")
        return
    
    print(f"✅ Python {sys.version} kullanılıyor")
    
    # Pip güncelle
    print("🔄 pip güncelleniyor...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    
    # Requirements yükle
    install_requirements()
    
    # TA-Lib yükle
    install_talib()
    
    # Config oluştur
    create_config()
    
    print("\n🎉 Kurulum tamamlandı!")
    print("📝 Sonraki adımlar:")
    print("1. config.json dosyasını düzenleyin")
    print("2. python test_run.py ile test edin")
    print("3. python start_bot.py ile başlatın")

if __name__ == "__main__":
    main()