# simple_test.py - Basit test scripti
import json
import os

def test_config():
    """Config dosyasını test et"""
    print("🔍 Config kontrolü...")
    
    if not os.path.exists('config.json'):
        print("❌ config.json bulunamadı")
        return False
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        print("✅ Config dosyası okundu")
        print(f"   API Key: {config.get('api_key', 'YOK')[:10]}...")
        print(f"   Sandbox: {config.get('sandbox', 'YOK')}")
        print(f"   Symbol: {config.get('symbol', 'YOK')}")
        print(f"   Telegram Token: {'VAR' if config.get('telegram_bot_token') else 'YOK'}")
        
        return True
    except Exception as e:
        print(f"❌ Config okuma hatası: {e}")
        return False

def test_basic_imports():
    """Temel paketleri test et"""
    print("\n🔍 Temel paket kontrolü...")
    
    basic_modules = ['json', 'os', 'sys', 'time', 'datetime']
    
    for module in basic_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError:
            print(f"❌ {module}")
            return False
    
    return True

def test_advanced_imports():
    """Gelişmiş paketleri test et"""
    print("\n🔍 Gelişmiş paket kontrolü...")
    
    modules = {
        'pandas': 'pandas',
        'numpy': 'numpy', 
        'ccxt': 'ccxt',
        'requests': 'requests'
    }
    
    results = {}
    for name, module in modules.items():
        try:
            __import__(module)
            print(f"✅ {name}")
            results[name] = True
        except ImportError:
            print(f"❌ {name} - pip install {module}")
            results[name] = False
    
    return results

def test_special_imports():
    """Özel paketleri test et"""
    print("\n🔍 Özel paket kontrolü...")
    
    # TA-Lib
    try:
        import talib
        print("✅ TA-Lib")
        talib_ok = True
    except ImportError:
        print("❌ TA-Lib - Özel kurulum gerekli")
        print("   Windows: https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib")
        talib_ok = False
    
    # Telegram Bot
    try:
        import telegram
        print("✅ python-telegram-bot")
        telegram_ok = True
    except ImportError:
        print("❌ python-telegram-bot - pip install python-telegram-bot")
        telegram_ok = False
    
    return {'talib': talib_ok, 'telegram': telegram_ok}

def test_exchange_connection():
    """Exchange bağlantısını test et"""
    print("\n🔍 Exchange bağlantısı...")
    
    try:
        import ccxt
        
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        exchange = ccxt.binance({
            'apiKey': config['api_key'],
            'secret': config['secret'],
            'sandbox': config.get('sandbox', True),
            'enableRateLimit': True
        })
        
        # Basit test
        ticker = exchange.fetch_ticker('BTC/USDT')
        print(f"✅ Binance bağlantısı OK")
        print(f"   BTC Fiyat: ${ticker['last']:,.2f}")
        print(f"   Sandbox Modu: {config.get('sandbox', 'Bilinmiyor')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Exchange bağlantı hatası: {e}")
        return False

def test_telegram_bot():
    """Telegram bot test et"""
    print("\n🔍 Telegram bot test...")
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        bot_token = config.get('telegram_bot_token')
        if not bot_token:
            print("❌ Telegram bot token yok")
            return False
        
        # Basit token format kontrolü
        if ':' in bot_token and len(bot_token) > 40:
            print("✅ Telegram bot token formatı OK")
        else:
            print("❌ Telegram bot token formatı hatalı")
            return False
        
        # Chat ID kontrolü
        chat_id = config.get('telegram_chat_id')
        if chat_id and chat_id != 'YOUR_CHAT_ID_HERE':
            print(f"✅ Chat ID ayarlanmış: {chat_id}")
        else:
            print("⚠️  Chat ID ayarlanmamış - get_chat_id.py çalıştırın")
        
        return True
        
    except Exception as e:
        print(f"❌ Telegram test hatası: {e}")
        return False

def show_next_steps(results):
    """Sonraki adımları göster"""
    print("\n" + "="*50)
    print("📋 SONRAKI ADIMLAR")
    print("="*50)
    
    if not results['basic']:
        print("❌ Temel Python paketleri eksik - Python kurulumunu kontrol edin")
        return
    
    if not all(results['advanced'].values()):
        print("📦 Eksik paketleri yükleyin:")
        for package, status in results['advanced'].items():
            if not status:
                print(f"   pip install {package}")
    
    if not results['special']['talib']:
        print("\n🔧 TA-Lib kurulumu:")
        print("   1. https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib")
        print("   2. Python versiyonunuza uygun .whl dosyası indirin")
        print("   3. pip install dosya_adi.whl")
    
    if not results['special']['telegram']:
        print("\n📱 Telegram bot kurulumu:")
        print("   pip install python-telegram-bot")
    
    if results['exchange']:
        print("\n✅ Exchange bağlantısı çalışıyor")
    else:
        print("\n❌ Exchange bağlantısını düzeltin")
    
    if not results.get('telegram', False):
        print("\n📞 Chat ID almak için:")
        print("   1. Telegram'da botunuza /start gönderin")
        print("   2. python get_chat_id.py çalıştırın")
    
    # Genel durum
    all_ok = (results['basic'] and 
              all(results['advanced'].values()) and 
              all(results['special'].values()) and 
              results['exchange'])
    
    if all_ok:
        print("\n🎉 HER ŞEY HAZIR!")
        print("   python telegram_trading_bot.py ile başlatabilirsiniz")
    else:
        print("\n⚠️  Yukarıdaki sorunları çözün ve tekrar test edin")

def main():
    print("🧪 BTC TRADING BOT - BASIT TEST")
    print("=" * 40)
    
    results = {
        'basic': test_basic_imports(),
        'config': test_config(),
        'advanced': test_advanced_imports(),
        'special': test_special_imports(),
        'exchange': False,
        'telegram': False
    }
    
    if results['config'] and all(results['advanced'].values()):
        results['exchange'] = test_exchange_connection()
    
    if results['special']['telegram']:
        results['telegram'] = test_telegram_bot()
    
    show_next_steps(results)

if __name__ == "__main__":
    main()
