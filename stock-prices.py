"""
title: OpenWebUI Stock Prices from Yahoo Finance
author: Rick Gouin
author_url: https://rickgouin.com
version: 1.0
license: GPL v3
description: Fetch live-ish stock quotes and recent OHLCV history from Yahoo Finance.
requirements: yfinance,pandas,pydantic
"""

from __future__ import annotations
from typing import Optional, Callable, Awaitable, Any
from datetime import datetime
import yfinance as yf
import pandas as pd

# Pydantic valves are recommended by OpenWebUI
from pydantic import BaseModel, Field

# Use stdlib zoneinfo if available, otherwise fall back to naive timestamps
try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


class Tools:
    """
    OpenWebUI Tools live in a single Python file with a metadata docstring and a Tools class.
    Methods WITH type hints are exposed as callable tools.
    """

    class Valves(BaseModel):
        timezone: str = Field(
            default="America/New_York",
            description="Timezone for timestamps, e.g., America/New_York or UTC",
        )
        default_history_rows: int = Field(
            default=20,
            ge=1,
            le=200,
            description="Default number of rows to show in history output",
        )
        use_fast_info: bool = Field(
            default=True,
            description="Prefer yfinance.fast_info when available for quotes",
        )

    def __init__(self):
        # Make valves configurable from the UI
        self.valves = self.Valves()

    # ---------- helpers ----------
    def _now_str(self) -> str:
        tzname = self.valves.timezone
        if ZoneInfo:
            try:
                return datetime.now(ZoneInfo(tzname)).strftime("%Y-%m-%d %H:%M:%S %Z")
            except Exception:
                pass  # fall back to native
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _fmt_usd(x: Optional[float]) -> str:
        try:
            return "—" if x is None else f"${x:,.2f}"
        except Exception:
            return "—"

    # ---------- tools you can call ----------
    async def health(
        self,
        __event_emitter__: Optional[Callable[[Any], Awaitable[None]]] = None,
    ) -> str:
        """
        Quick readiness check. Returns 'ok' if the tool is callable.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Health check", "done": True},
                }
            )
        return "ok: Stock Prices tool is installed and callable."

    async def stock_quote(
        self,
        symbol: str,
        __event_emitter__: Optional[Callable[[Any], Awaitable[None]]] = None,
    ) -> str:
        """
        Get the latest quote snapshot for a ticker.
        :param symbol: A ticker like 'AAPL', 'MSFT', 'TSLA', '^GSPC'
        :return: Markdown summary
        """
        try:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Fetching quote for {symbol}",
                            "done": False,
                        },
                    }
                )

            tkr = yf.Ticker(symbol)
            fi = getattr(tkr, "fast_info", None) if self.valves.use_fast_info else None
            hist = tkr.history(period="1d", interval="1m")

            last = None
            prev_close = None
            currency = "USD"
            year_high = None
            year_low = None

            if fi:
                last = getattr(fi, "last_price", None) or getattr(fi, "lastPrice", None)
                prev_close = getattr(fi, "previous_close", None) or getattr(
                    fi, "previousClose", None
                )
                currency = getattr(fi, "currency", currency)
                year_high = getattr(fi, "year_high", None)
                year_low = getattr(fi, "year_low", None)

            # Fallback from intraday history if needed
            if last is None and not hist.empty:
                last = float(hist["Close"].iloc[-1])
            if prev_close is None and not hist.empty:
                prev_close = float(hist["Close"].iloc[0])

            change = (
                None if (last is None or prev_close is None) else (last - prev_close)
            )
            pct = (
                None
                if (last is None or prev_close in (None, 0))
                else ((last / prev_close) - 1) * 100
            )

            now = self._now_str()
            lines = [
                f"### {symbol} — Quote ({now})",
                f"**Last:** {self._fmt_usd(last)} {currency}",
                (
                    f"**Change:** {self._fmt_usd(change)} ({pct:+.2f}% )"
                    if change is not None
                    else "**Change:** —"
                ),
                f"**Prev Close:** {self._fmt_usd(prev_close)}",
                f"**52-wk Range:** {self._fmt_usd(year_low)} — {self._fmt_usd(year_high)}",
            ]

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": f"Done: {symbol}", "done": True},
                    }
                )

            return (
                "\n".join(lines)
                if last is not None
                else f"Could not retrieve data for {symbol}."
            )

        except Exception as e:
            return f"Error fetching quote for {symbol}: {e}"

    async def stock_history(
        self,
        symbol: str,
        period: str = "5d",
        interval: str = "30m",
        rows: Optional[int] = None,
        __event_emitter__: Optional[Callable[[Any], Awaitable[None]]] = None,
    ) -> str:
        """
        Get a compact summary of recent OHLCV data.
        :param symbol: e.g., 'NVDA'
        :param period: e.g., '1d','5d','1mo','3mo','6mo','1y','max'
        :param interval: e.g., '1m','2m','5m','15m','30m','60m','1d','1wk','1mo'
        :param rows: override for how many rows to show (default uses valve)
        :return: Markdown table
        """
        try:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Fetching history for {symbol}",
                            "done": False,
                        },
                    }
                )

            df = yf.Ticker(symbol).history(period=period, interval=interval)
            if df.empty:
                return f"No historical data for {symbol} (period={period}, interval={interval})."

            n = rows or self.valves.default_history_rows
            out = df.tail(max(1, int(n)))[
                ["Open", "High", "Low", "Close", "Volume"]
            ].round(2)
            out.index = (
                out.index.tz_localize(None)
                if getattr(out.index, "tz", None)
                else out.index
            )

            md = out.to_markdown(tablefmt="github")
            now = self._now_str()

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": f"Done: {symbol}", "done": True},
                    }
                )

            return f"### {symbol} — History (period={period}, interval={interval}) @ {now}\n\n{md}"

        except Exception as e:
            return f"Error fetching history for {symbol}: {e}"