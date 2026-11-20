#!/usr/bin/env python3
"""
CCXT papi-only patch for Binance portfolio margin accounts.

This API key ONLY works with papi.binance.com/papi — fapi is completely blocked.
papi does NOT support leverageBrackets (returns 404), so we:
1. Mock get_leverage_tiers on ccxt.binance AND freqtrade.exchange.Exchange
2. Disable leverage tier loading in freqtrade config if possible
3. Rewrite all fapi URLs to papi at fetch level
"""

import ccxt
import logging
import sys

log = logging.getLogger(__name__)

FAPI_PREFIXES = [
    "https://fapi.binance.com",
    "https://fapi1.binance.com",
    "https://fapi2.binance.com",
    "https://fapi3.binance.com",
    "https://fapi4.binance.com",
]
PAPI_BASE = "https://papi.binance.com/papi"

def _rewrite_url(url):
    """Replace any fapi base URL with papi."""
    if not isinstance(url, str):
        return url
    for prefix in FAPI_PREFIXES:
        if url.startswith(prefix):
            return PAPI_BASE + url[len(prefix):]
    return url

def patch_binance_papi_only():
    """Patch CCXT Binance and freqtrade Exchange for papi-only operation."""
    try:
        binance_cls = ccxt.binance
    except Exception as e:
        log.warning("Could not access ccxt.binance: %s", e)
        return

    # 1. Patch fetch to rewrite fapi URLs to papi at request time
    original_fetch = binance_cls.fetch

    def patched_fetch(self, url, method="GET", headers=None, body=None):
        rewritten = _rewrite_url(url)
        if rewritten != url:
            log.debug("Rewriting fapi->papi: %s -> %s", url[:80], rewritten[:80])
        return original_fetch(self, rewritten, method, headers, body)

    if not getattr(binance_cls, "_papi_fetch_patched", False):
        binance_cls.fetch = patched_fetch
        binance_cls._papi_fetch_patched = True
        log.info("CCXT papi-only fetch patch applied")

    # 2. Patch __init__ to set urls dict at construction time
    original_init = binance_cls.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        if "api" in self.urls:
            for key in list(self.urls["api"].keys()):
                if "fapi" in key.lower():
                    self.urls["api"][key] = PAPI_BASE
            self.urls["api"]["fapi"] = PAPI_BASE
            self.urls["api"]["fapi1"] = PAPI_BASE
            self.urls["api"]["fapi2"] = PAPI_BASE
            self.urls["api"]["fapi3"] = PAPI_BASE
            self.urls["api"]["fapi4"] = PAPI_BASE

    if not getattr(binance_cls, "_papi_init_patched", False):
        binance_cls.__init__ = patched_init
        binance_cls._papi_init_patched = True
        log.info("CCXT papi-only init patch applied")

    # 3. Mock get_leverage_tiers on ccxt.binance
    def mock_get_leverage_tiers_ccxt(self, symbols=None):
        log.info("ccxt.binance.get_leverage_tiers mocked (papi incompatible)")
        return {}

    if not getattr(binance_cls, "_papi_leverage_mocked", False):
        binance_cls.get_leverage_tiers = mock_get_leverage_tiers_ccxt
        binance_cls._papi_leverage_mocked = True
        log.info("ccxt.binance.get_leverage_tiers mocked")

    # 4. Mock get_leverage_tiers on freqtrade's Exchange wrapper
    try:
        from freqtrade.exchange import Exchange as FtExchange
        
        # Store original if not already stored
        if not hasattr(FtExchange, '_original_get_leverage_tiers'):
            FtExchange._original_get_leverage_tiers = getattr(FtExchange, 'get_leverage_tiers', None)

        def mock_get_leverage_tiers_ft(self, symbols=None):
            log.info("freqtrade.Exchange.get_leverage_tiers mocked (papi incompatible)")
            return {}

        if not getattr(FtExchange, "_papi_leverage_mocked", False):
            FtExchange.get_leverage_tiers = mock_get_leverage_tiers_ft
            FtExchange._papi_leverage_mocked = True
            log.info("freqtrade.Exchange.get_leverage_tiers mocked")
    except ImportError:
        log.warning("Could not import freqtrade.exchange.Exchange")
    except Exception as e:
        log.warning("Failed to patch freqtrade.Exchange: %s", e)

    # 5. Monkey-patch the specific instance method if freqtrade is already running
    # This catches cases where the class patch didn't apply to an existing instance
    try:
        import freqtrade.exchange.exchange as ft_ex_module
        if hasattr(ft_ex_module, 'Exchange'):
            # Patch any existing instances in memory
            import gc
            for obj in gc.get_objects():
                if isinstance(obj, ft_ex_module.Exchange):
                    if hasattr(obj, 'get_leverage_tiers') and not getattr(obj, '_papi_instance_mocked', False):
                        obj.get_leverage_tiers = lambda symbols=None: (log.info("Instance get_leverage_tiers mocked"), {})[1]
                        obj._papi_instance_mocked = True
                        log.info("Patched existing freqtrade Exchange instance")
    except Exception as e:
        log.debug("Could not patch existing instances: %s", e)

    log.info("CCXT papi-only patch complete: ALL requests -> %s", PAPI_BASE)

if __name__ == "__main__":
    patch_binance_papi_only()
    print("CCXT papi-only patch applied successfully")