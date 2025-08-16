# debug_config.py - Config dosyasını debug et
import json
import requests

def debug_config():
    """Config dosyasını detaylı kontrol et"""
    
    print("🔍 Config Debug")
    print("=" * 30)
    
    # 1. Config dosyasını oku
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        print("✅ config.json başarıyla okundu")
    except Exception as e:
        print(f"❌ config.json okuma hatası: {e}")
        return
    
    # 2. Her değeri kontrol et
    print("\n📋 Config İçeriği:")
    for key, value in config.items():
        if 'secret' in key.lower() or 'token' in key.lower():
            print(f"   {key}: {str(value)[:10]}... (gizli)")
        else:
            print(f"   {key}: {value}")
    
    # 3. Kritik değerleri kontrol et
    bot_token = config.get('telegram_bot_token')
    chat_id = config.get('telegram_chat_id')
    
    print(f"\n🔍 Detaylı Kontrol:")
    print(f"   Bot Token: {bot_token[:15]}..." if bot_token else "❌ Bot Token YOK")
    print(f"   Chat ID: '{chat_id}' (tip: {type(chat_id)})")
    print(f"   Chat ID uzunluk: {len(str(chat_id)) if chat_id else 0}")
    
    # 4. Chat ID formatını kontrol et
    if chat_id:
        chat_id_str = str(chat_id).strip()
        print(f"   Chat ID (string): '{chat_id_str}'")
        print(f"   Chat ID boş mu: {chat_id_str == ''}")
        print(f"   Chat ID sayı mı: {chat_id_str.isdigit() or (chat_id_str.startswith('-') and chat_id_str[1:].isdigit())}")
    
    # 5. Telegram bot test
    if bot_token and chat_id:
        print(f"\n🧪 Telegram Bot Test:")
        
        # Bot bilgilerini al
        try:
            url = f"https://api.telegram.org/bot{bot_token}/getMe"
            response = requests.get(url)
            result = response.json()
            
            if result['ok']:
                bot_info = result['result']
                print(f"✅ Bot aktif: @{bot_info['username']}")
            else:
                print(f"❌ Bot token hatası: {result}")
                return
        except Exception as e:
            print(f"❌ Bot test hatası: {e}")
            return
        
        # Test mesajı gönder
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                'chat_id': str(chat_id).strip(),
                'text': '🧪 Config test mesajı!\n\n✅ Config doğru çalışıyor!'
            }
            
            response = requests.post(url, json=data)
            result = response.json()
            
            if result['ok']:
                print("✅ Test mesajı gönderildi!")
                print("📱 Telegram'ı kontrol edin")
            else:
                print(f"❌ Mesaj gönderme hatası: {result}")
                
                # Yaygın hataları kontrol et
                if result.get('error_code') == 400:
                    if 'chat not found' in result.get('description', '').lower():
                        print("💡 Çözüm: Telegram'da bota /start mesajı gönderin")
                    elif 'chat_id is empty' in result.get('description', '').lower():
                        print("💡 Çözüm: Chat ID formatını kontrol edin")
                elif result.get('error_code') == 403:
                    print("💡 Çözüm: Bot'u engellemişsiniz, Telegram'da engelini kaldırın")
                
        except Exception as e:
            print(f"❌ Test mesajı hatası: {e}")
    
    else:
        print("\n❌ Bot token veya Chat ID eksik!")

def fix_config():
    """Config dosyasını düzelt"""
    print("\n🔧 Config Düzeltme")
    print("=" * 20)
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except:
        print("❌ config.json okunamadı")
        return
    
    # Chat ID'yi düzelt
    current_chat_id = config.get('telegram_chat_id')
    print(f"Mevcut Chat ID: '{current_chat_id}'")
    
    if current_chat_id and str(current_chat_id).strip():
        # Chat ID var, sadece format düzelt
        chat_id_fixed = str(current_chat_id).strip()
        config['telegram_chat_id'] = chat_id_fixed
        
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
        
        print(f"✅ Chat ID düzeltildi: '{chat_id_fixed}'")
    else:
        print("❌ Chat ID boş, manuel olarak ayarlamanız gerekiyor")
        print("Çözüm: python get_chat_id_simple.py")

if __name__ == "__main__":
    debug_config()
    
    choice = input("\nConfig'i otomatik düzeltmeyi deneyelim mi? (e/h): ")
    if choice.lower() == 'e':
        fix_config()
        print("\n🔄 Düzeltme sonrası tekrar test:")
        debug_config()
