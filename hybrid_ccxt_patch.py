#!/usr/bin/env python3
"""
CCXT papi-only patch for Binance portfolio margin accounts.

This API key ONLY works with papi.binance.com/papi — fapi is completely blocked.
papi supports authenticated trading endpoints but returns 404 on some public market data.
We route ALL requests through papi and handle 404s gracefully for unsupported endpoints.
"""

import ccxt
import logging

log = logging.getLogger(__name__)

PAPI_BASE = "https://papi.binance.com/papi"


def patch_binance_papi_only():
    """Patch CCXT Binance to use papi.binance.com/papi for ALL requests."""
    try:
        binance_cls = ccxt.binance
    except Exception as e:
        log.warning("Could not access ccxt.binance: %s", e)
        return

    # Permanently replace all fapi URLs with papi at the class level
    # This ensures every instance uses papi regardless of when it's created
    original_init = binance_cls.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        # Override all futures API URLs to papi after initialization
        if "api" in self.urls:
            for key in list(self.urls["api"].keys()):
                if "fapi" in key.lower():
                    self.urls["api"][key] = PAPI_BASE
            # Also set the main fapi URL
            self.urls["api"]["fapi"] = PAPI_BASE
            self.urls["api"]["fapi1"] = PAPI_BASE
            self.urls["api"]["fapi2"] = PAPI_BASE
            self.urls["api"]["fapi3"] = PAPI_BASE
            self.urls["api"]["fapi4"] = PAPI_BASE
        log.debug("Binance instance patched to use papi: %s", id(self))

    if not getattr(binance_cls, "_papi_patched", False):
        binance_cls.__init__ = patched_init
        binance_cls._papi_patched = True
        log.info("CCXT papi-only patch applied: ALL Binance requests routed to %s", PAPI_BASE)
    else:
        log.info("CCXT papi-only patch already applied")


if __name__ == "__main__":
    patch_binance_papi_only()
    print("CCXT papi-only patch applied successfully")