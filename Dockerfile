# Freqtrade ATR_CHANNEL_2H — pinned to Python 3.11 via stable base image
# DO NOT upgrade to python:latest or freqtrade:develop — Freqtrade requires 3.11.x
FROM freqtradeorg/freqtrade:stable

# Copy custom strategy and config
COPY user_data/strategies/ATR_CHANNEL_2H.py /freqtrade/user_data/strategies/ATR_CHANNEL_2H.py
COPY config.json /freqtrade/config.json

# Default command: trade with our config
CMD ["trade", "--config", "/freqtrade/config.json", "--strategy", "ATR_CHANNEL_2H"]