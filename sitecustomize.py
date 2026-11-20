"""
sitecustomize.py — loaded automatically by Python at interpreter startup,
BEFORE freqtrade or ccxt are imported. Patches ccxt.binance so that when
freqtrade later creates its Exchange instance, all methods are already patched.
"""
import logging

log = logging.getLogger("papi_patch")

FAPI_PREFIXES = [
    "https://fapi.binance.com",
    "https://fapi1.binance.com",
    "https://fapi2.binance.com",
    "https://fapi3.binance.com",
    "https://fapi4.binance.com",
]
PAPI_BASE = "https://papi.binance.com/papi"


def _rewrite_url(url):
    if not isinstance(url, str):
        return url
    for prefix in FAPI_PREFIXES:
        if url.startswith(prefix):
            return PAPI_BASE + url[len(prefix):]
    return url


try:
    import ccxt
except ImportError:
    log.warning("ccxt not importable in sitecustomize")
    raise SystemExit(0)

binance_cls = ccxt.binance

# 1. Patch fetch to rewrite fapi URLs to papi
_original_fetch = binance_cls.fetch

def _patched_fetch(self, url, method="GET", headers=None, body=None):
    rewritten = _rewrite_url(url)
    return _original_fetch(self, rewritten, method, headers, body)

binance_cls.fetch = _patched_fetch

# 2. Patch __init__ to set urls dict at construction time
_original_init = binance_cls.__init__

def _patched_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    if "api" in self.urls:
        for key in list(self.urls["api"].keys()):
            if "fapi" in key.lower():
                self.urls["api"][key] = PAPI_BASE
        self.urls["api"]["fapi"] = PAPI_BASE
        self.urls["api"]["fapi1"] = PAPI_BASE
        self.urls["api"]["fapi2"] = PAPI_BASE
        self.urls["api"]["fapi3"] = PAPI_BASE
        self.urls["api"]["fapi4"] = PAPI_BASE

binance_cls.__init__ = _patched_init

# 3. Mock fetchLeverageTiers — papi returns 404 on /v1/leverageBrackets
def _mock_fetch_leverage_tiers(self, symbols=None, params=None):
    log.info("fetchLeverageTiers mocked (papi incompatible)")
    return {}

binance_cls.fetchLeverageTiers = _mock_fetch_leverage_tiers

log.info("sitecustomize papi patch applied: fetch+init+fetchLeverageTiers patched on ccxt.binance")