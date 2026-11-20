#!/bin/sh
set -e
mkdir -p /freqtrade/user_data/strategies

# Download config and strategy from GitHub
curl -sf "https://raw.githubusercontent.com/Dkpiec/freqtrade-atr-channel/COMMIT_HASH/config.json" -o /freqtrade/user_data/config.json
curl -sf "https://raw.githubusercontent.com/Dkpiec/freqtrade-atr-channel/COMMIT_HASH/user_data/strategies/ATR_CHANNEL_2H.py" -o /freqtrade/user_data/strategies/ATR_CHANNEL_2H.py

# Inject credentials and patch CCXT for papi.binance.com
python3 << 'PYEOF'
import json, os

# Patch config with credentials
with open('/freqtrade/user_data/config.json') as f:
    cfg = json.load(f)
cfg['exchange']['key'] = os.environ.get('BINANCE_API_KEY', '')
cfg['exchange']['secret'] = os.environ.get('BINANCE_SECRET_KEY', '')
tok = os.environ.get('FREQTRADE_TELEGRAM_TOKEN', '')
cid = os.environ.get('FREQTRADE_TELEGRAM_CHAT_ID', '')
if tok:
    cfg['telegram']['token'] = tok
if cid:
    cfg['telegram']['chat_id'] = cid
with open('/freqtrade/user_data/config.json', 'w') as f:
    json.dump(cfg, f, indent=4)

# Monkey-patch CCXT binance exchange to use papi.binance.com
import ccxt
original_init = ccxt.binance.__init__
def patched_init(self, config={}):
    original_init(self, config)
    if 'api' in self.urls:
        self.urls['api']['fapi'] = 'https://papi.binance.com/papi'
        self.urls['api']['dapi'] = 'https://papi.binance.com/papi'
        self.urls['api']['sapi'] = 'https://papi.binance.com/papi'
    print('CCXT patched: fapi/dapi/sapi -> papi.binance.com/papi')
ccxt.binance.__init__ = patched_init

print('LIVE MODE:', 'YES' if not cfg.get('dry_run') else 'NO')
print('Binance key injected:', 'YES' if cfg['exchange']['key'] else 'NO')
PYEOF

echo "Starting Freqtrade LIVE via papi.binance.com..."
exec freqtrade trade --config /freqtrade/user_data/config.json --strategy ATR_CHANNEL_2H --userdir /freqtrade/user_data

