FROM freqtradeorg/freqtrade:stable

# Hybrid CCXT patch: fapi for public market data, papi for authenticated trading
# fapi is blocked for this portfolio margin account on AUTHENTICATED endpoints only.
# Public endpoints (exchangeInfo, klines, ticker) work fine on fapi.
# papi supports authenticated trading but NOT public market data endpoints.
# Solution: keep fapi URLs in CCXT source, monkey-patch at runtime to route
# authenticated requests through papi while keeping market data on fapi.
COPY hybrid_ccxt_patch.py /freqtrade/hybrid_ccxt_patch.py
RUN echo "Hybrid CCXT patch installed (fapi=market data, papi=trading)"

# Bake in config and strategy
COPY config.json /freqtrade/user_data/config.json
COPY user_data/strategies/ATR_CHANNEL_2H.py /freqtrade/user_data/strategies/ATR_CHANNEL_2H.py

# Entrypoint: copy config to writable location, inject creds, apply hybrid patch, start freqtrade
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["cp /freqtrade/user_data/config.json /tmp/ft_config.json && chmod 666 /tmp/ft_config.json && python3 -c \"import json,os;cfg=json.load(open('/tmp/ft_config.json'));cfg['exchange']['key']=os.environ.get('BINANCE_API_KEY','');cfg['exchange']['secret']=os.environ.get('BINANCE_SECRET_KEY','');t=os.environ.get('FREQTRADE_TELEGRAM_TOKEN','');c=os.environ.get('FREQTRADE_TELEGRAM_CHAT_ID','');cfg['telegram']['token']=t if t else cfg['telegram']['token'];cfg['telegram']['chat_id']=c if c else cfg['telegram']['chat_id'];json.dump(cfg,open('/tmp/ft_config.json','w'),indent=4);print('LIVE:', 'YES' if not cfg.get('dry_run') else 'NO');print('Key injected:', 'YES' if cfg['exchange']['key'] else 'NO')\" && python3 /freqtrade/hybrid_ccxt_patch.py && exec freqtrade trade --config /tmp/ft_config.json --strategy ATR_CHANNEL_2H --userdir /freqtrade/user_data"]

