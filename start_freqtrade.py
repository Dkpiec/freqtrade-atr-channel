#!/usr/bin/env python3
"""
Freqtrade startup wrapper that applies papi-only CCXT patches
IN THE SAME PROCESS before freqtrade initializes its Exchange.
This avoids the cross-process mocking issue where standalone
patch scripts can't affect freqtrade's bound method references.
"""
import sys
import os
import logging
import json

log = logging.getLogger("papi_wrapper")

# ── 1. Apply CCXT papi patches BEFORE importing freqtrade ──
FAPI_PREFIXES = [
    "https://fapi.binance.com",
    "https://fapi1.binance.com",
    "https://fapi2.binance.com",
    "https://fapi3.binance.com",
    "https://fapi4.binance.com",
]
PAPI_BASE = "https://papi.binance.com/papi/v1"

def _rewrite_url(url):
    if not isinstance(url, str):
        return url
    for prefix in FAPI_PREFIXES:
        if url.startswith(prefix):
            return PAPI_BASE + url[len(prefix):]
    return url

import ccxt
binance_cls = ccxt.binance

# Endpoints that papi does not serve — match BOTH fapi and papi paths
_PAPI_INCOMPATIBLE_SUFFIXES = [
    "positionSide/dual",
    "multiAssetsMargin",
    "leverageBracket",
    "positionRisk",
]
_PAPI_MOCK_RESPONSES = {
    "positionSide/dual": {"dualSidePosition": False},
    "multiAssetsMargin": {"multiAssetsMargin": False},
    "leverageBracket": [],
    "positionRisk": [],
}

# Patch fetch
_original_fetch = binance_cls.fetch
def _patched_fetch(self, url, method="GET", headers=None, body=None):
    # Check both original and rewritten URL for incompatible endpoints
    from urllib.parse import urlparse
    for check_url in [url, _rewrite_url(url)]:
        parsed = urlparse(check_url)
        for suffix in _PAPI_INCOMPATIBLE_SUFFIXES:
            if parsed.path.endswith(suffix):
                mock_resp = _PAPI_MOCK_RESPONSES.get(suffix, {})
                log.info(f"Mocked incompatible endpoint: {suffix} (url={check_url[:80]})")
                return mock_resp
    rewritten = _rewrite_url(url)
    log.debug(f"papi_fetch: {method} {url[:100]} -> {rewritten[:100]}")
    result = _original_fetch(self, rewritten, method, headers, body)
    # Transform papi account response to standard CCXT balance format
    if 'account' in rewritten and isinstance(result, dict) and 'accountEquity' in result:
        equity = float(result.get('accountEquity', 0))
        init_margin = float(result.get('accountInitialMargin', 0))
        free = equity - init_margin
        log.info(f"papi account transformed: equity={equity}, used={init_margin}, free={free}")
        result = {
            'info': result,
            'USDT': {'free': free, 'used': init_margin, 'total': equity},
            'free': {'USDT': free},
            'used': {'USDT': init_margin},
            'total': {'USDT': equity},
        }
    return result
binance_cls.fetch = _patched_fetch

# Patch __init__ urls
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

# Mock fetchLeverageTiers on ccxt.binance
def _mock_flt(self, symbols=None, params=None):
    log.info("ccxt.binance.fetchLeverageTiers mocked (papi incompatible)")
    return {}
binance_cls.fetchLeverageTiers = _mock_flt

log.info("CCXT papi patches applied (fetch + init + fetchLeverageTiers + account transform)")

# ── 2. Now import freqtrade and patch its Exchange wrapper ──
from freqtrade.exchange import Exchange as FtExchange

def _mock_glt(self, symbols=None):
    log.info("freqtrade.Exchange.get_leverage_tiers mocked (papi incompatible)")
    return {}
FtExchange.get_leverage_tiers = _mock_glt
log.info("freqtrade.Exchange.get_leverage_tiers mocked")

# Discover and patch the correct Wallets update method
from freqtrade.wallets import Wallets as FtWallets
_wallet_methods = [m for m in dir(FtWallets) if not m.startswith('__')]
log.info(f"Wallets methods available: {_wallet_methods}")

# Try common method names for wallet updates
for method_name in ['update', 'get_all_balances', 'get_free', 'get_used', 'get_total', '_update', 'sync']:
    if hasattr(FtWallets, method_name):
        log.info(f"Found Wallets.{method_name} — will patch this")
        break
else:
    log.warning("No known wallet update method found; listing all public methods for debugging")

# Patch the 'update' method if it exists (most likely candidate)
if hasattr(FtWallets, 'update'):
    _original_wallet_update = FtWallets.update
    def _patched_wallet_update(self, *args, **kwargs):
        result = _original_wallet_update(self, *args, **kwargs)
        # After normal update, check if USDT balance is zero and inject papi data
        try:
            balances = self.get_all_balances() if hasattr(self, 'get_all_balances') else {}
            usdt_total = balances.get('USDT', {}).get('total', 0) if isinstance(balances.get('USDT'), dict) else 0
            if usdt_total == 0:
                exchange_obj = getattr(self, '_exchange', None) or getattr(self, 'exchange', None)
                ccxt_ex = getattr(exchange_obj, '_ccxt_exchange', None) or getattr(exchange_obj, 'exchange', None) if exchange_obj else None
                if ccxt_ex and hasattr(ccxt_ex, 'fetch') and hasattr(ccxt_ex, 'urls'):
                    account_data = ccxt_ex.fetch(ccxt_ex.urls['api']['fapi'] + '/account')
                    if isinstance(account_data, dict) and 'USDT' in account_data:
                        log.info(f"Wallets.update injecting papi USDT: {account_data['USDT']}")
                        # Store in internal wallets dict
                        if hasattr(self, '_wallets') and 'USDT' in self._wallets:
                            w = self._wallets['USDT']
                            w.total = float(account_data['USDT'].get('total', 0))
                            w.free = float(account_data['USDT'].get('free', 0))
                            w.used = float(account_data['USDT'].get('used', 0))
        except Exception as e:
            log.warning(f"Wallets.update papi injection failed: {e}")
        return result
    FtWallets.update = _patched_wallet_update
    log.info("freqtrade.Wallets.update patched for papi balance injection")
else:
    log.warning("Wallets.update not found — balance injection skipped")

# ── 3. Start freqtrade normally ──
# Prepend 'trade' subcommand since entrypoint passes --config/--strategy directly
from freqtrade.main import main
sys.argv.insert(1, 'trade')
sys.exit(main())