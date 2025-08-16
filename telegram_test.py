# telegram_test.py - Telegram bot test
import requests
import json

def test_telegram_bot():
    """Telegram bot'u test et"""
    
    # Config'i oku
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except:
        print("❌ config.json bulunamadı!")
        return
    
    bot_token = config.get('telegram_bot_token')
    chat_id = config.get('telegram_chat_id')
    
    print("🧪 Telegram Bot Test")
    print("=" * 30)
    print(f"🤖 Bot Token: {bot_token[:15]}..." if bot_token else "❌ Token yok")
    print(f"💬 Chat ID: {chat_id}" if chat_id else "❌ Chat ID yok")
    
    if not bot_token:
        print("❌ Bot token ayarlanmamış!")
        return
    
    # 1. Bot bilgilerini test et
    print("\n1️⃣ Bot bilgileri test ediliyor...")
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getMe"
        response = requests.get(url)
        result = response.json()
        
        if result['ok']:
            bot_info = result['result']
            print(f"✅ Bot aktif: @{bot_info['username']}")
            print(f"📝 Bot adı: {bot_info['first_name']}")
        else:
            print("❌ Bot token geçersiz!")
            return
    except Exception as e:
        print(f"❌ Bot test hatası: {e}")
        return
    
    # 2. Son mesajları kontrol et
    print("\n2️⃣ Son mesajlar kontrol ediliyor...")
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        response = requests.get(url)
        result = response.json()
        
        if result['ok'] and result['result']:
            print(f"✅ {len(result['result'])} mesaj bulundu")
            
            # Son mesajları göster
            for update in result['result'][-3:]:
                if 'message' in update:
                    msg = update['message']
                    print(f"   💬 {msg['from']['first_name']}: {msg.get('text', 'N/A')}")
        else:
            print("⚠️ Henüz mesaj yok")
    except Exception as e:
        print(f"❌ Mesaj kontrol hatası: {e}")
    
    # 3. Test mesajı gönder
    if chat_id and chat_id != "YOUR_CHAT_ID_HERE":
        print(f"\n3️⃣ Test mesajı gönderiliyor... (Chat ID: {chat_id})")
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': '🧪 Test mesajı!\n\n✅ Bot çalışıyor!\n⏰ ' + str(datetime.now().strftime('%H:%M:%S')),
                'parse_mode': 'HTML'
            }
            response = requests.post(url, json=data)
            result = response.json()
            
            if result['ok']:
                print("✅ Test mesajı gönderildi!")
                print("📱 Telegram'ı kontrol edin")
            else:
                print(f"❌ Mesaj gönderilemedi: {result}")
        except Exception as e:
            print(f"❌ Mesaj gönderme hatası: {e}")
    else:
        print("\n3️⃣ Chat ID ayarlanmamış, test mesajı gönderilemiyor")
    
    print("\n📋 Sonuç:")
    print("✅ Bot token çalışıyor" if bot_token else "❌ Bot token gerekli")
    print("✅ Chat ID var" if chat_id and chat_id != "YOUR_CHAT_ID_HERE" else "❌ Chat ID gerekli")

if __name__ == "__main__":
    from datetime import datetime
    test_telegram_bot()
