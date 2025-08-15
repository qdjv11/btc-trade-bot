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
import asyncio
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

class OriginalStrategyTelegramBot:
    def __init__(self, config_file='config.json'):
        # Load configuration
        self.config = self.load_config(config_file)
        
        # Initialize exchange (will be set later based on user choice)
        self.exchange = None
        self.exchange_type = None  # 'spot' or 'futures'
        
        # Strategy parameters (ORIGINAL SETTINGS)
        self.symbol = self.config.get('symbol', 'BTC/USDT')
        self.timeframe = self.config.get('timeframe', '15m')
        self.donchian_period = self.config.get('donchian_period', 20)
        self.ema_period = self.config.get('ema_period', 200)
        
        # Trading parameters (will be set by user)
        self.trading_capital = 0
        self.leverage = 1
        self.trading_mode = 'both'  # 'long_only', 'short_only', 'both'
        
        # ORIGINAL RISK MANAGEMENT (from your code)
        self.balance = 10000  # Starting balance
        self.risk_per_trade = 0.02  # 2% risk per trade (fixed from original)
        
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
        self.bot_configured = False
        self.setup_step = 0
        
        # Price alerts
        self.price_alerts_enabled = True
        self.last_hourly_report = None
        
        # User data storage for setup process
        self.user_setup_data = {}
        
        # Database setup
        self.db_path = 'trading_bot.db'
        self.setup_database()
        
        # Logging setup
        self.setup_logging()
        
        # Telegram setup
        self.telegram_bot = None
        self.chat_id = self.config.get('telegram_chat_id')
        
        self.logger.info("Original Strategy Telegram Bot initialized")

    def load_config(self, config_file):
        """Load configuration from JSON file"""
        with open(config_file, 'r') as f:
            return json.load(f)

    def save_trading_config(self):
        """Trading ayarlarını kaydet"""
        trading_config = {
            'trading_capital': self.trading_capital,
            'leverage': self.leverage,
            'exchange_type': self.exchange_type,
            'trading_mode': self.trading_mode,
            'balance': self.balance
        }
        
        with open('trading_settings.json', 'w') as f:
            json.dump(trading_config, f, indent=4)

    def load_trading_config(self):
        """Trading ayarlarını yükle"""
        try:
            with open('trading_settings.json', 'r') as f:
                settings = json.load(f)
                self.trading_capital = settings.get('trading_capital', 0)
                self.leverage = settings.get('leverage', 1)
                self.exchange_type = settings.get('exchange_type', 'spot')
                self.trading_mode = settings.get('trading_mode', 'both')
                self.balance = settings.get('balance', 10000)
                self.bot_configured = True
                return True
        except:
            return False

    def setup_exchange(self):
        """Exchange'i kullanıcı seçimine göre ayarla"""
        try:
            if self.exchange_type == 'futures':
                self.exchange = ccxt.binance({
                    'apiKey': self.config['api_key'],
                    'secret': self.config['secret'],
                    'sandbox': self.config.get('sandbox', True),
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'future'
                    }
                })
            else:  # spot
                self.exchange = ccxt.binance({
                    'apiKey': self.config['api_key'],
                    'secret': self.config['secret'],
                    'sandbox': self.config.get('sandbox', True),
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'spot'
                    }
                })
            
            # Test connection
            balance = self.exchange.fetch_balance()
            return True
            
        except Exception as e:
            self.logger.error(f"Exchange setup error: {e}")
            return False

    def setup_database(self):
        """Setup SQLite database"""
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
                leverage INTEGER,
                exchange_type TEXT,
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
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('trading_bot.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    async def send_telegram_message(self, message, reply_markup=None):
        """Send message to Telegram"""
        try:
            if self.telegram_bot and self.chat_id:
                await self.telegram_bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {e}")

    def send_telegram_sync(self, message, reply_markup=None):
        """Synchronous wrapper for sending Telegram messages"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.send_telegram_message(message, reply_markup))
            loop.close()
        except Exception as e:
            self.logger.error(f"Error in sync telegram send: {e}")

    # Telegram Command Handlers
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        
        # Önceki ayarları yükle
        self.load_trading_config()
        
        keyboard = [
            [InlineKeyboardButton("🚀 Trading Başlat", callback_data='start_trading')],
            [InlineKeyboardButton("⚙️ Trading Ayarları", callback_data='setup_trading')],
            [InlineKeyboardButton("💵 Anlık Fiyat", callback_data='current_price')],
            [InlineKeyboardButton("📈 Saatlik Rapor", callback_data='hourly_report')],
            [InlineKeyboardButton("📊 Bot Durumu", callback_data='show_status')],
            [InlineKeyboardButton("💰 Bakiye", callback_data='balance'),
             InlineKeyboardButton("📋 Raporlar", callback_data='reports')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_message = f"""
🤖 <b>BTC Trading Bot</b>
<i>Orijinal Donchian + EMA + MACD Stratejisi</i>

📊 <b>Durum:</b>
• Bot: {'🟢 Çalışıyor' if self.bot_running else '🔴 Durdu'}
• Ayarlar: {'✅ Yapılandırılmış' if self.bot_configured else '❌ Ayarlanmamış'}
• Saatlik Rapor: {'🔔 Açık' if self.price_alerts_enabled else '🔕 Kapalı'}

{self.get_current_settings_text() if self.bot_configured else '⚙️ Önce trading ayarlarını yapın'}

📈 <b>Strateji:</b> Donchian Channel breakout + EMA200 + MACD
        """
        
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='HTML')

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'setup_trading':
            await self.start_setup_process(query)
        elif query.data == 'show_status':
            await self.show_bot_status(query)
        elif query.data == 'start_trading':
            await self.start_trading_process(query)
        elif query.data == 'stop_trading':
            await self.stop_trading_process(query)
        elif query.data.startswith('setup_'):
            await self.handle_setup_step(query)
        elif query.data == 'balance':
            await self.show_balance(query)
        elif query.data == 'current_price':
            await self.show_current_price(query)
        elif query.data == 'hourly_report':
            await self.send_hourly_report(query)
        elif query.data == 'reports':
            await self.show_reports(query)

    async def start_setup_process(self, query):
        """Trading setup sürecini başlat"""
        self.setup_step = 1
        self.user_setup_data = {}
        
        keyboard = [
            [InlineKeyboardButton("💰 Spot Trading", callback_data='setup_spot')],
            [InlineKeyboardButton("⚡ Futures Trading", callback_data='setup_futures')],
            [InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = """
⚙️ <b>Trading Ayarları</b>

<b>1. Exchange Tipi Seçin:</b>

💰 <b>Spot Trading:</b>
• Daha güvenli, leverage yok
• Sadece sahip olduğunuz para ile

⚡ <b>Futures Trading:</b>
• Leverage kullanımı
• Daha riskli ama yüksek potansiyel

📈 <b>Strateji:</b> Her iki tipte de aynı Donchian+EMA+MACD stratejisi kullanılır
        """
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

    async def handle_setup_step(self, query):
        """Setup adımlarını handle et"""
        
        if query.data == 'setup_spot':
            self.user_setup_data['exchange_type'] = 'spot'
            self.user_setup_data['leverage'] = 1
            await self.ask_trading_capital(query)
            
        elif query.data == 'setup_futures':
            self.user_setup_data['exchange_type'] = 'futures'
            await self.ask_leverage(query)
            
        elif query.data.startswith('leverage_'):
            leverage = int(query.data.split('_')[1])
            self.user_setup_data['leverage'] = leverage
            await self.ask_trading_capital(query)
            
        elif query.data.startswith('capital_'):
            capital = int(query.data.split('_')[1])
            self.user_setup_data['trading_capital'] = capital
            await self.ask_trading_mode(query)
            
        elif query.data.startswith('mode_'):
            mode = query.data.split('_')[1]
            self.user_setup_data['trading_mode'] = mode
            await self.confirm_settings(query)
            
        elif query.data == 'confirm_settings':
            await self.save_and_apply_settings(query)

    async def ask_leverage(self, query):
        """Leverage seçimi sor"""
        keyboard = [
            [InlineKeyboardButton("5x", callback_data='leverage_5'),
             InlineKeyboardButton("10x", callback_data='leverage_10')],
            [InlineKeyboardButton("20x", callback_data='leverage_20'),
             InlineKeyboardButton("25x", callback_data='leverage_25')],
            [InlineKeyboardButton("🔙 Geri", callback_data='setup_trading')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = """
⚡ <b>Leverage Seçimi</b>

<b>2. Leverage oranını seçin:</b>

⚠️ <b>Risk sabit kalır:</b> Her işlemde sermayenin %2'si risk alınır (orijinal strateji)

• <b>5x-10x:</b> Orta risk
• <b>20x-25x:</b> Yüksek risk

💡 <b>Not:</b> Leverage sadece pozisyon büyüklüğünü etkiler, risk yönetimi aynı kalır
        """
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

    async def ask_trading_capital(self, query):
        """Trading sermayesi sor"""
        keyboard = [
            [InlineKeyboardButton("$1,000", callback_data='capital_1000'),
             InlineKeyboardButton("$5,000", callback_data='capital_5000')],
            [InlineKeyboardButton("$10,000", callback_data='capital_10000'),
             InlineKeyboardButton("$20,000", callback_data='capital_20000')],
            [InlineKeyboardButton("🔙 Geri", callback_data='setup_trading')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        exchange_text = "Spot" if self.user_setup_data.get('exchange_type') == 'spot' else f"Futures ({self.user_setup_data.get('leverage')}x)"
        
        message = f"""
💰 <b>Trading Sermayesi</b>

<b>3. Ne kadar sermaye ile başlayacaksınız?</b>

📊 <b>Seçiminiz:</b> {exchange_text}

⚖️ <b>Risk Yönetimi:</b>
• Her işlemde sermayenin %2'si risk alınır
• ATR bazlı stop loss (2x ATR)
• Take profit: 4x ATR (2:1 risk/reward)

💡 Bu orijinal backtest stratejinizdeki ayarlardır
        """
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

    async def ask_trading_mode(self, query):
        """Trading modu sor"""
        keyboard = [
            [InlineKeyboardButton("📈 Sadece Long", callback_data='mode_long')],
            [InlineKeyboardButton("📉 Sadece Short", callback_data='mode_short')],
            [InlineKeyboardButton("📈📉 İki Yönlü", callback_data='mode_both')],
            [InlineKeyboardButton("🔙 Geri", callback_data='setup_trading')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = """
📊 <b>Trading Modu</b>

<b>4. Hangi yönde işlem yapmak istiyorsunuz?</b>

📈 <b>Sadece Long:</b> Sadece yükseliş sinyalleri
📉 <b>Sadece Short:</b> Sadece düşüş sinyalleri  
📈📉 <b>İki Yönlü:</b> Her iki yön (orijinal strateji)

🎯 <b>Sinyal Koşulları:</b>
• Donchian Channel breakout
• EMA200 trend filtresi
• MACD konfirmasyonu
• Candlestick pattern filtresi
        """
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

    async def confirm_settings(self, query):
        """Ayarları onaylat"""
        keyboard = [
            [InlineKeyboardButton("✅ Ayarları Kaydet", callback_data='confirm_settings')],
            [InlineKeyboardButton("🔄 Değiştir", callback_data='setup_trading')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        exchange_text = "Spot" if self.user_setup_data['exchange_type'] == 'spot' else f"Futures ({self.user_setup_data['leverage']}x)"
        mode_map = {'long': '📈 Sadece Long', 'short': '📉 Sadece Short', 'both': '📈📉 İki Yönlü'}
        
        message = f"""
📋 <b>Ayar Özeti</b>

<b>Trading Parametreleri:</b>

💱 <b>Exchange:</b> {exchange_text}
💰 <b>Sermaye:</b> ${self.user_setup_data['trading_capital']:,}
📊 <b>Trading Modu:</b> {mode_map[self.user_setup_data['trading_mode']]}

📈 <b>Strateji Detayları:</b>
• Risk/İşlem: %2 (sabit)
• Stop Loss: 2x ATR
• Take Profit: 4x ATR
• Donchian Period: 20
• EMA Period: 200

⚠️ <b>Bu orijinal backtest stratejinizdir</b>
        """
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

    async def save_and_apply_settings(self, query):
        """Ayarları kaydet ve uygula"""
        
        # Ayarları bot'a uygula
        self.trading_capital = self.user_setup_data['trading_capital']
        self.leverage = self.user_setup_data['leverage']
        self.exchange_type = self.user_setup_data['exchange_type']
        self.trading_mode = self.user_setup_data['trading_mode']
        self.balance = self.trading_capital  # Starting balance
        self.bot_configured = True
        
        # Dosyaya kaydet
        self.save_trading_config()
        
        # Exchange'i ayarla
        if self.setup_exchange():
            keyboard = [
                [InlineKeyboardButton("🚀 Trading Başlat", callback_data='start_trading')],
                [InlineKeyboardButton("📊 Ana Menü", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = """
✅ <b>Ayarlar Kaydedildi!</b>

🎉 Trading botunuz orijinal Donchian+EMA+MACD stratejisi ile yapılandırıldı!

🚀 <b>Trading başlatmak için "Trading Başlat" butonuna tıklayın</b>

📊 Bot şu koşullarda işlem yapacak:
• Donchian üst/alt band kırılımları
• EMA200 trend filtresi
• MACD konfirmasyonu  
• Candlestick pattern kontrolü
            """
        else:
            keyboard = [
                [InlineKeyboardButton("🔄 Tekrar Dene", callback_data='confirm_settings')],
                [InlineKeyboardButton("📊 Ana Menü", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = """
❌ <b>Exchange Bağlantı Hatası!</b>

API anahtarlarınızda sorun olabilir.
Lütfen Binance API ayarlarınızı kontrol edin.
            """
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

    def get_current_settings_text(self):
        """Mevcut ayarları text olarak döndür"""
        if not self.bot_configured:
            return ""
        
        exchange_text = "Spot" if self.exchange_type == 'spot' else f"Futures ({self.leverage}x)"
        mode_map = {'long': '📈 Sadece Long', 'short': '📉 Sadece Short', 'both': '📈📉 İki Yönlü'}
        
        return f"""
💱 <b>Exchange:</b> {exchange_text}
💰 <b>Sermaye:</b> ${self.trading_capital:,}
📊 <b>Mod:</b> {mode_map.get(self.trading_mode, 'Bilinmiyor')}
⚖️ <b>Risk:</b> %2 (orijinal strateji)
        """

    # ORIGINAL STRATEGY METHODS (from your backtest code)
    def fetch_recent_data(self, limit=500):
        """Fetch recent OHLCV data"""
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
        """Calculate all indicators needed for the strategy (ORIGINAL)"""
        try:
            # EMA 200
            df['ema200'] = talib.EMA(df['close'], timeperiod=self.ema_period)
            
            # ATR calculation
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            
            # Donchian Channels
            df['upper_band'] = df['high'].rolling(window=self.donchian_period).max()
            df['lower_band'] = df['low'].rolling(window=self.donchian_period).min()
            df['middle_band'] = (df['upper_band'] + df['lower_band']) / 2
            
            # Band distance check
            df['band_distance'] = df['upper_band'] - df['lower_band']
            df['band_distance_vs_atr'] = df['band_distance'] / (df['atr'] * 4)
            
            # MACD
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(
                df['close'], fastperiod=12, slowperiod=26, signalperiod=9
            )
            
            df.dropna(inplace=True)
            return df
        except Exception as e:
            self.logger.error(f"Error calculating indicators: {e}")
            return None

    def check_entry_conditions(self, df):
        """Check if entry conditions are met (ORIGINAL LOGIC)"""
        if len(df) < 2:
            return {'long': False, 'short': False, 'market_trend': 'unknown'}
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Check if price, open, close are above/below EMA200
        above_ema = (current['close'] > current['ema200'] and 
                     current['open'] > current['ema200'])
        below_ema = (current['close'] < current['ema200'] and 
                     current['open'] < current['ema200'])
        
        # Check Donchian band conditions
        donchian_long = current['high'] >= current['upper_band']
        donchian_short = current['low'] <= current['lower_band']
        
        # Check candlestick conditions
        long_candle_condition = ((prev['high'] - prev['close']) < ((prev['close'] - prev['open']) / 2) or 
                                (prev['high'] - prev['close']) < 3)
        short_candle_condition = ((prev['close'] - prev['low']) < ((prev['open'] - prev['close']) / 2) or 
                                 (prev['close'] - prev['low']) < 3)
        
        # MACD conditions
        macd_long = current['macd'] > 100 and current['macd_hist'] > 0
        macd_short = current['macd'] < -100 and current['macd_hist'] < 0
        
        # Check if Donchian bands are on the correct side of EMA200
        donchian_band_placement = True
        if above_ema and current['upper_band'] < current['ema200']:
            donchian_band_placement = False
        if below_ema and current['lower_band'] > current['ema200']:
            donchian_band_placement = False
        
        # Check if band distance is sufficient (ATR*4)
        sufficient_band_distance = current['band_distance_vs_atr'] > 1.0
        
        # Combine conditions for LONG signal
        long_signal = (above_ema and donchian_long and long_candle_condition and 
                      macd_long and donchian_band_placement and sufficient_band_distance)
        
        # Combine conditions for SHORT signal
        short_signal = (below_ema and donchian_short and short_candle_condition and 
                       macd_short and donchian_band_placement and sufficient_band_distance)
        
        # Apply trading mode filter
        if self.trading_mode == 'long':
            short_signal = False
        elif self.trading_mode == 'short':
            long_signal = False
        
        # Determine market trend
        market_trend = 'up' if above_ema else 'down'
        
        return {'long': long_signal, 'short': short_signal, 'market_trend': market_trend}

    def calculate_exit_levels(self, df, i, position_type):
        """Calculate stop loss and take profit levels (ORIGINAL)"""
        current = df.iloc[i]
        atr_value = current['atr']
        
        if position_type == 'long':
            stop_loss = current['close'] - (atr_value * 2)
            take_profit = current['close'] + (atr_value * 4)
        else:  # short
            stop_loss = current['close'] + (atr_value * 2)
            take_profit = current['close'] - (atr_value * 4)
        
        return stop_loss, take_profit

    def check_exit_conditions(self, df):
        """Check if exit conditions are met (ORIGINAL)"""
        if not self.position or len(df) < 2:
            return None, None
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        if self.position == 'long':
            # Check stop loss
            if current['low'] <= self.stop_loss:
                return 'stop_loss', self.stop_loss
            # Check take profit
            elif current['high'] >= self.take_profit:
                return 'take_profit', self.take_profit
            # CVD exit
            elif current['atr'] > prev['atr'] * 1.5 and current['close'] < prev['close']:
                return 'cvd_exit', current['close']
        
        elif self.position == 'short':
            # Check stop loss
            if current['high'] >= self.stop_loss:
                return 'stop_loss', self.stop_loss
            # Check take profit
            elif current['low'] <= self.take_profit:
                return 'take_profit', self.take_profit
            # CVD exit
            elif current['atr'] > prev['atr'] * 1.5 and current['close'] > prev['close']:
                return 'cvd_exit', current['close']
        
        return None, None

    def calculate_position_size(self, entry_price, stop_loss_price):
        """Calculate position size based on original risk management"""
        try:
            # Risk 2% of balance (ORIGINAL LOGIC)
            risk_amount = self.balance * self.risk_per_trade
            
            # Calculate stop distance
            stop_distance = abs(entry_price - stop_loss_price)
            
            # Calculate position size
            position_size = risk_amount / stop_distance
            
            return position_size
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0

    # Price Alert Methods (same as before)
    async def show_current_price(self, query):
        """Anlık fiyat bilgisi göster"""
        try:
            # Basit exchange oluştur (sadece fiyat için)
            temp_exchange = ccxt.binance({
                'apiKey': self.config['api_key'],
                'secret': self.config['secret'],
                'sandbox': self.config.get('sandbox', True),
                'enableRateLimit': True
            })
            
            # Ticker bilgisi al
            ticker = temp_exchange.fetch_ticker(self.symbol)
            
            # 24 saatlik değişim hesapla
            price_change = ticker['change']
            price_change_pct = ticker['percentage']
            
            # Emoji belirleme
            trend_emoji = "📈" if price_change > 0 else "📉" if price_change < 0 else "➡️"
            color_emoji = "🟢" if price_change > 0 else "🔴" if price_change < 0 else "🟡"
            
            # Volume formatla
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
            
            keyboard = [
                [InlineKeyboardButton("🔄 Yenile", callback_data='current_price')],
                [InlineKeyboardButton("📈 Saatlik Rapor", callback_data='hourly_report')],
                [InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
            
        except Exception as e:
            await query.edit_message_text(f"❌ Fiyat alınamadı: {e}")

    async def send_hourly_report(self, query=None):
        """Saatlik rapor gönder"""
        try:
            # Exchange oluştur
            temp_exchange = ccxt.binance({
                'apiKey': self.config['api_key'],
                'secret': self.config['secret'],
                'sandbox': self.config.get('sandbox', True),
                'enableRateLimit': True
            })
            
            # Mevcut fiyat
            ticker = temp_exchange.fetch_ticker(self.symbol)
            current_price = ticker['last']
            
            # Son 24 saatlik veriler
            ohlcv_24h = temp_exchange.fetch_ohlcv(self.symbol, '1h', limit=24)
            df_24h = pd.DataFrame(ohlcv_24h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Son saatlik veriler
            last_hour = df_24h.iloc[-1]
            prev_hour = df_24h.iloc[-2] if len(df_24h) > 1 else last_hour
            
            # Saatlik değişim
            hourly_change = last_hour['close'] - prev_hour['close']
            hourly_change_pct = (hourly_change / prev_hour['close']) * 100
            
            # Trend analizi (son 4 saat)
            if len(df_24h) >= 4:
                recent_prices = df_24h.tail(4)['close'].tolist()
                trend = self.analyze_trend(recent_prices)
            else:
                trend = "Yetersiz veri"
            
            # Emoji belirleme
            trend_emoji = "📈" if hourly_change > 0 else "📉" if hourly_change < 0 else "➡️"
            
            # Pozisyon detayları ve P&L hesaplama
            position_info = ""
            if self.position and self.entry_price > 0:
                # Anlık P&L hesapla
                if self.position == 'long':
                    unrealized_pnl = (current_price - self.entry_price) * self.position_size
                else:  # short
                    unrealized_pnl = (self.entry_price - current_price) * self.position_size
                
                # P&L yüzdesi
                risk_amount = self.balance * self.risk_per_trade
                pnl_percentage = (unrealized_pnl / risk_amount) * 100
                
                # Stop Loss ve Take Profit'e olan mesafeler
                sl_distance = abs(current_price - self.stop_loss)
                tp_distance = abs(self.take_profit - current_price)
                
                # SL/TP mesafe yüzdeleri
                sl_distance_pct = (sl_distance / current_price) * 100
                tp_distance_pct = (tp_distance / current_price) * 100
                
                # Pozisyon emoji
                pos_emoji = "📈" if self.position == 'long' else "📉"
                pnl_emoji = "🟢" if unrealized_pnl > 0 else "🔴" if unrealized_pnl < 0 else "🟡"
                
                position_info = f"""

💼 <b>AÇIK POZİSYON:</b>
{pos_emoji} <b>Yön:</b> {self.position.upper()}
💰 <b>Giriş:</b> ${self.entry_price:,.2f}
📊 <b>Miktar:</b> {self.position_size:.6f} BTC
⚡ <b>Leverage:</b> {self.leverage}x

🎯 <b>Seviyeler:</b>
🛑 SL: ${self.stop_loss:,.2f} (📏{sl_distance_pct:.1f}% mesafe)
🏆 TP: ${self.take_profit:,.2f} (📏{tp_distance_pct:.1f}% mesafe)

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

🎯 <b>Trend (6h):</b> {trend}{position_info}

🤖 <b>Bot Durumu:</b>
• Trading: {'🟢 Aktif' if self.bot_running else '🔴 Pasif'}
• Strateji: Donchian+EMA+MACD
• Bakiye: ${self.balance:,.2f}

⏰ <b>Rapor Zamanı:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}
            """
            
            if query:
                # Manuel istek
                keyboard = [
                    [InlineKeyboardButton("🔄 Yenile", callback_data='hourly_report')],
                    [InlineKeyboardButton("💵 Anlık Fiyat", callback_data='current_price')],
                    [InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
            else:
                # Otomatik rapor
                self.send_telegram_sync(message)
                
        except Exception as e:
            error_msg = f"❌ Saatlik rapor hatası: {e}"
            if query:
                await query.edit_message_text(error_msg)
            else:
                self.send_telegram_sync(error_msg)

    def analyze_trend(self, prices):
        """Basit trend analizi"""
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

    async def show_bot_status(self, query):
        """Bot durumunu detaylı göster"""
        try:
            if self.exchange:
                df = self.fetch_recent_data(limit=10)
                current_price = df.iloc[-1]['close'] if df is not None else "N/A"
                balance = self.exchange.fetch_balance()
                usdt_balance = balance['USDT']['free']
            else:
                current_price = "N/A"
                usdt_balance = 0
            
            status_message = f"""
📊 <b>Bot Durumu Detayı</b>

🤖 <b>Bot:</b> {'🟢 Çalışıyor' if self.bot_running else '🔴 Durdu'}
⚙️ <b>Ayarlar:</b> {'✅ Yapılandırılmış' if self.bot_configured else '❌ Ayarlanmamış'}
💱 <b>Exchange:</b> {self.exchange_type or 'Ayarlanmamış'}
💰 <b>Leverage:</b> {self.leverage}x
💵 <b>Sembol:</b> {self.symbol}
📈 <b>Timeframe:</b> {self.timeframe}

💰 <b>Fiyat:</b> ${current_price}
💵 <b>Bakiye:</b> {usdt_balance:.2f} USDT
📊 <b>Trading Sermaye:</b> ${self.trading_capital:,}

📈 <b>Pozisyon:</b> {self.position or 'Yok'}
{f'💰 Giriş: ${self.entry_price:.2f}' if self.position else ''}
{f'🛑 Stop Loss: ${self.stop_loss:.2f}' if self.position else ''}
{f'🎯 Take Profit: ${self.take_profit:.2f}' if self.position else ''}

📊 <b>Strateji Parametreleri:</b>
• Donchian Period: {self.donchian_period}
• EMA Period: {self.ema_period}
• Risk/İşlem: %{self.risk_per_trade*100}
• Trading Modu: {self.trading_mode}

⏰ <b>Son Güncelleme:</b> {datetime.now().strftime('%H:%M:%S')}
            """
            
            keyboard = [
                [InlineKeyboardButton("🔄 Yenile", callback_data='show_status')],
                [InlineKeyboardButton("🚀 Trading Başlat", callback_data='start_trading') if not self.bot_running else InlineKeyboardButton("⏹️ Trading Durdur", callback_data='stop_trading')],
                [InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(status_message, reply_markup=reply_markup, parse_mode='HTML')
        except Exception as e:
            await query.edit_message_text(f"❌ Durum alınamadı: {e}")

    async def start_trading_process(self, query):
        """Trading sürecini başlat"""
        if not self.bot_configured:
            await query.edit_message_text("❌ Önce trading ayarlarını yapın!")
            return
        
        if self.bot_running:
            await query.edit_message_text("⚠️ Bot zaten çalışıyor!")
            return
        
        self.bot_running = True
        
        # Trading döngüsünü başlat
        threading.Thread(target=self.trading_loop, daemon=True).start()
        
        keyboard = [
            [InlineKeyboardButton("⏹️ Trading Durdur", callback_data='stop_trading')],
            [InlineKeyboardButton("📊 Bot Durumu", callback_data='show_status')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f"""
🚀 <b>Trading Başlatıldı!</b>

✅ Bot artık orijinal Donchian+EMA+MACD stratejisi ile çalışıyor

📊 <b>Strateji Detayları:</b>
{self.get_current_settings_text()}

🎯 <b>Giriş Koşulları:</b>
• Donchian Channel breakout
• EMA200 trend filtresi  
• MACD konfirmasyonu
• Candlestick pattern kontrolü
• Yeterli band distance

🔄 Bot her dakika piyasayı analiz edecek
📱 Tüm işlemler size bildirilecek
        """
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

    async def stop_trading_process(self, query):
        """Trading'i durdur"""
        self.bot_running = False
        
        keyboard = [
            [InlineKeyboardButton("🚀 Trading Başlat", callback_data='start_trading')],
            [InlineKeyboardButton("📊 Ana Menü", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text("⏹️ Trading durduruldu!", reply_markup=reply_markup)

    async def show_balance(self, query):
        """Bakiye göster"""
        try:
            if not self.exchange:
                await query.edit_message_text("❌ Exchange bağlantısı yok!")
                return
            
            balance = self.exchange.fetch_balance()
            
            if self.exchange_type == 'futures':
                balance_text = f"USDT: {balance['USDT']['free']:.2f}"
            else:
                balance_text = f"USDT: {balance['USDT']['free']:.2f}\nBTC: {balance['BTC']['free']:.6f}"
            
            message = f"""
💰 <b>Hesap Bakiyesi</b>

{balance_text}

📊 <b>Trading Sermayesi:</b> ${self.trading_capital:,}
💰 <b>Mevcut Balance:</b> ${self.balance:,.2f}
⚖️ <b>Risk/İşlem:</b> ${self.balance * self.risk_per_trade:.2f} (%2)

⏰ <b>Güncelleme:</b> {datetime.now().strftime('%H:%M:%S')}
            """
            
            await query.edit_message_text(message, parse_mode='HTML')
        except Exception as e:
            await query.edit_message_text(f"❌ Bakiye alınamadı: {e}")

    async def show_reports(self, query):
        """Raporları göster"""
        keyboard = [
            [InlineKeyboardButton("📈 Saatlik Rapor", callback_data='hourly_report')],
            [InlineKeyboardButton("💵 Anlık Fiyat", callback_data='current_price')],
            [InlineKeyboardButton("📊 Bot Durumu", callback_data='show_status')],
            [InlineKeyboardButton("🔙 Ana Menü", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        total_trades = len(self.trades)
        profitable_trades = len([t for t in self.trades if t.get('profit', 0) > 0])
        
        message = f"""
📋 <b>Trading Raporları</b>

📊 <b>Genel İstatistikler:</b>
🔢 Toplam İşlem: {total_trades}
✅ Karlı İşlem: {profitable_trades}
📈 Başarı Oranı: {(profitable_trades/total_trades*100) if total_trades > 0 else 0:.1f}%

💰 <b>Performans:</b>
💵 Başlangıç: ${self.trading_capital:,}
💰 Mevcut: ${self.balance:,.2f}
📊 Toplam P&L: ${self.balance - self.trading_capital:+,.2f}

🎯 <b>Strateji:</b> Orijinal Donchian+EMA+MACD
⚖️ <b>Risk Yönetimi:</b> %2 per trade

Hangi raporu görmek istiyorsunuz?
        """
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

    def enter_position(self, side, df):
        """Enter a new position (ORIGINAL LOGIC)"""
        try:
            current = df.iloc[-1]
            
            # Calculate exit levels
            atr_value = current['atr']
            if side == 'buy':  # Long position
                stop_loss = current['close'] - (atr_value * 2)
                take_profit = current['close'] + (atr_value * 4)
                position_type = 'long'
            else:  # Short position
                stop_loss = current['close'] + (atr_value * 2)
                take_profit = current['close'] - (atr_value * 4)
                position_type = 'short'
            
            # Calculate position size (original logic)
            position_size = self.calculate_position_size(current['close'], stop_loss)
            
            if position_size <= 0:
                return False
            
            # Set position
            self.position = position_type
            self.position_size = position_size
            self.entry_price = current['close']
            self.stop_loss = stop_loss
            self.take_profit = take_profit
            
            # Log trade
            trade_record = {
                'entry_date': datetime.now(),
                'entry_price': self.entry_price,
                'position': self.position,
                'position_size': self.position_size,
                'stop_loss': self.stop_loss,
                'take_profit': self.take_profit,
                'balance': self.balance,
                'market_trend': self.current_market_trend
            }
            
            message = f"""
🚀 <b>POZISYON AÇILDI!</b>

📈 <b>Yön:</b> {position_type.upper()}
💰 <b>Fiyat:</b> ${self.entry_price:,.2f}
📊 <b>Miktar:</b> {position_size:.6f} BTC
⚡ <b>Leverage:</b> {self.leverage}x

🎯 <b>Seviyeler:</b>
🛑 Stop Loss: ${self.stop_loss:,.2f}
🏆 Take Profit: ${self.take_profit:,.2f}

📊 <b>Risk:</b> ${self.balance * self.risk_per_trade:.2f} (%2)
📈 <b>Trend:</b> {self.current_market_trend}

⏰ {datetime.now().strftime('%H:%M:%S')}
            """
            
            self.send_telegram_sync(message)
            return True
            
        except Exception as e:
            self.logger.error(f"Error entering position: {e}")
            return False

    def exit_position(self, exit_reason, exit_price=None):
        """Exit current position (ORIGINAL LOGIC)"""
        try:
            if not self.position:
                return False
            
            actual_exit_price = exit_price or self.entry_price
            
            # Calculate profit (original logic)
            if self.position == 'long':
                profit = (actual_exit_price - self.entry_price) * self.position_size
            else:
                profit = (self.entry_price - actual_exit_price) * self.position_size
            
            # Update balance
            self.balance += profit
            
            # Record trade
            trade_record = {
                'exit_date': datetime.now(),
                'exit_price': actual_exit_price,
                'profit': profit,
                'exit_reason': exit_reason,
                'balance_after': self.balance
            }
            self.trades.append(trade_record)
            
            message = f"""
🏁 <b>POZISYON KAPANDI!</b>

📉 <b>Yön:</b> {self.position.upper()}
💰 <b>Çıkış:</b> ${actual_exit_price:,.2f}
💵 <b>Kar/Zarar:</b> ${profit:+,.2f}
📋 <b>Sebep:</b> {exit_reason}

💰 <b>Yeni Bakiye:</b> ${self.balance:,.2f}
📊 <b>Toplam P&L:</b> ${self.balance - self.trading_capital:+,.2f}

⏰ {datetime.now().strftime('%H:%M:%S')}
            """
            
            self.send_telegram_sync(message)
            
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
        """Main trading loop with original strategy"""
        self.logger.info("Trading loop started with original strategy")
        
        while self.bot_running:
            try:
                current_time = datetime.now()
                
                # Saatlik rapor kontrolü
                if (self.price_alerts_enabled and 
                    (self.last_hourly_report is None or 
                     current_time.hour != self.last_hourly_report.hour)):
                    
                    asyncio.run(self.send_hourly_report())
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
                
                # Check if we have an open position
                if self.position:
                    # Check exit conditions
                    exit_reason, exit_price = self.check_exit_conditions(df)
                    if exit_reason:
                        self.exit_position(exit_reason, exit_price)
                else:
                    # Check entry conditions (ORIGINAL LOGIC)
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

    async def start_telegram_bot(self):
        """Start Telegram bot"""
        try:
            self.telegram_bot = Bot(token=self.config['telegram_bot_token'])
            
            if not self.chat_id or self.chat_id.startswith('@'):
                print("⚠️ Lütfen Telegram botunuza /start mesajı gönderin...")
                print(f"Bot linki: https://t.me/{(await self.telegram_bot.get_me()).username}")
            
            application = Application.builder().token(self.config['telegram_bot_token']).build()
            
            application.add_handler(CommandHandler("start", self.start_command))
            application.add_handler(CallbackQueryHandler(self.button_handler))
            
            print("🤖 Telegram bot başlatıldı!")
            print("📈 Orijinal Donchian+EMA+MACD stratejisi hazır!")
            await application.run_polling()
            
        except Exception as e:
            self.logger.error(f"Error starting Telegram bot: {e}")

    def run(self):
        """Run the bot"""
        try:
            asyncio.run(self.start_telegram_bot())
        except KeyboardInterrupt:
            self.logger.info("Bot stopped by user")
            self.bot_running = False

if __name__ == "__main__":
    bot = OriginalStrategyTelegramBot()
    bot.run()
            