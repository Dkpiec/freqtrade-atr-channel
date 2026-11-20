#!/bin/sh
set -e
echo "=== Patching CCXT source for papi.binance.com ==="
CCXT_DIR=$(python3 -c "import ccxt, os; print(os.path.dirname(ccxt.__file__))")
echo "CCXT installed at: $CCXT_DIR"
if [ -z "$CCXT_DIR" ] || [ ! -d "$CCXT_DIR" ]; then
    echo "ERROR: Could not determine CCXT directory"
    exit 1
fi
PATCHED=0
for f in $(grep -rl "fapi.binance.com" "$CCXT_DIR" --include="*.py" 2>/dev/null); do
    echo "Patching: $f"
    sed -i 's|https://fapi.binance.com|https://papi.binance.com/papi|g' "$f"
    sed -i 's|https://fapi1.binance.com|https://papi.binance.com/papi|g' "$f"
    sed -i 's|https://fapi2.binance.com|https://papi.binance.com/papi|g' "$f"
    sed -i 's|https://fapi3.binance.com|https://papi.binance.com/papi|g' "$f"
    sed -i 's|https://fapi4.binance.com|https://papi.binance.com/papi|g' "$f"
    PATCHED=$((PATCHED + 1))
done
echo "Patched $PATCHED files"
if grep -r "fapi.binance.com" "$CCXT_DIR/binance.py" >/dev/null 2>&1; then
    echo "WARNING: fapi references still present in binance.py!"
else
    echo "OK: All fapi references replaced in binance.py"
fi
echo "=== Setting up Freqtrade ==="
mkdir -p /freqtrade/user_data/strategies
curl -sf "https://raw.githubusercontent.com/Dkpiec/freqtrade-atr-channel/main/config.json" -o /freqtrade/user_data/config.json
curl -sf "https://raw.githubusercontent.com/Dkpiec/freqtrade-atr-channel/main/user_data/strategies/ATR_CHANNEL_2H.py" -o /freqtrade/user_data/strategies/ATR_CHANNEL_2H.py
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
echo "=== Starting Freqtrade LIVE (CCXT source patched to papi) ==="
exec freqtrade trade --config /freqtrade/user_data/config.json --strategy ATR_CHANNEL_2H --userdir /freqtrade/user_data

