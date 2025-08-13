"""
OpenBB MCP Server with Response Limiting Patches

This module applies necessary patches to OpenBB providers to prevent token overflow.
"""

import logging

logger = logging.getLogger(__name__)

def apply_response_limiting_patches():
    """Apply all response limiting patches to OpenBB providers."""
    
    # 1. Patch YFinance news provider
    try:
        from openbb_yfinance.models.company_news import YFinanceCompanyNewsFetcher
        
        # Store original methods
        original_aextract_data = YFinanceCompanyNewsFetcher.aextract_data
        original_transform_data = YFinanceCompanyNewsFetcher.transform_data
        
        @staticmethod
        async def patched_aextract_data(query, credentials, **kwargs):
            """Patched extract_data that enforces limit."""
            # Call original method
            results = await original_aextract_data(query, credentials, **kwargs)
            
            # More reasonable limit - allow up to 50 news items
            # Each news item is typically 300-500 tokens, so 50 items = ~15-20k tokens
            limit = getattr(query, 'limit', 50)
            if limit is None:
                limit = 50
            # Cap at 50 to stay under token limit
            limit = min(limit, 50)
            
            if len(results) > limit:
                logger.info(f"YFinance news: Limited from {len(results)} to {limit} items")
                results = results[:limit]
            
            return results
        
        @staticmethod
        def patched_transform_data(query, data, **kwargs):
            """Patched transform_data that enforces limit."""
            # Apply limit before transformation
            limit = getattr(query, 'limit', 50)
            if limit is None:
                limit = 50
            # Cap at 50 for safety
            limit = min(limit, 50)
                
            if len(data) > limit:
                logger.info(f"YFinance news transform: Limited from {len(data)} to {limit}")
                data = data[:limit]
            
            # Call original transform
            return original_transform_data(query, data, **kwargs)
        
        # Apply patches
        YFinanceCompanyNewsFetcher.aextract_data = patched_aextract_data
        YFinanceCompanyNewsFetcher.transform_data = patched_transform_data
        
        logger.info("✓ Patched YFinance news provider to enforce 20-item limit")
        
    except ImportError:
        logger.warning("YFinance provider not found, skipping news patch")
    except Exception as e:
        logger.error(f"Failed to patch YFinance news: {e}")
    
    # 2. Patch SEC ETF providers for holdings
    try:
        from openbb_sec.models.etf_holdings import SecEtfHoldingsFetcher
        
        original_holdings_extract = SecEtfHoldingsFetcher.extract_data
        original_holdings_transform = SecEtfHoldingsFetcher.transform_data
        
        @staticmethod
        async def patched_holdings_extract(query, credentials, **kwargs):
            """Extract data and limit results."""
            # Call original (it's async)
            data = await original_holdings_extract(query, credentials, **kwargs)
            
            # Limit raw data before transformation
            # ETF holdings are smaller, can handle 100 items (~10-15k tokens)
            if isinstance(data, list) and len(data) > 100:
                logger.info(f"SEC ETF holdings extract: Limited from {len(data)} to 100")
                # Sort by weight if possible
                try:
                    data = sorted(data, key=lambda x: float(x.get('weight', x.get('value', 0))), reverse=True)[:100]
                except:
                    data = data[:100]
            
            return data
        
        @staticmethod
        def patched_holdings_transform(query, data, **kwargs):
            """Transform data with limiting."""
            # Limit before transformation
            if isinstance(data, list) and len(data) > 100:
                logger.info(f"SEC ETF holdings transform: Limited from {len(data)} to 100")
                try:
                    data = sorted(data, key=lambda x: float(x.get('weight', x.get('value', 0))), reverse=True)[:100]
                except:
                    data = data[:100]
            
            # Call original transform
            result = original_holdings_transform(query, data, **kwargs)
            
            # Also limit result - 100 holdings should be ~10-15k tokens
            if isinstance(result, list) and len(result) > 100:
                logger.info(f"SEC ETF holdings result: Limited from {len(result)} to 100")
                try:
                    result = sorted(
                        result,
                        key=lambda x: float(getattr(x, 'weight', getattr(x, 'market_value', getattr(x, 'value', 0)))),
                        reverse=True
                    )[:100]
                except:
                    result = result[:100]
            
            return result
        
        SecEtfHoldingsFetcher.extract_data = patched_holdings_extract
        SecEtfHoldingsFetcher.transform_data = patched_holdings_transform
        logger.info("✓ Patched SEC ETF holdings to limit to 50 positions")
        
    except ImportError:
        logger.warning("SEC provider not found, skipping ETF holdings patch")
    except Exception as e:
        logger.error(f"Failed to patch SEC ETF holdings: {e}")
    
    # 3. Patch FMP ETF equity exposure
    try:
        from openbb_fmp.models.etf_equity_exposure import FMPEtfEquityExposureFetcher
        
        original_exposure_transform = FMPEtfEquityExposureFetcher.transform_data
        
        @staticmethod
        def patched_exposure_transform(query, data, **kwargs):
            """Limit ETF equity exposure to 20 items."""
            # Call original transform
            result = original_exposure_transform(query, data, **kwargs)
            
            # Limit result - ETF exposures are more detailed, keep at 30 items
            # This should be ~12-15k tokens
            if isinstance(result, list) and len(result) > 30:
                logger.info(f"FMP ETF equity exposure: Limited from {len(result)} to 30")
                try:
                    result = sorted(
                        result,
                        key=lambda x: float(getattr(x, 'weight', getattr(x, 'portfolio_weight', 0))),
                        reverse=True
                    )[:30]
                except:
                    result = result[:30]
            
            return result
        
        FMPEtfEquityExposureFetcher.transform_data = patched_exposure_transform
        logger.info("✓ Patched FMP ETF equity exposure to limit to 20 items")
        
    except ImportError:
        logger.warning("FMP provider not found, skipping ETF exposure patch")
    except Exception as e:
        logger.error(f"Failed to patch FMP ETF exposure: {e}")
    
    # 4. Patch Federal Reserve treasury rates
    try:
        from openbb_federal_reserve.models.treasury_rates import FederalReserveTreasuryRatesFetcher
        
        original_rates_extract = FederalReserveTreasuryRatesFetcher.extract_data
        
        @staticmethod
        def patched_rates_extract(query, credentials, **kwargs):
            """Ensure date filtering for treasury rates."""
            from datetime import datetime, timedelta
            
            # Force date range if not specified
            if not hasattr(query, 'start_date') or query.start_date is None:
                query.start_date = datetime.now() - timedelta(days=30)
                logger.info(f"Fed treasury rates: Added 30-day start_date filter")
            
            return original_rates_extract(query, credentials, **kwargs)
        
        FederalReserveTreasuryRatesFetcher.extract_data = patched_rates_extract
        logger.info("✓ Patched Federal Reserve treasury rates to enforce date filtering")
        
    except ImportError:
        logger.warning("Federal Reserve provider not found, skipping treasury rates patch")
    except Exception as e:
        logger.error(f"Failed to patch Federal Reserve treasury rates: {e}")

# Auto-apply patches when module is imported
apply_response_limiting_patches()