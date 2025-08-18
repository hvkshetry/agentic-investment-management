#!/usr/bin/env python3
"""
Tax Reconciliation System - Single Source of Truth
Ensures tax calculations are consistent across all portfolio revisions
Recomputes tax on every revision and maintains immutable audit trail
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)


@dataclass
class TaxLot:
    """Immutable tax lot record"""
    symbol: str
    quantity: float
    purchase_date: datetime
    purchase_price: float
    cost_basis: float
    lot_id: str
    
    @property
    def is_long_term(self) -> bool:
        """Check if lot qualifies for long-term capital gains"""
        days_held = (datetime.now(timezone.utc) - self.purchase_date).days
        return days_held > 365
    
    def calculate_gain(self, sale_price: float, sale_quantity: float) -> Dict[str, float]:
        """Calculate gain/loss for partial or full sale"""
        if sale_quantity > self.quantity:
            raise ValueError(f"Cannot sell {sale_quantity} shares from lot with {self.quantity}")
        
        sale_proceeds = sale_quantity * sale_price
        cost_basis_sold = (sale_quantity / self.quantity) * self.cost_basis
        gain_loss = sale_proceeds - cost_basis_sold
        
        return {
            "proceeds": sale_proceeds,
            "cost_basis": cost_basis_sold,
            "gain_loss": gain_loss,
            "is_long_term": self.is_long_term,
            "quantity_sold": sale_quantity,
            "quantity_remaining": self.quantity - sale_quantity
        }


@dataclass
class TaxArtifact:
    """Immutable tax calculation artifact for audit trail"""
    artifact_id: str
    timestamp: datetime
    allocation_id: str  # Links to portfolio allocation
    tax_year: int
    positions: Dict[str, float]  # Symbol -> weight
    realized_gains: Dict[str, float]
    unrealized_gains: Dict[str, float]
    tax_liability: Dict[str, float]
    wash_sales: List[Dict[str, Any]]
    checksum: str = field(init=False)
    
    def __post_init__(self):
        """Generate checksum after initialization"""
        self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """Generate deterministic checksum for verification"""
        content = {
            "artifact_id": self.artifact_id,
            "timestamp": self.timestamp.isoformat(),
            "allocation_id": self.allocation_id,
            "tax_year": self.tax_year,
            "positions": self.positions,
            "realized_gains": self.realized_gains,
            "unrealized_gains": self.unrealized_gains,
            "tax_liability": self.tax_liability,
            "wash_sales": self.wash_sales
        }
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        # Ensure timestamp has proper timezone format
        timestamp_str = self.timestamp.isoformat()
        if not timestamp_str.endswith(('Z', '+00:00', '-00:00')):
            timestamp_str += "Z"
        elif timestamp_str.endswith('+00:00'):
            timestamp_str = timestamp_str[:-6] + "Z"
        
        return {
            "artifact_id": self.artifact_id,
            "timestamp": timestamp_str,
            "allocation_id": self.allocation_id,
            "tax_year": self.tax_year,
            "positions": self.positions,
            "realized_gains": self.realized_gains,
            "unrealized_gains": self.unrealized_gains,
            "tax_liability": self.tax_liability,
            "wash_sales": self.wash_sales,
            "checksum": self.checksum
        }


class TaxReconciliation:
    """
    Single source of truth for tax calculations.
    Ensures consistency across portfolio revisions.
    """
    
    def __init__(self, tax_year: int = 2024):
        self.tax_year = tax_year
        self.tax_lots: Dict[str, List[TaxLot]] = {}  # Symbol -> List of lots
        self.artifacts: List[TaxArtifact] = []  # Historical artifacts
        self.current_artifact: Optional[TaxArtifact] = None
        
        # Tax rates (2024)
        self.tax_rates = {
            "short_term": {
                "brackets": [
                    (11600, 0.10),   # 10% bracket
                    (47150, 0.12),   # 12% bracket
                    (100525, 0.22),  # 22% bracket
                    (191950, 0.24),  # 24% bracket
                    (243725, 0.32),  # 32% bracket
                    (609350, 0.35),  # 35% bracket
                    (float('inf'), 0.37)  # 37% bracket
                ]
            },
            "long_term": {
                "brackets": [
                    (47025, 0.00),   # 0% bracket
                    (518900, 0.15),  # 15% bracket
                    (float('inf'), 0.20)  # 20% bracket
                ]
            },
            "niit": 0.038,  # Net Investment Income Tax
            "state": {}  # State-specific rates
        }
        
        # Wash sale tracking
        self.wash_sale_window = 61  # 30 days before + 30 days after + sale day
        self.sale_history: List[Dict[str, Any]] = []
    
    def load_tax_lots(self, lots: List[Dict[str, Any]]) -> None:
        """Load tax lots from portfolio state"""
        self.tax_lots.clear()
        
        for lot_data in lots:
            lot = TaxLot(
                symbol=lot_data["symbol"],
                quantity=lot_data["quantity"],
                purchase_date=datetime.fromisoformat(lot_data["purchase_date"]),
                purchase_price=lot_data["purchase_price"],
                cost_basis=lot_data["cost_basis"],
                lot_id=lot_data.get("lot_id", self._generate_lot_id(lot_data))
            )
            
            if lot.symbol not in self.tax_lots:
                self.tax_lots[lot.symbol] = []
            self.tax_lots[lot.symbol].append(lot)
        
        # Sort lots by purchase date for FIFO
        for symbol in self.tax_lots:
            self.tax_lots[symbol].sort(key=lambda x: x.purchase_date)
    
    def recompute_tax_on_revision(self,
                                  allocation_id: str,
                                  current_allocation: Dict[str, float],
                                  target_allocation: Dict[str, float],
                                  portfolio_value: float,
                                  current_prices: Dict[str, float]) -> TaxArtifact:
        """
        Recompute tax impact for portfolio revision.
        This is the SINGLE SOURCE OF TRUTH for tax calculations.
        
        Args:
            allocation_id: Unique ID for this allocation
            current_allocation: Current weights {symbol: weight}
            target_allocation: Target weights after revision
            portfolio_value: Total portfolio value
            current_prices: Current market prices
            
        Returns:
            Immutable TaxArtifact with all tax calculations
        """
        artifact_id = self._generate_artifact_id()
        timestamp = datetime.now(timezone.utc)
        
        # Calculate required trades
        trades = self._calculate_trades(
            current_allocation,
            target_allocation,
            portfolio_value,
            current_prices
        )
        
        # Calculate realized gains/losses
        realized_gains = self._calculate_realized_gains(trades, current_prices)
        
        # Calculate unrealized gains/losses
        unrealized_gains = self._calculate_unrealized_gains(
            target_allocation,
            portfolio_value,
            current_prices
        )
        
        # Check for wash sales
        wash_sales = self._detect_wash_sales(trades)
        
        # Adjust realized losses for wash sales
        if wash_sales:
            realized_gains = self._adjust_for_wash_sales(realized_gains, wash_sales)
        
        # Calculate tax liability
        tax_liability = self._calculate_tax_liability(realized_gains)
        
        # Create immutable artifact
        artifact = TaxArtifact(
            artifact_id=artifact_id,
            timestamp=timestamp,
            allocation_id=allocation_id,
            tax_year=self.tax_year,
            positions=target_allocation,
            realized_gains=realized_gains,
            unrealized_gains=unrealized_gains,
            tax_liability=tax_liability,
            wash_sales=wash_sales
        )
        
        # Store artifact
        self.artifacts.append(artifact)
        self.current_artifact = artifact
        
        # Update sale history for wash sale tracking
        self._update_sale_history(trades, timestamp)
        
        logger.info(f"Created tax artifact {artifact_id} for allocation {allocation_id}")
        logger.info(f"Tax impact: ${tax_liability.get('total', 0):.2f}")
        
        return artifact
    
    def _calculate_trades(self,
                         current: Dict[str, float],
                         target: Dict[str, float],
                         portfolio_value: float,
                         prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """Calculate required trades to move from current to target allocation"""
        trades = []
        
        all_symbols = set(current.keys()) | set(target.keys())
        
        for symbol in all_symbols:
            current_weight = current.get(symbol, 0)
            target_weight = target.get(symbol, 0)
            weight_change = target_weight - current_weight
            
            if abs(weight_change) > 0.001:  # Threshold for trade
                current_value = current_weight * portfolio_value
                target_value = target_weight * portfolio_value
                value_change = target_value - current_value
                
                price = prices.get(symbol, 0)
                if price > 0:
                    shares_change = value_change / price
                    
                    trades.append({
                        "symbol": symbol,
                        "action": "buy" if value_change > 0 else "sell",
                        "shares": abs(shares_change),
                        "price": price,
                        "value": abs(value_change),
                        "current_weight": current_weight,
                        "target_weight": target_weight
                    })
        
        return trades
    
    def _calculate_realized_gains(self,
                                 trades: List[Dict[str, Any]],
                                 prices: Dict[str, float]) -> Dict[str, float]:
        """Calculate realized capital gains/losses from trades"""
        total_stcg = 0
        total_ltcg = 0
        
        for trade in trades:
            if trade["action"] == "sell":
                symbol = trade["symbol"]
                quantity = trade["shares"]
                sale_price = trade["price"]
                
                if symbol in self.tax_lots:
                    # Use FIFO to determine which lots are sold
                    remaining_to_sell = quantity
                    
                    for lot in self.tax_lots[symbol]:
                        if remaining_to_sell <= 0:
                            break
                        
                        if lot.quantity > 0:
                            sell_from_lot = min(remaining_to_sell, lot.quantity)
                            gain_info = lot.calculate_gain(sale_price, sell_from_lot)
                            
                            if gain_info["is_long_term"]:
                                total_ltcg += gain_info["gain_loss"]
                            else:
                                total_stcg += gain_info["gain_loss"]
                            
                            # Update lot quantity
                            lot.quantity = gain_info["quantity_remaining"]
                            remaining_to_sell -= sell_from_lot
        
        return {
            "short_term": total_stcg,
            "long_term": total_ltcg,
            "total": total_stcg + total_ltcg
        }
    
    def _calculate_unrealized_gains(self,
                                   allocation: Dict[str, float],
                                   portfolio_value: float,
                                   prices: Dict[str, float]) -> Dict[str, float]:
        """Calculate unrealized gains for current holdings"""
        total_unrealized = 0
        
        for symbol, weight in allocation.items():
            if symbol in self.tax_lots:
                current_value = weight * portfolio_value
                total_cost_basis = sum(lot.cost_basis for lot in self.tax_lots[symbol] if lot.quantity > 0)
                unrealized = current_value - total_cost_basis
                total_unrealized += unrealized
        
        return {
            "total": total_unrealized,
            "by_symbol": {symbol: 0 for symbol in allocation}  # Simplified
        }
    
    def _detect_wash_sales(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect potential wash sale violations"""
        wash_sales = []
        
        for trade in trades:
            if trade["action"] == "sell" and trade.get("realized_loss", 0) < 0:
                symbol = trade["symbol"]
                
                # Check if same or substantially identical security was purchased
                # within 30 days before or after
                for historical_trade in self.sale_history[-30:]:  # Look back 30 days
                    if historical_trade["symbol"] == symbol and historical_trade["action"] == "buy":
                        wash_sales.append({
                            "symbol": symbol,
                            "loss_disallowed": abs(trade.get("realized_loss", 0)),
                            "sale_date": datetime.now(timezone.utc).isoformat(),
                            "purchase_date": historical_trade["date"]
                        })
        
        return wash_sales
    
    def _adjust_for_wash_sales(self,
                               realized_gains: Dict[str, float],
                               wash_sales: List[Dict[str, Any]]) -> Dict[str, float]:
        """Adjust realized losses for wash sale rules"""
        total_disallowed = sum(ws["loss_disallowed"] for ws in wash_sales)
        
        # Add disallowed losses back (they become part of cost basis)
        adjusted = realized_gains.copy()
        adjusted["short_term"] += total_disallowed
        adjusted["total"] += total_disallowed
        adjusted["wash_sale_adjustment"] = total_disallowed
        
        return adjusted
    
    def _calculate_tax_liability(self, realized_gains: Dict[str, float]) -> Dict[str, float]:
        """Calculate actual tax liability"""
        stcg = realized_gains.get("short_term", 0)
        ltcg = realized_gains.get("long_term", 0)
        
        # Simplified calculation - would use actual income levels in production
        stcg_tax = stcg * 0.24 if stcg > 0 else 0  # Assume 24% bracket
        ltcg_tax = ltcg * 0.15 if ltcg > 0 else 0  # Assume 15% bracket
        
        # NIIT on investment income over threshold
        niit = 0
        if (stcg + ltcg) > 0:
            niit = (stcg + ltcg) * self.tax_rates["niit"]
        
        return {
            "short_term_tax": stcg_tax,
            "long_term_tax": ltcg_tax,
            "niit": niit,
            "total": stcg_tax + ltcg_tax + niit
        }
    
    def verify_consistency(self,
                          artifact: TaxArtifact,
                          allocation: Dict[str, float]) -> Tuple[bool, Optional[str]]:
        """Verify tax artifact is consistent with allocation"""
        # Check positions match
        if set(artifact.positions.keys()) != set(allocation.keys()):
            return False, "Position mismatch between artifact and allocation"
        
        # Check weights match (within tolerance)
        for symbol, weight in allocation.items():
            if abs(artifact.positions.get(symbol, 0) - weight) > 0.001:
                return False, f"Weight mismatch for {symbol}"
        
        # Verify checksum
        calculated_checksum = artifact._calculate_checksum()
        if calculated_checksum != artifact.checksum:
            return False, "Checksum verification failed"
        
        return True, None
    
    def get_artifact_by_allocation(self, allocation_id: str) -> Optional[TaxArtifact]:
        """Retrieve tax artifact for specific allocation"""
        for artifact in reversed(self.artifacts):  # Check most recent first
            if artifact.allocation_id == allocation_id:
                return artifact
        return None
    
    def _generate_artifact_id(self) -> str:
        """Generate unique artifact ID"""
        timestamp = datetime.now(timezone.utc).isoformat()
        return f"tax_{hashlib.sha256(timestamp.encode()).hexdigest()[:8]}"
    
    def _generate_lot_id(self, lot_data: Dict[str, Any]) -> str:
        """Generate unique lot ID"""
        content = f"{lot_data['symbol']}_{lot_data['purchase_date']}_{lot_data['quantity']}"
        return hashlib.sha256(content.encode()).hexdigest()[:8]
    
    def _update_sale_history(self, trades: List[Dict[str, Any]], timestamp: datetime):
        """Update sale history for wash sale tracking"""
        for trade in trades:
            self.sale_history.append({
                "symbol": trade["symbol"],
                "action": trade["action"],
                "quantity": trade["shares"],
                "date": timestamp.isoformat(),
                "price": trade["price"]
            })
        
        # Keep only last 61 days of history
        cutoff = datetime.now(timezone.utc).timestamp() - (61 * 24 * 3600)
        self.sale_history = [
            h for h in self.sale_history
            if datetime.fromisoformat(h["date"]).timestamp() > cutoff
        ]
    
    def export_audit_trail(self, filepath: Path) -> None:
        """Export complete audit trail to file"""
        audit_data = {
            "tax_year": self.tax_year,
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "artifacts": [a.to_dict() for a in self.artifacts],
            "total_artifacts": len(self.artifacts)
        }
        
        with open(filepath, 'w') as f:
            json.dump(audit_data, f, indent=2)
        
        logger.info(f"Exported audit trail with {len(self.artifacts)} artifacts to {filepath}")


class TaxReconciliationCache:
    """Cache for tax reconciliation artifacts"""
    
    def __init__(self, cache_dir: Path = Path("cache/tax_artifacts")):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def save_artifact(self, artifact: TaxArtifact) -> None:
        """Save artifact to cache"""
        filepath = self.cache_dir / f"{artifact.artifact_id}.json"
        with open(filepath, 'w') as f:
            json.dump(artifact.to_dict(), f, indent=2)
    
    def load_artifact(self, artifact_id: str) -> Optional[TaxArtifact]:
        """Load artifact from cache"""
        filepath = self.cache_dir / f"{artifact_id}.json"
        if not filepath.exists():
            return None
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Handle timestamp properly - remove duplicate timezone info
        timestamp_str = data["timestamp"]
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1] + "+00:00"
        elif "+00:00+00:00" in timestamp_str:
            timestamp_str = timestamp_str.replace("+00:00+00:00", "+00:00")
        
        return TaxArtifact(
            artifact_id=data["artifact_id"],
            timestamp=datetime.fromisoformat(timestamp_str),
            allocation_id=data["allocation_id"],
            tax_year=data["tax_year"],
            positions=data["positions"],
            realized_gains=data["realized_gains"],
            unrealized_gains=data["unrealized_gains"],
            tax_liability=data["tax_liability"],
            wash_sales=data["wash_sales"]
        )