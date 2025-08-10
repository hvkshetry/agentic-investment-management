#!/usr/bin/env python3
"""
Portfolio Value Service - Single source of truth for portfolio valuations
Ensures consistent use of current_value instead of cost_basis
Eliminates inconsistent portfolio value calculations
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class PortfolioValueService:
    """Centralized service for portfolio value calculations"""
    
    def __init__(self):
        """Initialize portfolio value service"""
        pass
    
    def validate_lot_data(self, lot: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate that a tax lot has required fields
        
        Args:
            lot: Tax lot dictionary
        
        Returns:
            Tuple of (is_valid, list_of_missing_fields)
        """
        required_fields = ['quantity', 'cost_basis']
        recommended_fields = ['current_value', 'unrealized_gain', 'current_price']
        
        missing_required = [field for field in required_fields if field not in lot]
        missing_recommended = [field for field in recommended_fields if field not in lot]
        
        if missing_required:
            logger.error(f"Tax lot missing required fields: {missing_required}")
            return False, missing_required
        
        if missing_recommended:
            logger.warning(f"Tax lot missing recommended fields: {missing_recommended}")
        
        return True, missing_recommended
    
    def get_lot_current_value(self, lot: Dict[str, Any]) -> float:
        """
        Get current value of a tax lot
        NEVER uses cost_basis as a proxy - fails if current_value not available
        
        Args:
            lot: Tax lot dictionary
        
        Returns:
            Current value of the lot
        
        Raises:
            ValueError: If current value cannot be determined
        """
        # First choice: Use current_value if available
        if 'current_value' in lot and lot['current_value'] is not None:
            return float(lot['current_value'])
        
        # Second choice: Calculate from quantity and current_price
        if 'quantity' in lot and 'current_price' in lot:
            quantity = float(lot.get('quantity', 0))
            current_price = float(lot.get('current_price', 0))
            if current_price > 0:
                return quantity * current_price
        
        # Third choice: Calculate from cost_basis and unrealized_gain
        if 'cost_basis' in lot and 'unrealized_gain' in lot:
            cost_basis = float(lot.get('cost_basis', 0))
            unrealized_gain = float(lot.get('unrealized_gain', 0))
            return cost_basis + unrealized_gain
        
        # FAIL LOUDLY - Never use cost_basis as proxy for current_value
        raise ValueError(
            f"Cannot determine current value for lot. "
            f"Available fields: {list(lot.keys())}. "
            f"Need either 'current_value', 'quantity+current_price', or 'cost_basis+unrealized_gain'"
        )
    
    def get_lot_unrealized_gain(self, lot: Dict[str, Any]) -> float:
        """
        Get unrealized gain/loss for a tax lot
        
        Args:
            lot: Tax lot dictionary
        
        Returns:
            Unrealized gain (negative for loss)
        """
        # First choice: Use unrealized_gain directly
        if 'unrealized_gain' in lot and lot['unrealized_gain'] is not None:
            return float(lot['unrealized_gain'])
        
        # Second choice: Calculate from current_value and cost_basis
        try:
            current_value = self.get_lot_current_value(lot)
            cost_basis = float(lot.get('cost_basis', 0))
            return current_value - cost_basis
        except ValueError:
            # If we can't get current value, we can't calculate gain
            logger.warning("Cannot calculate unrealized gain without current value")
            return 0.0
    
    def get_portfolio_total_value(self, portfolio_state: Dict[str, Any]) -> float:
        """
        Calculate total portfolio value from portfolio state
        Uses current_value, never cost_basis
        
        Args:
            portfolio_state: Portfolio state dictionary
        
        Returns:
            Total portfolio value
        
        Raises:
            ValueError: If portfolio value cannot be calculated
        """
        total_value = 0.0
        errors = []
        
        # Try summary first (if available and reliable)
        if 'summary' in portfolio_state:
            summary = portfolio_state['summary']
            if 'total_value' in summary and summary['total_value'] > 0:
                return float(summary['total_value'])
        
        # Calculate from positions
        if 'positions' in portfolio_state:
            for position in portfolio_state['positions']:
                try:
                    if 'current_value' in position:
                        total_value += float(position['current_value'])
                    elif 'quantity' in position and 'current_price' in position:
                        quantity = float(position['quantity'])
                        price = float(position['current_price'])
                        total_value += quantity * price
                    else:
                        errors.append(f"Position {position.get('symbol', 'unknown')} missing value data")
                except Exception as e:
                    errors.append(f"Error processing position: {e}")
        
        # Calculate from tax lots if positions not available
        elif 'tax_lots' in portfolio_state:
            tax_lots = portfolio_state['tax_lots']
            
            # Handle both list and dict formats
            if isinstance(tax_lots, dict):
                for symbol, lots in tax_lots.items():
                    for lot in lots:
                        try:
                            total_value += self.get_lot_current_value(lot)
                        except ValueError as e:
                            errors.append(f"Lot for {symbol}: {e}")
            elif isinstance(tax_lots, list):
                for lot in tax_lots:
                    try:
                        total_value += self.get_lot_current_value(lot)
                    except ValueError as e:
                        errors.append(f"Lot {lot.get('lot_id', 'unknown')}: {e}")
        
        if errors:
            logger.warning(f"Errors calculating portfolio value: {errors}")
        
        if total_value <= 0:
            raise ValueError(f"Invalid portfolio value calculated: ${total_value:,.2f}. Errors: {errors}")
        
        return total_value
    
    def get_position_value(self, position: Dict[str, Any]) -> float:
        """
        Get value of a position
        
        Args:
            position: Position dictionary
        
        Returns:
            Position value
        """
        # First choice: Use current_value
        if 'current_value' in position and position['current_value'] is not None:
            return float(position['current_value'])
        
        # Second choice: Calculate from quantity and current_price
        if 'quantity' in position and 'current_price' in position:
            quantity = float(position['quantity'])
            price = float(position['current_price'])
            return quantity * price
        
        # Third choice: Sum tax lots if available
        if 'tax_lots' in position:
            total = 0.0
            for lot in position['tax_lots']:
                try:
                    total += self.get_lot_current_value(lot)
                except ValueError:
                    pass
            if total > 0:
                return total
        
        # FAIL LOUDLY
        raise ValueError(
            f"Cannot determine value for position {position.get('symbol', 'unknown')}. "
            f"Available fields: {list(position.keys())}"
        )
    
    def calculate_position_weights(self, portfolio_state: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate position weights based on current values
        
        Args:
            portfolio_state: Portfolio state dictionary
        
        Returns:
            Dictionary of symbol -> weight
        """
        weights = {}
        total_value = self.get_portfolio_total_value(portfolio_state)
        
        if 'positions' in portfolio_state:
            for position in portfolio_state['positions']:
                symbol = position.get('symbol', 'UNKNOWN')
                try:
                    position_value = self.get_position_value(position)
                    weights[symbol] = position_value / total_value if total_value > 0 else 0
                except ValueError as e:
                    logger.warning(f"Could not calculate weight for {symbol}: {e}")
                    weights[symbol] = 0.0
        
        return weights
    
    def get_tax_lots_by_symbol(self, portfolio_state: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """
        Get tax lots organized by symbol
        Handles both list and dict formats from portfolio state
        
        Args:
            portfolio_state: Portfolio state dictionary
        
        Returns:
            Dictionary of symbol -> list of tax lots
        """
        tax_lots_by_symbol = {}
        
        if 'tax_lots' not in portfolio_state:
            logger.warning("No tax_lots in portfolio state")
            return {}
        
        tax_lots = portfolio_state['tax_lots']
        
        # Handle dict format (already organized by symbol)
        if isinstance(tax_lots, dict):
            return tax_lots
        
        # Handle list format (need to organize by symbol)
        elif isinstance(tax_lots, list):
            for lot in tax_lots:
                symbol = lot.get('symbol', 'UNKNOWN')
                if symbol not in tax_lots_by_symbol:
                    tax_lots_by_symbol[symbol] = []
                tax_lots_by_symbol[symbol].append(lot)
        
        return tax_lots_by_symbol
    
    def calculate_total_unrealized_gain(self, portfolio_state: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate total unrealized gains/losses
        
        Args:
            portfolio_state: Portfolio state dictionary
        
        Returns:
            Dictionary with total, long_term, and short_term gains
        """
        total_gain = 0.0
        long_term_gain = 0.0
        short_term_gain = 0.0
        
        tax_lots_by_symbol = self.get_tax_lots_by_symbol(portfolio_state)
        
        for symbol, lots in tax_lots_by_symbol.items():
            for lot in lots:
                gain = self.get_lot_unrealized_gain(lot)
                total_gain += gain
                
                if lot.get('is_long_term', False):
                    long_term_gain += gain
                else:
                    short_term_gain += gain
        
        return {
            'total': total_gain,
            'long_term': long_term_gain,
            'short_term': short_term_gain
        }
    
    def calculate_portfolio_metrics(self, portfolio_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate comprehensive portfolio metrics
        
        Args:
            portfolio_state: Portfolio state dictionary
        
        Returns:
            Dictionary with portfolio metrics
        """
        try:
            total_value = self.get_portfolio_total_value(portfolio_state)
            total_cost_basis = 0.0
            
            # Calculate total cost basis
            tax_lots_by_symbol = self.get_tax_lots_by_symbol(portfolio_state)
            for symbol, lots in tax_lots_by_symbol.items():
                for lot in lots:
                    total_cost_basis += float(lot.get('cost_basis', 0))
            
            unrealized_gains = self.calculate_total_unrealized_gain(portfolio_state)
            
            return {
                'total_value': total_value,
                'total_cost_basis': total_cost_basis,
                'total_unrealized_gain': unrealized_gains['total'],
                'long_term_unrealized': unrealized_gains['long_term'],
                'short_term_unrealized': unrealized_gains['short_term'],
                'total_return_pct': ((total_value - total_cost_basis) / total_cost_basis * 100) if total_cost_basis > 0 else 0,
                'position_weights': self.calculate_position_weights(portfolio_state)
            }
        except Exception as e:
            logger.error(f"Error calculating portfolio metrics: {e}")
            raise

# Singleton instance
_portfolio_value_service = None

def get_portfolio_value_service() -> PortfolioValueService:
    """Get or create the singleton PortfolioValueService instance"""
    global _portfolio_value_service
    if _portfolio_value_service is None:
        _portfolio_value_service = PortfolioValueService()
    return _portfolio_value_service