#!/usr/bin/env python3
"""
Hybrid CCXT patch for Binance portfolio margin accounts.

Problem:
  - fapi.binance.com works for PUBLIC endpoints (exchangeInfo, klines, ticker)
  - fapi is BLOCKED for AUTHENTICATED endpoints on portfolio margin accounts
  - papi.binance.com/papi supports AUTHENTICATED endpoints but returns 404 on public market data

Solution:
  - Keep CCXT source URLs as fapi.binance.com (public market data works)
  - Monkey-patch CCXT's request handler to route AUTHENTICATED requests through papi
  - Detect auth by checking if the request is a private endpoint
"""

import ccxt
import re
import logging

log = logging.getLogger(__name__)

FAPI_BASE = "https://fapi.binance.com"
PAPI_BASE = "https://papi.binance.com/papi"

# Endpoints that require authentication (private endpoints)
PRIVATE_ENDPOINTS = re.compile(
    r"(?i)"
    r"(^/fapi/v1/(account|positionRisk|leverage|marginType|order|openOrders|myTrades|income|userTrades)"
    r"|^/fapi/v1/(changeLeverage|changeMarginMode|changePositionMode)"
    r"|^/fapi/v1/(countdown|compositeIndexPrice)"
    r"|^/fapi/v2/(account|positionRisk)"
    r"|^/fapi/v3/(account|positionRisk)"
    r")"
)


def patch_binance_hybrid():
    """Patch CCXT Binance to use hybrid fapi/papi routing."""
    try:
        binance_cls = ccxt.binance
        test_instance = binance_cls()
    except Exception as e:
        log.warning("Could not create CCXT binance instance: %s", e)
        return

    original_fetch = binance_cls.fetch

    def hybrid_fetch(self, path, api="public", method="GET", params=None, headers=None, body=None):
        """Route authenticated requests to papi, public requests to fapi."""
        # Determine if this is a private/authenticated endpoint
        is_private = (api == "private")
        
        # Check if the path matches known private endpoint patterns
        if path and PRIVATE_ENDPOINTS.search(path):
            is_private = True

        if is_private:
            # Rewrite the URL to use papi base for this request only
            urls = self.urls
            if "api" in urls and "fapi" in urls["api"]:
                original_url = urls["api"]["fapi"]
                urls["api"]["fapi"] = PAPI_BASE
                log.debug("Routing private request to papi: %s %s", method, path)
                try:
                    return original_fetch(self, path, api, method, params, headers, body)
                finally:
                    urls["api"]["fapi"] = original_url
            else:
                log.debug("No fapi URL found in urls, proceeding with default: %s %s", method, path)
                return original_fetch(self, path, api, method, params, headers, body)
        else:
            # Public endpoint - keep fapi (market data works fine)
            log.debug("Routing public request to fapi: %s %s", method, path)
            return original_fetch(self, path, api, method, params, headers, body)

    # Apply the patch to the class level so all instances benefit
    if not getattr(binance_cls, "_hybrid_patched", False):
        binance_cls.fetch = hybrid_fetch
        binance_cls._hybrid_patched = True
        log.info("CCXT hybrid papi/fapi patch applied to binance.fetch")
    else:
        log.info("CCXT hybrid patch already applied")


if __name__ == "__main__":
    patch_binance_hybrid()
    print("Hybrid CCXT patch applied successfully")
