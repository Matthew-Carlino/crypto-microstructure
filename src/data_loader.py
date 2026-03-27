"""
Historical trade data loading from Binance public API.

This module handles fetching aggregated trades from Binance's public endpoint,
manages caching, rate limiting, and efficient storage in Parquet format.
No API key required.
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Configuration
BINANCE_API_BASE = "https://api.binance.com"
BINANCE_AGG_TRADES_ENDPOINT = f"{BINANCE_API_BASE}/api/v3/aggTrades"
DEFAULT_CACHE_DIR = Path("data")
MAX_TRADES_PER_REQUEST = 1000  # Binance limit
REQUEST_TIMEOUT = 30
RATE_LIMIT_DELAY = 0.05  # seconds between requests to avoid rate limits


class BinanceTradeLoader:
    """
    Fetches and caches historical aggregated trade data from Binance public API.

    Trades are cached locally in Parquet format for efficient reuse. Implements
    retry logic and rate limiting to handle network issues and API constraints.

    Attributes:
        cache_dir (Path): Directory for caching trade data
        session (requests.Session): HTTP session with retry strategy
    """

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        """
        Initialize the trade loader.

        Args:
            cache_dir: Directory for caching trade data. Defaults to ./data
        """
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Set up session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _get_cache_path(self, symbol: str, start_date: str, end_date: str) -> Path:
        """
        Generate cache file path for a symbol and date range.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            start_date: Start date as YYYY-MM-DD
            end_date: End date as YYYY-MM-DD

        Returns:
            Path to cache file
        """
        filename = f"{symbol.lower()}_{start_date}_{end_date}.parquet"
        return self.cache_dir / filename

    def _fetch_trades_for_date(
        self, symbol: str, start_time: int, end_time: int
    ) -> pd.DataFrame:
        """
        Fetch aggregated trades for a symbol within a time range.

        Uses Binance's aggregated trades endpoint, which groups trades at the same
        price into a single record. Handles pagination automatically.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds

        Returns:
            DataFrame with columns: [timestamp, price, qty, is_buyer_maker]

        Raises:
            requests.RequestException: If API request fails after retries
        """
        all_trades = []
        from_id = 0

        while True:
            params = {
                "symbol": symbol,
                "limit": MAX_TRADES_PER_REQUEST,
                "startTime": start_time,
                "endTime": end_time,
            }
            if from_id > 0:
                params["fromId"] = from_id

            try:
                response = self.session.get(
                    BINANCE_AGG_TRADES_ENDPOINT,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"Failed to fetch trades for {symbol}: {e}")
                raise

            trades = response.json()
            if not trades:
                break

            all_trades.extend(trades)

            # Move to next batch
            from_id = trades[-1]["a"] + 1

            # Stop if we've reached the end time
            if int(trades[-1]["T"]) >= end_time:
                break

            # Rate limiting
            import time
            time.sleep(RATE_LIMIT_DELAY)

        if not all_trades:
            return pd.DataFrame()

        # Parse trades into DataFrame
        df = pd.DataFrame(all_trades)
        df = df.rename(columns={
            "T": "timestamp",
            "p": "price",
            "q": "qty",
            "m": "is_buyer_maker",
        })

        # Convert types
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df["price"] = pd.to_numeric(df["price"], downcast="float")
        df["qty"] = pd.to_numeric(df["qty"], downcast="float")
        df["is_buyer_maker"] = df["is_buyer_maker"].astype(bool)

        return df[["timestamp", "price", "qty", "is_buyer_maker"]].reset_index(drop=True)

    def load_cached_trades(
        self,
        symbol: str,
        start: str,
        end: str,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """
        Load historical trades for a symbol and date range, with caching.

        Fetches data from Binance API if not cached, then caches to Parquet
        for future use. Dates are processed in daily chunks to handle large
        date ranges efficiently.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            start: Start date as YYYY-MM-DD
            end: End date as YYYY-MM-DD
            force_refresh: If True, ignore cache and re-fetch from API

        Returns:
            DataFrame with columns: [timestamp, price, qty, is_buyer_maker]
            Sorted by timestamp, duplicates removed.

        Raises:
            ValueError: If date format is invalid or start > end
        """
        # Parse dates
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end_dt = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError as e:
            raise ValueError(f"Invalid date format. Use YYYY-MM-DD: {e}")

        if start_dt > end_dt:
            raise ValueError(f"Start date {start} must be before end date {end}")

        # Check cache
        cache_path = self._get_cache_path(symbol, start, end)
        if cache_path.exists() and not force_refresh:
            logger.info(f"Loading cached trades from {cache_path}")
            return pd.read_parquet(cache_path)

        # Fetch data
        logger.info(f"Fetching {symbol} trades from {start} to {end}")
        all_trades = []

        current_dt = start_dt
        while current_dt <= end_dt:
            next_dt = current_dt + timedelta(days=1)

            # Fetch trades for this day
            start_ms = int(current_dt.timestamp() * 1000)
            end_ms = int(next_dt.timestamp() * 1000)

            logger.debug(f"Fetching trades for {current_dt.date()}")
            trades = self._fetch_trades_for_date(symbol, start_ms, end_ms)

            if not trades.empty:
                all_trades.append(trades)

            current_dt = next_dt

        if not all_trades:
            logger.warning(f"No trades found for {symbol} in range {start} to {end}")
            return pd.DataFrame(columns=["timestamp", "price", "qty", "is_buyer_maker"])

        # Combine and deduplicate
        df = pd.concat(all_trades, ignore_index=True)
        df = df.drop_duplicates(subset=["timestamp", "price", "qty"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        # Cache to disk
        logger.info(f"Caching {len(df)} trades to {cache_path}")
        df.to_parquet(cache_path, compression="snappy", index=False)

        return df

    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """
        Clear cached data.

        Args:
            symbol: If provided, only clear cache for this symbol.
                   If None, clear all cache.
        """
        if symbol:
            pattern = f"{symbol.lower()}_*.parquet"
            files = self.cache_dir.glob(pattern)
            for f in files:
                f.unlink()
                logger.info(f"Removed cache: {f}")
        else:
            for f in self.cache_dir.glob("*.parquet"):
                f.unlink()
                logger.info(f"Removed cache: {f}")
