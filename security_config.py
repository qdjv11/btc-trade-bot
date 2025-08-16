# enhanced_config.json (Gelişmiş güvenlik ayarları)
{
    "api_key": "YOUR_BINANCE_API_KEY",
    "secret": "YOUR_BINANCE_SECRET",
    "sandbox": true,
    "symbol": "BTC/USDT",
    "timeframe": "15m",
    
    "risk_management": {
        "risk_per_trade": 0.01,
        "max_position_size": 0.05,
        "max_daily_trades": 3,
        "max_daily_loss": 100,
        "max_drawdown": 0.10,
        "emergency_stop_loss": 0.15
    },
    
    "trading_hours": {
        "enabled": true,
        "start_hour": 6,
        "end_hour": 22,
        "timezone": "UTC"
    },
    
    "notifications": {
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "notify_on_entry": true,
        "notify_on_exit": true,
        "notify_on_error": true,
        "daily_report": true
    },
    
    "api_settings": {
        "spot_trading_enabled": true,
        "futures_trading_enabled": false,
        "margin_trading_enabled": false,
        "withdrawals_enabled": false,
        "ip_whitelist": ["YOUR_SERVER_IP"]
    }
}

# security_monitor.py (Güvenlik monitörü)
import json
import time
import ccxt
from datetime import datetime, timedelta
import sqlite3

class SecurityMonitor:
    def __init__(self, config_file='enhanced_config.json'):
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        self.risk_config = self.config['risk_management']
        self.daily_loss = 0
        self.daily_trades = 0
        self.current_drawdown = 0
        
        # Initialize exchange for balance checking
        self.exchange = ccxt.binance({
            'apiKey': self.config['api_key'],
            'secret': self.config['secret'],
            'sandbox': self.config.get('sandbox', True),
            'enableRateLimit': True
        })
        
        self.initial_balance = self.get_current_balance()
        self.peak_balance = self.initial_balance
    
    def get_current_balance(self):
        """Get current USDT balance"""
        try:
            balance = self.exchange.fetch_balance()
            return balance['USDT']['free']
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return 0
    
    def check_daily_limits(self):
        """Check if daily limits are exceeded"""
        current_balance = self.get_current_balance()
        
        # Calculate daily P&L
        daily_pnl = current_balance - self.initial_balance
        
        # Check daily loss limit
        if daily_pnl <= -self.risk_config['max_daily_loss']:
            return False, "Daily loss limit exceeded"
        
        # Check max trades
        if self.daily_trades >= self.risk_config['max_daily_trades']:
            return False, "Daily trade limit exceeded"
        
        return True, "OK"
    
    def check_drawdown(self):
        """Check current drawdown"""
        current_balance = self.get_current_balance()
        
        # Update peak balance
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance
        
        # Calculate drawdown
        drawdown = (self.peak_balance - current_balance) / self.peak_balance
        
        # Check emergency stop
        if drawdown >= self.risk_config['emergency_stop_loss']:
            return False, f"Emergency stop triggered. Drawdown: {drawdown:.2%}"
        
        # Check max drawdown
        if drawdown >= self.risk_config['max_drawdown']:
            return False, f"Max drawdown exceeded: {drawdown:.2%}"
        
        return True, f"Current drawdown: {drawdown:.2%}"
    
    def is_trading_hours(self):
        """Check if within allowed trading hours"""
        if not self.config['trading_hours']['enabled']:
            return True
        
        current_hour = datetime.utcnow().hour
        start_hour = self.config['trading_hours']['start_hour']
        end_hour = self.config['trading_hours']['end_hour']
        
        return start_hour <= current_hour <= end_hour
    
    def validate_trade(self, position_size, entry_price):
        """Validate if trade meets all security criteria"""
        current_balance = self.get_current_balance()
        
        # Check position size
        position_value = position_size * entry_price
        position_pct = position_value / current_balance
        
        if position_pct > self.risk_config['max_position_size']:
            return False, "Position size too large"
        
        # Check daily limits
        daily_ok, daily_msg = self.check_daily_limits()
        if not daily_ok:
            return False, daily_msg
        
        # Check drawdown
        drawdown_ok, drawdown_msg = self.check_drawdown()
        if not drawdown_ok:
            return False, drawdown_msg
        
        # Check trading hours
        if not self.is_trading_hours():
            return False, "Outside trading hours"
        
        return True, "Trade validated"

# risk_manager.py (Risk yöneticisi)
class RiskManager:
    def __init__(self, config):
        self.config = config
        self.security_monitor = SecurityMonitor()
        
    def calculate_safe_position_size(self, entry_price, stop_loss_price, balance):
        """Calculate position size with multiple safety checks"""
        
        # Kelly Criterion hesaplaması (opsiyonel)
        # Bu, tarihsel performansa dayalı optimal position size hesaplar
        
        # Temel risk yönetimi
        risk_amount = balance * self.config['risk_management']['risk_per_trade']
        
        # Stop loss mesafesi
        stop_distance = abs(entry_price - stop_loss_price)
        
        # Position size
        position_size = risk_amount / stop_distance
        
        # Maksimum position size kontrolü
        max_position_value = balance * self.config['risk_management']['max_position_size']
        max_position_size = max_position_value / entry_price
        
        # En küçük değeri al
        final_position_size = min(position_size, max_position_size)
        
        return final_position_size
    
    def should_stop_trading(self):
        """Determine if trading should be stopped"""
        
        # Güvenlik kontrolleri
        daily_ok, daily_msg = self.security_monitor.check_daily_limits()
        if not daily_ok:
            return True, daily_msg
        
        drawdown_ok, drawdown_msg = self.security_monitor.check_drawdown()
        if not drawdown_ok:
            return True, drawdown_msg
        
        if not self.security_monitor.is_trading_hours():
            return True, "Outside trading hours"
        
        return False, "Trading allowed"

# performance_tracker.py (Performans takipçisi)
class PerformanceTracker:
    def __init__(self, db_path='trading_bot.db'):
        self.db_path = db_path
    
    def get_daily_performance(self):
        """Get today's performance"""
        try:
            conn = sqlite3.connect(self.db_path)
            today = datetime.now().date()
            
            query = """
            SELECT 
                COUNT(*) as trades,
                SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                SUM(profit) as total_profit,
                AVG(profit) as avg_profit
            FROM trades 
            WHERE DATE(timestamp) = ? AND status = 'EXIT'
            """
            
            result = conn.execute(query, (today,)).fetchone()
            conn.close()
            
            return {
                'trades': result[0],
                'wins': result[1],
                'win_rate': result[1] / result[0] * 100 if result[0] > 0 else 0,
                'total_profit': result[2] or 0,
                'avg_profit': result[3] or 0
            }
        except Exception as e:
            print(f"Error getting daily performance: {e}")
            return {}
    
    def generate_daily_report(self):
        """Generate daily performance report"""
        perf = self.get_daily_performance()
        
        report = f"""
📊 Daily Trading Report - {datetime.now().strftime('%Y-%m-%d')}
{'=' * 50}

🔢 Trades Today: {perf.get('trades', 0)}
✅ Winning Trades: {perf.get('wins', 0)}
📈 Win Rate: {perf.get('win_rate', 0):.1f}%
💰 Total P&L: ${perf.get('total_profit', 0):.2f}
📊 Avg Profit/Trade: ${perf.get('avg_profit', 0):.2f}

🛡️ Risk Status: Active monitoring
⏰ Next Report: Tomorrow same time
        """
        
        return report

# backup_manager.py (Yedekleme yöneticisi)
import shutil
import os
from datetime import datetime

class BackupManager:
    def __init__(self, db_path='trading_bot.db'):
        self.db_path = db_path
        self.backup_dir = 'backups'
        
        # Backup klasörünü oluştur
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
    
    def create_backup(self):
        """Create database backup"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"trading_bot_backup_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            shutil.copy2(self.db_path, backup_path)
            print(f"Backup created: {backup_path}")
            
            # Eski backupları temizle (30 günden eski)
            self.cleanup_old_backups()
            
            return backup_path
        except Exception as e:
            print(f"Error creating backup: {e}")
            return None
    
    def cleanup_old_backups(self, days=30):
        """Remove backups older than specified days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            for filename in os.listdir(self.backup_dir):
                if filename.startswith('trading_bot_backup_'):
                    file_path = os.path.join(self.backup_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    
                    if file_time < cutoff_date:
                        os.remove(file_path)
                        print(f"Removed old backup: {filename}")
        except Exception as e:
            print(f"Error cleaning up backups: {e}")

# auto_restart.py (Otomatik yeniden başlatma)
import subprocess
import sys
import time
import psutil
import logging

class AutoRestarter:
    def __init__(self, script_name='live_trading_bot.py'):
        self.script_name = script_name
        self.max_restarts = 5
        self.restart_count = 0
        self.last_restart_time = 0
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def is_bot_running(self):
        """Check if trading bot is running"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and self.script_name in ' '.join(proc.info['cmdline']):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    
    def start_bot(self):
        """Start the trading bot"""
        try:
            self.logger.info(f"Starting {self.script_name}...")
            subprocess.Popen([sys.executable, self.script_name])
            self.restart_count += 1
            self.last_restart_time = time.time()
            return True
        except Exception as e:
            self.logger.error(f"Error starting bot: {e}")
            return False
    
    def monitor_and_restart(self):
        """Monitor bot and restart if needed"""
        while True:
            try:
                if not self.is_bot_running():
                    self.logger.warning("Bot is not running!")
                    
                    # Rate limiting for restarts
                    if time.time() - self.last_restart_time < 300:  # 5 minutes
                        if self.restart_count >= self.max_restarts:
                            self.logger.error("Too many restarts, stopping monitor")
                            break
                    else:
                        self.restart_count = 0  # Reset counter after 5 minutes
                    
                    self.start_bot()
                    time.sleep(60)  # Wait 1 minute before checking again
                else:
                    self.logger.info("Bot is running normally")
                    time.sleep(300)  # Check every 5 minutes
                    
            except KeyboardInterrupt:
                self.logger.info("Monitor stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Monitor error: {e}")
                time.sleep(60)

if __name__ == "__main__":
    restarter = AutoRestarter()
    restarter.monitor_and_restart()