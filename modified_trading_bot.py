import pandas as pd
import numpy as np
import ccxt
import talib
import time
import logging
import json
import sqlite3
from datetime import datetime, timedelta
import os
import threading

# Basit requests ile telegram
import requests

class SimpleTelegramBot:
    def __init__(self, config_file='config.json'):
        # Load configuration
        self.config = self.load_config(config_file)
        
        # Initialize exchange
        self.exchange = self.setup_exchange()
        
        # Strategy parameters (ORIGINAL SETTINGS)
        self.symbol = self.config.get('symbol', 'BTC/USDT')
        self.timeframe = self.config.get('timeframe', '15m')
        self.donchian_period = self.config.get('donchian_period', 20)
        self.ema_period = self.config.get('ema_period', 200)
        
        # Trading parameters (will be set by user)
        self.trading_capital = 10000
        self.leverage = 1
        self.trading_mode = 'both'
        self.exchange_type = 'spot'
        
        # ORIGINAL RISK MANAGEMENT
        self.balance = 10000
        self.risk_per_trade = 0.02
        
        # Trading state
        self.position = None
        self.position_size = 0
        self.entry_price = 0
        self.stop_loss = 0
        self.take_profit = 0
        self.trades = []
        self.current_market_trend = None
        
        # Bot state
        self.bot_running = False
        self.bot_configured = True
        
        # Setup state
        self.setup_data = {}
        self.waiting_for_input = None  # 'leverage' veya 'capital'
        
        # Price alerts
        self.price_alerts_enabled = True
        self.last_hourly_report = None
        self.last_update_id = 0
        
        # Telegram setup
        self.bot_token = self.config['telegram_bot_token']
        self.chat_id = self.config['telegram_chat_id']
        
        # Database setup
        self.db_path = 'trading_bot.db'
        self.setup_database()
        
        # Logging setup
        self.setup_logging()
        
        self.logger.info("Simple Telegram Bot initialized")

    def load_config(self, config_file):
        with open(config_file, 'r') as f:
            return json.load(f)

    def setup_exchange(self):
        try:
            exchange = ccxt.binance({
                'apiKey': self.config['api_key'],
                'secret': self.config['secret'],
                'sandbox': self.config.get('sandbox', True),
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })
            
            # Test connection
            balance = exchange.fetch_balance()
            print(f"✅ Binance bağlantısı OK - USDT: {balance['USDT']['free']}")
            return exchange
            
        except Exception as e:
            print(f"❌ Exchange bağlantı hatası: {e}")
            return None

    def setup_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                side TEXT,
                amount REAL,
                price REAL,
                stop_loss REAL,
                take_profit REAL,
                profit REAL,
                status TEXT,
                exit_reason TEXT,
                balance_after REAL,
                market_trend TEXT
            )
        ''')
        
        conn.commit()
        conn.close()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('trading_bot.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def send_telegram_message(self, message, reply_markup=None):
        """Basit HTTP ile mesaj gönder"""
        try:
            # Chat ID kontrolü
            if not self.chat_id or str(self.chat_id).strip() == '':
                print(f"❌ Chat ID boş: '{self.chat_id}'")
                print("Config.json'da telegram_chat_id ayarlı mı kontrol edin")
                return False
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            data = {
                'chat_id': str(self.chat_id).strip(),
                'text': message,
                'parse_mode': 'HTML'
            }
            
            if reply_markup:
                data['reply_markup'] = json.dumps(reply_markup)
            
            response = requests.post(url, json=data)
            result = response.json()
            
            if result['ok']:
                print(f"✅ Mesaj gönderildi (Chat ID: {self.chat_id})")
                return True
            else:
                print(f"❌ Telegram mesaj hatası: {result}")
                return False
                
        except Exception as e:
            print(f"❌ Telegram gönderme hatası: {e}")
            return False

    def get_telegram_updates(self):
        """Telegram güncellemelerini al"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {'offset': self.last_update_id + 1}
            
            response = requests.get(url, params=params)
            result = response.json()
            
            if result['ok']:
                return result['result']
            else:
                return []
                
        except Exception as e:
            self.logger.error(f"Telegram güncelleme hatası: {e}")
            return []

    def create_keyboard(self, buttons):
        """Keyboard oluştur"""
        return {
            'inline_keyboard': buttons
        }

    def process_telegram_command(self, message):
        """Telegram komutlarını işle"""
        text = message.get('text', '').strip()
        chat_id = message['chat']['id']
        
        # Chat ID kontrolü
        if str(chat_id) != str(self.chat_id):
            return
        
        # Kullanıcı input bekliyorsak
        if self.waiting_for_input:
            if self.waiting_for_input == 'leverage':
                self.process_leverage_input(text)
                return
            elif self.waiting_for_input == 'capital':
                self.process_capital_input(text)
                return
        
        # Normal komutlar
        text_lower = text.lower()
        if text == '/start' or text_lower == 'start':
            self.send_start_menu()
        elif text == '/status' or text_lower == 'status':
            self.send_status()
        elif text == '/price' or text_lower == 'price':
            self.send_current_price()
        elif text == '/report' or text_lower == 'report':
            self.send_hourly_report()
        elif text == '/trading start' or text_lower == 'trading start':
            self.start_trading()
        elif text == '/trading stop' or text_lower == 'trading stop':
            self.stop_trading()
        elif text.startswith('/'):
            self.send_help()

    def process_leverage_input(self, text):
        """Leverage input işle"""
        try:
            leverage = float(text)
            if leverage < 1 or leverage > 125:
                self.send_telegram_message("❌ Leverage 1x ile 125x arasında olmalıdır. Lütfen tekrar deneyin:")
                return
            
            self.setup_data['leverage'] = leverage
            self.waiting_for_input = None
            self.send_trading_setup_step3_capital('futures', leverage)
            
        except ValueError:
            self.send_telegram_message("❌ Geçersiz leverage değeri. Lütfen sadece sayı girin (örnek: 10):")

    def process_capital_input(self, text):
        """Capital input işle"""
        try:
            capital = float(text)
            if capital <= 0:
                self.send_telegram_message("❌ Sermaye 0'dan büyük olmalıdır. Lütfen tekrar deneyin:")
                return
            
            self.setup_data['capital'] = capital
            self.waiting_for_input = None
            self.send_trading_setup_step4_mode(
                self.setup_data['exchange_type'],
                self.setup_data['leverage'],
                capital
            )
            
        except ValueError:
            self.send_telegram_message("❌ Geçersiz sermaye miktarı. Lütfen sadece sayı girin (örnek: 1000):")

    def apply_settings_and_start(self):
        """Ayarları uygula ve trading'i başlat"""
        try:
            # Ayarları uygula
            self.exchange_type = self.setup_data['exchange_type']
            self.leverage = self.setup_data['leverage']
            self.trading_capital = self.setup_data['capital']
            self.balance = self.trading_capital
            
            # Trading mode çevir
            mode_map = {
                'long_only': 'long',
                'short_only': 'short',
                'both': 'both'
            }
            self.trading_mode = mode_map[self.setup_data['trading_mode']]
            
            # Exchange'i yeniden ayarla
            if self.exchange_type == 'futures':
                try:
                    self.exchange = ccxt.binance({
                        'apiKey': self.config['api_key'],
                        'secret': self.config['secret'],
                        'sandbox': self.config.get('sandbox', True),
                        'enableRateLimit': True,
                        'options': {'defaultType': 'future'}
                    })
                    print(f"✅ Futures exchange ayarlandı")
                except Exception as e:
                    print(f"❌ Futures exchange ayarlanamadı: {e}")
                    self.send_telegram_message("❌ Futures exchange ayarlanamadı! Spot modunda devam edilecek.")
                    self.exchange_type = 'spot'
            
            # Trading'i başlat
            self.bot_running = True
            threading.Thread(target=self.trading_loop, daemon=True).start()
            
            exchange_text = "Spot" if self.exchange_type == 'spot' else f"Futures ({self.leverage}x)"
            mode_map_display = {
                'long': '📈 Sadece Long',
                'short': '📉 Sadece Short',
                'both': '📈📉 İki Yönlü'
            }
            
            message = f"""
🚀 <b>Trading Başlatıldı!</b>

✅ Bot orijinal Donchian+EMA+MACD stratejisi ile çalışıyor

📊 <b>Ayarlarınız:</b>
💱 Exchange: {exchange_text}
💰 Sermaye: ${self.trading_capital:,}
📊 Mod: {mode_map_display[self.trading_mode]}
⚖️ Risk: %2 per trade

📈 <b>Strateji Detayları:</b>
• Donchian Channel breakout
• EMA200 trend filtresi
• MACD konfirmasyonu
• Stop Loss: 2x ATR
• Take Profit: 4x ATR

🔄 Bot her dakika piyasayı analiz edecek
📱 Tüm işlemler size bildirilecek

⏰ Başlatma: {datetime.now().strftime('%H:%M:%S')}
            """
            
            keyboard = self.create_keyboard([
                [
                    {'text': '⏹️ Trading Durdur', 'callback_data': 'stop_trading'},
                    {'text': '📊 Bot Durumu', 'callback_data': 'show_status'}
                ]
            ])
            
            self.send_telegram_message(message, keyboard)
            
            # Setup data'yı temizle
            self.setup_data = {}
            
        except Exception as e:
            self.send_telegram_message(f"❌ Trading başlatma hatası: {e}")
            print(f"Trading başlatma hatası: {e}")

    def process_telegram_callback(self, callback_query):
        """Callback query işle"""
        data = callback_query.get('data', '')
        chat_id = callback_query['message']['chat']['id']
        
        # Chat ID kontrolü
        if str(chat_id) != str(self.chat_id):
            return
        
        # Ana komutlar
        if data == 'current_price':
            self.send_current_price()
        elif data == 'hourly_report':
            self.send_hourly_report()
        elif data == 'show_status':
            self.send_status()
        elif data == 'start_trading':
            self.start_trading()
        elif data == 'stop_trading':
            self.stop_trading()
        
        # Setup adımları
        elif data == 'setup_spot':
            self.setup_data = {'exchange_type': 'spot', 'leverage': 1}
            self.send_trading_setup_step3_capital('spot', 1)
        elif data == 'setup_futures':
            self.setup_data = {'exchange_type': 'futures'}
            self.send_trading_setup_step2_leverage()
        
        # Trading modu seçimi
        elif data.startswith('mode_'):
            trading_mode = data.split('_', 1)[1]  # 'long_only', 'short_only', 'both'
            self.setup_data['trading_mode'] = trading_mode
            self.send_trading_setup_confirm(
                self.setup_data['exchange_type'],
                self.setup_data['leverage'],
                self.setup_data['capital'],
                trading_mode
            )
        
        # Final onay
        elif data == 'confirm_and_start':
            self.apply_settings_and_start()
        elif data == 'restart_setup':
            self.send_trading_setup_step1()
        
        # Geri butonları
        elif data == 'back_to_menu':
            self.send_start_menu()
        elif data == 'back_step1':
            self.send_trading_setup_step1()
        elif data == 'back_step2':
            if self.setup_data.get('exchange_type') == 'futures':
                self.send_trading_setup_step2_leverage()
            else:
                self.send_trading_setup_step1()
        elif data == 'back_step3':
            self.send_trading_setup_step3_capital(
                self.setup_data['exchange_type'],
                self.setup_data['leverage']
            )

    def send_start_menu(self):
        """Ana menüyü gönder"""
        keyboard = self.create_keyboard([
            [
                {'text': '💵 Anlık Fiyat', 'callback_data': 'current_price'},
                {'text': '📈 Saatlik Rapor', 'callback_data': 'hourly_report'}
            ],
            [
                {'text': '📊 Bot Durumu', 'callback_data': 'show_status'},
                {'text': '🚀 Trading Başlat' if not self.bot_running else '⏹️ Trading Durdur', 
                 'callback_data': 'start_trading' if not self.bot_running else 'stop_trading'}
            ]
        ])
        
        message = f"""
🤖 <b>BTC Trading Bot</b>
<i>Orijinal Donchian + EMA + MACD Stratejisi</i>

📊 <b>Durum:</b>
• Bot: {'🟢 Çalışıyor' if self.bot_running else '🔴 Durdu'}
• Exchange: {'✅ Bağlı' if self.exchange else '❌ Bağlantı Yok'}
• Pozisyon: {self.position or '❌ Yok'}

💰 <b>Sermaye:</b> ${self.balance:,.2f}
⚖️ <b>Risk:</b> %2 per trade

📈 <b>Strateji:</b> Donchian Channel + EMA200 + MACD

🎮 <b>Komutlar:</b>
• /price - Anlık fiyat
• /report - Saatlik rapor  
• /status - Bot durumu
• /trading start - Trading başlat
• /trading stop - Trading durdur
        """
        
        self.send_telegram_message(message, keyboard)

    def send_current_price(self):
        """Anlık fiyat gönder"""
        try:
            if not self.exchange:
                self.send_telegram_message("❌ Exchange bağlantısı yok!")
                return
            
            ticker = self.exchange.fetch_ticker(self.symbol)
            
            price_change = ticker['change']
            price_change_pct = ticker['percentage']
            
            trend_emoji = "📈" if price_change > 0 else "📉" if price_change < 0 else "➡️"
            color_emoji = "🟢" if price_change > 0 else "🔴" if price_change < 0 else "🟡"
            
            volume_24h = ticker['quoteVolume']
            volume_text = f"{volume_24h/1_000_000:.1f}M" if volume_24h > 1_000_000 else f"{volume_24h/1_000:.1f}K"
            
            message = f"""
💵 <b>Anlık BTC Fiyatı</b>

{trend_emoji} <b>${ticker['last']:,.2f}</b>

📊 <b>24 Saatlik Değişim:</b>
{color_emoji} ${price_change:+,.2f} ({price_change_pct:+.2f}%)

📈 <b>En Yüksek:</b> ${ticker['high']:,.2f}
📉 <b>En Düşük:</b> ${ticker['low']:,.2f}

🔄 <b>Hacim (24s):</b> {volume_text} USDT

⏰ <b>Güncelleme:</b> {datetime.now().strftime('%H:%M:%S')}
            """
            
            keyboard = self.create_keyboard([
                [
                    {'text': '🔄 Yenile', 'callback_data': 'current_price'},
                    {'text': '📈 Saatlik Rapor', 'callback_data': 'hourly_report'}
                ]
            ])
            
            self.send_telegram_message(message, keyboard)
            
        except Exception as e:
            self.send_telegram_message(f"❌ Fiyat alınamadı: {e}")

    def send_hourly_report(self):
        """Saatlik rapor gönder"""
        try:
            if not self.exchange:
                self.send_telegram_message("❌ Exchange bağlantısı yok!")
                return
            
            ticker = self.exchange.fetch_ticker(self.symbol)
            current_price = ticker['last']
            
            ohlcv_24h = self.exchange.fetch_ohlcv(self.symbol, '1h', limit=24)
            df_24h = pd.DataFrame(ohlcv_24h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            last_hour = df_24h.iloc[-1]
            prev_hour = df_24h.iloc[-2] if len(df_24h) > 1 else last_hour
            
            hourly_change = last_hour['close'] - prev_hour['close']
            hourly_change_pct = (hourly_change / prev_hour['close']) * 100
            
            if len(df_24h) >= 4:
                recent_prices = df_24h.tail(4)['close'].tolist()
                trend = self.analyze_trend(recent_prices)
            else:
                trend = "Yetersiz veri"
            
            trend_emoji = "📈" if hourly_change > 0 else "📉" if hourly_change < 0 else "➡️"
            
            # Pozisyon detayları
            position_info = ""
            if self.position and self.entry_price > 0:
                if self.position == 'long':
                    unrealized_pnl = (current_price - self.entry_price) * self.position_size
                else:
                    unrealized_pnl = (self.entry_price - current_price) * self.position_size
                
                risk_amount = self.balance * self.risk_per_trade
                pnl_percentage = (unrealized_pnl / risk_amount) * 100
                
                sl_distance_pct = (abs(current_price - self.stop_loss) / current_price) * 100
                tp_distance_pct = (abs(self.take_profit - current_price) / current_price) * 100
                
                pos_emoji = "📈" if self.position == 'long' else "📉"
                pnl_emoji = "🟢" if unrealized_pnl > 0 else "🔴" if unrealized_pnl < 0 else "🟡"
                
                position_info = f"""

💼 <b>AÇIK POZİSYON:</b>
{pos_emoji} <b>Yön:</b> {self.position.upper()}
💰 <b>Giriş:</b> ${self.entry_price:,.2f}
📊 <b>Miktar:</b> {self.position_size:.6f} BTC

🎯 <b>Seviyeler:</b>
🛑 SL: ${self.stop_loss:,.2f} (🔻{sl_distance_pct:.1f}%)
🏆 TP: ${self.take_profit:,.2f} (🔺{tp_distance_pct:.1f}%)

💰 <b>Anlık P&L:</b>
{pnl_emoji} <b>${unrealized_pnl:+,.2f}</b> ({pnl_percentage:+.1f}%)
📊 Risk Oranı: {abs(pnl_percentage/100):.1f}R
"""
            else:
                position_info = "\n💼 <b>POZİSYON:</b> ❌ Açık pozisyon yok"
            
            message = f"""
📈 <b>Saatlik BTC Raporu</b>

{trend_emoji} <b>Fiyat:</b> ${current_price:,.2f}

⏰ <b>Son 1 Saat:</b>
{trend_emoji} ${hourly_change:+,.2f} ({hourly_change_pct:+.2f}%)

📊 <b>24 Saat Özeti:</b>
📈 En Yüksek: ${df_24h['high'].max():,.2f}
📉 En Düşük: ${df_24h['low'].min():,.2f}
📊 Ortalama: ${df_24h['close'].mean():,.2f}

🎯 <b>Trend (4h):</b> {trend}{position_info}

🤖 <b>Bot Durumu:</b>
• Trading: {'🟢 Aktif' if self.bot_running else '🔴 Pasif'}
• Strateji: Donchian+EMA+MACD
• Bakiye: ${self.balance:,.2f}

⏰ <b>Rapor Zamanı:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}
            """
            
            keyboard = self.create_keyboard([
                [
                    {'text': '🔄 Yenile', 'callback_data': 'hourly_report'},
                    {'text': '💵 Anlık Fiyat', 'callback_data': 'current_price'}
                ]
            ])
            
            self.send_telegram_message(message, keyboard)
            
        except Exception as e:
            self.send_telegram_message(f"❌ Saatlik rapor hatası: {e}")

    def send_status(self):
        """Bot durumunu gönder"""
        try:
            if self.exchange:
                balance = self.exchange.fetch_balance()
                usdt_balance = balance['USDT']['free']
                
                df = self.fetch_recent_data(limit=10)
                current_price = df.iloc[-1]['close'] if df is not None else "N/A"
            else:
                current_price = "N/A"
                usdt_balance = 0
            
            total_trades = len(self.trades)
            profitable_trades = len([t for t in self.trades if t.get('profit', 0) > 0])
            
            message = f"""
📊 <b>Bot Durumu Detayı</b>

🤖 <b>Bot:</b> {'🟢 Çalışıyor' if self.bot_running else '🔴 Durdu'}
💱 <b>Exchange:</b> {'✅ Bağlı' if self.exchange else '❌ Bağlantı Yok'}
💰 <b>Fiyat:</b> ${current_price}
💵 <b>Bakiye:</b> {usdt_balance:.2f} USDT

📈 <b>Pozisyon:</b> {self.position or 'Yok'}
{f'💰 Giriş: ${self.entry_price:.2f}' if self.position else ''}
{f'🛑 SL: ${self.stop_loss:.2f}' if self.position else ''}
{f'🎯 TP: ${self.take_profit:.2f}' if self.position else ''}

📊 <b>İstatistikler:</b>
🔢 Toplam İşlem: {total_trades}
✅ Karlı İşlem: {profitable_trades}
📈 Başarı Oranı: {(profitable_trades/total_trades*100) if total_trades > 0 else 0:.1f}%

📊 <b>Strateji:</b>
• Donchian Period: {self.donchian_period}
• EMA Period: {self.ema_period}
• Risk/İşlem: %{self.risk_per_trade*100}

⏰ <b>Son Güncelleme:</b> {datetime.now().strftime('%H:%M:%S')}
            """
            
            keyboard = self.create_keyboard([
                [
                    {'text': '🔄 Yenile', 'callback_data': 'show_status'},
                    {'text': '🚀 Trading Başlat' if not self.bot_running else '⏹️ Trading Durdur', 
                     'callback_data': 'start_trading' if not self.bot_running else 'stop_trading'}
                ]
            ])
            
            self.send_telegram_message(message, keyboard)
            
        except Exception as e:
            self.send_telegram_message(f"❌ Durum alınamadı: {e}")

    def start_trading(self):
        """Trading başlat - Etkileşimli setup"""
        if self.bot_running:
            self.send_telegram_message("⚠️ Bot zaten çalışıyor!")
            return
        
        if not self.exchange:
            self.send_telegram_message("❌ Exchange bağlantısı yok!")
            return
        
        # Etkileşimli setup başlat
        self.send_trading_setup_step1()

    def send_trading_setup_step1(self):
        """Step 1: Exchange tipi seç"""
        keyboard = self.create_keyboard([
            [
                {'text': '💰 Spot Trading', 'callback_data': 'setup_spot'},
                {'text': '⚡ Futures Trading', 'callback_data': 'setup_futures'}
            ],
            [
                {'text': '🔙 Ana Menü', 'callback_data': 'back_to_menu'}
            ]
        ])
        
        message = """
⚙️ <b>Trading Setup - Adım 1/4</b>

<b>Exchange tipini seçin:</b>

💰 <b>Spot Trading:</b>
• Daha güvenli
• Leverage yok
• Sadece sahip olduğunuz para ile

⚡ <b>Futures Trading:</b>
• Leverage kullanımı
• Daha riskli ama yüksek potansiyel
• Short pozisyon alabilme

Hangi tipte trading yapmak istiyorsunuz?
        """
        
        self.send_telegram_message(message, keyboard)

    def send_trading_setup_step2_leverage(self):
        """Step 2: Leverage değeri gir (manuel)"""
        keyboard = self.create_keyboard([
            [
                {'text': '🔙 Geri', 'callback_data': 'back_step1'}
            ]
        ])
        
        self.waiting_for_input = 'leverage'
        
        message = """
⚙️ <b>Trading Setup - Adım 2/4</b>

<b>Leverage oranını yazın:</b>

⚠️ <b>Risk Uyarısı:</b>
• 1x-5x: Düşük risk
• 5x-10x: Orta risk  
• 10x-25x: Yüksek risk
• 25x+: Çok yüksek risk

💡 <b>Strateji:</b> Her işlemde sermayenin %2'si risk alınır (sabit)

<b>Lütfen leverage değerini yazın (örnek: 10):</b>
Minimum: 1x, Maksimum: 125x
        """
        
        self.send_telegram_message(message, keyboard)

    def send_trading_setup_step3_capital(self, exchange_type, leverage=1):
        """Step 3: Sermaye miktarı gir (manuel)"""
        keyboard = self.create_keyboard([
            [
                {'text': '🔙 Geri', 'callback_data': 'back_step2' if exchange_type == 'futures' else 'back_step1'}
            ]
        ])
        
        self.waiting_for_input = 'capital'
        
        exchange_text = "Spot" if exchange_type == 'spot' else f"Futures ({leverage}x)"
        
        message = f"""
⚙️ <b>Trading Setup - Adım {3 if exchange_type == 'spot' else 3}/4</b>

<b>Ne kadar sermaye ile başlayacaksınız?</b>

📊 <b>Seçiminiz:</b> {exchange_text}

⚖️ <b>Risk Yönetimi:</b>
• Her işlemde sermayenin %2'si risk alınır
• ATR bazlı stop loss (2x ATR)
• Take profit: 4x ATR (2:1 risk/reward)

<b>Lütfen sermaye miktarını yazın (örnek: 1000):</b>
Not: Sadece sayı yazın, $ işareti koymayın
        """
        
        self.send_telegram_message(message, keyboard)

    def send_trading_setup_step4_mode(self, exchange_type, leverage, capital):
        """Step 4: Trading modu seç"""
        keyboard = self.create_keyboard([
            [
                {'text': '📈 Sadece Long', 'callback_data': 'mode_long_only'}
            ],
            [
                {'text': '📉 Sadece Short', 'callback_data': 'mode_short_only'}
            ],
            [
                {'text': '📈📉 İki Yönlü', 'callback_data': 'mode_both'}
            ],
            [
                {'text': '🔙 Geri', 'callback_data': 'back_step3'}
            ]
        ])
        
        exchange_text = "Spot" if exchange_type == 'spot' else f"Futures ({leverage}x)"
        
        message = f"""
⚙️ <b>Trading Setup - Adım 4/4</b>

<b>Hangi yönde işlem yapmak istiyorsunuz?</b>

📊 <b>Ayarlarınız:</b>
• Exchange: {exchange_text}
• Sermaye: ${capital:,}

📈 <b>Sadece Long:</b>
• Sadece yükseliş bekler
• Daha güvenli (genel trend yukarı)

📉 <b>Sadece Short:</b>
• Sadece düşüş bekler
• Daha riskli

📈📉 <b>İki Yönlü:</b>
• Her iki yönde işlem
• Daha fazla fırsat

💡 <b>Önerilen:</b> Yeni başlayanlar için "Sadece Long"
        """
        
        self.send_telegram_message(message, keyboard)

    def send_trading_setup_confirm(self, exchange_type, leverage, capital, trading_mode):
        """Final: Ayarları onayla"""
        keyboard = self.create_keyboard([
            [
                {'text': '✅ Ayarları Onayla ve Başlat', 'callback_data': 'confirm_and_start'}
            ],
            [
                {'text': '🔄 Ayarları Değiştir', 'callback_data': 'restart_setup'}
            ]
        ])
        
        exchange_text = "Spot" if exchange_type == 'spot' else f"Futures ({leverage}x)"
        mode_map = {
            'long_only': '📈 Sadece Long',
            'short_only': '📉 Sadece Short', 
            'both': '📈📉 İki Yönlü'
        }
        
        message = f"""
📋 <b>Trading Ayarları Özeti</b>

<b>Seçimlerinizi kontrol edin:</b>

💱 <b>Exchange:</b> {exchange_text}
💰 <b>Sermaye:</b> ${capital:,}
📊 <b>Trading Modu:</b> {mode_map[trading_mode]}
⚖️ <b>Risk/İşlem:</b> %2 (sabit)

📈 <b>Strateji Detayları:</b>
• Donchian Channel breakout + EMA200 + MACD
• Stop Loss: 2x ATR
• Take Profit: 4x ATR
• Risk/Reward: 1:2

⚠️ <b>Bu ayarlarla trading başlatılacak!</b>
        """
        
        self.send_telegram_message(message, keyboard)

    def stop_trading(self):
        """Trading durdur"""
        self.bot_running = False
        self.send_telegram_message("⏹️ Trading durduruldu!")

    def send_help(self):
        """Yardım mesajı gönder"""
        message = """
🤖 <b>BTC Trading Bot Komutları</b>

📱 <b>Temel Komutlar:</b>
• /start - Ana menü
• /price - Anlık BTC fiyatı
• /report - Saatlik detaylı rapor
• /status - Bot durumu

🎮 <b>Trading Komutları:</b>
• /trading start - Trading başlat
• /trading stop - Trading durdur

📊 <b>Strateji:</b> Donchian + EMA200 + MACD
⚖️ <b>Risk:</b> %2 per trade
        """
        
        self.send_telegram_message(message)

    def analyze_trend(self, prices):
        """Trend analizi"""
        if len(prices) < 3:
            return "Yetersiz veri"
        
        recent = prices[-3:]
        if all(recent[i] < recent[i+1] for i in range(len(recent)-1)):
            return "🚀 Güçlü Yükseliş"
        elif all(recent[i] > recent[i+1] for i in range(len(recent)-1)):
            return "📉 Güçlü Düşüş"
        elif prices[-1] > prices[0]:
            return "📈 Yukarı Trend"
        elif prices[-1] < prices[0]:
            return "📉 Aşağı Trend"
        else:
            return "➡️ Yatay Seyir"

    # ORIGINAL STRATEGY METHODS (aynı)
    def fetch_recent_data(self, limit=500):
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            self.logger.error(f"Error fetching data: {e}")
            return None

    def calculate_indicators(self, df):
        try:
            df['ema200'] = talib.EMA(df['close'], timeperiod=self.ema_period)
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            df['upper_band'] = df['high'].rolling(window=self.donchian_period).max()
            df['lower_band'] = df['low'].rolling(window=self.donchian_period).min()
            df['middle_band'] = (df['upper_band'] + df['lower_band']) / 2
            df['band_distance'] = df['upper_band'] - df['lower_band']
            df['band_distance_vs_atr'] = df['band_distance'] / (df['atr'] * 4)
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(
                df['close'], fastperiod=12, slowperiod=26, signalperiod=9
            )
            df.dropna(inplace=True)
            return df
        except Exception as e:
            self.logger.error(f"Error calculating indicators: {e}")
            return None

    def check_entry_conditions(self, df):
        if len(df) < 2:
            return {'long': False, 'short': False, 'market_trend': 'unknown'}
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        above_ema = (current['close'] > current['ema200'] and current['open'] > current['ema200'])
        below_ema = (current['close'] < current['ema200'] and current['open'] < current['ema200'])
        
        donchian_long = current['high'] >= current['upper_band']
        donchian_short = current['low'] <= current['lower_band']
        
        long_candle_condition = ((prev['high'] - prev['close']) < ((prev['close'] - prev['open']) / 2) or 
                                (prev['high'] - prev['close']) < 3)
        short_candle_condition = ((prev['close'] - prev['low']) < ((prev['open'] - prev['close']) / 2) or 
                                 (prev['close'] - prev['low']) < 3)
        
        macd_long = current['macd'] > 100 and current['macd_hist'] > 0
        macd_short = current['macd'] < -100 and current['macd_hist'] < 0
        
        donchian_band_placement = True
        if above_ema and current['upper_band'] < current['ema200']:
            donchian_band_placement = False
        if below_ema and current['lower_band'] > current['ema200']:
            donchian_band_placement = False
        
        sufficient_band_distance = current['band_distance_vs_atr'] > 1.0
        
        long_signal = (above_ema and donchian_long and long_candle_condition and 
                      macd_long and donchian_band_placement and sufficient_band_distance)
        
        short_signal = (below_ema and donchian_short and short_candle_condition and 
                       macd_short and donchian_band_placement and sufficient_band_distance)
        
        if self.trading_mode == 'long':
            short_signal = False
        elif self.trading_mode == 'short':
            long_signal = False
        
        market_trend = 'up' if above_ema else 'down'
        
        return {'long': long_signal, 'short': short_signal, 'market_trend': market_trend}

    def check_exit_conditions(self, df):
        if not self.position or len(df) < 2:
            return None, None
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        if self.position == 'long':
            if current['low'] <= self.stop_loss:
                return 'stop_loss', self.stop_loss
            elif current['high'] >= self.take_profit:
                return 'take_profit', self.take_profit
            elif current['atr'] > prev['atr'] * 1.5 and current['close'] < prev['close']:
                return 'cvd_exit', current['close']
        
        elif self.position == 'short':
            if current['high'] >= self.stop_loss:
                return 'stop_loss', self.stop_loss
            elif current['low'] <= self.take_profit:
                return 'take_profit', self.take_profit
            elif current['atr'] > prev['atr'] * 1.5 and current['close'] > prev['close']:
                return 'cvd_exit', current['close']
        
        return None, None

    def calculate_position_size(self, entry_price, stop_loss_price):
        try:
            risk_amount = self.balance * self.risk_per_trade
            stop_distance = abs(entry_price - stop_loss_price)
            position_size = risk_amount / stop_distance
            return position_size
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0

    def enter_position(self, side, df):
        try:
            current = df.iloc[-1]
            
            atr_value = current['atr']
            if side == 'buy':
                stop_loss = current['close'] - (atr_value * 2)
                take_profit = current['close'] + (atr_value * 4)
                position_type = 'long'
            else:
                stop_loss = current['close'] + (atr_value * 2)
                take_profit = current['close'] - (atr_value * 4)
                position_type = 'short'
            
            position_size = self.calculate_position_size(current['close'], stop_loss)
            
            if position_size <= 0:
                return False
            
            self.position = position_type
            self.position_size = position_size
            self.entry_price = current['close']
            self.stop_loss = stop_loss
            self.take_profit = take_profit
            
            message = f"""
🚀 <b>POZİSYON AÇILDI!</b>

📈 <b>Yön:</b> {position_type.upper()}
💰 <b>Fiyat:</b> ${self.entry_price:,.2f}
📊 <b>Miktar:</b> {position_size:.6f} BTC

🎯 <b>Seviyeler:</b>
🛑 Stop Loss: ${self.stop_loss:,.2f}
🏆 Take Profit: ${self.take_profit:,.2f}

📊 <b>Risk:</b> ${self.balance * self.risk_per_trade:.2f} (%2)
📈 <b>Trend:</b> {self.current_market_trend}

⏰ {datetime.now().strftime('%H:%M:%S')}
            """
            
            self.send_telegram_message(message)
            return True
            
        except Exception as e:
            self.logger.error(f"Error entering position: {e}")
            return False

    def exit_position(self, exit_reason, exit_price=None):
        try:
            if not self.position:
                return False
            
            actual_exit_price = exit_price or self.entry_price
            
            if self.position == 'long':
                profit = (actual_exit_price - self.entry_price) * self.position_size
            else:
                profit = (self.entry_price - actual_exit_price) * self.position_size
            
            self.balance += profit
            
            trade_record = {
                'exit_date': datetime.now(),
                'exit_price': actual_exit_price,
                'profit': profit,
                'exit_reason': exit_reason,
                'balance_after': self.balance
            }
            self.trades.append(trade_record)
            
            message = f"""
🔒 <b>POZİSYON KAPANDI!</b>

📉 <b>Yön:</b> {self.position.upper()}
💰 <b>Çıkış:</b> ${actual_exit_price:,.2f}
💵 <b>Kar/Zarar:</b> ${profit:+,.2f}
📋 <b>Sebep:</b> {exit_reason}

💰 <b>Yeni Bakiye:</b> ${self.balance:,.2f}
📊 <b>Toplam P&L:</b> ${self.balance - self.trading_capital:+,.2f}

⏰ {datetime.now().strftime('%H:%M:%S')}
            """
            
            self.send_telegram_message(message)
            
            # Reset position
            self.position = None
            self.position_size = 0
            self.entry_price = 0
            self.stop_loss = 0
            self.take_profit = 0
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error exiting position: {e}")
            return False

    def trading_loop(self):
        """Main trading loop"""
        self.logger.info("Trading loop started")
        
        while self.bot_running:
            try:
                current_time = datetime.now()
                
                # Saatlik rapor kontrolü
                if (self.price_alerts_enabled and 
                    (self.last_hourly_report is None or 
                     current_time.hour != self.last_hourly_report.hour)):
                    
                    self.send_hourly_report()
                    self.last_hourly_report = current_time
                
                if not self.exchange:
                    time.sleep(60)
                    continue
                
                # Fetch data
                df = self.fetch_recent_data()
                if df is None or len(df) < self.ema_period:
                    time.sleep(60)
                    continue
                
                # Calculate indicators
                df = self.calculate_indicators(df)
                if df is None:
                    time.sleep(60)
                    continue
                
                # Check positions
                if self.position:
                    exit_reason, exit_price = self.check_exit_conditions(df)
                    if exit_reason:
                        self.exit_position(exit_reason, exit_price)
                else:
                    entry_signals = self.check_entry_conditions(df)
                    self.current_market_trend = entry_signals['market_trend']
                    
                    if entry_signals['long']:
                        self.enter_position('buy', df)
                    elif entry_signals['short']:
                        self.enter_position('sell', df)
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Error in trading loop: {e}")
                time.sleep(60)

    def run(self):
        """Ana döngü - Telegram mesajlarını dinle"""
        print("🤖 Simple Telegram Bot başlatıldı!")
        print("📱 Telegram'da /start yazarak başlayın")
        print("⏹️ Durdurmak için Ctrl+C")
        
        # Başlangıç mesajı gönder
        self.send_telegram_message("🤖 Bot başlatıldı! /start yazarak menüyü açın.")
        
        try:
            while True:
                # Telegram güncellemelerini al
                updates = self.get_telegram_updates()
                
                for update in updates:
                    self.last_update_id = update['update_id']
                    
                    # Text mesaj
                    if 'message' in update:
                        self.process_telegram_command(update['message'])
                    
                    # Callback query (buton)
                    elif 'callback_query' in update:
                        self.process_telegram_callback(update['callback_query'])
                
                time.sleep(1)  # 1 saniye bekle
                
        except KeyboardInterrupt:
            print("\n⏹️ Bot durduruldu")
            self.bot_running = False
            self.send_telegram_message("⏹️ Bot durduruldu!")
        except Exception as e:
            print(f"❌ Bot hatası: {e}")
            self.send_telegram_message(f"❌ Bot hatası: {e}")

if __name__ == "__main__":
    bot = SimpleTelegramBot()
    bot.run()