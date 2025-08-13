"""
Response Limiter for OpenBB MCP Server
Handles response size limiting and pagination for large datasets
"""

import json
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
        }
    
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