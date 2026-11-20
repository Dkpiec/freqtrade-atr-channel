#!/usr/bin/env python3
"""
CCXT papi-only patch for Binance portfolio margin accounts.

This API key ONLY works with papi.binance.com/papi — fapi is completely blocked.
papi does NOT support leverageBrackets (returns 404), so we:
1. Rewrite all fapi URLs to papi at fetch level
2. Patch freqtrade.exchange.common.api_retry_call to skip get_leverage_tiers entirely
"""

import ccxt
import logging

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
    """Patch CCXT Binance and freqtrade for papi-only operation."""
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

    # 3. Patch freqtrade.exchange.common.api_retry_call to skip get_leverage_tiers
    # This is the actual retry wrapper that calls get_leverage_tiers and logs the error
    try:
        import freqtrade.exchange.common as ft_common
        
        original_api_retry = getattr(ft_common, 'api_retry_call', None)
        
        def patched_api_retry_call(func, *args, **kwargs):
            func_name = getattr(func, '__name__', str(func))
            if 'leverage_tier' in func_name.lower():
                log.info("Skipping get_leverage_tiers via api_retry_call patch (papi incompatible)")
                return {}
            if original_api_retry:
                return original_api_retry(func, *args, **kwargs)
            return func(*args, **kwargs)
        
        if not getattr(ft_common, '_papi_retry_patched', False):
            ft_common.api_retry_call = patched_api_retry_call
            ft_common._papi_retry_patched = True
            log.info("freqtrade.exchange.common.api_retry_call patched to skip leverage_tiers")
    except ImportError:
        log.warning("Could not import freqtrade.exchange.common")
    except Exception as e:
        log.warning("Failed to patch api_retry_call: %s", e)

    # 4. Also patch the Exchange class method directly as fallback
    try:
        from freqtrade.exchange import Exchange as FtExchange
        
        def mock_get_leverage_tiers_ft(self, symbols=None):
            log.info("freqtrade.Exchange.get_leverage_tiers mocked (papi incompatible)")
            return {}
        
        if not getattr(FtExchange, "_papi_leverage_mocked", False):
            FtExchange.get_leverage_tiers = mock_get_leverage_tiers_ft
            FtExchange._papi_leverage_mocked = True
            log.info("freqtrade.Exchange.get_leverage_tiers mocked")
    except ImportError:
        pass
    except Exception as e:
        log.debug("Could not patch FtExchange: %s", e)

    log.info("CCXT papi-only patch complete: ALL requests -> %s", PAPI_BASE)


if __name__ == "__main__":
    patch_binance_papi_only()
    print("CCXT papi-only patch applied successfully")