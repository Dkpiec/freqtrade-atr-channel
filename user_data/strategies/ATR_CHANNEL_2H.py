"""ATR_CHANNEL_2H — Freqtrade IStrategy port of V4 Ultra ATR_CHANNEL_2H.

Source: /opt/data/trading-engine/binance_v4_ultra/v4_ultra_strategy.py
Validated config (2026-11-18): PF 3.70, 55% WR, MDD 28.7% on 15-symbol 2H futures.

Logic:
  - 2H Wilder ATR(14)
  - Exclusive 40-bar Donchian channel (shift(1) so current bar is excluded)
  - Entry: close breaks upper band (hh + 1.5*ATR) for longs,
           lower band (ll - 1.5*ATR) for shorts
  - Daily trend gate: EMA10/20 on 1D informative pair
      long  allowed only when daily_close > EMA20 AND EMA10 > EMA20
      short allowed only when daily_close < EMA20 AND EMA10 < EMA20
  - SL = 1.0 * ATR(14) from entry
  - TP = 4.0R (single full target, no partials)
  - Leverage cap 5x; risk sizing 10% of equity per trade
  - Time exit at 120 bars (240h)
"""

from datetime import datetime, timedelta, timezone
from functools import reduce
from typing import Optional

import numpy as np
import pandas as pd
from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter,
    merge_informative_pair,
)


class ATR_CHANNEL_2H(IStrategy):
    """Freqtrade port of V4 Ultra ATR_CHANNEL_2H."""

    INTERFACE_VERSION = 3

    # --- Core timeframe ---
    timeframe = "2h"

    # --- Informative pairs (daily trend gate) ---
    def informative_pairs(self):
        return [(pair, "1d") for pair in self.config["exchange"]["pair_whitelist"]]

    # --- Disable built-in ROI; exits handled via custom_exit + custom_stoploss ---
    minimal_roi = {"0": 100}  # effectively disabled

    # --- Stoploss (backstop only; real SL via custom_stoploss) ---
    stoploss = -0.99

    # --- Leverage ---
    leverage_multiplier = 5.0

    # --- Strategy parameters (exposed for hyperopt but pinned to validated values) ---
    chan_lookback = IntParameter(20, 60, default=40, space="buy", optimize=False)
    atr_period = IntParameter(10, 20, default=14, space="buy", optimize=False)
    atr_mult = DecimalParameter(1.0, 2.5, default=1.5, decimals=1, space="buy", optimize=False)
    sl_atr_mult = DecimalParameter(0.5, 2.0, default=1.0, decimals=1, space="sell", optimize=False)
    tp_r = DecimalParameter(2.0, 6.0, default=4.0, decimals=1, space="sell", optimize=False)
    max_hold_bars = IntParameter(60, 200, default=120, space="sell", optimize=False)

    # --- Risk sizing constants ---
    BASE_RISK_PCT = 0.10       # 10% of equity per trade
    LEVERAGE_CAP = 5.0         # max notional = equity * 5 / 2

    # ------------------------------------------------------------------
    # Indicators
    # ------------------------------------------------------------------
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        df = dataframe.copy()

        # --- Wilder ATR(14) ---
        high, low, close = df["high"], df["low"], df["close"]
        pc = close.shift(1)
        tr = pd.concat([
            (high - low),
            (high - pc).abs(),
            (low - pc).abs(),
        ], axis=1).max(axis=1)
        alpha = 1.0 / self.atr_period.value
        df["atr"] = tr.ewm(alpha=alpha, adjust=False).mean()

        # --- Exclusive Donchian channel (prior CHAN_LOOKBACK bars, excluding current) ---
        lb = self.chan_lookback.value
        df["hh"] = high.shift(1).rolling(lb).max()
        df["ll"] = low.shift(1).rolling(lb).min()

        # --- Channel bands ---
        atr_m = self.atr_mult.value
        df["upper_band"] = df["hh"] + atr_m * df["atr"]
        df["lower_band"] = df["ll"] - atr_m * df["atr"]

        return df

    # ------------------------------------------------------------------
    # Daily trend gate via informative 1D pair
    # ------------------------------------------------------------------
    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        df = dataframe.copy()

        # Merge 1D informative data
        pair = metadata["pair"]
        inf = self.dp.get_pair_dataframe(pair, "1d")
        if inf is not None and len(inf) >= 20:
            inf = inf.copy()
            c = inf["close"]
            inf["ema10"] = c.ewm(span=10, adjust=False).mean()
            inf["ema20"] = c.ewm(span=20, adjust=False).mean()
            # Use last fully closed daily candle (shift to avoid lookahead)
            inf["daily_close"] = c.shift(1)
            inf["daily_ema10"] = inf["ema10"].shift(1)
            inf["daily_ema20"] = inf["ema20"].shift(1)
            inf["trend_up"] = (
                (inf["daily_close"] > inf["daily_ema20"]) &
                (inf["daily_ema10"] > inf["daily_ema20"])
            ).astype(int)
            inf["trend_down"] = (
                (inf["daily_close"] < inf["daily_ema20"]) &
                (inf["daily_ema10"] < inf["daily_ema20"])
            ).astype(int)
            # Forward-fill daily trend onto 2H bars via merge_asof
            inf = inf[["date", "trend_up", "trend_down"]].dropna(subset=["date"])
            df = pd.merge_asof(
                df.sort_values("date"),
                inf.sort_values("date"),
                on="date",
                direction="backward",
            )
        else:
            df["trend_up"] = 0
            df["trend_down"] = 0

        # --- Long signal: close > upper_band AND daily trend up ---
        long_cond = (
            (df["close"] > df["upper_band"]) &
            (df["trend_up"] == 1) &
            (df["atr"] > 0) &
            (df["hh"].notna()) &
            (df["ll"].notna())
        )

        # --- Short signal: close < lower_band AND daily trend down ---
        short_cond = (
            (df["close"] < df["lower_band"]) &
            (df["trend_down"] == 1) &
            (df["atr"] > 0) &
            (df["hh"].notna()) &
            (df["ll"].notna())
        )

        df["enter_long"] = long_cond.astype(int)
        df["enter_short"] = short_cond.astype(int)
        df["exit_long"] = 0
        df["exit_short"] = 0

        return df

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Exits handled by custom_stoploss + custom_exit; no signal-based exits.
        df = dataframe.copy()
        df["exit_long"] = 0
        df["exit_short"] = 0
        return df

    # ------------------------------------------------------------------
    # Custom stoploss: SL = sl_atr_mult * ATR from entry
    # ------------------------------------------------------------------
    def custom_stoploss(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float:
        """Return stoploss as a negative fraction of current_rate.

        Freqtrade calls this every iteration. We compute the absolute SL price
        from the stored entry ATR, then convert to a relative distance from
        current_rate so the exchange-side stop tracks correctly.
        """
        atr = trade.entry_extra.get("atr") if hasattr(trade, "entry_extra") else None
        if atr is None or atr <= 0:
            return self.stoploss  # fall back to backstop

        sl_dist = self.sl_atr_mult.value * atr

        if trade.is_short:
            sl_price = trade.open_rate + sl_dist
            # For shorts, stoploss is above entry; return positive relative dist
            # Freqtrade expects negative for below-rate stops on longs,
            # but for shorts the sign convention is inverted internally.
            rel = (sl_price - current_rate) / current_rate
            return -rel  # negate so freqtrade treats it as a valid stop distance
        else:
            sl_price = trade.open_rate - sl_dist
            rel = (current_rate - sl_price) / current_rate
            return -rel

    # ------------------------------------------------------------------
    # Custom exit: TP at tp_r * R, time exit at max_hold_bars
    # ------------------------------------------------------------------
    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:
        atr = trade.entry_extra.get("atr") if hasattr(trade, "entry_extra") else None
        if atr is None or atr <= 0:
            return None

        sl_dist = self.sl_atr_mult.value * atr
        if sl_dist <= 0:
            return None

        # Compute R-multiple
        if trade.is_short:
            r_mult = (trade.open_rate - current_rate) / sl_dist
        else:
            r_mult = (current_rate - trade.open_rate) / sl_dist

        # TP at tp_r R
        if r_mult >= self.tp_r.value:
            return f"tp_{self.tp_r.value}r"

        # Time exit
        bars_held = int((current_time - trade.open_date_utc).total_seconds() // (2 * 3600))
        if bars_held >= self.max_hold_bars.value:
            return f"time_exit_{bars_held}bars"

        return None

    # ------------------------------------------------------------------
    # Position sizing: 10% equity risk, capped at 5x leverage
    # ------------------------------------------------------------------
    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: Optional[float],
        max_stake: float,
        leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        """Override stake to enforce 10%-equity risk sizing with 5x leverage cap."""
        # Get current wallet balance (equity proxy)
        try:
            wallet = self.wallets.get_total("USDT")
        except Exception:
            return proposed_stake

        if wallet <= 0:
            return proposed_stake

        # Fetch latest ATR for this pair
        df = self.dp.get_pair_dataframe(pair, self.timeframe)
        if df is None or df.empty or "atr" not in df.columns:
            return proposed_stake
        atr = df["atr"].iloc[-1]
        if pd.isna(atr) or atr <= 0:
            return proposed_stake

        sl_dist = self.sl_atr_mult.value * atr
        if sl_dist <= 0 or current_rate <= 0:
            return proposed_stake

        # Risk-based quantity
        risk_usdt = wallet * self.BASE_RISK_PCT
        qty = risk_usdt / sl_dist
        notional = qty * current_rate

        # Leverage cap: max notional = equity * LEVERAGE_CAP / 2
        max_notional = (wallet * self.LEVERAGE_CAP) / 2.0
        if notional > max_notional:
            qty = max_notional / current_rate
            notional = qty * current_rate

        # Respect exchange min/max
        if min_stake and notional < min_stake:
            notional = min_stake
        if notional > max_stake:
            notional = max_stake

        return notional

    # ------------------------------------------------------------------
    # Leverage callback
    # ------------------------------------------------------------------
    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        return min(self.LEVERAGE_CAP, max_leverage)

    # ------------------------------------------------------------------
    # Store ATR in trade extra for SL/TP calculations
    # ------------------------------------------------------------------
    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> bool:
        # Tag the trade with current ATR for custom_stoploss/custom_exit
        df = self.dp.get_pair_dataframe(pair, self.timeframe)
        if df is not None and not df.empty and "atr" in df.columns:
            atr_val = float(df["atr"].iloc[-1])
            if not pd.isna(atr_val) and atr_val > 0:
                kwargs.setdefault("extra", {})["atr"] = atr_val
        return True