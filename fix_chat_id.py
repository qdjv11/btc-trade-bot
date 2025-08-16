# fix_chat_id.py - Chat ID problemini çöz
import json
import requests
def fix_chat_id_problem():
    """Chat ID problemini teşhis et ve çöz"""
    
    print("🔧 Chat ID Problemi Çözüm Aracı")
    print("=" * 40)
    
    # 1. Config'i oku
    try:
        with open('config.json', 'r') as f:
            content = f.read()
        print("✅ Config dosyası okundu")
        print(f"📄 Ham içerik:\n{content[:200]}...")
    except Exception as e:
        print(f"❌ Config okuma hatası: {e}")
        return
    
    # 2. JSON parse et
    try:
        config = json.loads(content)
        print("✅ JSON parse başarılı")
    except Exception as e:
        print(f"❌ JSON parse hatası: {e}")
        return
    
    # 3. Chat ID'yi incele
    chat_id_raw = config.get('telegram_chat_id')
    print(f"\n🔍 Chat ID İnceleme:")
    print(f"   Raw değer: {repr(chat_id_raw)}")
    print(f"   Tip: {type(chat_id_raw)}")
    print(f"   Değer: '{chat_id_raw}'")
    
    if chat_id_raw is None:
        print("   ❌ Chat ID None!")
    elif chat_id_raw == "":
        print("   ❌ Chat ID boş string!")
    elif str(chat_id_raw).strip() == "":
        print("   ❌ Chat ID sadece boşluk!")
    else:
        print(f"   ✅ Chat ID değeri var: '{chat_id_raw}'")
    
    # 4. Doğru formatta yeniden yaz
    print(f"\n🔧 Config Düzeltme:")
    
    # Chat ID'yi doğru formatta ayarla
    config['telegram_chat_id'] = "5508768640"
    
    # Config'i yeniden yaz
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    print("✅ Config dosyası yeniden yazıldı")
    
    # 5. Tekrar kontrol et
    with open('config.json', 'r') as f:
        new_config = json.load(f)
    
    new_chat_id = new_config.get('telegram_chat_id')
    print(f"✅ Yeni Chat ID: '{new_chat_id}' (tip: {type(new_chat_id)})")
    
    # 6. Test et
    print(f"\n🧪 Test:")
    if new_chat_id and str(new_chat_id).strip():
        print("✅ Chat ID artık doğru!")
        
        # Hemen test mesajı gönder
        import requests
        
        bot_token = new_config.get('telegram_bot_token')
        if bot_token:
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                data = {
                    'chat_id': str(new_chat_id).strip(),
                    'text': '🎉 Chat ID sorunu çözüldü!\n\n✅ Artık bot mesajları alabilirsiniz!'
                }
                
                response = requests.post(url, json=data)
                result = response.json()
                
                if result['ok']:
                    print("🎉 Test mesajı başarıyla gönderildi!")
                    print("📱 Telegram'ı kontrol edin")
                    return True
                else:
                    print(f"❌ Test mesajı hatası: {result}")
            except Exception as e:
                print(f"❌ Test hatası: {e}")
    
    print("❌ Chat ID hala problematik")
    return False

def get_chat_id_from_telegram():
    """Telegram'dan Chat ID al"""
    print("\n📱 Telegram'dan Chat ID Alma")
    print("=" * 30)
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except:
        print("❌ Config okunamadı")
        return
    
    bot_token = config.get('telegram_bot_token')
    if not bot_token:
        print("❌ Bot token yok")
        return
    
    print("1. Telegram'da bota /start mesajı gönderin")
    print("2. Bu scriptte ENTER'a basın")
    input("⏳ Mesaj gönderdiniz mi? ENTER'a basın...")
    
    try:
        # Son mesajları al
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        response = requests.get(url)
        result = response.json()
        
        if result['ok'] and result['result']:
            print("✅ Mesajlar bulundu!")
            
            for update in result['result'][-5:]:
                if 'message' in update:
                    msg = update['message']
                    chat_id = msg['chat']['id']
                    username = msg['from'].get('first_name', 'Bilinmiyor')
                    text = msg.get('text', '')
                    
                    print(f"   💬 {username}: {text}")
                    print(f"   📊 Chat ID: {chat_id}")
                    print("-" * 20)
            
            # Son chat ID'yi al
            last_update = result['result'][-1]
            if 'message' in last_update:
                new_chat_id = last_update['message']['chat']['id']
                
                choice = input(f"\nBu Chat ID'yi ({new_chat_id}) kullanmak ister misiniz? (e/h): ")
                if choice.lower() == 'e':
                    config['telegram_chat_id'] = str(new_chat_id)
                    
                    with open('config.json', 'w') as f:
                        json.dump(config, f, indent=4)
                    
                    print("✅ Chat ID kaydedildi!")
                    return True
        else:
            print("❌ Mesaj bulunamadı. Telegram'da bota mesaj gönderdiniz mi?")
    
    except Exception as e:
        print(f"❌ Hata: {e}")
    
    return False

if __name__ == "__main__":
    # Önce mevcut problemi çöz
    if fix_chat_id_problem():
        print("\n🎉 Problem çözüldü! Bot'u başlatabilirsiniz.")
    else:
        print("\n🔄 Chat ID'yi Telegram'dan alarak tekrar deneyelim...")
        if get_chat_id_from_telegram():
            print("\n🎉 Chat ID başarıyla alındı!")
            fix_chat_id_problem()  # Tekrar test et
        else:
            print("\n❌ Chat ID alınamadı. Manuel müdahale gerekli.")
            print("\nÇözüm adımları:")
            print("1. Telegram'da @Enis_1Bot'a /start gönderin")
            print("2. Bu scripti tekrar çalıştırın")
