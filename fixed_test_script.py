# fixed_test.py - Düzeltilmiş test scripti
import json
import os
import sys

def check_config():
    """Config dosyasını kontrol et"""
    print("🔍 Config dosyası kontrol ediliyor...")
    
    if not os.path.exists('config.json'):
        print("❌ config.json bulunamadı")
        return False
    
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    if config.get('api_key') == 'YOUR_BINANCE_API_KEY':
        print("⚠️  API anahtarı ayarlanmamış")
        return False
    
    if not config.get('telegram_bot_token'):
        print("⚠️  Telegram bot token ayarlanmamış")
        return False
    
    print("✅ Config dosyası OK")
    return True

def test_imports():
    """Gerekli modülleri test et"""
    print("🔍 Modüller test ediliyor...")
    
    modules = [
        'pandas', 'numpy', 'ccxt', 'requests', 'asyncio'
    ]
    
    for module in modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError:
            print(f"❌ {module} bulunamadı")
            return False
    
    # TA-Lib özel kontrol
    try:
        import talib
        print("✅ talib")
    except ImportError:
        print("❌ talib bulunamadı - TA-Lib kurulumu gerekli")
        return False
    
    # Telegram bot
    try:
        import telegram
        print("✅ python-telegram-bot")
    except ImportError:
        print("❌ python-telegram-bot bulunamadı")
        return False
    
    return True

def test_exchange_connection():
    """Exchange bağlantısını test et"""
    print("🔍 Exchange bağlantısı test ediliyor...")
    
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
        
        # Test API call
        ticker = exchange.fetch_ticker('BTC/USDT')
        print(f"✅ Binance bağlantısı OK - BTC Fiyat: ${ticker['last']}")
        return True
        
    except Exception as e:
        print(f"❌ Exchange bağlantı hatası: {e}")
        return False

def test_telegram_bot():
    """Telegram bot test et"""
    print("🔍 Telegram bot test ediliyor...")
    
    try:
        import asyncio
        from telegram import Bot
        
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        async def test_bot():
            bot = Bot(token=config['telegram_bot_token'])
            bot_info = await bot.get_me()
            return bot_info
        
        bot_info = asyncio.run(test_bot())
        print(f"✅ Telegram bot OK - @{bot_info.username}")
        return True
        
    except Exception as e:
        print(f"❌ Telegram bot hatası: {e}")
        return False

def run_dry_test():
    """Kuru çalışma testi"""
    print("🔍 Bot kuru çalışma testi...")
    
    try:
        # Import the correct file name
        from telegram_trading_bot import TelegramTradingBot
        
        bot = TelegramTradingBot()
        
        # Veri çekme testi
        df = bot.fetch_recent_data(limit=100)
        if df is not None and len(df) > 50:
            print("✅ Veri çekme OK")
        else:
            print("❌ Veri çekme problemi")
            return False
        
        # İndikatör hesaplama testi
        df_with_indicators = bot.calculate_indicators(df)
        if df_with_indicators is not None:
            print("✅ İndikatör hesaplama OK")
        else:
            print("❌ İndikatör hesaplama problemi")
            return False
        
        print("✅ Bot kuru testi başarılı")
        return True
        
    except Exception as e:
        print(f"❌ Bot test hatası: {e}")
        return False

def main():
    print("🧪 Telegram Trading Bot Test Süreci")
    print("=" * 40)
    
    tests = [
        ("Config Kontrolü", check_config),
        ("Modül Kontrolü", test_imports),
        ("Exchange Bağlantısı", test_exchange_connection),
        ("Telegram Bot", test_telegram_bot),
        ("Bot Kuru Testi", run_dry_test)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 {test_name}")
        if test_func():
            passed += 1
        else:
            print(f"💥 {test_name} başarısız!")
    
    print(f"\n📊 Test Sonucu: {passed}/{total}")
    
    if passed == total:
        print("🎉 Tüm testler başarılı! Bot çalıştırılabilir.")
        print("▶️  python telegram_trading_bot.py ile başlatın")
    else:
        print("⚠️  Bazı testler başarısız. Sorunları çözün ve tekrar deneyin.")

if __name__ == "__main__":
    main()
