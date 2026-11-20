FROM freqtradeorg/freqtrade:stable

# NOTE: papi.binance.com does NOT support market data endpoints (exchangeInfo, klines, etc.)
# Portfolio margin accounts work fine via standard fapi.binance.com — no patch needed.
# Previous papi patch removed 2026-11-20 after confirming 404 on all trading endpoints.
RUN echo "Using default fapi.binance.com endpoints (papi incompatible with CCXT market loading)"

# Bake in config and strategy
COPY config.json /freqtrade/user_data/config.json
COPY user_data/strategies/ATR_CHANNEL_2H.py /freqtrade/user_data/strategies/ATR_CHANNEL_2H.py

# Entrypoint injects credentials from env vars at runtime
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["python3 -c \"import json,os;cfg=json.load(open('/freqtrade/user_data/config.json'));cfg['exchange']['key']=os.environ.get('BINANCE_API_KEY','');cfg['exchange']['secret']=os.environ.get('BINANCE_SECRET_KEY','');t=os.environ.get('FREQTRADE_TELEGRAM_TOKEN','');c=os.environ.get('FREQTRADE_TELEGRAM_CHAT_ID','');cfg['telegram']['token']=t if t else cfg['telegram']['token'];cfg['telegram']['chat_id']=c if c else cfg['telegram']['chat_id'];json.dump(cfg,open('/freqtrade/user_data/config.json','w'),indent=4);print('LIVE:', 'YES' if not cfg.get('dry_run') else 'NO');print('Key injected:', 'YES' if cfg['exchange']['key'] else 'NO')\" && exec freqtrade trade --config /freqtrade/user_data/config.json --strategy ATR_CHANNEL_2H --userdir /freqtrade/user_data"]

