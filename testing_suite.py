# test_bot.py (Bot test süiti)
import unittest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch
from live_trading_bot import LiveTradingBot
import json
import tempfile
import os

class TestLiveTradingBot(unittest.TestCase):
    def setUp(self):
        """Test için geçici config oluştur"""
        self.test_config = {
            "api_key": "test_key",
            "secret": "test_secret",
            "sandbox": True,
            "symbol": "BTC/USDT",
            "timeframe": "15m",
            "donchian_period": 20,
            "ema_period": 200,
            "risk_per_trade": 0.02,
            "max_position_size": 0.1,
            "max_daily_trades": 5
        }
        
        # Geçici config dosyası oluştur
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        json.dump(self.test_config, self.temp_config)
        self.temp_config.close()
        
        # Mock exchange
        with patch('live_trading_bot.ccxt.binance') as mock_exchange:
            mock_exchange.return_value.fetch_balance.return_value = {'USDT': {'free': 10000}}
            self.bot = LiveTradingBot(self.temp_config.name)
    
    def tearDown(self):
        """Test sonrası temizlik"""
        os.unlink(self.temp_config.name)
    
    def test_indicator_calculation(self):
        """İndikatör hesaplamalarını test et"""
        # Test verisi oluştur
        dates = pd.date_range('2024-01-01', periods=300, freq='15min')
        test_data = pd.DataFrame({
            'open': np.random.uniform(40000, 50000, 300),
            'high': np.random.uniform(50000, 52000, 300),
            'low': np.random.uniform(38000, 40000, 300),
            'close': np.random.uniform(40000, 50000, 300),
            'volume': np.random.uniform(100, 1000, 300)
        }, index=dates)
        
        # İndikatörleri hesapla
        result = self.bot.calculate_indicators(test_data.copy())
        
        # Kontroller
        self.assertIsNotNone(result)
        self.assertIn('ema200', result.columns)
        self.assertIn('atr', result.columns)
        self.assertIn('upper_band', result.columns)
        self.assertIn('macd', result.columns)
    
    def test_entry_conditions(self):
        """Giriş koşullarını test et"""
        # Test verisi oluştur (trend yukarı)
        test_data = pd.DataFrame({
            'close': [45000, 45100],
            'open': [44900, 45000],
            'high': [45200, 45300],
            'low': [44800, 44900],
            'ema200': [44000, 44000],
            'upper_band': [45150, 45200],
            'lower_band': [44000, 44000],
            'atr': [500, 500],
            'band_distance_vs_atr': [1.5, 1.5],
            'macd': [150, 150],
            'macd_hist': [10, 10]
        })
        
        signals = self.bot.check_entry_conditions(test_data)
        
        # Long sinyali olmalı
        self.assertIn('long', signals)
        self.assertIn('short', signals)
    
    def test_position_size_calculation(self):
        """Position size hesaplamasını test et"""
        with patch.object(self.bot.exchange, 'fetch_balance') as mock_balance:
            mock_balance.return_value = {'USDT': {'free': 10000}}
            
            entry_price = 45000
            stop_loss = 44000
            
            position_size = self.bot.calculate_position_size(entry_price, stop_loss)
            
            # Position size pozitif olmalı ve makul bir değerde
            self.assertGreater(position_size, 0)
            self.assertLess(position_size * entry_price, 1000)  # Max 1000 USDT

class SecurityTests(unittest.TestCase):
    def test_daily_limits(self):
        """Günlük limitleri test et"""
        from security_monitor import SecurityMonitor
        
        # Mock config ile SecurityMonitor oluştur
        with patch('builtins.open', unittest.mock.mock_open(read_data=json.dumps({
            'risk_management': {'max_daily_loss': 100, 'max_daily_trades': 3}
        }))):
            monitor = SecurityMonitor()
            
            # Test daily limits
            monitor.daily_trades = 2
            result, msg = monitor.check_daily_limits()
            self.assertTrue(result)
            
            monitor.daily_trades = 4
            result, msg = monitor.check_daily_limits()
            self.assertFalse(result)

# simple_test.py (Basit fonksiyonel test)
def test_basic_functionality():
    """Temel bot fonksiyonlarını test et"""
    print("🧪 Testing basic bot functionality...")
    
    # Config dosyası var mı?
    if os.path.exists('config.json'):
        print("✅ Config file found")
    else:
        print("❌ Config file missing")
        return False
    
    # Gerekli modüller import edilebiliyor mu?
    try:
        import pandas as pd
        import numpy as np
        import ccxt
        import talib
        print("✅ All required modules imported successfully")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    
    # Bot oluşturulabiliyor mu?
    try:
        from live_trading_bot import LiveTradingBot
        bot = LiveTradingBot()
        print("✅ Bot instance created successfully")
    except Exception as e:
        print(f"❌ Bot creation error: {e}")
        return False
    
    print("🎉 All basic tests passed!")
    return True

# paper_trading_test.py (Kağıt üzerinde trading testi)
class PaperTradingTest:
    def __init__(self):
        self.balance = 10000
        self.trades = []
        self.position = None
        
    def simulate_trading_day(self, price_data):
        """Bir günlük trading simülasyonu"""
        from live_trading_bot import LiveTradingBot
        
        # Bot'u test modunda oluştur
        bot = LiveTradingBot()
        bot.exchange = Mock()  # Mock exchange kullan
        
        for i, price in enumerate(price_data):
            # Basit test stratejisi
            if not self.position and price > price_data[max(0, i-1)] * 1.001:
                # Long pozisyon aç
                self.position = {
                    'side': 'long',
                    'entry_price': price,
                    'size': 1000 / price  # 1000 USDT worth
                }
                print(f"📈 Opened LONG at {price}")
            
            elif self.position and (
                price < self.position['entry_price'] * 0.99 or  # Stop loss
                price > self.position['entry_price'] * 1.02     # Take profit
            ):
                # Pozisyonu kapat
                profit = (price - self.position['entry_price']) * self.position['size']
                self.balance += profit
                
                self.trades.append({
                    'entry': self.position['entry_price'],
                    'exit': price,
                    'profit': profit
                })
                
                print(f"📉 Closed LONG at {price}, Profit: ${profit:.2f}")
                self.position = None
        
        return self.get_results()
    
    def get_results(self):
        """Test sonuçlarını döndür"""
        if not self.trades:
            return "No trades executed"
        
        total_profit = sum(trade['profit'] for trade in self.trades)
        win_rate = len([t for t in self.trades if t['profit'] > 0]) / len(self.trades) * 100
        
        return f"""
Paper Trading Results:
===================
Total Trades: {len(self.trades)}
Total Profit: ${total_profit:.2f}
Win Rate: {win_rate:.1f}%
Final Balance: ${self.balance:.2f}
        """

# deployment_checker.py (Deployment kontrol)
def check_deployment_readiness():
    """Deployment öncesi kontrol listesi"""
    checks = []
    
    # 1. Config dosyası kontrolü
    if os.path.exists('config.json'):
        with open('config.json', 'r') as f:
            config = json.load(f)
            
        if config.get('api_key') == 'YOUR_BINANCE_API_KEY_HERE':
            checks.append("❌ API key not set")
        else:
            checks.append("✅ API key configured")
            
        if config.get('sandbox', False):
            checks.append("⚠️  Sandbox mode enabled (good for testing)")
        else:
            checks.append("🚨 LIVE TRADING MODE - Double check everything!")
    else:
        checks.append("❌ config.json not found")
    
    # 2. Required files kontrolü
    required_files = [
        'live_trading_bot.py',
        'requirements.txt',
        'Dockerfile'
    ]
    
    for file in required_files:
        if os.path.exists(file):
            checks.append(f"✅ {file} exists")
        else:
            checks.append(f"❌ {file} missing")
    
    # 3. Database kontrolü
    if os.path.exists('trading_bot.db'):
        checks.append("ℹ️  Database file exists (will preserve trade history)")
    else:
        checks.append("ℹ️  Fresh database will be created")
    
    print("🔍 Deployment Readiness Check")
    print("=" * 40)
    for check in checks:
        print(check)
    
    # Genel değerlendirme
    errors = len([c for c in checks if c.startswith("❌")])
    if errors == 0:
        print("\n🎉 Ready for deployment!")
        return True
    else:
        print(f"\n⚠️  Please fix {errors} issue(s) before deployment")
        return False

# run_all_tests.py (Tüm testleri çalıştır)
def run_all_tests():
    """Tüm testleri çalıştırma scripti"""
    print("🚀 Running all tests...")
    print("=" * 50)
    
    # 1. Deployment readiness
    print("\n1️⃣ Checking deployment readiness...")
    check_deployment_readiness()
    
    # 2. Basic functionality
    print("\n2️⃣ Testing basic functionality...")
    test_basic_functionality()
    
    # 3. Paper trading simulation
    print("\n3️⃣ Running paper trading test...")
    paper_test = PaperTradingTest()
    
    # Generate random price data for test
    np.random.seed(42)
    prices = [45000]
    for i in range(100):
        change = np.random.normal(0, 0.002)  # 0.2% average change
        prices.append(prices[-1] * (1 + change))
    
    result = paper_test.simulate_trading_day(prices)
    print(result)
    
    # 4. Unit tests
    print("\n4️⃣ Running unit tests...")
    try:
        unittest.main(module='test_bot', exit=False, verbosity=2)
    except Exception as e:
        print(f"Unit test error: {e}")
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    run_all_tests()