#!/bin/sh
set -e
mkdir -p /freqtrade/user_data/strategies
base64 -d /opt/freqtrade-custom/config.b64 > /freqtrade/user_data/config.json
base64 -d /opt/freqtrade-custom/strategy.b64 > /freqtrade/user_data/strategies/ATR_CHANNEL_2H.py
echo "Files decoded and written successfully"
ls -la /freqtrade/user_data/config.json /freqtrade/user_data/strategies/ATR_CHANNEL_2H.py
exec freqtrade trade --config /freqtrade/user_data/config.json --strategy ATR_CHANNEL_2H --userdir /freqtrade/user_data

