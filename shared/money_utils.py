"""
Money calculation utilities using Decimal for financial accuracy.
Prevents cumulative rounding errors in portfolio calculations.
"""
from decimal import Decimal, ROUND_HALF_UP, getcontext, InvalidOperation
from typing import Union, Optional, List, Dict, Any
import logging

# Set decimal precision for financial calculations
getcontext().prec = 28

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Constants for common calculations
ZERO_MONEY = Decimal('0.00')
ONE_HUNDRED = Decimal('100')


def money(value: Union[str, int, float, Decimal]) -> Decimal:
    """
    Convert a value to a Decimal with 2 decimal places for money calculations.
    
    Args:
        value: Value to convert (string, int, float, or Decimal)
        
    Returns:
        Decimal rounded to 2 decimal places
        
    Raises:
        ValueError: If value cannot be converted to Decimal
    """
    try:
        # Convert to string first to avoid float precision issues
        if isinstance(value, float):
            # Use string conversion to preserve precision
            decimal_value = Decimal(str(value))
        else:
            decimal_value = Decimal(value) if not isinstance(value, Decimal) else value
        
        # Round to 2 decimal places (cents)
        return decimal_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as e:
        raise ValueError(f"Cannot convert {value} to money: {e}")


def calculate_gain_loss(proceeds: Union[str, float, Decimal], 
                       cost_basis: Union[str, float, Decimal]) -> Dict[str, Decimal]:
    """
    Calculate gain or loss from a transaction.
    
    Args:
        proceeds: Sale proceeds
        cost_basis: Original cost basis
        
    Returns:
        Dictionary with proceeds, cost_basis, gain_loss, and percentage
    """
    proceeds_decimal = money(proceeds)
    cost_basis_decimal = money(cost_basis)
    
    gain_loss = proceeds_decimal - cost_basis_decimal
    
    # Calculate percentage gain/loss
    if cost_basis_decimal != ZERO_MONEY:
        percentage = ((gain_loss / cost_basis_decimal) * ONE_HUNDRED).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
    else:
        percentage = Decimal('0.00')
    
    return {
        'proceeds': proceeds_decimal,
        'cost_basis': cost_basis_decimal,
        'gain_loss': gain_loss,
        'percentage': percentage
    }


def calculate_position_value(quantity: Union[int, float, Decimal],
                            price: Union[str, float, Decimal]) -> Decimal:
    """
    Calculate the total value of a position.
    
    Args:
        quantity: Number of shares
        price: Price per share
        
    Returns:
        Total position value as Decimal
    """
    # Quantity can have fractional shares
    quantity_decimal = Decimal(str(quantity))
    price_decimal = money(price)
    
    return money(quantity_decimal * price_decimal)


def calculate_weighted_average_price(transactions: List[Dict[str, Any]]) -> Decimal:
    """
    Calculate weighted average price from a list of transactions.
    
    Args:
        transactions: List of dicts with 'quantity' and 'price' keys
        
    Returns:
        Weighted average price as Decimal
    """
    if not transactions:
        return ZERO_MONEY
    
    total_value = Decimal('0')
    total_quantity = Decimal('0')
    
    for txn in transactions:
        quantity = Decimal(str(txn['quantity']))
        price = money(txn['price'])
        
        total_value += quantity * price
        total_quantity += quantity
    
    if total_quantity == Decimal('0'):
        return ZERO_MONEY
    
    return money(total_value / total_quantity)


def calculate_portfolio_allocation(positions: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Decimal]]:
    """
    Calculate portfolio allocation percentages.
    
    Args:
        positions: Dictionary of position data with 'value' key
        
    Returns:
        Dictionary with allocation percentages
    """
    # Calculate total portfolio value
    total_value = Decimal('0')
    for pos_data in positions.values():
        if isinstance(pos_data, dict) and 'value' in pos_data:
            total_value += money(pos_data['value'])
        else:
            # Handle case where pos_data might be just a value
            total_value += money(pos_data)
    
    if total_value == ZERO_MONEY:
        return {}
    
    allocations = {}
    for symbol, pos_data in positions.items():
        if isinstance(pos_data, dict) and 'value' in pos_data:
            position_value = money(pos_data['value'])
        else:
            position_value = money(pos_data)
        
        percentage = (position_value / total_value * ONE_HUNDRED).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        allocations[symbol] = {
            'value': position_value,
            'percentage': percentage
        }
    
    return allocations


def calculate_tax_impact(gain_loss: Union[str, float, Decimal],
                        tax_rate: Union[str, float, Decimal]) -> Decimal:
    """
    Calculate tax impact of a gain or loss.
    
    Args:
        gain_loss: Capital gain or loss
        tax_rate: Tax rate as decimal (e.g., 0.15 for 15%)
        
    Returns:
        Tax impact as Decimal (positive for tax owed, negative for tax benefit)
    """
    gain_loss_decimal = money(gain_loss)
    tax_rate_decimal = Decimal(str(tax_rate))
    
    tax_impact = gain_loss_decimal * tax_rate_decimal
    
    return money(tax_impact)


def sum_money_values(values: List[Union[str, float, Decimal]]) -> Decimal:
    """
    Sum a list of money values with proper decimal precision.
    
    Args:
        values: List of values to sum
        
    Returns:
        Sum as Decimal with 2 decimal places
    """
    total = Decimal('0')
    for value in values:
        total += money(value)
    
    return money(total)


def format_money(value: Union[str, float, Decimal], 
                 currency_symbol: str = '$',
                 negative_format: str = 'parentheses') -> str:
    """
    Format a money value for display.
    
    Args:
        value: Value to format
        currency_symbol: Currency symbol to use
        negative_format: How to format negative values ('minus' or 'parentheses')
        
    Returns:
        Formatted string representation
    """
    decimal_value = money(value)
    
    if decimal_value < ZERO_MONEY:
        abs_value = abs(decimal_value)
        if negative_format == 'parentheses':
            return f"({currency_symbol}{abs_value:,.2f})"
        else:
            return f"-{currency_symbol}{abs_value:,.2f}"
    else:
        return f"{currency_symbol}{decimal_value:,.2f}"


def parse_money(money_string: str) -> Decimal:
    """
    Parse a money string into a Decimal.
    
    Handles formats like:
    - $1,234.56
    - ($1,234.56) for negative
    - -$1,234.56
    - 1234.56
    
    Args:
        money_string: String representation of money
        
    Returns:
        Decimal value
    """
    # Remove currency symbols and whitespace
    cleaned = money_string.strip().replace('$', '').replace('€', '').replace('£', '')
    
    # Remove commas
    cleaned = cleaned.replace(',', '')
    
    # Handle parentheses for negative values
    if cleaned.startswith('(') and cleaned.endswith(')'):
        cleaned = '-' + cleaned[1:-1]
    
    return money(cleaned)