"""
Middleware to apply response limiting for OpenBB MCP Server.
This intercepts FastAPI responses and applies limiting before they're sent.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

logger = logging.getLogger(__name__)

class ResponseLimitingMiddleware(BaseHTTPMiddleware):
    """Middleware to limit response sizes for problematic endpoints."""
    
    TOKEN_LIMIT = 20000  # Conservative limit to stay well below 25k
    CHARS_PER_TOKEN_ESTIMATE = 4
    MAX_RESPONSE_CHARS = TOKEN_LIMIT * CHARS_PER_TOKEN_ESTIMATE
    
    def __init__(self, app):
        super().__init__(app)
        self.problem_endpoints = {
            '/api/v1/news/company': self.limit_news_company,
            '/api/v1/etf/equity_exposure': self.limit_etf_equity_exposure,
            '/api/v1/etf/holdings': self.limit_etf_holdings,
            '/api/v1/equity/compare/company_facts': self.limit_company_facts,
            '/api/v1/fixedincome/government/treasury_rates': self.apply_treasury_filter,
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process the request and limit response if needed."""
        
        # Check if this is a problematic endpoint
        path = request.url.path
        limiting_func = None
        
        for endpoint, func in self.problem_endpoints.items():
            if endpoint in path:
                limiting_func = func
                break
        
        # If it's a problematic endpoint, modify query params
        if limiting_func and path == '/api/v1/news/company':
            # Force limit parameter for news
            query_params = dict(request.query_params)
            if 'limit' not in query_params or int(query_params.get('limit', 100)) > 20:
                query_params['limit'] = '20'
                # Reconstruct URL with new params
                from urllib.parse import urlencode
                new_query = urlencode(query_params)
                request._url = request.url.replace(query=new_query)
                logger.info(f"Forced limit=20 for news/company endpoint")
        
        # Process the request
        response = await call_next(request)
        
        # If it's a problematic endpoint and JSON response, apply limiting
        if limiting_func and response.status_code == 200:
            # Read the response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            try:
                # Parse JSON and apply limiting
                data = json.loads(body.decode('utf-8'))
                
                # Apply the limiting function
                if 'results' in data and isinstance(data['results'], list):
                    data['results'] = limiting_func(data['results'])
                    logger.info(f"Applied response limiting to {path}")
                
                # Create new response with limited data
                return JSONResponse(
                    content=data,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
                
            except (json.JSONDecodeError, UnicodeDecodeError):
                # If not JSON, return original response
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type
                )
        
        return response
    
    def limit_news_company(self, data: List[Dict]) -> List[Dict]:
        """Limit news items to 20 most recent."""
        if len(data) <= 20:
            return data
        logger.info(f"Limited news from {len(data)} to 20 items")
        return data[:20]
    
    def limit_etf_equity_exposure(self, data: List[Dict]) -> List[Dict]:
        """Limit ETF exposure to top 20 by weight."""
        if len(data) <= 20:
            return data
        try:
            sorted_data = sorted(
                data,
                key=lambda x: float(x.get('weight', x.get('market_value', 0))),
                reverse=True
            )
            logger.info(f"Limited ETF exposure from {len(data)} to 20 items")
            return sorted_data[:20]
        except Exception as e:
            logger.error(f"Error sorting ETF exposure: {e}")
            return data[:20]
    
    def limit_etf_holdings(self, data: List[Dict]) -> List[Dict]:
        """Limit ETF holdings to top 50 by weight."""
        if len(data) <= 50:
            return data
        try:
            sorted_data = sorted(
                data,
                key=lambda x: float(x.get('weight', x.get('market_value', 0))),
                reverse=True
            )
            logger.info(f"Limited ETF holdings from {len(data)} to 50 items")
            return sorted_data[:50]
        except Exception:
            return data[:50]
    
    def limit_company_facts(self, data: Any) -> Any:
        """Limit company facts to recent years."""
        # Complex nested structure, needs careful handling
        if not isinstance(data, (list, dict)):
            return data
        
        # For now, just return as-is since structure varies
        return data
    
    def apply_treasury_filter(self, data: Any) -> Any:
        """Treasury rates - just pass through, filtering happens in params."""
        return data