import os
import sys
import time
import json
from datetime import datetime

def check_prerequisites():
    """Ön koşulları kontrol et"""
    
    # Config kontrolü
    if not os.path.exists('config.json'):
        print("❌ config.json bulunamadı!")
        return False
    
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    if config.get('api_key') == 'YOUR_BINANCE_API_KEY':
        print("❌ API anahtarları ayarlanmamış!")
        print("config.json dosyasını düzenleyin")
        return False
    
    # Bot dosyası kontrolü
    if not os.path.exists('live_trading_bot.py'):
        print("❌ live_trading_bot.py bulunamadı!")
        return False
    
    return True

def show_startup_info():
    """Başlangıç bilgilerini göster"""
    
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    print("🚀 BTC Trading Bot Başlatılıyor")
    print("=" * 50)
    print(f"📅 Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💱 Sembol: {config.get('symbol', 'BTC/USDT')}")
    print(f"⏱️  Zaman Dilimi: {config.get('timeframe', '15m')}")
    print(f"🧪 Test Modu: {'AÇIK' if config.get('sandbox', True) else 'KAPALI'}")
    print(f"💰 Risk/İşlem: %{config.get('risk_per_trade', 0.01)*100}")
    print("=" * 50)
    
    if not config.get('sandbox', True):
        print("🚨 GERÇEK PARA İLE TİCARET MODU!")
        print("⚠️  Bu ayarlardan emin misiniz?")
        
        response = input("Devam etmek için 'EVET' yazın: ")
        if response != 'EVET':
            print("❌ İşlem iptal edildi")
            return False
    
    return True

def start_bot():
    """Bot'u başlat"""
    try:
        print("🔄 Bot başlatılıyor...")
        
        from live_trading_bot import LiveTradingBot
        
        bot = LiveTradingBot()
        
        print("✅ Bot başarıyla oluşturuldu")
        print("🔄 Trading döngüsü başlatılıyor...")
        print("⏹️  Durdurmak için Ctrl+C tuşlayın")
        
        # Bot'u çalıştır
        bot.run(check_interval=60)  # Her dakika kontrol et
        
    except KeyboardInterrupt:
        print("\n⏹️  Bot kullanıcı tarafından durduruldu")
    except Exception as e:
        print(f"\n💥 Bot hatası: {e}")
        print("📋 Hata detayları için trading_bot.log dosyasını kontrol edin")

def main():
    # Ön koşul kontrolü
    if not check_prerequisites():
        return
    
    # Başlangıç bilgilerini göster
    if not show_startup_info():
        return
    
    # Son uyarı
    print("\n🔔 Bot başlatılacak...")
    time.sleep(3)
    
    # Bot'u başlat
    start_bot()

if __name__ == "__main__":
    main()