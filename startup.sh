#!/bin/sh
set -e
mkdir -p /freqtrade/user_data/strategies

# Download config and strategy from GitHub
curl -sf "https://raw.githubusercontent.com/Dkpiec/freqtrade-atr-channel/2287b5b7c49910caf762b0eb9615ddca497a407d/config.json" -o /freqtrade/user_data/config.json
curl -sf "https://raw.githubusercontent.com/Dkpiec/freqtrade-atr-channel/2287b5b7c49910caf762b0eb9615ddca497a407d/user_data/strategies/ATR_CHANNEL_2H.py" -o /freqtrade/user_data/strategies/ATR_CHANNEL_2H.py

# Inject credentials into config
python3 -c "
import json, os
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
print('LIVE MODE:', 'YES' if not cfg.get('dry_run') else 'NO')
print('Binance key injected:', 'YES' if cfg['exchange']['key'] else 'NO')
"

# Patch CCXT at module level: find the installed binance.py and replace fapi URLs
# This ensures ALL CCXT calls (including get_leverage_tiers) use papi.binance.com
python3 << 'PYEOF'
import ccxt
import os

# Find where ccxt stores its URL definitions for binance
exchange = ccxt.binance()
print("Original fapi URL:", exchange.urls.get('api', {}).get('fapi', 'NOT FOUND'))

# Monkey-patch the class-level urls dict BEFORE any instance is created
# CCXT stores default URLs in ccxt.binance.urls (class attribute)
if hasattr(ccxt.binance, 'urls'):
    original_urls = ccxt.binance.urls.copy()
    if 'api' in original_urls:
        api_urls = original_urls['api'].copy() if isinstance(original_urls['api'], dict) else {}
        api_urls['fapi'] = 'https://papi.binance.com/papi'
        api_urls['dapi'] = 'https://papi.binance.com/papi'
        api_urls['sapi'] = 'https://papi.binance.com/papi'
        ccxt.binance.urls = {**original_urls, 'api': api_urls}
        print("Patched ccxt.binance.urls['api']['fapi'] -> https://papi.binance.com/papi")
    else:
        print("WARNING: 'api' not in ccxt.binance.urls")
else:
    print("WARNING: ccxt.binance has no 'urls' class attribute")

# Verify the patch
verify = ccxt.binance()
print("Verified fapi URL after patch:", verify.urls.get('api', {}).get('fapi', 'NOT FOUND'))
PYEOF

echo "Starting Freqtrade LIVE via papi.binance.com..."
exec freqtrade trade --config /freqtrade/user_data/config.json --strategy ATR_CHANNEL_2H --userdir /freqtrade/user_data

