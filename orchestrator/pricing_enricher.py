#!/usr/bin/env python3
"""
Pricing Enrichment Module

Enriches portfolio data with current market prices before analysis.
Ensures tax lots have current_price and current_value fields populated.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class PricingEnricher:
    """Enriches portfolio artifacts with current market prices."""
    
    def __init__(self, price_cache_path: Optional[str] = None):
        """
        Initialize pricing enricher.
        
        Args:
            price_cache_path: Optional path to price cache file
        """
        self.price_cache_path = Path(price_cache_path) if price_cache_path else None
        self.price_cache = self._load_price_cache()
        
    def _load_price_cache(self) -> Dict[str, float]:
        """Load price cache from file if available."""
        if self.price_cache_path and self.price_cache_path.exists():
            try:
                with open(self.price_cache_path) as f:
                    data = json.load(f)
                    return data.get("prices", {})
            except Exception as e:
                logger.warning(f"Failed to load price cache: {e}")
        return {}
    
    def enrich_portfolio_state(
        self, 
        portfolio_state: Dict[str, Any],
        price_source: Optional[Dict[str, float]] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Enrich portfolio state with current prices.
        
        Args:
            portfolio_state: Raw portfolio state from MCP server
            price_source: Optional dict of symbol -> price mappings
            
        Returns:
            Tuple of (enriched_state, enrichment_metadata)
        """
        enriched = portfolio_state.copy()
        metadata = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "enrichment_type": "pricing",
            "statistics": {
                "total_positions": 0,
                "lots_enriched": 0,
                "lots_missing_price": 0,
                "positions_missing_price": []
            }
        }
        
        # Merge price sources (argument takes precedence)
        prices = self.price_cache.copy()
        if price_source:
            prices.update(price_source)
            
        # Enrich positions
        if "positions" in enriched:
            metadata["statistics"]["total_positions"] = len(enriched["positions"])
            
            for symbol, position in enriched["positions"].items():
                # Get current price
                current_price = prices.get(symbol)
                
                if current_price is None:
                    # Try to get from position data
                    current_price = position.get("current_price")
                    
                if current_price is None:
                    # Fall back to last known price or cost basis
                    current_price = position.get("average_cost", 0)
                    metadata["statistics"]["positions_missing_price"].append(symbol)
                    logger.warning(f"No current price for {symbol}, using cost basis")
                
                # Update position
                position["current_price"] = current_price
                position["current_value"] = position.get("total_quantity", 0) * current_price
                
                # Update unrealized gain
                cost_basis = position.get("total_cost_basis", 0)
                position["unrealized_gain"] = position["current_value"] - cost_basis
                position["unrealized_return"] = (
                    (position["current_value"] / cost_basis - 1) 
                    if cost_basis > 0 else 0
                )
                
                # Enrich tax lots
                if "tax_lots" in position:
                    for lot in position["tax_lots"]:
                        if "current_price" not in lot or lot["current_price"] is None:
                            lot["current_price"] = current_price
                            lot["current_value"] = lot.get("quantity", 0) * current_price
                            metadata["statistics"]["lots_enriched"] += 1
                        
                        # Calculate unrealized gain for lot
                        lot_cost = lot.get("cost_basis", 0)
                        lot["unrealized_gain"] = lot["current_value"] - lot_cost
                        
                        # Update holding period
                        if "purchase_date" in lot:
                            # Parse purchase date
                            purchase_str = lot["purchase_date"].replace("Z", "+00:00")
                            if "T" not in purchase_str:
                                # Date only, add time
                                purchase_str += "T00:00:00+00:00"
                            purchase_date = datetime.fromisoformat(purchase_str)
                            days_held = (datetime.now(timezone.utc) - purchase_date).days
                            lot["holding_period_days"] = days_held
                            lot["is_long_term"] = days_held > 365
        
        # Update summary totals
        if "summary" in enriched:
            total_value = sum(
                pos.get("current_value", 0) 
                for pos in enriched.get("positions", {}).values()
            )
            total_cost = sum(
                pos.get("total_cost_basis", 0)
                for pos in enriched.get("positions", {}).values()
            )
            
            enriched["summary"]["total_value"] = total_value
            enriched["summary"]["total_cost"] = total_cost
            enriched["summary"]["total_gain_loss"] = total_value - total_cost
            enriched["summary"]["total_return"] = (
                (total_value / total_cost - 1) if total_cost > 0 else 0
            )
            
        # Add enrichment metadata
        enriched["enrichment"] = metadata
        
        return enriched, metadata
    
    def enrich_tax_lots(
        self,
        tax_lots: List[Dict[str, Any]],
        price_source: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Enrich a list of tax lots with current prices.
        
        Args:
            tax_lots: List of tax lot dictionaries
            price_source: Dict of symbol -> price mappings
            
        Returns:
            List of enriched tax lots
        """
        enriched_lots = []
        
        for lot in tax_lots:
            enriched_lot = lot.copy()
            symbol = lot.get("symbol", "")
            
            # Get current price
            current_price = price_source.get(symbol)
            if current_price is None:
                current_price = lot.get("purchase_price", 0)
                logger.warning(f"No current price for {symbol} lot, using purchase price")
                
            # Enrich lot
            enriched_lot["current_price"] = current_price
            enriched_lot["current_value"] = lot.get("quantity", 0) * current_price
            
            # Calculate unrealized gain
            cost_basis = lot.get("cost_basis", 0)
            enriched_lot["unrealized_gain"] = enriched_lot["current_value"] - cost_basis
            enriched_lot["unrealized_return"] = (
                (enriched_lot["current_value"] / cost_basis - 1)
                if cost_basis > 0 else 0
            )
            
            # Update holding period
            if "purchase_date" in lot:
                try:
                    # Parse purchase date
                    purchase_str = lot["purchase_date"].replace("Z", "+00:00")
                    if "T" not in purchase_str:
                        # Date only, add time
                        purchase_str += "T00:00:00+00:00"
                    purchase_date = datetime.fromisoformat(purchase_str)
                    days_held = (datetime.now(timezone.utc) - purchase_date).days
                    enriched_lot["holding_period_days"] = days_held
                    enriched_lot["is_long_term"] = days_held > 365
                except Exception as e:
                    logger.warning(f"Failed to parse purchase date: {e}")
                    
            enriched_lots.append(enriched_lot)
            
        return enriched_lots
    
    def validate_enrichment(self, enriched_state: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate that enrichment was successful.
        
        Args:
            enriched_state: Enriched portfolio state
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Check for enrichment metadata
        if "enrichment" not in enriched_state:
            issues.append("Missing enrichment metadata")
            return False, issues
            
        metadata = enriched_state["enrichment"]
        stats = metadata.get("statistics", {})
        
        # Check for missing prices
        missing_positions = stats.get("positions_missing_price", [])
        if missing_positions:
            issues.append(f"Missing prices for: {', '.join(missing_positions)}")
            
        # Check that all tax lots have prices
        for symbol, position in enriched_state.get("positions", {}).items():
            for i, lot in enumerate(position.get("tax_lots", [])):
                if "current_price" not in lot:
                    issues.append(f"{symbol} lot {i} missing current_price")
                if "current_value" not in lot:
                    issues.append(f"{symbol} lot {i} missing current_value")
                    
        # Check summary totals
        summary = enriched_state.get("summary", {})
        if summary.get("total_value", 0) <= 0:
            issues.append("Invalid total_value in summary")
            
        return len(issues) == 0, issues
    
    def save_price_cache(self, prices: Dict[str, float]) -> None:
        """Save price cache to file."""
        if self.price_cache_path:
            cache_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "prices": prices
            }
            try:
                self.price_cache_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.price_cache_path, 'w') as f:
                    json.dump(cache_data, f, indent=2)
                logger.info(f"Saved {len(prices)} prices to cache")
            except Exception as e:
                logger.error(f"Failed to save price cache: {e}")


def enrich_session_artifacts(session_dir: Path) -> Dict[str, Any]:
    """
    Enrich all artifacts in a session directory with pricing data.
    
    Args:
        session_dir: Path to session directory
        
    Returns:
        Summary of enrichment results
    """
    enricher = PricingEnricher(price_cache_path="shared/cache/market_data_cache.json")
    results = {
        "session": str(session_dir),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "artifacts_enriched": [],
        "issues": []
    }
    
    # Look for portfolio snapshot
    snapshot_path = session_dir / "portfolio_snapshot.json"
    if snapshot_path.exists():
        try:
            with open(snapshot_path) as f:
                portfolio_state = json.load(f)
                
            # Enrich the portfolio state
            enriched, metadata = enricher.enrich_portfolio_state(portfolio_state)
            
            # Validate enrichment
            is_valid, issues = enricher.validate_enrichment(enriched)
            
            if is_valid:
                # Save enriched version
                enriched_path = session_dir / "portfolio_snapshot_enriched.json"
                with open(enriched_path, 'w') as f:
                    json.dump(enriched, f, indent=2)
                    
                results["artifacts_enriched"].append({
                    "file": "portfolio_snapshot.json",
                    "enriched_file": "portfolio_snapshot_enriched.json",
                    "lots_enriched": metadata["statistics"]["lots_enriched"],
                    "positions_missing_price": metadata["statistics"]["positions_missing_price"]
                })
            else:
                results["issues"].extend(issues)
                
        except Exception as e:
            results["issues"].append(f"Failed to enrich portfolio snapshot: {str(e)}")
            
    # Look for tax analysis artifacts
    for tax_file in session_dir.glob("tax_*.json"):
        try:
            with open(tax_file) as f:
                tax_data = json.load(f)
                
            if "tax_lots" in tax_data:
                # Load prices from enriched portfolio if available
                prices = {}
                if (session_dir / "portfolio_snapshot_enriched.json").exists():
                    with open(session_dir / "portfolio_snapshot_enriched.json") as f:
                        enriched_portfolio = json.load(f)
                        for symbol, pos in enriched_portfolio.get("positions", {}).items():
                            prices[symbol] = pos.get("current_price", 0)
                            
                # Enrich tax lots
                enriched_lots = enricher.enrich_tax_lots(tax_data["tax_lots"], prices)
                tax_data["tax_lots"] = enriched_lots
                tax_data["enrichment"] = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "lots_enriched": len(enriched_lots)
                }
                
                # Save enriched version
                enriched_path = tax_file.parent / f"{tax_file.stem}_enriched.json"
                with open(enriched_path, 'w') as f:
                    json.dump(tax_data, f, indent=2)
                    
                results["artifacts_enriched"].append({
                    "file": tax_file.name,
                    "enriched_file": enriched_path.name,
                    "lots_enriched": len(enriched_lots)
                })
                
        except Exception as e:
            results["issues"].append(f"Failed to enrich {tax_file.name}: {str(e)}")
            
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enrich portfolio artifacts with pricing")
    parser.add_argument("session_dir", help="Path to session directory")
    parser.add_argument("--price-cache", default="shared/cache/market_data_cache.json",
                       help="Path to price cache file")
    
    args = parser.parse_args()
    
    results = enrich_session_artifacts(Path(args.session_dir))
    
    print(f"\nPricing Enrichment Results")
    print("=" * 50)
    print(f"Session: {results['session']}")
    print(f"Artifacts enriched: {len(results['artifacts_enriched'])}")
    
    for artifact in results["artifacts_enriched"]:
        print(f"  ✅ {artifact['file']} -> {artifact['enriched_file']}")
        if artifact.get("positions_missing_price"):
            print(f"     ⚠️  Missing prices: {', '.join(artifact['positions_missing_price'])}")
            
    if results["issues"]:
        print("\nIssues:")
        for issue in results["issues"]:
            print(f"  ❌ {issue}")