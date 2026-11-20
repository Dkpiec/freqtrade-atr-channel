FROM freqtradeorg/freqtrade:stable

# Hybrid CCXT patch: fapi for public market data, papi for authenticated trading
# fapi is blocked for this portfolio margin account on AUTHENTICATED endpoints only.
# Public endpoints (exchangeInfo, klines, ticker) work fine on fapi.
# papi supports authenticated trading but NOT public market data endpoints.
# Solution: keep fapi URLs in CCXT source, monkey-patch at runtime to route
# authenticated requests through papi while keeping market data on fapi.
COPY start_freqtrade.py /freqtrade/start_freqtrade.py
COPY entrypoint.sh /freqtrade/entrypoint.sh
RUN chmod +x /freqtrade/entrypoint.sh /freqtrade/start_freqtrade.py && echo "Entrypoint + papi wrapper installed"

# Bake in config and strategy
COPY config.json /freqtrade/user_data/config.json
COPY user_data/strategies/ATR_CHANNEL_2H.py /freqtrade/user_data/strategies/ATR_CHANNEL_2H.py

ENTRYPOINT ["/freqtrade/entrypoint.sh"]

