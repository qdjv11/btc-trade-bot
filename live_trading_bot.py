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
from typing import Dict, Any, Optional, Tuple
import requests

class LiveTradingBot:
    def __init__(self, config_file='config.json'):
        # Load configuration
        self.config = self.load_config(config_file)
        
        # Initialize exchange
        self.exchange = self.initialize_exchange()
        
        # Strategy parameters
        self.symbol = self.config.get('symbol', 'BTC/USDT')
        self.timeframe = self.config.get('timeframe', '15m')
        self.donchian_period = self.config.get('donchian_period', 20)
        self.ema_period = self.config.get('ema_period', 200)
        
        # Risk management
        self.risk_per_trade = self.config.get('risk_per_trade', 0.02)  # 2%
        self.max_position_size = self.config.get('max_position_size', 0.1)  # 10% of balance
        
        # Trading state
        self.position = None
        self.position_size = 0
        self.entry_price = 0
        self.stop_loss = 0
        self.take_profit = 0
        self.last_check_time = 0
        
        # Database setup
        self.db_path = 'trading_bot.db'
        self.setup_database()
        
        # Logging setup
        self.setup_logging()
        
        # Telegram notifications (optional)
        self.telegram_bot_token = self.config.get('telegram_bot_token')
        self.telegram_chat_id = self.config.get('telegram_chat_id')
        
        # Safety checks
        self.max_daily_trades = self.config.get('max_daily_trades', 5)
        self.daily_trade_count = 0
        self.last_trade_date = None
        
        self.logger.info("Live Trading Bot initialized successfully")

    def load_config(self, config_file):
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Create default config
            default_config = {
                "api_key": "YOUR_BINANCE_API_KEY",
                "secret": "YOUR_BINANCE_SECRET",
                "sandbox": True,
                "symbol": "BTC/USDT",
                "timeframe": "15m",
                "donchian_period": 20,
                "ema_period": 200,
                "risk_per_trade": 0.02,
                "max_position_size": 0.1,
                "max_daily_trades": 5,
                "telegram_bot_token": "",
                "telegram_chat_id": ""
            }
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
            print(f"Created default config file: {config_file}")
            print("Please update the API credentials and restart the bot")
            return default_config

    def initialize_exchange(self):
        """Initialize Binance exchange connection"""
        try:
            exchange = ccxt.binance({
                'apiKey': self.config['api_key'],
                'secret': self.config['secret'],
                'sandbox': self.config.get('sandbox', True),
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot'  # Use spot trading
                }
            })
            
            # Test connection
            balance = exchange.fetch_balance()
            print(f"Successfully connected to Binance. USDT Balance: {balance['USDT']['free']}")
            return exchange
            
        except Exception as e:
            print(f"Error connecting to exchange: {e}")
            raise

    def setup_database(self):
        """Setup SQLite database for storing trades and logs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create trades table
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
                balance_after REAL
            )
        ''')
        
        # Create logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                level TEXT,
                message TEXT
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
        """Calculate technical indicators"""
        try:
            # EMA 200
            df['ema200'] = talib.EMA(df['close'], timeperiod=self.ema_period)
            
            # ATR
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
        """Check if entry conditions are met"""
        if len(df) < 2:
            return {'long': False, 'short': False}
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Price vs EMA200
        above_ema = (current['close'] > current['ema200'] and 
                     current['open'] > current['ema200'])
        below_ema = (current['close'] < current['ema200'] and 
                     current['open'] < current['ema200'])
        
        # Donchian breakouts
        donchian_long = current['high'] >= current['upper_band']
        donchian_short = current['low'] <= current['lower_band']
        
        # Candlestick conditions
        long_candle_condition = ((prev['high'] - prev['close']) < ((prev['close'] - prev['open']) / 2) or 
                                (prev['high'] - prev['close']) < 3)
        short_candle_condition = ((prev['close'] - prev['low']) < ((prev['open'] - prev['close']) / 2) or 
                                 (prev['close'] - prev['low']) < 3)
        
        # MACD conditions
        macd_long = current['macd'] > 100 and current['macd_hist'] > 0
        macd_short = current['macd'] < -100 and current['macd_hist'] < 0
        
        # Band placement check
        donchian_band_placement = True
        if above_ema and current['upper_band'] < current['ema200']:
            donchian_band_placement = False
        if below_ema and current['lower_band'] > current['ema200']:
            donchian_band_placement = False
        
        # Sufficient band distance
        sufficient_band_distance = current['band_distance_vs_atr'] > 1.0
        
        # Combine conditions
        long_signal = (above_ema and donchian_long and long_candle_condition and 
                      macd_long and donchian_band_placement and sufficient_band_distance)
        
        short_signal = (below_ema and donchian_short and short_candle_condition and 
                       macd_short and donchian_band_placement and sufficient_band_distance)
        
        return {'long': long_signal, 'short': short_signal}

    def check_exit_conditions(self, df):
        """Check if exit conditions are met"""
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
        """Calculate position size based on risk management"""
        try:
            balance = self.exchange.fetch_balance()
            usdt_balance = balance['USDT']['free']
            
            # Calculate risk amount
            risk_amount = usdt_balance * self.risk_per_trade
            
            # Calculate stop distance
            stop_distance = abs(entry_price - stop_loss_price)
            
            # Calculate position size
            position_size = risk_amount / stop_distance
            
            # Apply maximum position size limit
            max_size = usdt_balance * self.max_position_size / entry_price
            position_size = min(position_size, max_size)
            
            return position_size
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0

    def place_order(self, side, amount, price=None, order_type='market'):
        """Place an order on the exchange"""
        try:
            if order_type == 'market':
                order = self.exchange.create_market_order(self.symbol, side, amount)
            else:
                order = self.exchange.create_limit_order(self.symbol, side, amount, price)
            
            self.logger.info(f"Order placed: {side} {amount} {self.symbol} at {price if price else 'market'}")
            return order
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return None

    def enter_position(self, side, df):
        """Enter a new position"""
        try:
            current = df.iloc[-1]
            
            # Calculate stop loss and take profit
            atr_value = current['atr']
            if side == 'buy':  # Long position
                stop_loss = current['close'] - (atr_value * 2)
                take_profit = current['close'] + (atr_value * 4)
            else:  # Short position (sell)
                stop_loss = current['close'] + (atr_value * 2)
                take_profit = current['close'] - (atr_value * 4)
            
            # Calculate position size
            position_size = self.calculate_position_size(current['close'], stop_loss)
            
            if position_size <= 0:
                self.logger.warning("Position size is 0 or negative, skipping trade")
                return False
            
            # Place the order
            order = self.place_order(side, position_size)
            
            if order:
                self.position = 'long' if side == 'buy' else 'short'
                self.position_size = position_size
                self.entry_price = order.get('average', current['close'])
                self.stop_loss = stop_loss
                self.take_profit = take_profit
                
                # Log trade to database
                self.log_trade_to_db('ENTRY', side, position_size, self.entry_price)
                
                # Send notification
                self.send_notification(f"Entered {self.position} position: {position_size:.6f} {self.symbol} at {self.entry_price:.2f}")
                
                self.daily_trade_count += 1
                return True
        except Exception as e:
            self.logger.error(f"Error entering position: {e}")
        
        return False

    def exit_position(self, exit_reason, exit_price=None):
        """Exit current position"""
        try:
            if not self.position:
                return False
            
            side = 'sell' if self.position == 'long' else 'buy'
            
            # Place exit order
            order = self.place_order(side, self.position_size)
            
            if order:
                actual_exit_price = order.get('average', exit_price)
                
                # Calculate profit
                if self.position == 'long':
                    profit = (actual_exit_price - self.entry_price) * self.position_size
                else:
                    profit = (self.entry_price - actual_exit_price) * self.position_size
                
                # Log trade to database
                self.log_trade_to_db('EXIT', side, self.position_size, actual_exit_price, profit, exit_reason)
                
                # Send notification
                self.send_notification(f"Exited {self.position} position: Profit: ${profit:.2f} ({exit_reason})")
                
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

    def log_trade_to_db(self, action, side, amount, price, profit=None, exit_reason=None):
        """Log trade to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            balance = self.exchange.fetch_balance()['USDT']['free']
            
            cursor.execute('''
                INSERT INTO trades (timestamp, symbol, side, amount, price, stop_loss, take_profit, profit, status, exit_reason, balance_after)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                self.symbol,
                side,
                amount,
                price,
                self.stop_loss,
                self.take_profit,
                profit,
                action,
                exit_reason,
                balance
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Error logging trade to database: {e}")

    def send_notification(self, message):
        """Send Telegram notification"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': f"🤖 Trading Bot Alert\n\n{message}\n\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
            requests.post(url, json=payload)
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")

    def check_daily_limits(self):
        """Check if daily trading limits are exceeded"""
        today = datetime.now().date()
        
        if self.last_trade_date != today:
            self.daily_trade_count = 0
            self.last_trade_date = today
        
        return self.daily_trade_count < self.max_daily_trades

    def run_once(self):
        """Run one iteration of the trading loop"""
        try:
            # Fetch recent data
            df = self.fetch_recent_data()
            if df is None or len(df) < self.ema_period:
                self.logger.warning("Insufficient data for analysis")
                return
            
            # Calculate indicators
            df = self.calculate_indicators(df)
            if df is None:
                return
            
            # Check if we have a position
            if self.position:
                # Check exit conditions
                exit_reason, exit_price = self.check_exit_conditions(df)
                if exit_reason:
                    self.exit_position(exit_reason, exit_price)
            else:
                # Check entry conditions
                if self.check_daily_limits():
                    signals = self.check_entry_conditions(df)
                    
                    if signals['long']:
                        self.enter_position('buy', df)
                    elif signals['short']:
                        self.enter_position('sell', df)
                else:
                    self.logger.info("Daily trade limit reached")
            
            # Log current status
            current_price = df.iloc[-1]['close']
            balance = self.exchange.fetch_balance()['USDT']['free']
            
            self.logger.info(f"Status: {self.position or 'No position'} | Price: {current_price:.2f} | Balance: {balance:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error in trading loop: {e}")

    def run(self, check_interval=60):
        """Main trading loop"""
        self.logger.info("Starting live trading bot...")
        self.send_notification("Trading bot started")
        
        try:
            while True:
                self.run_once()
                time.sleep(check_interval)
        except KeyboardInterrupt:
            self.logger.info("Bot stopped by user")
            self.send_notification("Trading bot stopped")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            self.send_notification(f"Bot error: {e}")

    def get_performance_report(self):
        """Generate performance report from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            trades_df = pd.read_sql_query("SELECT * FROM trades WHERE status = 'EXIT'", conn)
            conn.close()
            
            if len(trades_df) == 0:
                return "No completed trades yet"
            
            total_trades = len(trades_df)
            profitable_trades = len(trades_df[trades_df['profit'] > 0])
            win_rate = profitable_trades / total_trades * 100
            total_profit = trades_df['profit'].sum()
            
            report = f"""
Performance Report:
==================
Total Trades: {total_trades}
Profitable Trades: {profitable_trades}
Win Rate: {win_rate:.2f}%
Total Profit: ${total_profit:.2f}
Average Profit per Trade: ${total_profit/total_trades:.2f}
Current Balance: ${self.exchange.fetch_balance()['USDT']['free']:.2f}
            """
            
            return report
        except Exception as e:
            return f"Error generating report: {e}"

if __name__ == "__main__":
    # Create and run the bot
    bot = LiveTradingBot()
    
    # Print performance report
    print(bot.get_performance_report())
    
    # Start the bot
    bot.run(check_interval=60)  # Check every minute