#!/usr/bin/env python3
"""
CCXT papi-only patch for Binance portfolio margin accounts.

This API key ONLY works with papi.binance.com/papi — fapi is completely blocked.
We monkey-patch fetch() to rewrite ANY fapi URL to papi at request time,
ensuring leverage_tiers, account, positionRisk, and all other endpoints go through papi.
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
    """Patch CCXT Binance to use papi.binance.com/papi for ALL requests."""
    try:
        binance_cls = ccxt.binance
    except Exception as e:
        log.warning("Could not access ccxt.binance: %s", e)
        return

    original_fetch = binance_cls.fetch

    def patched_fetch(self, url, method="GET", headers=None, body=None):
        """Rewrite fapi URLs to papi before every request."""
        rewritten = _rewrite_url(url)
        if rewritten != url:
            log.debug("Rewriting fapi->papi: %s -> %s", url[:80], rewritten[:80])
        return original_fetch(self, rewritten, method, headers, body)

    if not getattr(binance_cls, "_papi_fetch_patched", False):
        binance_cls.fetch = patched_fetch
        binance_cls._papi_fetch_patched = True
        log.info("CCXT papi-only fetch patch applied: ALL fapi URLs rewritten to %s", PAPI_BASE)
    else:
        log.info("CCXT papi-only fetch patch already applied")

    # Also patch __init__ to set urls dict at construction time
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


if __name__ == "__main__":
    patch_binance_papi_only()
    print("CCXT papi-only patch applied successfully")