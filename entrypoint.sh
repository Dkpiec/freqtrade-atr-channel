#!/bin/sh
set -e
# Config and strategy are baked into /opt/freqtrade-custom/ by Dockerfile COPY
# Copy them to the runtime user_data directory
mkdir -p /freqtrade/user_data/strategies
cp /opt/freqtrade-custom/config.json /freqtrade/user_data/config.json
cp /opt/freqtrade-custom/ATR_CHANNEL_2H.py /freqtrade/user_data/strategies/ATR_CHANNEL_2H.py
echo "Files copied to /freqtrade/user_data/"
ls -la /freqtrade/user_data/config.json /freqtrade/user_data/strategies/ATR_CHANNEL_2H.py
# Run freqtrade with the original entrypoint
exec freqtrade trade --config /freqtrade/user_data/config.json --strategy ATR_CHANNEL_2H --userdir /freqtrade/user_data

