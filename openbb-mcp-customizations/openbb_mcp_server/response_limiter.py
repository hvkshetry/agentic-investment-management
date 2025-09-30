"""
Response Limiter for OpenBB MCP Server
Handles response size limiting and pagination for large datasets
"""

import json
import hashlib
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class ResponseLimiter:
    """Limit response sizes for problematic endpoints to avoid token overflow"""

    TOKEN_LIMIT = 20000  # Conservative limit to stay well below 25k
    CHARS_PER_TOKEN_ESTIMATE = 4  # Approximate characters per token
    MAX_RESPONSE_CHARS = TOKEN_LIMIT * CHARS_PER_TOKEN_ESTIMATE

    def __init__(self):
        self.problem_endpoints = {
            'etf_equity_exposure': self.limit_etf_equity_exposure,
            'etf_holdings': self.limit_etf_holdings,
            'equity_compare_company_facts': self.limit_company_facts,
            'fixedincome_government_treasury_rates': self.apply_date_filter,
            'fixedincome_spreads_tcm': self.apply_date_filter,
            'fixedincome_spreads_treasury_effr': self.apply_date_filter,
            'news_company': self.limit_news_company,
            # New free provider endpoints
            'news_search': self.limit_news_search,
            'economy_wb_indicator': self.limit_macro_data,
            'economy_imf_series': self.limit_macro_data,
            'equity_screen': self.limit_screener,
        }
        # Continuation token storage with expiration (token -> (data, expiry_timestamp))
        self._continuation_cache: Dict[str, tuple[Any, float]] = {}
        self.TOKEN_TTL_SECONDS = 600  # 10 minutes
        self.MAX_TOKENS = 100  # Prevent unbounded growth
    
    def should_limit(self, endpoint: str) -> bool:
        """Check if this endpoint needs response limiting"""
        return endpoint in self.problem_endpoints
    
    def apply_limits(self, endpoint: str, data: Any, params: Optional[Dict] = None) -> Any:
        """Apply appropriate limiting strategy for the endpoint"""
        if endpoint in self.problem_endpoints:
            handler = self.problem_endpoints[endpoint]
            if params:
                return handler(data, params)
            return handler(data)
        return data
    
    def preprocess_params(self, endpoint: str, params: Dict) -> Dict:
        """Preprocess parameters before API call to prevent large responses"""
        if endpoint in ['fixedincome_government_treasury_rates',
                       'fixedincome_spreads_tcm',
                       'fixedincome_spreads_treasury_effr']:
            return self.apply_date_filter_params(params)
        elif endpoint == 'news_company':
            return self.fix_news_parameters(params)
        elif endpoint == 'etf_equity_exposure':
            # Ensure limit is set for ETF exposure
            if 'limit' not in params:
                params['limit'] = 30
        # New endpoints
        elif endpoint == 'news_search':
            return self.preprocess_news_search(params)
        elif endpoint in ['economy_wb_indicator', 'economy_imf_series']:
            return self.preprocess_macro_params(params)
        elif endpoint == 'equity_screen':
            return self.preprocess_screener_params(params)
        return params

    def preprocess_news_search(self, params: Dict) -> Dict:
        """Ensure news search has proper limits and filters."""
        # Default limit to 20 items
        if 'limit' not in params:
            params['limit'] = 20
        # Cap at 30 max
        params['limit'] = min(params['limit'], 30)

        # Ensure date range isn't too wide (max 30 days)
        if 'start_date' not in params:
            params['start_date'] = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        if 'end_date' not in params:
            params['end_date'] = datetime.now().strftime('%Y-%m-%d')

        logger.info(f"News search preprocessed: limit={params['limit']}, dates={params['start_date']} to {params['end_date']}")
        return params

    def preprocess_macro_params(self, params: Dict) -> Dict:
        """Ensure macro endpoints have date limits."""
        # Default to last 5 years if not specified
        if 'start' not in params and 'start_date' not in params:
            params['start'] = str(datetime.now().year - 5)
        if 'end' not in params and 'end_date' not in params:
            params['end'] = str(datetime.now().year)

        # Cap country list to 20
        if 'countries' in params and isinstance(params['countries'], list):
            if len(params['countries']) > 20:
                logger.warning(f"Country list truncated from {len(params['countries'])} to 20")
                params['countries'] = params['countries'][:20]

        logger.info(f"Macro params preprocessed: years={params.get('start', 'N/A')} to {params.get('end', 'N/A')}")
        return params

    def preprocess_screener_params(self, params: Dict) -> Dict:
        """Ensure screener has reasonable limits."""
        # Default limit to 50
        if 'limit' not in params:
            params['limit'] = 50
        # Cap at 100 max
        params['limit'] = min(params['limit'], 100)

        logger.info(f"Screener preprocessed: limit={params['limit']}")
        return params
    
    def limit_etf_holdings(self, data: Any) -> Any:
        """Limit ETF holdings to top positions by weight"""
        if isinstance(data, list):
            # If it's a list of holdings, limit to top 100 by weight
            if len(data) > 100:
                try:
                    # Sort by weight/value if available
                    sorted_data = sorted(
                        data,
                        key=lambda x: float(x.get('weight', x.get('market_value', x.get('value', 0)))),
                        reverse=True
                    )
                    logger.info(f"Limited ETF holdings from {len(data)} to 100 positions")
                    return sorted_data[:100]
                except Exception as e:
                    logger.error(f"Error sorting ETF holdings: {e}")
                    return data[:100]
            return data
        elif isinstance(data, dict):
            # SEC provider returns complex structure with results
            if 'results' in data and isinstance(data['results'], list):
                for result in data['results']:
                    # Look for holdings in the nested structure
                    if 'holdings' in result and isinstance(result['holdings'], list):
                        if len(result['holdings']) > 100:
                            try:
                                sorted_holdings = sorted(
                                    result['holdings'],
                                    key=lambda x: float(x.get('weight', x.get('market_value', x.get('value', 0)))),
                                    reverse=True
                                )
                                logger.info(f"Limited ETF holdings from {len(result['holdings'])} to 100 positions")
                                result['holdings'] = sorted_holdings[:100]
                            except:
                                result['holdings'] = result['holdings'][:100]
                    
                    # Also check for securities_lending if it exists
                    if 'securities_lending' in result and isinstance(result['securities_lending'], list):
                        if len(result['securities_lending']) > 10:
                            result['securities_lending'] = result['securities_lending'][:10]
                            logger.info("Limited securities lending data to 10 entries")
            return data
        return data
    
    def limit_etf_equity_exposure(self, data: List[Dict]) -> List[Dict]:
        """Limit ETF equity exposure to top 30 ETFs by weight"""
        if not isinstance(data, list):
            return data
            
        # Limit to 30 items for better context while staying under token limit
        if len(data) <= 30:
            return data
        
        # Sort by weight if available, otherwise by market value
        try:
            sorted_data = sorted(
                data, 
                key=lambda x: float(x.get('weight', x.get('market_value', 0))), 
                reverse=True
            )
            logger.info(f"Limited ETF exposure from {len(data)} to 30 items")
            return sorted_data[:30]
        except Exception as e:
            logger.error(f"Error sorting ETF exposure data: {e}")
            # If sorting fails, just return first 30
            return data[:30]
    
    def limit_company_facts(self, data: Dict) -> Dict:
        """Limit company facts to most recent 2 years of data"""
        if not isinstance(data, dict):
            return data
        
        try:
            current_year = datetime.now().year
            cutoff_year = current_year - 2
            
            # Filter facts to recent years
            if 'facts' in data:
                filtered_facts = {}
                for category, items in data['facts'].items():
                    if isinstance(items, dict):
                        filtered_items = {}
                        for key, values in items.items():
                            if isinstance(values, list):
                                # Filter by year if date field exists
                                filtered_values = []
                                for v in values:
                                    if 'filed' in v:
                                        try:
                                            year = int(v['filed'][:4])
                                            if year >= cutoff_year:
                                                filtered_values.append(v)
                                        except:
                                            filtered_values.append(v)
                                    elif 'end' in v:
                                        try:
                                            year = int(v['end'][:4])
                                            if year >= cutoff_year:
                                                filtered_values.append(v)
                                        except:
                                            filtered_values.append(v)
                                    else:
                                        # No date field, include it
                                        filtered_values.append(v)
                                
                                if filtered_values:
                                    filtered_items[key] = filtered_values[-10:]  # Keep only last 10 entries
                            else:
                                filtered_items[key] = values
                        if filtered_items:
                            filtered_facts[category] = filtered_items
                    else:
                        filtered_facts[category] = items
                
                data['facts'] = filtered_facts
                logger.info(f"Limited company facts to last 2 years")
            
            return data
            
        except Exception as e:
            logger.error(f"Error filtering company facts: {e}")
            # If filtering fails, try to return a subset
            try:
                data_str = json.dumps(data)
                if len(data_str) > self.MAX_RESPONSE_CHARS:
                    # Truncate the data
                    logger.warning("Company facts too large, truncating response")
                    if 'facts' in data:
                        # Keep only essential facts
                        essential_categories = ['dei', 'us-gaap']
                        data['facts'] = {k: v for k, v in data['facts'].items() 
                                       if k in essential_categories}
            except:
                pass
            
            return data
    
    def apply_date_filter_params(self, params: Dict) -> Dict:
        """Force date range for treasury/spread endpoints to prevent token overflow"""
        if 'start_date' not in params:
            # Default to last 30 days
            params['start_date'] = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            logger.info(f"Added start_date filter: {params['start_date']}")
        
        if 'end_date' not in params:
            params['end_date'] = datetime.now().strftime('%Y-%m-%d')
        
        return params
    
    def apply_date_filter(self, data: Any, params: Optional[Dict] = None) -> Any:
        """This is called on response data, but filtering should happen in params"""
        return data
    
    def limit_news_company(self, data: Any) -> Any:
        """Limit news_company response to prevent token overflow"""
        # Handle both list and dict responses
        if isinstance(data, list):
            # If it's a list of news items, limit to 50 most recent
            if len(data) > 50:
                logger.info(f"Limited news items from {len(data)} to 50")
                return data[:50]
            return data
        elif isinstance(data, dict):
            # Some providers return dict with 'results' key
            if 'results' in data and isinstance(data['results'], list):
                if len(data['results']) > 50:
                    logger.info(f"Limited news results from {len(data['results'])} to 50")
                    data['results'] = data['results'][:50]
            return data
        return data
    
    def fix_news_parameters(self, params: Dict) -> Dict:
        """Ensure correct parameter types for news endpoints"""
        # Fix limit parameter type
        if 'limit' in params:
            if isinstance(params['limit'], str):
                try:
                    params['limit'] = int(params['limit'])
                except ValueError:
                    params['limit'] = 50
        else:
            # Set default limit to prevent token overflow
            params['limit'] = 50
        
        # Add date filtering for yfinance to reduce response size
        if params.get('provider') == 'yfinance' and 'start_date' not in params:
            # Default to last 7 days for yfinance
            params['start_date'] = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            params['end_date'] = datetime.now().strftime('%Y-%m-%d')
            logger.info(f"Added date filter for yfinance news: {params['start_date']} to {params['end_date']}")
        
        # Ensure provider is set
        if 'provider' not in params:
            params['provider'] = 'yfinance'
        
        logger.info(f"Fixed news parameters: limit={params.get('limit')}, provider={params.get('provider')}")
        return params
    
    def estimate_response_size(self, data: Any) -> int:
        """Estimate the token size of a response"""
        try:
            data_str = json.dumps(data) if not isinstance(data, str) else data
            char_count = len(data_str)
            token_estimate = char_count // self.CHARS_PER_TOKEN_ESTIMATE
            return token_estimate
        except:
            return 0
    
    def check_response_size(self, data: Any, endpoint: str) -> bool:
        """Check if response is within token limits"""
        token_estimate = self.estimate_response_size(data)
        if token_estimate > self.TOKEN_LIMIT:
            logger.warning(f"Response for {endpoint} exceeds token limit: ~{token_estimate} tokens")
            return False
        return True

    # New endpoint limiters for free providers

    def limit_news_search(self, data: Any) -> Any:
        """Limit GDELT news search results with continuation token support."""
        if isinstance(data, dict) and 'articles' in data:
            articles = data['articles']
            if len(articles) > 30:
                # Generate continuation token
                token = self._generate_continuation_token(data)
                # Store remaining data with expiration
                self._store_continuation_data(token, {
                    'articles': articles[30:],
                    'metadata': data.get('metadata', {})
                })
                # Return limited result with token
                logger.info(f"Limited news_search from {len(articles)} to 30 articles (token: {token[:8]}...)")
                return {
                    'articles': articles[:30],
                    'metadata': data.get('metadata', {}),
                    'truncated': True,
                    'continuation_token': token,
                    'total_results': len(articles)
                }
            return data
        elif isinstance(data, list):
            if len(data) > 30:
                token = self._generate_continuation_token(data)
                self._store_continuation_data(token, data[30:])
                logger.info(f"Limited news_search from {len(data)} to 30 items")
                return {
                    'articles': data[:30],
                    'truncated': True,
                    'continuation_token': token,
                    'total_results': len(data)
                }
            return {'articles': data, 'truncated': False}
        return data

    def limit_macro_data(self, data: Any) -> Any:
        """Limit macro data results with paging support."""
        if isinstance(data, dict) and 'data' in data:
            records = data['data']
            if isinstance(records, list) and len(records) > 500:
                token = self._generate_continuation_token(data)
                self._store_continuation_data(token, {
                    'data': records[500:],
                    'metadata': data.get('metadata', {})
                })
                logger.info(f"Limited macro data from {len(records)} to 500 records")
                return {
                    'data': records[:500],
                    'metadata': data.get('metadata', {}),
                    'truncated': True,
                    'continuation_token': token,
                    'total_records': len(records)
                }
            return data
        elif isinstance(data, list):
            if len(data) > 500:
                token = self._generate_continuation_token(data)
                self._store_continuation_data(token, data[500:])
                logger.info(f"Limited macro data from {len(data)} to 500 records")
                return {
                    'data': data[:500],
                    'truncated': True,
                    'continuation_token': token,
                    'total_records': len(data)
                }
            return {'data': data, 'truncated': False}
        return data

    def limit_screener(self, data: Any) -> Any:
        """Limit screener results to 100 rows."""
        if isinstance(data, dict) and 'results' in data:
            results = data['results']
            if len(results) > 100:
                token = self._generate_continuation_token(data)
                self._store_continuation_data(token, {
                    'results': results[100:],
                    'metadata': data.get('metadata', {})
                })
                logger.info(f"Limited screener from {len(results)} to 100 results")
                return {
                    'results': results[:100],
                    'metadata': data.get('metadata', {}),
                    'truncated': True,
                    'continuation_token': token,
                    'total_results': len(results)
                }
            return data
        elif isinstance(data, list):
            if len(data) > 100:
                token = self._generate_continuation_token(data)
                self._store_continuation_data(token, data[100:])
                logger.info(f"Limited screener from {len(data)} to 100 results")
                return {
                    'results': data[:100],
                    'truncated': True,
                    'continuation_token': token,
                    'total_results': len(data)
                }
            return {'results': data, 'truncated': False}
        return data

    def _generate_continuation_token(self, data: Any) -> str:
        """Generate a unique continuation token for paginated data."""
        # Hash the data with timestamp for uniqueness
        data_str = json.dumps(data, sort_keys=True)
        timestamp = datetime.now().isoformat()
        token_input = f"{data_str}{timestamp}"
        token = hashlib.sha256(token_input.encode()).hexdigest()
        return token

    def _store_continuation_data(self, token: str, data: Any):
        """Store continuation data with expiration."""
        # Clean up expired tokens first
        self._cleanup_expired_tokens()

        # Check if we're at max capacity
        if len(self._continuation_cache) >= self.MAX_TOKENS:
            # Remove oldest token (simple FIFO eviction)
            oldest_token = next(iter(self._continuation_cache))
            del self._continuation_cache[oldest_token]
            logger.warning(f"Continuation cache at capacity, evicted oldest token")

        # Store with expiration timestamp
        expiry = time.time() + self.TOKEN_TTL_SECONDS
        self._continuation_cache[token] = (data, expiry)
        logger.debug(f"Stored continuation token {token[:8]}... (expires in {self.TOKEN_TTL_SECONDS}s)")

    def _cleanup_expired_tokens(self):
        """Remove expired tokens from cache."""
        now = time.time()
        expired = [token for token, (_, expiry) in self._continuation_cache.items() if expiry < now]
        for token in expired:
            del self._continuation_cache[token]
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired continuation tokens")

    def get_continuation_data(self, token: str) -> Optional[Any]:
        """
        Retrieve and consume data for a continuation token.
        Token is removed after reading (one-time use).
        """
        self._cleanup_expired_tokens()

        if token not in self._continuation_cache:
            logger.warning(f"Continuation token {token[:8]}... not found or expired")
            return None

        data, expiry = self._continuation_cache[token]

        # Check if expired
        if expiry < time.time():
            del self._continuation_cache[token]
            logger.warning(f"Continuation token {token[:8]}... expired")
            return None

        # Remove token after reading (one-time use)
        del self._continuation_cache[token]
        logger.debug(f"Retrieved and consumed continuation token {token[:8]}...")

        return data