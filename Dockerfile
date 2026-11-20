FROM freqtradeorg/freqtrade:stable
COPY config.b64 /opt/freqtrade-custom/config.b64
COPY strategy.b64 /opt/freqtrade-custom/strategy.b64
COPY entrypoint.sh /opt/freqtrade-custom/entrypoint.sh
RUN chmod +x /opt/freqtrade-custom/entrypoint.sh
ENTRYPOINT ["/opt/freqtrade-custom/entrypoint.sh"]

