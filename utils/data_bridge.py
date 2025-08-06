#!/usr/bin/env python3
"""
Data Bridge Utilities for MCP Server Integration
Transforms data between OpenBB formats and MCP server formats
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta

class DataBridge:
    """Handles data format conversions between OpenBB and MCP servers"""
    
    @staticmethod
    def openbb_prices_to_returns(
        price_data: Union[pd.DataFrame, Dict, List],
        method: str = "simple"
    ) -> np.ndarray:
        """
        Convert OpenBB price history to returns matrix for portfolio/risk servers
        
        Args:
            price_data: OpenBB price data (various formats)
            method: "simple" or "log" returns
            
        Returns:
            numpy array of returns (dates x assets)
        """
        # Handle different OpenBB return formats
        if isinstance(price_data, pd.DataFrame):
            prices = price_data
        elif isinstance(price_data, dict):
            # Convert dict to DataFrame
            if 'close' in price_data:
                prices = pd.DataFrame(price_data['close'])
            else:
                prices = pd.DataFrame(price_data)
        elif isinstance(price_data, list):
            # List of price records
            prices = pd.DataFrame(price_data)
        else:
            raise ValueError(f"Unsupported price data format: {type(price_data)}")
        
        # Calculate returns
        if method == "simple":
            returns = prices.pct_change().dropna()
        else:  # log returns
            returns = np.log(prices / prices.shift(1)).dropna()
        
        # Convert to numpy array
        return returns.values
    
    @staticmethod
    def prepare_tax_scenario(
        portfolio_data: Dict[str, Any],
        income_data: Dict[str, Any],
        year: int = 2024
    ) -> Dict[str, Any]:
        """
        Format data for tax MCP server TaxScenario
        
        Args:
            portfolio_data: Portfolio gains/losses
            income_data: Income information
            year: Tax year
            
        Returns:
            Dictionary formatted for TaxScenario
        """
        tax_scenario = {
            "year": year,
            "filing_status": income_data.get("filing_status", "Single"),
            "state": income_data.get("state", None),
            "num_dependents": income_data.get("dependents", 0),
            "w2_income": income_data.get("w2_income", 0),
            "taxable_interest": income_data.get("interest", 0),
            "qualified_dividends": portfolio_data.get("qualified_dividends", 0),
            "ordinary_dividends": portfolio_data.get("ordinary_dividends", 0),
            "short_term_capital_gains": portfolio_data.get("stcg", 0),
            "long_term_capital_gains": portfolio_data.get("ltcg", 0),
            "incentive_stock_option_gains": portfolio_data.get("iso_gains", 0),
            "itemized_deductions": income_data.get("itemized_deductions", 0)
        }
        
        return tax_scenario
    
    @staticmethod
    def format_optimization_request(
        tickers: List[str],
        historical_data: Union[Dict, pd.DataFrame],
        constraints: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Prepare data for portfolio optimization MCP server
        
        Args:
            tickers: List of asset symbols
            historical_data: Historical price/return data
            constraints: Optional portfolio constraints
            
        Returns:
            Dictionary formatted for portfolio optimizer
        """
        # Convert prices to returns
        if isinstance(historical_data, (dict, pd.DataFrame)):
            returns = DataBridge.openbb_prices_to_returns(historical_data)
        else:
            returns = historical_data  # Assume already returns
        
        request = {
            "returns": returns.tolist(),
            "symbols": tickers,
            "risk_free_rate": 0.04,  # Default 4%
            "constraints": constraints or {}
        }
        
        return request
    
    @staticmethod
    def format_risk_request(
        returns: Union[np.ndarray, List],
        weights: Optional[Union[np.ndarray, List]] = None,
        confidence_level: float = 0.95,
        time_horizon: int = 1
    ) -> Dict[str, Any]:
        """
        Prepare data for risk analytics MCP server
        
        Args:
            returns: Historical returns matrix
            weights: Portfolio weights (optional)
            confidence_level: VaR confidence level
            time_horizon: Days for VaR calculation
            
        Returns:
            Dictionary formatted for risk analyzer
        """
        # Convert to list if numpy array
        if isinstance(returns, np.ndarray):
            returns = returns.tolist()
        
        request = {
            "returns": returns,
            "confidence_level": confidence_level,
            "time_horizon": time_horizon,
            "method": "historical"
        }
        
        if weights is not None:
            if isinstance(weights, np.ndarray):
                weights = weights.tolist()
            request["weights"] = weights
        
        return request
    
    @staticmethod
    def parse_openbb_fundamental(
        fundamental_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Extract key metrics from OpenBB fundamental data
        
        Args:
            fundamental_data: OpenBB fundamental response
            
        Returns:
            Dictionary of key financial metrics
        """
        metrics = {}
        
        # Common fundamental fields
        field_mapping = {
            "pe_ratio": ["pe", "peRatio", "price_to_earnings"],
            "eps": ["eps", "earningsPerShare"],
            "revenue": ["revenue", "totalRevenue"],
            "net_income": ["netIncome", "net_income"],
            "debt_to_equity": ["debtToEquity", "debt_to_equity"],
            "roe": ["roe", "returnOnEquity"],
            "current_ratio": ["currentRatio", "current_ratio"],
            "dividend_yield": ["dividendYield", "dividend_yield"]
        }
        
        for metric_name, possible_fields in field_mapping.items():
            for field in possible_fields:
                if field in fundamental_data:
                    metrics[metric_name] = float(fundamental_data[field])
                    break
        
        return metrics
    
    @staticmethod
    def combine_agent_responses(
        responses: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Combine multiple agent responses into a unified analysis
        
        Args:
            responses: List of agent response dictionaries
            
        Returns:
            Combined analysis with consensus and recommendations
        """
        # Extract signals
        signals = []
        confidences = []
        recommendations = []
        risks = []
        
        for response in responses:
            if "signal" in response:
                signals.append(response["signal"])
            if "confidence" in response:
                confidences.append(response["confidence"])
            if "recommendations" in response:
                recommendations.extend(response["recommendations"])
            if "risks" in response:
                risks.extend(response["risks"])
        
        # Determine consensus
        if signals:
            signal_counts = {
                "bullish": signals.count("bullish"),
                "neutral": signals.count("neutral"),
                "bearish": signals.count("bearish")
            }
            consensus_signal = max(signal_counts, key=signal_counts.get)
        else:
            consensus_signal = "neutral"
        
        # Calculate average confidence
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        combined = {
            "timestamp": datetime.now().isoformat(),
            "consensus_signal": consensus_signal,
            "average_confidence": avg_confidence,
            "all_recommendations": list(set(recommendations)),  # Unique
            "all_risks": list(set(risks)),  # Unique
            "agent_count": len(responses)
        }
        
        return combined
    
    @staticmethod
    def format_trade_list(
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        portfolio_value: float
    ) -> List[Dict[str, Any]]:
        """
        Generate trade list from current to target weights
        
        Args:
            current_weights: Current portfolio weights
            target_weights: Target portfolio weights
            portfolio_value: Total portfolio value
            
        Returns:
            List of trades to execute
        """
        trades = []
        
        all_symbols = set(current_weights.keys()) | set(target_weights.keys())
        
        for symbol in all_symbols:
            current = current_weights.get(symbol, 0.0)
            target = target_weights.get(symbol, 0.0)
            diff = target - current
            
            if abs(diff) > 0.001:  # Threshold for trading
                trade = {
                    "symbol": symbol,
                    "action": "buy" if diff > 0 else "sell",
                    "weight_change": abs(diff),
                    "dollar_amount": abs(diff * portfolio_value),
                    "from_weight": current,
                    "to_weight": target
                }
                trades.append(trade)
        
        return sorted(trades, key=lambda x: x["dollar_amount"], reverse=True)


class ValidationHelper:
    """Validates data before sending to MCP servers"""
    
    @staticmethod
    def validate_returns_matrix(returns: np.ndarray) -> bool:
        """Validate returns matrix format"""
        if not isinstance(returns, np.ndarray):
            return False
        if returns.ndim != 2:
            return False
        if np.any(np.isnan(returns)):
            return False
        if np.any(np.isinf(returns)):
            return False
        return True
    
    @staticmethod
    def validate_weights(weights: Union[np.ndarray, List]) -> bool:
        """Validate portfolio weights"""
        if isinstance(weights, list):
            weights = np.array(weights)
        
        # Check sum to 1
        if not np.isclose(weights.sum(), 1.0, rtol=1e-5):
            return False
        
        # Check all non-negative
        if np.any(weights < 0):
            return False
        
        return True
    
    @staticmethod
    def validate_tax_scenario(scenario: Dict) -> bool:
        """Validate tax scenario dictionary"""
        required_fields = ["year", "filing_status", "w2_income"]
        
        for field in required_fields:
            if field not in scenario:
                return False
        
        # Check valid filing status
        valid_statuses = ["Single", "Married Filing Jointly", 
                         "Married Filing Separately", "Head of Household"]
        if scenario["filing_status"] not in valid_statuses:
            return False
        
        # Check year range
        if scenario["year"] < 2018 or scenario["year"] > 2024:
            return False
        
        return True


# Example usage functions
def example_portfolio_optimization():
    """Example of using data bridge for portfolio optimization"""
    
    # Simulate OpenBB price data
    price_data = {
        "AAPL": [150, 152, 149, 153, 155],
        "MSFT": [300, 302, 298, 305, 307],
        "GOOGL": [2800, 2810, 2790, 2820, 2830]
    }
    
    # Convert to returns
    bridge = DataBridge()
    returns = bridge.openbb_prices_to_returns(pd.DataFrame(price_data))
    
    # Format for optimization
    request = bridge.format_optimization_request(
        tickers=["AAPL", "MSFT", "GOOGL"],
        historical_data=returns
    )
    
    return request


def example_tax_calculation():
    """Example of preparing tax scenario"""
    
    portfolio_data = {
        "ltcg": 10000,
        "stcg": 2000,
        "qualified_dividends": 1500
    }
    
    income_data = {
        "w2_income": 150000,
        "filing_status": "Single",
        "state": "CA"
    }
    
    bridge = DataBridge()
    tax_scenario = bridge.prepare_tax_scenario(portfolio_data, income_data)
    
    return tax_scenario


if __name__ == "__main__":
    print("Data Bridge Utilities for MCP Server Integration")
    print("=" * 50)
    
    # Test portfolio optimization formatting
    opt_request = example_portfolio_optimization()
    print(f"Portfolio optimization request: {len(opt_request['returns'])} days of returns")
    
    # Test tax scenario formatting
    tax_scenario = example_tax_calculation()
    print(f"Tax scenario prepared for: {tax_scenario['filing_status']}")