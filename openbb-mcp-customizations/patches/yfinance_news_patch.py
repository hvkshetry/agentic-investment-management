"""
Patch for YFinance Company News to properly limit results.
The yfinance library's get_news() method ignores the count parameter,
causing massive token overflow. This patch fixes that.
"""

import logging

logger = logging.getLogger(__name__)

def apply_yfinance_news_patch():
    """Apply patch to YFinance CompanyNewsFetcher to limit results."""
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
            
            # Apply limit - YFinance ignores the count parameter
            limit = getattr(query, 'limit', 20)
            if limit is None:
                limit = 20  # Default to 20 if not specified
            
            if len(results) > limit:
                logger.info(f"YFinance news: Limiting results from {len(results)} to {limit}")
                results = results[:limit]
            
            return results
        
        @staticmethod
        def patched_transform_data(query, data, **kwargs):
            """Patched transform_data that enforces limit."""
            # Apply limit before transformation
            limit = getattr(query, 'limit', 20)
            if limit is None:
                limit = 20  # Default to 20 if not specified
                
            if len(data) > limit:
                logger.info(f"YFinance news transform: Limiting from {len(data)} to {limit}")
                data = data[:limit]
            
            # Call original transform
            return original_transform_data(query, data, **kwargs)
        
        # Apply patches
        YFinanceCompanyNewsFetcher.aextract_data = patched_aextract_data
        YFinanceCompanyNewsFetcher.transform_data = patched_transform_data
        
        logger.info("Successfully patched YFinance CompanyNewsFetcher to enforce limits")
        return True
        
    except Exception as e:
        logger.error(f"Failed to patch YFinance news: {e}")
        return False