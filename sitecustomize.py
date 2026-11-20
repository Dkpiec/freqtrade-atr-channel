"""
sitecustomize.py — loaded automatically by Python at interpreter startup,
BEFORE freqtrade or ccxt are imported. This ensures our patches are in place
when freqtrade creates its Exchange instance and binds CCXT methods.
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


def _apply_patches():
    try:
        import ccxt
    except ImportError:
        log.warning("ccxt not yet importable in sitecustomize, deferring")
        return

    binance_cls = ccxt.binance

    # 1. Patch fetch to rewrite fapi URLs to papi
    original_fetch = binance_cls.fetch

    def patched_fetch(self, url, method="GET", headers=None, body=None):
        rewritten = _rewrite_url(url)
        if rewritten != url:
            log.debug("Rewriting fapi->papi: %s", url[:80])
        return original_fetch(self, rewritten, method, headers, body)

    if not getattr(binance_cls, "_papi_fetch_patched", False):
        binance_cls.fetch = patched_fetch
        binance_cls._papi_fetch_patched = True

    # 2. Patch __init__ to set urls dict
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

    # 3. Mock fetchLeverageTiers on ccxt.binance
    def mock_fetch_leverage_tiers(self, symbols=None, params=None):
        log.info("fetchLeverageTiers mocked (papi incompatible)")
        return {}

    if not getattr(binance_cls, "_papi_flt_mocked", False):
        binance_cls.fetchLeverageTiers = mock_fetch_leverage_tiers
        binance_cls._papi_flt_mocked = True

    # 4. Patch freqtrade.Exchange.get_leverage_tiers if available
    try:
        from freqtrade.exchange import Exchange as FtExchange

        def mock_glt_ft(self, symbols=None):
            log.info("freqtrade.Exchange.get_leverage_tiers mocked")
            return {}

        if not getattr(FtExchange, "_papi_glt_mocked", False):
            FtExchange.get_leverage_tiers = mock_glt_ft
            FtExchange._papi_glt_mocked = True
    except ImportError:
        pass  # freqtrade not yet imported; will be patched via import hook below

    log.info("sitecustomize papi patch applied successfully")


# Register an import hook to patch freqtrade when it's first imported
import sys

class _FreqtradePatchFinder:
    """Import hook that patches freqtrade.exchange after it loads."""
    def find_module(self, fullname, path=None):
        if fullname == "freqtrade.exchange.exchange":
            return self
        return None

    def load_module(self, fullname):
        # Remove ourselves to avoid recursion
        sys.meta_path.remove(self)
        # Let the normal import happen
        mod = __import__(fullname, fromlist=[""])
        # Now patch
        try:
            if hasattr(mod, "Exchange"):
                Exch = mod.Exchange

                def mock_glt(self, symbols=None):
                    log.info("freqtrade.Exchange.get_leverage_tiers mocked (via import hook)")
                    return {}

                if not getattr(Exch, "_papi_glt_mocked", False):
                    Exch.get_leverage_tiers = mock_glt
                    Exch._papi_glt_mocked = True
                    log.info("Import hook: patched freqtrade.Exchange.get_leverage_tiers")
        except Exception as e:
            log.warning("Import hook patch failed: %s", e)
        return mod


_apply_patches()
sys.meta_path.insert(0, _FreqtradePatchFinder())