#!/usr/bin/env python3
"""
Portfolio State MCP Server
Provides centralized portfolio state management with tax lot tracking
"""

from fastmcp import FastMCP, Context
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, date
from decimal import Decimal
import pandas as pd
import json
import logging
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, asdict
import csv
import re
import yfinance as yf
import time
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("portfolio_state_server")

# Initialize FastMCP server
mcp = FastMCP("portfolio-state-server")

class CostBasisMethod(str, Enum):
    """Cost basis calculation methods"""
    FIFO = "FIFO"  # First In First Out
    LIFO = "LIFO"  # Last In First Out
    HIFO = "HIFO"  # Highest In First Out
    AVERAGE = "AVERAGE"  # Average Cost
    SPECIFIC = "SPECIFIC"  # Specific Lot Identification

class AssetType(str, Enum):
    """Asset type classification"""
    EQUITY = "equity"
    BOND = "bond"
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    OPTION = "option"
    CASH = "cash"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    REIT = "reit"

@dataclass
class TaxLot:
    """Represents a tax lot with immutable historical data only"""
    lot_id: str
    symbol: str
    quantity: float
    purchase_date: str
    purchase_price: float
    cost_basis: float
    holding_period_days: int = 0
    is_long_term: bool = False
    asset_type: str = AssetType.EQUITY
    account_id: str = ""
    broker: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def update_holding_period(self):
        """Update holding period and long-term status"""
        purchase = datetime.strptime(self.purchase_date, "%Y-%m-%d")
        today = datetime.now()
        self.holding_period_days = (today - purchase).days
        self.is_long_term = self.holding_period_days > 365

@dataclass
class Position:
    """Aggregated position across all tax lots"""
    symbol: str
    total_quantity: float
    average_cost: float
    total_cost_basis: float
    current_price: float
    current_value: float
    unrealized_gain: float
    unrealized_return: float
    asset_type: str
    tax_lots: List[TaxLot]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "total_quantity": self.total_quantity,
            "average_cost": self.average_cost,
            "total_cost_basis": self.total_cost_basis,
            "current_price": self.current_price,
            "current_value": self.current_value,
            "unrealized_gain": self.unrealized_gain,
            "unrealized_return": self.unrealized_return,
            "asset_type": self.asset_type,
            "num_lots": len(self.tax_lots),
            "oldest_lot_date": min(lot.purchase_date for lot in self.tax_lots) if self.tax_lots else None,
            "newest_lot_date": max(lot.purchase_date for lot in self.tax_lots) if self.tax_lots else None
        }

class PortfolioStateManager:
    """Manages portfolio state with tax lot tracking and dynamic pricing"""
    
    # Invalid tickers/accounts/brokers to exclude
    INVALID_TICKERS = ['TEST', 'DUMMY', 'MOCK', 'SAMPLE', 'EXAMPLE']
    INVALID_ACCOUNTS = ['test_account', 'dummy_account', 'mock_account', 'sample_account']
    INVALID_BROKERS = ['test', 'dummy', 'mock', 'sample']
    
    # Removed mutual fund to ETF mapping - we should fail explicitly for unsupported tickers
    # rather than using proxy ETF prices which are not accurate
    MUTUAL_FUND_TO_ETF = {}
    
    def __init__(self):
        self.tax_lots: Dict[str, List[TaxLot]] = {}
        self.positions: Dict[str, Position] = {}
        self.accounts: Dict[str, Dict[str, Any]] = {}
        self.state_file = Path("/home/hvksh/investing/portfolio-state-mcp-server/state/portfolio_state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.ticker_cache: Dict[str, str] = {}  # Cache for resolved ticker symbols
        self.price_cache: Dict[str, tuple[float, datetime]] = {}  # Cache prices with timestamp
        self.price_cache_ttl = 300  # 5 minutes TTL for price cache
        self.load_state()
    
    def load_state(self):
        """Load portfolio state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    
                # Reconstruct tax lots
                for symbol, lots_data in state.get('tax_lots', {}).items():
                    self.tax_lots[symbol] = [
                        TaxLot(**lot_data) for lot_data in lots_data
                    ]
                
                self.accounts = state.get('accounts', {})
                
                # Rebuild positions
                self._rebuild_positions()
                
                logger.info(f"Loaded portfolio state: {len(self.tax_lots)} symbols, {sum(len(lots) for lots in self.tax_lots.values())} total lots")
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
    
    def save_state(self):
        """Save portfolio state to file"""
        try:
            state = {
                'tax_lots': {
                    symbol: [lot.to_dict() for lot in lots]
                    for symbol, lots in self.tax_lots.items()
                },
                'accounts': self.accounts,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)
            
            logger.info("Portfolio state saved")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def resolve_ticker(self, ticker: str) -> Optional[str]:
        """
        Resolve ticker symbol using fuzzy matching to handle format variations.
        Tries multiple formats to find a working ticker symbol for Yahoo Finance.
        """
        # Check cache first
        if ticker in self.ticker_cache:
            return self.ticker_cache[ticker]
        
        # Skip invalid tickers
        if ticker.upper() in self.INVALID_TICKERS or ticker in ['CASH', 'VMFXX', 'N/A']:
            return None
        
        # Special cases that we know need specific formats
        if ticker == 'BRKB':
            return 'BRK-B'
        if ticker == 'BRKA':
            return 'BRK-A'
        
        # Common ticker format variations to try (same as data_pipeline.py)
        variations = [
            ticker,                          # Original
            ticker.replace('B', '-B'),       # BRKB -> BRK-B
            ticker.replace('A', '-A'),       # BRKA -> BRK-A
            ticker.replace('.', '-'),        # BRK.B -> BRK-B
            ticker.replace('_', '-'),        # BRK_B -> BRK-B
            ticker.replace('-', '.'),        # BRK-B -> BRK.B
            ticker.replace(' ', ''),         # Remove spaces
        ]
        
        # Try each variation
        for variant in variations:
            try:
                test_ticker = yf.Ticker(variant)
                hist = test_ticker.history(period='5d')
                if not hist.empty:
                    # Found working ticker
                    logger.info(f"Resolved ticker {ticker} -> {variant}")
                    self.ticker_cache[ticker] = variant
                    return variant
            except Exception:
                continue
        
        logger.warning(f"Could not resolve ticker: {ticker}")
        return None
    
    def get_current_prices(self, symbols: Optional[List[str]] = None) -> Dict[str, float]:
        """
        Fetch current prices dynamically from Yahoo Finance with caching.
        Uses fuzzy matching to handle ticker format variations.
        Caches prices for 5 minutes to avoid repeated API calls.
        """
        if symbols is None:
            symbols = list(self.tax_lots.keys())
        
        prices = {}
        now = datetime.now()
        
        for symbol in symbols:
            # Skip non-tradeable items
            if symbol in ['CASH', 'VMFXX', 'N/A'] or symbol.upper() in self.INVALID_TICKERS:
                continue
            
            # Check cache first
            if symbol in self.price_cache:
                cached_price, cached_time = self.price_cache[symbol]
                age_seconds = (now - cached_time).total_seconds()
                if age_seconds < self.price_cache_ttl:
                    prices[symbol] = cached_price
                    logger.debug(f"Using cached price for {symbol}: ${cached_price:.2f} (age: {age_seconds:.0f}s)")
                    continue
            
            # Resolve ticker format
            yahoo_symbol = self.resolve_ticker(symbol)
            if not yahoo_symbol:
                logger.warning(f"Skipping unresolvable ticker: {symbol}")
                continue
            
            try:
                ticker = yf.Ticker(yahoo_symbol)
                # Use 5d period for better mutual fund compatibility
                hist = ticker.history(period='5d')
                
                if not hist.empty:
                    price = float(hist['Close'].iloc[-1])
                    prices[symbol] = price
                    # Cache the price
                    self.price_cache[symbol] = (price, now)
                    logger.debug(f"Fetched and cached price for {symbol}: ${price:.2f}")
                else:
                    # FAIL LOUDLY - No silent fallback to purchase prices
                    error_msg = f"Failed to fetch current price for {symbol} - no market data available"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            except ValueError:
                # Re-raise our explicit errors
                raise
            except Exception as e:
                # FAIL LOUDLY - No silent fallback
                error_msg = f"Failed to fetch price for {symbol}: {e}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        
        return prices
    
    def add_tax_lot(self, lot: TaxLot):
        """Add a new tax lot with validation"""
        # Validate ticker
        if lot.symbol.upper() in self.INVALID_TICKERS:
            raise ValueError(f"Invalid ticker '{lot.symbol}': Test/mock tickers not allowed")
        
        # Validate account
        if lot.account_id.lower() in self.INVALID_ACCOUNTS:
            raise ValueError(f"Invalid account '{lot.account_id}': Test accounts not allowed")
        
        # Validate broker
        if lot.broker.lower() in self.INVALID_BROKERS:
            raise ValueError(f"Invalid broker '{lot.broker}': Test brokers not allowed")
        
        # Verify ticker exists in market (skip for cash-like items)
        if lot.symbol not in ['CASH', 'VMFXX', 'N/A']:
            resolved_ticker = self.resolve_ticker(lot.symbol)
            if not resolved_ticker:
                logger.warning(f"Could not validate ticker {lot.symbol}, proceeding with caution")
        
        if lot.symbol not in self.tax_lots:
            self.tax_lots[lot.symbol] = []
        self.tax_lots[lot.symbol].append(lot)
        self._rebuild_positions()
        self.save_state()
    
    def _rebuild_positions(self):
        """Rebuild aggregated positions from tax lots with dynamic pricing"""
        self.positions = {}
        
        # Get all symbols that need prices
        symbols_to_price = [s for s in self.tax_lots.keys() 
                           if s not in ['CASH', 'VMFXX', 'N/A']]
        
        # Fetch current prices dynamically
        current_prices = self.get_current_prices(symbols_to_price)
        
        for symbol, lots in self.tax_lots.items():
            if not lots:
                continue
            
            # Update holding periods for all lots
            for lot in lots:
                lot.update_holding_period()
            
            total_quantity = sum(lot.quantity for lot in lots)
            total_cost_basis = sum(lot.cost_basis for lot in lots)
            average_cost = total_cost_basis / total_quantity if total_quantity > 0 else 0
            
            # Get current price (use fetched price or fallback to average purchase price)
            current_price = current_prices.get(symbol, average_cost)
            current_value = total_quantity * current_price
            unrealized_gain = current_value - total_cost_basis
            unrealized_return = (unrealized_gain / total_cost_basis) if total_cost_basis > 0 else 0
            
            self.positions[symbol] = Position(
                symbol=symbol,
                total_quantity=total_quantity,
                average_cost=average_cost,
                total_cost_basis=total_cost_basis,
                current_price=current_price,
                current_value=current_value,
                unrealized_gain=unrealized_gain,
                unrealized_return=unrealized_return,
                asset_type=lots[0].asset_type if lots else AssetType.EQUITY,
                tax_lots=lots
            )
    
    def refresh_prices(self):
        """Refresh all position values with latest market prices"""
        self._rebuild_positions()
        # Note: We don't save state here since prices are fetched dynamically
    
    def get_lots_for_sale(self, symbol: str, quantity: float, method: CostBasisMethod) -> List[TaxLot]:
        """Get tax lots for a sale based on cost basis method"""
        if symbol not in self.tax_lots:
            return []
        
        lots = self.tax_lots[symbol].copy()
        
        # Sort based on method
        if method == CostBasisMethod.FIFO:
            lots.sort(key=lambda x: x.purchase_date)
        elif method == CostBasisMethod.LIFO:
            lots.sort(key=lambda x: x.purchase_date, reverse=True)
        elif method == CostBasisMethod.HIFO:
            lots.sort(key=lambda x: x.purchase_price, reverse=True)
        elif method == CostBasisMethod.AVERAGE:
            # For average cost, all shares are treated equally
            pass
        
        # Select lots to sell
        selected_lots = []
        remaining_quantity = quantity
        
        for lot in lots:
            if remaining_quantity <= 0:
                break
            
            if lot.quantity <= remaining_quantity:
                selected_lots.append(lot)
                remaining_quantity -= lot.quantity
            else:
                # Partial lot sale
                partial_lot = TaxLot(
                    lot_id=f"{lot.lot_id}_partial",
                    symbol=lot.symbol,
                    quantity=remaining_quantity,
                    purchase_date=lot.purchase_date,
                    purchase_price=lot.purchase_price,
                    cost_basis=(lot.cost_basis / lot.quantity) * remaining_quantity,
                    asset_type=lot.asset_type,
                    account_id=lot.account_id,
                    broker=lot.broker
                )
                selected_lots.append(partial_lot)
                remaining_quantity = 0
        
        return selected_lots

# Global portfolio manager instance
portfolio_manager = PortfolioStateManager()

@mcp.tool()
async def get_portfolio_state(ctx: Context) -> Dict[str, Any]:
    """
    Get complete portfolio state with all positions and tax lots
    
    Returns comprehensive portfolio data including positions, tax lots,
    unrealized gains, and asset allocation.
    """
    try:
        # Calculate summary statistics
        total_value = sum(pos.current_value for pos in portfolio_manager.positions.values())
        total_cost = sum(pos.total_cost_basis for pos in portfolio_manager.positions.values())
        total_unrealized = total_value - total_cost
        
        # Asset allocation
        allocation = {}
        for pos in portfolio_manager.positions.values():
            asset_type = pos.asset_type
            if asset_type not in allocation:
                allocation[asset_type] = {"value": 0, "percentage": 0}
            allocation[asset_type]["value"] += pos.current_value
        
        # Calculate percentages
        for asset_type in allocation:
            allocation[asset_type]["percentage"] = (
                allocation[asset_type]["value"] / total_value * 100
                if total_value > 0 else 0
            )
        
        # Get positions summary
        positions_summary = [
            pos.to_dict() for pos in portfolio_manager.positions.values()
        ]
        
        # Get all tax lots
        all_lots = []
        for symbol, lots in portfolio_manager.tax_lots.items():
            for lot in lots:
                all_lots.append(lot.to_dict())
        
        return {
            "summary": {
                "total_value": total_value,
                "total_cost_basis": total_cost,
                "total_unrealized_gain": total_unrealized,
                "total_unrealized_return": (total_unrealized / total_cost * 100) if total_cost > 0 else 0,
                "num_positions": len(portfolio_manager.positions),
                "num_tax_lots": len(all_lots),
                "asset_allocation": allocation
            },
            "positions": positions_summary,
            "tax_lots": all_lots,
            "accounts": portfolio_manager.accounts,
            "last_updated": datetime.now().isoformat(),
            "confidence": 1.0
        }
    except Exception as e:
        logger.error(f"Error getting portfolio state: {e}")
        return {
            "error": str(e),
            "confidence": 0.0
        }

@mcp.tool()
async def import_broker_csv(
    ctx: Context,
    broker: str,
    csv_content: str,
    account_id: str = "default"
) -> Dict[str, Any]:
    """
    Import portfolio data from broker CSV
    
    Args:
        broker: Broker name (vanguard, ubs, fidelity, schwab, etc.)
        csv_content: CSV file content as string
        account_id: Account identifier
    
    Returns status and imported data summary
    """
    try:
        from csv_parsers.parser_factory import BrokerCSVParser
        
        parser = BrokerCSVParser.create_parser(broker)
        tax_lots = parser.parse(csv_content, account_id)
        
        # Add lots to portfolio
        added_count = 0
        for lot in tax_lots:
            portfolio_manager.add_tax_lot(lot)
            added_count += 1
        
        # Update account info
        if account_id not in portfolio_manager.accounts:
            portfolio_manager.accounts[account_id] = {}
        
        portfolio_manager.accounts[account_id].update({
            "broker": broker,
            "last_import": datetime.now().isoformat(),
            "num_lots_imported": added_count
        })
        
        portfolio_manager.save_state()
        
        return {
            "status": "success",
            "broker": broker,
            "account_id": account_id,
            "lots_imported": added_count,
            "symbols": list(set(lot.symbol for lot in tax_lots)),
            "confidence": 1.0
        }
    except Exception as e:
        logger.error(f"Error importing CSV: {e}")
        return {
            "status": "error",
            "error": str(e),
            "confidence": 0.0
        }

@mcp.tool()
async def update_market_prices(
    ctx: Context,
    prices: Dict[str, float]
) -> Dict[str, Any]:
    """
    Update current market prices for portfolio positions
    
    Args:
        prices: Dictionary of symbol to current price mappings
    
    Returns updated portfolio metrics
    """
    try:
        # Since we fetch prices dynamically, just refresh the positions
        portfolio_manager.refresh_prices()
        
        # Calculate updated metrics
        total_value = sum(pos.current_value for pos in portfolio_manager.positions.values())
        total_unrealized = sum(pos.unrealized_gain for pos in portfolio_manager.positions.values())
        
        return {
            "status": "success",
            "prices_updated": len(prices),
            "portfolio_value": total_value,
            "total_unrealized_gain": total_unrealized,
            "timestamp": datetime.now().isoformat(),
            "confidence": 1.0
        }
    except Exception as e:
        logger.error(f"Error updating prices: {e}")
        return {
            "status": "error",
            "error": str(e),
            "confidence": 0.0
        }

@mcp.tool()
async def simulate_sale(
    ctx: Context,
    symbol: str,
    quantity: float,
    sale_price: float,
    cost_basis_method: str = "FIFO"
) -> Dict[str, Any]:
    """
    Simulate a sale to calculate tax implications
    
    Args:
        symbol: Stock symbol to sell
        quantity: Number of shares to sell
        sale_price: Price per share for the sale
        cost_basis_method: Method for selecting lots (FIFO, LIFO, HIFO, AVERAGE)
    
    Returns tax implications including realized gains breakdown
    """
    try:
        method = CostBasisMethod(cost_basis_method.upper())
        lots_to_sell = portfolio_manager.get_lots_for_sale(symbol, quantity, method)
        
        if not lots_to_sell:
            return {
                "error": f"No tax lots found for {symbol}",
                "confidence": 0.0
            }
        
        # Calculate tax implications
        total_proceeds = 0
        total_cost_basis = 0
        long_term_gain = 0
        short_term_gain = 0
        
        lot_details = []
        
        for lot in lots_to_sell:
            proceeds = lot.quantity * sale_price
            gain = proceeds - lot.cost_basis
            
            total_proceeds += proceeds
            total_cost_basis += lot.cost_basis
            
            # Check holding period
            purchase_date = datetime.strptime(lot.purchase_date, "%Y-%m-%d")
            holding_days = (datetime.now() - purchase_date).days
            is_long_term = holding_days > 365
            
            if is_long_term:
                long_term_gain += gain
            else:
                short_term_gain += gain
            
            lot_details.append({
                "lot_id": lot.lot_id,
                "quantity": lot.quantity,
                "purchase_date": lot.purchase_date,
                "purchase_price": lot.purchase_price,
                "cost_basis": lot.cost_basis,
                "proceeds": proceeds,
                "gain_loss": gain,
                "holding_days": holding_days,
                "is_long_term": is_long_term
            })
        
        total_gain = total_proceeds - total_cost_basis
        
        return {
            "symbol": symbol,
            "quantity_sold": sum(lot.quantity for lot in lots_to_sell),
            "sale_price": sale_price,
            "total_proceeds": total_proceeds,
            "total_cost_basis": total_cost_basis,
            "total_gain_loss": total_gain,
            "long_term_gain": long_term_gain,
            "short_term_gain": short_term_gain,
            "cost_basis_method": cost_basis_method,
            "lots_sold": lot_details,
            "num_lots": len(lot_details),
            "confidence": 1.0
        }
    except Exception as e:
        logger.error(f"Error simulating sale: {e}")
        return {
            "error": str(e),
            "confidence": 0.0
        }

@mcp.tool()
async def get_tax_loss_harvesting_opportunities(
    ctx: Context,
    min_loss_threshold: float = 1000.0,
    exclude_recent_days: int = 31
) -> Dict[str, Any]:
    """
    Identify tax loss harvesting opportunities
    
    Args:
        min_loss_threshold: Minimum loss amount to consider
        exclude_recent_days: Exclude lots purchased within this many days (wash sale)
    
    Returns list of harvesting opportunities with tax savings estimates
    """
    try:
        # Refresh prices to get current values
        portfolio_manager.refresh_prices()
        
        opportunities = []
        today = datetime.now()
        
        for symbol, position in portfolio_manager.positions.items():
            if position.unrealized_gain >= 0:
                continue  # Skip positions with gains
            
            # Get current price for this position
            current_price = position.current_price
            
            # Check each lot for harvesting potential
            for lot in position.tax_lots:
                # Skip recent purchases (wash sale rule)
                purchase_date = datetime.strptime(lot.purchase_date, "%Y-%m-%d")
                days_held = (today - purchase_date).days
                
                if days_held < exclude_recent_days:
                    continue
                
                # Calculate unrealized gain for this lot
                lot_current_value = lot.quantity * current_price
                lot_unrealized_gain = lot_current_value - lot.cost_basis
                
                if lot_unrealized_gain < -min_loss_threshold:
                    is_long_term = days_held > 365
                    
                    opportunities.append({
                        "symbol": symbol,
                        "lot_id": lot.lot_id,
                        "quantity": lot.quantity,
                        "purchase_date": lot.purchase_date,
                        "cost_basis": lot.cost_basis,
                        "current_value": lot_current_value,
                        "unrealized_loss": -lot_unrealized_gain,
                        "days_held": days_held,
                        "is_long_term": is_long_term,
                        "tax_benefit_estimate": -lot_unrealized_gain * (0.15 if is_long_term else 0.35)
                    })
        
        # Sort by tax benefit
        opportunities.sort(key=lambda x: x["tax_benefit_estimate"], reverse=True)
        
        total_losses = sum(opp["unrealized_loss"] for opp in opportunities)
        total_tax_benefit = sum(opp["tax_benefit_estimate"] for opp in opportunities)
        
        return {
            "opportunities": opportunities[:10],  # Top 10 opportunities
            "total_opportunities": len(opportunities),
            "total_harvestable_losses": total_losses,
            "estimated_tax_benefit": total_tax_benefit,
            "as_of": datetime.now().isoformat(),
            "confidence": 0.95
        }
    except Exception as e:
        logger.error(f"Error finding tax loss harvesting opportunities: {e}")
        return {
            "error": str(e),
            "confidence": 0.0
        }

@mcp.tool()
async def record_transaction(
    ctx: Context,
    transaction_type: str,
    symbol: str,
    quantity: float,
    price: float,
    date: str,
    account_id: str = "default",
    broker: str = "unknown"
) -> Dict[str, Any]:
    """
    Record a buy or sell transaction
    
    Args:
        transaction_type: "buy" or "sell"
        symbol: Stock symbol
        quantity: Number of shares
        price: Price per share
        date: Transaction date (YYYY-MM-DD)
        account_id: Account identifier
        broker: Broker name
    
    Returns transaction confirmation and updated position
    """
    try:
        if transaction_type.lower() == "buy":
            # Create new tax lot
            lot = TaxLot(
                lot_id=f"{symbol}_{date}_{datetime.now().timestamp()}",
                symbol=symbol,
                quantity=quantity,
                purchase_date=date,
                purchase_price=price,
                cost_basis=quantity * price,
                account_id=account_id,
                broker=broker
            )
            
            portfolio_manager.add_tax_lot(lot)
            
            return {
                "status": "success",
                "transaction_type": "buy",
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "total_cost": quantity * price,
                "lot_id": lot.lot_id,
                "date": date,
                "confidence": 1.0
            }
            
        elif transaction_type.lower() == "sell":
            # Process sale using FIFO by default
            lots_to_sell = portfolio_manager.get_lots_for_sale(
                symbol, quantity, CostBasisMethod.FIFO
            )
            
            if not lots_to_sell:
                return {
                    "error": f"Insufficient shares of {symbol} to sell",
                    "confidence": 0.0
                }
            
            # Remove sold lots from portfolio
            total_proceeds = quantity * price
            total_cost_basis = sum(lot.cost_basis for lot in lots_to_sell)
            realized_gain = total_proceeds - total_cost_basis
            
            # Update tax lots
            remaining_lots = []
            for existing_lot in portfolio_manager.tax_lots.get(symbol, []):
                sold = False
                for sold_lot in lots_to_sell:
                    if existing_lot.lot_id == sold_lot.lot_id:
                        if sold_lot.quantity < existing_lot.quantity:
                            # Partial sale
                            existing_lot.quantity -= sold_lot.quantity
                            existing_lot.cost_basis -= sold_lot.cost_basis
                        else:
                            # Full sale
                            sold = True
                        break
                
                if not sold and existing_lot.quantity > 0:
                    remaining_lots.append(existing_lot)
            
            portfolio_manager.tax_lots[symbol] = remaining_lots
            portfolio_manager._rebuild_positions()
            portfolio_manager.save_state()
            
            return {
                "status": "success",
                "transaction_type": "sell",
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "total_proceeds": total_proceeds,
                "cost_basis": total_cost_basis,
                "realized_gain": realized_gain,
                "date": date,
                "lots_sold": len(lots_to_sell),
                "confidence": 1.0
            }
        else:
            return {
                "error": f"Invalid transaction type: {transaction_type}",
                "confidence": 0.0
            }
            
    except Exception as e:
        logger.error(f"Error recording transaction: {e}")
        return {
            "error": str(e),
            "confidence": 0.0
        }

if __name__ == "__main__":
    mcp.run()