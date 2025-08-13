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
            'equity_compare_company_facts': self.limit_company_facts,
            'fixedincome_government_treasury_rates': self.apply_date_filter,
            'fixedincome_spreads_tcm': self.apply_date_filter,
            'fixedincome_spreads_treasury_effr': self.apply_date_filter,
            'news_company': self.fix_news_parameters,
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
        return params
    
    def limit_etf_equity_exposure(self, data: List[Dict]) -> List[Dict]:
        """Limit ETF equity exposure to top 50 ETFs by weight/importance"""
        if not isinstance(data, list):
            return data
            
        if len(data) <= 50:
            return data
        
        # Sort by weight if available, otherwise by market value
        try:
            sorted_data = sorted(
                data, 
                key=lambda x: float(x.get('weight', x.get('market_value', 0))), 
                reverse=True
            )
            logger.info(f"Limited ETF exposure from {len(data)} to 50 items")
            return sorted_data[:50]
        except Exception as e:
            logger.error(f"Error sorting ETF exposure data: {e}")
            # If sorting fails, just return first 50
            return data[:50]
    
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
    
    def fix_news_parameters(self, params: Dict) -> Dict:
        """Ensure correct parameter types for news endpoints"""
        # Fix limit parameter type
        if 'limit' in params:
            if isinstance(params['limit'], str):
                try:
                    params['limit'] = int(params['limit'])
                except ValueError:
                    params['limit'] = 20
        else:
            # Set default limit to prevent token overflow
            params['limit'] = 20
        
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