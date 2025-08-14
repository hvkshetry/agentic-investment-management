#!/usr/bin/env python3
"""
Execution Rules - Instrument-specific trading execution guidance
Ensures correct order types and execution methods for different asset classes
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
from .symbol_resolver import SymbolResolver

logger = logging.getLogger(__name__)

class OrderType(Enum):
    """Types of orders"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    NAV = "NAV"  # For mutual funds
    MOC = "MOC"  # Market on Close
    LOC = "LOC"  # Limit on Close
    
class ExecutionVenue(Enum):
    """Execution venues"""
    EXCHANGE = "EXCHANGE"  # Regular exchange
    FUND_COMPANY = "FUND_COMPANY"  # Direct with fund company
    DARK_POOL = "DARK_POOL"  # For large blocks
    
@dataclass
class ExecutionGuidance:
    """Execution guidance for a trade"""
    symbol: str
    asset_type: str
    order_types_allowed: List[OrderType]
    recommended_order_type: OrderType
    execution_venue: ExecutionVenue
    settlement: str  # T+1, T+2, etc.
    pre_market_available: bool
    after_hours_available: bool
    minimum_lot_size: int
    special_instructions: str
    warnings: List[str]

class ExecutionRules:
    """
    Manages execution rules for different instrument types
    """
    
    def __init__(self):
        self.symbol_resolver = SymbolResolver()
        
    def get_execution_guidance(self, symbol: str, quantity: int = 0) -> ExecutionGuidance:
        """
        Get execution guidance for a symbol
        
        Args:
            symbol: Ticker symbol
            quantity: Order quantity (for large order detection)
            
        Returns:
            ExecutionGuidance object
        """
        # Get symbol information
        info = self.symbol_resolver.validate_symbol(symbol)
        
        if not info.valid:
            return ExecutionGuidance(
                symbol=symbol,
                asset_type="UNKNOWN",
                order_types_allowed=[],
                recommended_order_type=OrderType.MARKET,
                execution_venue=ExecutionVenue.EXCHANGE,
                settlement="Unknown",
                pre_market_available=False,
                after_hours_available=False,
                minimum_lot_size=1,
                special_instructions="Symbol validation failed",
                warnings=[f"Symbol {symbol} could not be validated"]
            )
        
        # Route to appropriate handler based on asset type
        if info.asset_type == 'MUTUALFUND':
            return self._mutual_fund_rules(symbol, info, quantity)
        elif info.asset_type == 'ETF':
            return self._etf_rules(symbol, info, quantity)
        elif info.asset_type == 'EQUITY':
            return self._equity_rules(symbol, info, quantity)
        else:
            return self._default_rules(symbol, info, quantity)
            
    def _mutual_fund_rules(self, symbol: str, info: Any, quantity: int) -> ExecutionGuidance:
        """
        Execution rules for mutual funds
        
        Mutual funds:
        - Trade at NAV (Net Asset Value)
        - Orders executed at end of day
        - No limit orders allowed
        - No pre/after market trading
        """
        warnings = []
        
        # Check for common mistakes
        if symbol in ['VWLUX', 'VMLUX', 'VWIUX']:
            warnings.append(f"{symbol} is a Vanguard mutual fund - trades at NAV only")
            
        return ExecutionGuidance(
            symbol=symbol,
            asset_type="MUTUALFUND",
            order_types_allowed=[OrderType.NAV],
            recommended_order_type=OrderType.NAV,
            execution_venue=ExecutionVenue.FUND_COMPANY,
            settlement="T+1",
            pre_market_available=False,
            after_hours_available=False,
            minimum_lot_size=1,  # Can buy fractional shares
            special_instructions="Mutual fund orders execute at end-of-day NAV. No limit orders available.",
            warnings=warnings
        )
        
    def _etf_rules(self, symbol: str, info: Any, quantity: int) -> ExecutionGuidance:
        """
        Execution rules for ETFs
        
        ETFs:
        - Trade like stocks during market hours
        - Support limit and market orders
        - Available for pre/after market trading
        """
        warnings = []
        recommended_type = OrderType.LIMIT
        
        # Large order detection
        if quantity > 10000:
            warnings.append("Large order - consider splitting or using MOC/LOC orders")
            recommended_type = OrderType.LOC
            
        # Check for low-volume ETFs
        low_volume_etfs = ['JAAA', 'MINT']  # Examples
        if symbol in low_volume_etfs:
            warnings.append(f"{symbol} may have lower liquidity - use limit orders")
            
        return ExecutionGuidance(
            symbol=symbol,
            asset_type="ETF",
            order_types_allowed=[OrderType.MARKET, OrderType.LIMIT, OrderType.MOC, OrderType.LOC],
            recommended_order_type=recommended_type,
            execution_venue=ExecutionVenue.EXCHANGE,
            settlement="T+2",
            pre_market_available=True,
            after_hours_available=True,
            minimum_lot_size=1,
            special_instructions="ETF trades during market hours. Consider limit orders for better price control.",
            warnings=warnings
        )
        
    def _equity_rules(self, symbol: str, info: Any, quantity: int) -> ExecutionGuidance:
        """
        Execution rules for individual stocks
        
        Equities:
        - Full range of order types
        - Pre/after market available
        - Consider liquidity for order type
        """
        warnings = []
        recommended_type = OrderType.LIMIT
        
        # Large order detection
        market_cap = info.metadata.get('market_cap', 0)
        if market_cap > 0:
            order_value = quantity * info.current_price
            if order_value > market_cap * 0.001:  # More than 0.1% of market cap
                warnings.append("Large order relative to market cap - consider splitting")
                recommended_type = OrderType.LIMIT
                
        # Penny stock detection
        if info.current_price < 5:
            warnings.append("Low-priced stock - use limit orders to avoid slippage")
            recommended_type = OrderType.LIMIT
            
        return ExecutionGuidance(
            symbol=symbol,
            asset_type="EQUITY",
            order_types_allowed=[OrderType.MARKET, OrderType.LIMIT, OrderType.MOC, OrderType.LOC],
            recommended_order_type=recommended_type,
            execution_venue=ExecutionVenue.EXCHANGE,
            settlement="T+2",
            pre_market_available=True,
            after_hours_available=True,
            minimum_lot_size=1,
            special_instructions="Standard equity trading rules apply.",
            warnings=warnings
        )
        
    def _default_rules(self, symbol: str, info: Any, quantity: int) -> ExecutionGuidance:
        """
        Default execution rules for unknown asset types
        """
        return ExecutionGuidance(
            symbol=symbol,
            asset_type=info.asset_type,
            order_types_allowed=[OrderType.MARKET, OrderType.LIMIT],
            recommended_order_type=OrderType.LIMIT,
            execution_venue=ExecutionVenue.EXCHANGE,
            settlement="T+2",
            pre_market_available=False,
            after_hours_available=False,
            minimum_lot_size=1,
            special_instructions="Default rules applied - verify execution requirements.",
            warnings=["Asset type not fully recognized - using conservative execution rules"]
        )
        
    def validate_trade_list(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate a list of trades for execution issues
        
        Args:
            trades: List of trade dictionaries
            
        Returns:
            Validation results with any issues found
        """
        issues = []
        validated_trades = []
        
        for trade in trades:
            symbol = trade.get('symbol', '')
            quantity = trade.get('quantity', 0)
            order_type = trade.get('order_type', 'MARKET')
            
            # Get execution guidance
            guidance = self.get_execution_guidance(symbol, quantity)
            
            # Check for invalid order types
            if order_type == 'LIMIT' and guidance.asset_type == 'MUTUALFUND':
                issues.append({
                    'symbol': symbol,
                    'issue': 'Mutual funds cannot use limit orders',
                    'recommended': 'NAV order',
                    'severity': 'ERROR'
                })
                
            # Add execution guidance to trade
            validated_trade = trade.copy()
            validated_trade['execution_guidance'] = {
                'recommended_order_type': guidance.recommended_order_type.value,
                'execution_venue': guidance.execution_venue.value,
                'settlement': guidance.settlement,
                'special_instructions': guidance.special_instructions,
                'warnings': guidance.warnings
            }
            validated_trades.append(validated_trade)
            
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'validated_trades': validated_trades
        }
        
    def get_execution_summary(self, trades: List[Dict[str, Any]]) -> str:
        """
        Generate a human-readable execution summary
        
        Args:
            trades: List of trade dictionaries
            
        Returns:
            Formatted execution summary
        """
        summary = "# Execution Summary\n\n"
        
        # Group by execution type
        mutual_funds = []
        etfs = []
        equities = []
        
        for trade in trades:
            symbol = trade.get('symbol', '')
            guidance = self.get_execution_guidance(symbol)
            
            if guidance.asset_type == 'MUTUALFUND':
                mutual_funds.append(trade)
            elif guidance.asset_type == 'ETF':
                etfs.append(trade)
            else:
                equities.append(trade)
                
        if mutual_funds:
            summary += "## Mutual Funds (NAV Orders)\n"
            summary += "Execute at end-of-day NAV pricing:\n"
            for trade in mutual_funds:
                summary += f"- {trade['symbol']}: {trade.get('action', 'BUY')} {trade.get('quantity', 0)} shares\n"
            summary += "\n"
            
        if etfs:
            summary += "## ETFs (Exchange Traded)\n"
            summary += "Use limit orders during market hours:\n"
            for trade in etfs:
                summary += f"- {trade['symbol']}: {trade.get('action', 'BUY')} {trade.get('quantity', 0)} shares\n"
            summary += "\n"
            
        if equities:
            summary += "## Individual Stocks\n"
            summary += "Execute with appropriate order types:\n"
            for trade in equities:
                summary += f"- {trade['symbol']}: {trade.get('action', 'BUY')} {trade.get('quantity', 0)} shares\n"
            summary += "\n"
            
        return summary