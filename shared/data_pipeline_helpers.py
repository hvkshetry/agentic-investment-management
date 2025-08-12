"""
Helper functions extracted from fetch_equity_data for better maintainability.
Each function handles a single responsibility and is under 100 lines.
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta, timezone
from scipy import stats

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def resolve_tickers(
    tickers: List[str],
    resolver_func=None
) -> Tuple[List[str], Dict[str, str]]:
    """
    Resolve ticker aliases for market data compatibility.
    
    Args:
        tickers: Original ticker symbols
        resolver_func: Function to resolve individual tickers
        
    Returns:
        Tuple of (resolved_tickers, ticker_map)
    """
    resolved_tickers = []
    ticker_map = {}  # Map resolved back to original
    
    for ticker in tickers:
        if resolver_func:
            resolved = resolver_func(ticker)
        else:
            resolved = ticker  # No resolution, use as-is
            
        if resolved:
            resolved_tickers.append(resolved)
            ticker_map[resolved] = ticker
        else:
            logger.warning(f"Could not resolve ticker {ticker}, skipping")
    
    if not resolved_tickers:
        raise ValueError(f"Could not resolve any tickers from {tickers}")
    
    return resolved_tickers, ticker_map


def fetch_market_data(
    tickers: List[str],
    start_date: str,
    end_date: str,
    provider: str = "yfinance",
    fallback_provider: Optional[str] = "openbb"
) -> pd.DataFrame:
    """
    Fetch market data from specified provider with fallback.
    
    Args:
        tickers: List of ticker symbols to fetch
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        provider: Primary data provider
        fallback_provider: Fallback if primary fails
        
    Returns:
        DataFrame with price data
    """
    data = None
    
    # Try primary provider
    if provider == "yfinance":
        data = _fetch_from_yfinance(tickers, start_date, end_date)
    elif provider == "openbb":
        data = _fetch_from_openbb(tickers, start_date, end_date)
    
    # Try fallback if primary failed
    if data is None or data.empty:
        logger.warning(f"Primary provider {provider} failed, trying {fallback_provider}")
        if fallback_provider == "yfinance":
            data = _fetch_from_yfinance(tickers, start_date, end_date)
        elif fallback_provider == "openbb":
            data = _fetch_from_openbb(tickers, start_date, end_date)
    
    if data is None or data.empty:
        raise ValueError(f"Could not fetch data for {tickers} from any provider")
    
    return data


def _fetch_from_yfinance(tickers: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch data from yfinance."""
    try:
        import yfinance as yf
        
        # Handle single vs multiple tickers
        if len(tickers) == 1:
            ticker_obj = yf.Ticker(tickers[0])
            data = ticker_obj.history(start=start_date, end=end_date)
            if not data.empty:
                # Add ticker column for consistency
                data['Ticker'] = tickers[0]
        else:
            # Download multiple tickers
            tickers_str = ' '.join(tickers)
            data = yf.download(
                tickers_str,
                start=start_date,
                end=end_date,
                group_by='ticker',
                auto_adjust=True,
                progress=False
            )
        
        return data
        
    except Exception as e:
        logger.error(f"yfinance fetch failed: {e}")
        return pd.DataFrame()


def _fetch_from_openbb(tickers: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch data from OpenBB."""
    try:
        from openbb import obb
        
        all_data = []
        for ticker in tickers:
            try:
                result = obb.equity.price.historical(
                    symbol=ticker,
                    start_date=start_date,
                    end_date=end_date,
                    provider="yfinance"
                )
                
                if hasattr(result, 'to_dataframe'):
                    df = result.to_dataframe()
                elif hasattr(result, 'results'):
                    df = pd.DataFrame([r.model_dump() for r in result.results])
                else:
                    df = pd.DataFrame(result)
                
                if not df.empty:
                    df['Ticker'] = ticker
                    all_data.append(df)
                    
            except Exception as e:
                logger.warning(f"OpenBB fetch failed for {ticker}: {e}")
                continue
        
        if all_data:
            return pd.concat(all_data, axis=0)
        return pd.DataFrame()
        
    except ImportError:
        logger.error("OpenBB not installed")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"OpenBB fetch failed: {e}")
        return pd.DataFrame()


def calculate_data_quality_score(
    data: pd.DataFrame,
    expected_days: int,
    min_required_points: int = 100
) -> Dict[str, float]:
    """
    Calculate quality scores for market data.
    
    Args:
        data: Price data DataFrame
        expected_days: Expected number of trading days
        min_required_points: Minimum required data points
        
    Returns:
        Dictionary of quality scores by ticker
    """
    quality_scores = {}
    
    # Get unique tickers
    if 'Ticker' in data.columns:
        tickers = data['Ticker'].unique()
    else:
        # Assume single ticker
        tickers = ['UNKNOWN']
    
    for ticker in tickers:
        # Filter data for this ticker
        if 'Ticker' in data.columns:
            ticker_data = data[data['Ticker'] == ticker]
        else:
            ticker_data = data
        
        # Calculate quality metrics
        completeness = len(ticker_data) / max(expected_days, 1)
        completeness = min(completeness, 1.0)
        
        # Check for gaps
        if len(ticker_data) > 1:
            dates = pd.to_datetime(ticker_data.index if ticker_data.index.name else ticker_data.iloc[:, 0])
            date_diffs = dates.diff().dt.days
            max_gap = date_diffs.max()
            gap_penalty = 1.0 - min(max_gap / 10, 1.0) if max_gap > 1 else 1.0
        else:
            gap_penalty = 0.5
        
        # Check for outliers in returns
        if 'Close' in ticker_data.columns and len(ticker_data) > 2:
            returns = ticker_data['Close'].pct_change().dropna()
            if len(returns) > 0:
                z_scores = np.abs(stats.zscore(returns))
                outlier_ratio = np.sum(z_scores > 3) / len(returns)
                outlier_penalty = 1.0 - min(outlier_ratio * 10, 1.0)
            else:
                outlier_penalty = 0.5
        else:
            outlier_penalty = 0.5
        
        # Check data sufficiency
        sufficiency = 1.0 if len(ticker_data) >= min_required_points else len(ticker_data) / min_required_points
        
        # Combined quality score
        quality_score = (
            completeness * 0.3 +
            gap_penalty * 0.3 +
            outlier_penalty * 0.2 +
            sufficiency * 0.2
        )
        
        quality_scores[ticker] = round(quality_score, 3)
        
        logger.debug(f"Quality score for {ticker}: {quality_score:.3f} "
                    f"(completeness={completeness:.2f}, gaps={gap_penalty:.2f}, "
                    f"outliers={outlier_penalty:.2f}, sufficiency={sufficiency:.2f})")
    
    return quality_scores


def shape_output_data(
    raw_data: pd.DataFrame,
    ticker_map: Dict[str, str],
    quality_scores: Dict[str, float],
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    Shape the fetched data into the expected output format.
    
    Args:
        raw_data: Raw price data
        ticker_map: Mapping of resolved to original tickers
        quality_scores: Quality scores by ticker
        start_date: Start date of request
        end_date: End date of request
        
    Returns:
        Formatted output dictionary
    """
    # Calculate returns
    returns_data = {}
    prices_data = {}
    
    # Get unique tickers
    if 'Ticker' in raw_data.columns:
        tickers = raw_data['Ticker'].unique()
    else:
        tickers = list(ticker_map.values())[:1]  # Single ticker case
    
    for ticker in tickers:
        # Get original ticker name
        original_ticker = ticker_map.get(ticker, ticker)
        
        # Filter data for this ticker
        if 'Ticker' in raw_data.columns:
            ticker_data = raw_data[raw_data['Ticker'] == ticker]
        else:
            ticker_data = raw_data
        
        # Store prices
        if 'Adj Close' in ticker_data.columns:
            prices_data[original_ticker] = ticker_data['Adj Close'].to_dict()
        elif 'Close' in ticker_data.columns:
            prices_data[original_ticker] = ticker_data['Close'].to_dict()
        
        # Calculate returns
        if 'Adj Close' in ticker_data.columns:
            returns = ticker_data['Adj Close'].pct_change().dropna()
        elif 'Close' in ticker_data.columns:
            returns = ticker_data['Close'].pct_change().dropna()
        else:
            returns = pd.Series()
        
        returns_data[original_ticker] = returns.to_dict()
    
    # Build output structure
    output = {
        'data': raw_data,
        'returns': returns_data,
        'prices': prices_data,
        'quality_scores': quality_scores,
        'metadata': {
            'source': 'market_data',
            'start_date': start_date,
            'end_date': end_date,
            'fetch_time': datetime.now(timezone.utc).isoformat(),
            'ticker_count': len(tickers),
            'data_points': len(raw_data)
        }
    }
    
    return output


def validate_and_clean_data(
    data: pd.DataFrame,
    min_quality_threshold: float = 0.5
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Validate and clean fetched data.
    
    Args:
        data: Raw market data
        min_quality_threshold: Minimum acceptable quality score
        
    Returns:
        Tuple of (cleaned_data, warnings)
    """
    warnings = []
    
    # Remove duplicates
    if not data.empty:
        original_len = len(data)
        data = data.drop_duplicates()
        if len(data) < original_len:
            warnings.append(f"Removed {original_len - len(data)} duplicate rows")
    
    # Handle missing values
    if data.isnull().any().any():
        # Forward fill for small gaps
        data = data.fillna(method='ffill', limit=2)
        # Drop rows with remaining NaNs
        before_drop = len(data)
        data = data.dropna()
        if len(data) < before_drop:
            warnings.append(f"Dropped {before_drop - len(data)} rows with missing values")
    
    # Ensure proper data types
    numeric_columns = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
    for col in numeric_columns:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce')
    
    # Sort by date
    if not data.empty and data.index.name:
        data = data.sort_index()
    
    return data, warnings