#!/bin/bash
set -e

# Copy config to writable location
cp /freqtrade/user_data/config.json /tmp/ft_config.json
chmod 666 /tmp/ft_config.json

# Inject credentials from environment variables
python3 -c "
import json, os
cfg = json.load(open('/tmp/ft_config.json'))
cfg['exchange']['key'] = os.environ.get('BINANCE_API_KEY', '')
cfg['exchange']['secret'] = os.environ.get('BINANCE_SECRET_KEY', '')
t = os.environ.get('FREQTRADE_TELEGRAM_TOKEN', '')
c = os.environ.get('FREQTRADE_TELEGRAM_CHAT_ID', '')
cfg['telegram']['token'] = t if t else cfg['telegram']['token']
cfg['telegram']['chat_id'] = c if c else cfg['telegram']['chat_id']
json.dump(cfg, open('/tmp/ft_config.json', 'w'), indent=4)
print('LIVE:', 'YES' if not cfg.get('dry_run') else 'NO')
print('Key injected:', 'YES' if cfg['exchange']['key'] else 'NO')
"

# Start freqtrade via the in-process papi wrapper
exec python3 /freqtrade/start_freqtrade.py \
    --config /tmp/ft_config.json \
    --strategy ATR_CHANNEL_2H \
    --userdir /freqtrade/user_data