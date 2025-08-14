#!/usr/bin/env python3
"""
Tax Ledger Manager - Single Source of Truth for Tax Calculations
Ensures consistent tax calculations across all artifacts
"""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class TaxCalculation:
    """Standardized tax calculation result"""
    # Losses harvested
    short_term_losses: float
    long_term_losses: float
    total_losses_harvested: float
    
    # Gains realized
    short_term_gains: float
    long_term_gains: float
    total_gains_realized: float
    
    # Tax savings/costs
    federal_tax_on_stcg: float
    federal_tax_on_ltcg: float
    state_tax_on_stcg: float
    state_tax_on_ltcg: float
    niit_impact: float
    
    # Net results
    total_tax_savings: float  # From losses
    total_tax_cost: float     # From gains
    net_tax_benefit: float    # Savings minus costs
    
    # Rates used
    federal_stcg_rate: float
    federal_ltcg_rate: float
    state_stcg_rate: float
    state_ltcg_rate: float
    niit_rate: float
    
    # Metadata
    calculated_at: str
    session_id: str
    portfolio_value: float
    
class TaxLedgerManager:
    """
    Manages the single source of truth for tax calculations in a session.
    Only the tax-advisor agent should write to this.
    All other agents must read from it.
    """
    
    def __init__(self, session_directory: str):
        """
        Initialize with session directory
        
        Args:
            session_directory: Path to session directory (e.g., ./runs/20250813_143022/)
        """
        self.session_directory = Path(session_directory)
        self.ledger_file = self.session_directory / "tax_ledger.json"
        self._cached_calculation = None
        
    def write_calculation(self, calculation: TaxCalculation) -> None:
        """
        Write tax calculation to ledger (should only be called by tax-advisor)
        
        Args:
            calculation: TaxCalculation object with all tax details
        """
        # Ensure directory exists
        self.session_directory.mkdir(parents=True, exist_ok=True)
        
        # Convert to dictionary
        data = asdict(calculation)
        
        # Add metadata
        data['schema_version'] = '1.0.0'
        data['created_by'] = 'tax-advisor'
        data['immutable'] = True  # Flag that this should not be modified
        
        # Write to file
        with open(self.ledger_file, 'w') as f:
            json.dump(data, f, indent=2)
            
        logger.info(f"Tax ledger written to {self.ledger_file}")
        logger.info(f"Net tax benefit: ${calculation.net_tax_benefit:,.2f}")
        
        # Update cache
        self._cached_calculation = calculation
        
    def read_calculation(self) -> Optional[TaxCalculation]:
        """
        Read tax calculation from ledger
        
        Returns:
            TaxCalculation object or None if not found
        """
        # Check cache first
        if self._cached_calculation:
            return self._cached_calculation
            
        # Check if file exists
        if not self.ledger_file.exists():
            logger.warning(f"Tax ledger not found at {self.ledger_file}")
            return None
            
        # Read from file
        try:
            with open(self.ledger_file, 'r') as f:
                data = json.load(f)
                
            # Remove metadata fields
            data.pop('schema_version', None)
            data.pop('created_by', None)
            data.pop('immutable', None)
            
            # Create TaxCalculation object
            calculation = TaxCalculation(**data)
            
            # Cache it
            self._cached_calculation = calculation
            
            return calculation
            
        except Exception as e:
            logger.error(f"Error reading tax ledger: {e}")
            return None
            
    def get_summary_for_artifacts(self) -> Dict[str, Any]:
        """
        Get standardized tax summary for use in other artifacts
        
        Returns:
            Dictionary with key tax metrics for consistent reporting
        """
        calculation = self.read_calculation()
        if not calculation:
            return {}
            
        return {
            'tax_losses_harvested': calculation.total_losses_harvested,
            'tax_gains_realized': calculation.total_gains_realized,
            'tax_savings': calculation.total_tax_savings,
            'tax_cost': calculation.total_tax_cost,
            'net_tax_benefit': calculation.net_tax_benefit,
            'effective_tax_rate': abs(calculation.net_tax_benefit / calculation.total_losses_harvested) if calculation.total_losses_harvested else 0,
            'portfolio_value': calculation.portfolio_value,
            'calculated_at': calculation.calculated_at,
            'session_id': calculation.session_id
        }
        
    def validate_tax_references(self, artifact: Dict[str, Any], artifact_name: str) -> bool:
        """
        Validate that tax numbers in an artifact match the ledger
        
        Args:
            artifact: Artifact dictionary to validate
            artifact_name: Name of artifact for logging
            
        Returns:
            True if all tax references match, False otherwise
        """
        calculation = self.read_calculation()
        if not calculation:
            logger.warning(f"Cannot validate {artifact_name} - no tax ledger found")
            return False
            
        mismatches = []
        
        # Define mappings of possible field names to ledger values
        field_mappings = {
            'tax_savings': calculation.total_tax_savings,
            'total_tax_savings': calculation.total_tax_savings,
            'tax_benefit': calculation.net_tax_benefit,
            'net_tax_benefit': calculation.net_tax_benefit,
            'after_tax_value': calculation.net_tax_benefit,
            'net_after_tax_benefit': calculation.net_tax_benefit,
            'tax_losses_harvested': calculation.total_losses_harvested,
            'total_losses_harvested': calculation.total_losses_harvested,
            'harvested_losses': calculation.total_losses_harvested
        }
        
        # Recursively check artifact for tax fields
        def check_values(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    
                    # Check if this key is a tax field
                    if key in field_mappings:
                        expected = field_mappings[key]
                        if isinstance(value, (int, float)):
                            # Allow small rounding differences (< $1)
                            if abs(value - expected) > 1.0:
                                mismatches.append(
                                    f"{new_path}: {value:,.2f} != {expected:,.2f} (ledger)"
                                )
                    
                    # Recurse
                    check_values(value, new_path)
                    
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_values(item, f"{path}[{i}]")
                    
        check_values(artifact)
        
        if mismatches:
            logger.error(f"Tax validation failed for {artifact_name}:")
            for mismatch in mismatches:
                logger.error(f"  - {mismatch}")
            return False
            
        logger.info(f"Tax validation passed for {artifact_name}")
        return True
        
    @staticmethod
    def create_from_tax_analysis(
        tax_analysis: Dict[str, Any],
        session_id: str,
        portfolio_value: float
    ) -> TaxCalculation:
        """
        Helper to create TaxCalculation from tax-advisor output
        
        Args:
            tax_analysis: Tax analysis artifact from tax-advisor
            session_id: Session ID
            portfolio_value: Portfolio value from portfolio state
            
        Returns:
            TaxCalculation object
        """
        payload = tax_analysis.get('payload', {})
        harvestable = payload.get('harvestable_losses', {})
        tax_impact = payload.get('tax_impact_analysis', {})
        tax_calcs = tax_impact.get('tax_savings_calculation', {})
        
        # Extract loss/gain values
        st_losses = abs(harvestable.get('total_short_term_losses', 0))
        lt_losses = abs(harvestable.get('total_long_term_losses', 0))
        
        # Extract tax savings
        st_savings = tax_calcs.get('short_term_loss_savings', {})
        lt_savings = tax_calcs.get('long_term_loss_savings', {})
        
        # Get rates from baseline scenario
        baseline = tax_impact.get('baseline_tax_scenario', {})
        
        # Calculate net benefit (this should be consistent!)
        total_tax_savings = st_savings.get('total_savings', 0) + lt_savings.get('total_savings', 0)
        niit_savings = tax_impact.get('niit_impact', {}).get('additional_savings', 0)
        
        return TaxCalculation(
            short_term_losses=st_losses,
            long_term_losses=lt_losses,
            total_losses_harvested=st_losses + lt_losses,
            
            short_term_gains=0,  # To be filled if gains are realized
            long_term_gains=0,
            total_gains_realized=0,
            
            federal_tax_on_stcg=st_savings.get('federal_savings', 0),
            federal_tax_on_ltcg=lt_savings.get('federal_savings', 0),
            state_tax_on_stcg=st_savings.get('ma_state_savings', 0),
            state_tax_on_ltcg=lt_savings.get('ma_state_savings', 0),
            niit_impact=niit_savings,
            
            total_tax_savings=total_tax_savings + niit_savings,
            total_tax_cost=0,  # To be calculated if gains realized
            net_tax_benefit=total_tax_savings + niit_savings,
            
            federal_stcg_rate=baseline.get('federal_marginal_rate', 0) / 100,
            federal_ltcg_rate=0.15,  # Standard LTCG rate
            state_stcg_rate=baseline.get('ma_stcg_rate', 0) / 100,
            state_ltcg_rate=baseline.get('ma_ltcg_rate', 0) / 100,
            niit_rate=0.038,
            
            calculated_at=datetime.now().isoformat(),
            session_id=session_id,
            portfolio_value=portfolio_value
        )