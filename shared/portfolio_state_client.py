#!/usr/bin/env python3
"""
Portfolio State Client - Shared client for accessing Portfolio State Server
Provides a unified interface for all MCP servers to access portfolio data
Supports both real portfolio state and synthetic data for testing
"""

import json
import logging
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import asyncio
import yfinance as yf
import numpy as np

# Import the data pipeline for ticker resolution - DRY principle
from data_pipeline import MarketDataPipeline

logger = logging.getLogger(__name__)

class TaxLot:
    """Represents a tax lot with cost basis information"""
    def __init__(self, data: Dict[str, Any]):
        self.lot_id = data.get('lot_id', '')
        self.symbol = data.get('symbol', '')
        self.quantity = float(data.get('quantity', 0))
        self.purchase_date = data.get('purchase_date', '')
        self.purchase_price = float(data.get('purchase_price', 0))
        self.cost_basis = float(data.get('cost_basis', 0))
        self.holding_period_days = int(data.get('holding_period_days', 0))
        self.is_long_term = bool(data.get('is_long_term', False))
        self.asset_type = data.get('asset_type', 'equity')
        self.account_id = data.get('account_id', '')
        self.broker = data.get('broker', '')
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'lot_id': self.lot_id,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'purchase_date': self.purchase_date,
            'purchase_price': self.purchase_price,
            'cost_basis': self.cost_basis,
            'holding_period_days': self.holding_period_days,
            'is_long_term': self.is_long_term,
            'asset_type': self.asset_type,
            'account_id': self.account_id,
            'broker': self.broker
        }

class Position:
    """Represents an aggregated position across all tax lots"""
    def __init__(self, symbol: str, tax_lots: List[TaxLot], current_price: Optional[float] = None, fetch_price: bool = True):
        self.symbol = symbol
        self.tax_lots = tax_lots
        self.data_pipeline = MarketDataPipeline()  # Reuse existing ticker resolution logic
        
        # Calculate aggregated values
        self.total_quantity = sum(lot.quantity for lot in tax_lots)
        self.total_cost_basis = sum(lot.cost_basis for lot in tax_lots)
        self.average_cost = self.total_cost_basis / self.total_quantity if self.total_quantity > 0 else 0
        
        # Get current price if not provided
        if current_price is None and fetch_price:
            self.current_price = self._fetch_current_price()
        elif current_price is not None:
            self.current_price = current_price
        else:
            # Use average cost as fallback when price fetching is disabled
            self.current_price = self.average_cost
            
        # Calculate current values
        self.current_value = self.total_quantity * self.current_price
        self.unrealized_gain = self.current_value - self.total_cost_basis
        self.unrealized_return = (self.unrealized_gain / self.total_cost_basis) if self.total_cost_basis > 0 else 0
        
        # Get asset type from first lot
        self.asset_type = tax_lots[0].asset_type if tax_lots else 'equity'
        
    def _fetch_current_price(self) -> float:
        """Fetch current price using yfinance with ticker resolution from data pipeline"""
        # Use the data pipeline's resolve_ticker method - DRY principle
        resolved_symbol = self.data_pipeline.resolve_ticker(self.symbol)
        
        if resolved_symbol:
            try:
                ticker = yf.Ticker(resolved_symbol)
                hist = ticker.history(period='1d')
                if not hist.empty:
                    return float(hist['Close'].iloc[-1])
            except Exception as e:
                logger.warning(f"Error fetching price for {resolved_symbol}: {e}")
        
        # If resolution or fetch fails, use average cost
        logger.warning(f"No price data for {self.symbol}, using average cost")
        return self.average_cost
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'total_quantity': self.total_quantity,
            'average_cost': self.average_cost,
            'total_cost_basis': self.total_cost_basis,
            'current_price': self.current_price,
            'current_value': self.current_value,
            'unrealized_gain': self.unrealized_gain,
            'unrealized_return': self.unrealized_return,
            'asset_type': self.asset_type,
            'tax_lots': [lot.to_dict() for lot in self.tax_lots]
        }

class PortfolioStateClient:
    """
    Client for accessing Portfolio State Server data
    Provides unified interface for all MCP servers
    """
    
    def __init__(self, use_portfolio_state: bool = True, state_file_path: Optional[str] = None):
        """
        Initialize Portfolio State Client
        
        Args:
            use_portfolio_state: Whether to use real portfolio state or synthetic data
            state_file_path: Path to portfolio state JSON file
        """
        self.use_portfolio_state = use_portfolio_state
        # Use environment variable or relative path to portfolio state
        default_path = os.path.join(os.path.dirname(__file__), "..", "portfolio-state-mcp-server", "state", "portfolio_state.json")
        self.state_file_path = state_file_path or os.getenv("PORTFOLIO_STATE_PATH", default_path)
        self._positions_cache = None
        self._cache_timestamp = None
        self.cache_ttl = timedelta(minutes=5)  # Cache for 5 minutes
        
        # Check if state file exists
        if self.use_portfolio_state and not os.path.exists(self.state_file_path):
            logger.warning(f"Portfolio state file not found at {self.state_file_path}, will use synthetic data")
            self.use_portfolio_state = False
    
    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid"""
        if self._cache_timestamp is None:
            return False
        return datetime.now() - self._cache_timestamp < self.cache_ttl
    
    async def get_portfolio_state(self) -> Dict[str, Any]:
        """
        Get raw portfolio state data
        
        Returns:
            Dictionary containing tax lots and other portfolio data
        """
        if not self.use_portfolio_state:
            raise ValueError("Portfolio State is required but not enabled. Set USE_PORTFOLIO_STATE=true")
        
        try:
            with open(self.state_file_path, 'r') as f:
                state_data = json.load(f)
            return state_data
        except Exception as e:
            logger.error(f"Error reading portfolio state: {e}")
            # Fail loudly - no fallback
            raise ValueError(f"Failed to read Portfolio State from {self.state_file_path}: {e}")
    
    async def get_positions(self, symbols: Optional[List[str]] = None, fetch_prices: bool = True) -> Dict[str, Position]:
        """
        Get current positions with aggregated data
        
        Args:
            symbols: Optional list of symbols to filter by
            fetch_prices: Whether to fetch current prices (can be slow for many positions)
        
        Returns:
            Dictionary mapping symbols to Position objects
        """
        # Check cache
        if self._is_cache_valid() and self._positions_cache is not None and fetch_prices:
            positions = self._positions_cache
        else:
            # Load fresh data
            state_data = await self.get_portfolio_state()
            positions = {}
            
            tax_lots_data = state_data.get('tax_lots', {})
            
            # Process tax lots by symbol
            for symbol, lots_list in tax_lots_data.items():
                if symbols and symbol not in symbols:
                    continue
                    
                tax_lots = [TaxLot(lot_data) for lot_data in lots_list]
                if tax_lots:
                    positions[symbol] = Position(symbol, tax_lots, fetch_price=fetch_prices)
            
            # Update cache
            self._positions_cache = positions
            self._cache_timestamp = datetime.now()
        
        # Filter by requested symbols if provided
        if symbols:
            return {s: positions[s] for s in symbols if s in positions}
        return positions
    
    async def get_tax_lots(self, symbol: Optional[str] = None) -> List[TaxLot]:
        """
        Get tax lots for specified symbol or all symbols
        
        Args:
            symbol: Optional symbol to filter by
        
        Returns:
            List of TaxLot objects
        """
        state_data = await self.get_portfolio_state()
        tax_lots_data = state_data.get('tax_lots', {})
        
        all_lots = []
        for sym, lots_list in tax_lots_data.items():
            if symbol and sym != symbol:
                continue
            for lot_data in lots_list:
                all_lots.append(TaxLot(lot_data))
        
        return all_lots
    
    async def get_portfolio_value(self) -> float:
        """
        Get total portfolio value
        
        Returns:
            Total current value of all positions
        """
        positions = await self.get_positions(fetch_prices=True)  # Need prices for value
        return sum(pos.current_value for pos in positions.values())
    
    async def get_portfolio_composition(self) -> Dict[str, float]:
        """
        Get portfolio composition as weights
        
        Returns:
            Dictionary mapping symbols to their portfolio weights
        """
        positions = await self.get_positions(fetch_prices=True)  # Need prices for weights
        total_value = sum(pos.current_value for pos in positions.values())
        
        if total_value == 0:
            return {}
        
        return {
            symbol: pos.current_value / total_value
            for symbol, pos in positions.items()
        }
    
    async def get_unrealized_gains(self) -> Dict[str, Dict[str, float]]:
        """
        Get unrealized gains/losses by symbol
        
        Returns:
            Dictionary with gain/loss information per symbol
        """
        positions = await self.get_positions(fetch_prices=False)  # Can use average cost for gains
        
        gains = {}
        for symbol, pos in positions.items():
            gains[symbol] = {
                'unrealized_gain': pos.unrealized_gain,
                'unrealized_return': pos.unrealized_return,
                'cost_basis': pos.total_cost_basis,
                'current_value': pos.current_value,
                'quantity': pos.total_quantity
            }
        
        return gains
    
    async def get_tax_loss_harvesting_opportunities(self, threshold: float = -1000) -> List[Dict[str, Any]]:
        """
        Identify tax loss harvesting opportunities
        
        Args:
            threshold: Minimum loss threshold (negative value)
        
        Returns:
            List of positions with unrealized losses above threshold
        """
        positions = await self.get_positions()
        
        opportunities = []
        for symbol, pos in positions.items():
            if pos.unrealized_gain < threshold:
                # Check for both short-term and long-term losses
                st_loss = 0
                lt_loss = 0
                
                for lot in pos.tax_lots:
                    lot_value = lot.quantity * pos.current_price
                    lot_gain = lot_value - lot.cost_basis
                    if lot_gain < 0:
                        if lot.is_long_term:
                            lt_loss += lot_gain
                        else:
                            st_loss += lot_gain
                
                opportunities.append({
                    'symbol': symbol,
                    'total_loss': pos.unrealized_gain,
                    'short_term_loss': st_loss,
                    'long_term_loss': lt_loss,
                    'quantity': pos.total_quantity,
                    'current_price': pos.current_price,
                    'cost_basis': pos.total_cost_basis
                })
        
        # Sort by total loss (most negative first)
        opportunities.sort(key=lambda x: x['total_loss'])
        return opportunities
    

# Singleton instance
_client = None

def get_portfolio_state_client(use_portfolio_state: Optional[bool] = None) -> PortfolioStateClient:
    """
    Get or create the singleton PortfolioStateClient instance
    
    Args:
        use_portfolio_state: Override whether to use real portfolio state
    
    Returns:
        PortfolioStateClient instance
    """
    global _client
    
    # Check environment variable for configuration - DEFAULT TO TRUE (fail loudly)
    if use_portfolio_state is None:
        use_portfolio_state = os.getenv('USE_PORTFOLIO_STATE', 'true').lower() == 'true'
    
    if _client is None:
        _client = PortfolioStateClient(use_portfolio_state=use_portfolio_state)
    elif use_portfolio_state is not None:
        # Update the configuration if explicitly provided
        _client.use_portfolio_state = use_portfolio_state
    
    return _client