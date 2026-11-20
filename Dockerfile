# Freqtrade ATR_CHANNEL_2H — pinned to Python 3.11 via stable base image
FROM freqtradeorg/freqtrade:stable

# Copy custom files to a staging directory (avoids overwriting container internals)
COPY config.json /opt/freqtrade-custom/config.json
COPY user_data/strategies/ATR_CHANNEL_2H.py /opt/freqtrade-custom/ATR_CHANNEL_2H.py
COPY entrypoint.sh /opt/freqtrade-custom/entrypoint.sh
RUN chmod +x /opt/freqtrade-custom/entrypoint.sh

ENTRYPOINT ["/opt/freqtrade-custom/entrypoint.sh"]

