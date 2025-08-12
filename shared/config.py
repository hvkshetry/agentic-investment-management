"""
Configuration loader for personal investment management system.
Loads settings from config/settings.yaml with sensible defaults.
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class Config:
    """
    Singleton configuration manager that loads and provides access to settings.
    """
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file with defaults."""
        # Look for config file in multiple locations
        config_paths = [
            Path.home() / ".investing" / "config" / "settings.yaml",
            Path(__file__).parent.parent / "config" / "settings.yaml",
            Path("config/settings.yaml"),
        ]
        
        config_file = None
        for path in config_paths:
            if path.exists():
                config_file = path
                break
        
        if config_file:
            try:
                with open(config_file, 'r') as f:
                    self._config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_file}")
            except Exception as e:
                logger.error(f"Failed to load config from {config_file}: {e}")
                self._config = self._get_defaults()
        else:
            logger.warning("No configuration file found, using defaults")
            self._config = self._get_defaults()
        
        # Merge with defaults to ensure all keys exist
        self._config = self._merge_with_defaults(self._config)
    
    def _get_defaults(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "user": {
                "tax": {
                    "federal_bracket": 0.24,
                    "state_rate": 0.05,
                    "capital_gains_long": 0.15,
                    "capital_gains_short": 0.24,
                    "medicare_surtax": 0.038,
                },
                "risk": {
                    "max_position_size": 0.20,
                    "min_position_size": 0.01,
                    "var_confidence": 0.95,
                    "risk_tolerance": "moderate",
                    "max_drawdown_tolerance": 0.25,
                },
                "portfolio": {
                    "rebalance_threshold": 0.05,
                    "min_trade_value": 100,
                    "tax_loss_harvest_threshold": 1000,
                    "wash_sale_days": 31,
                },
                "data": {
                    "preferred_provider": "openbb",
                    "fallback_provider": "yfinance",
                    "quality_threshold": 0.7,
                },
            },
            "system": {
                "logging": {
                    "level": "INFO",
                    "file": "~/.investing/investing.log",
                    "max_size_mb": 100,
                    "backup_count": 5,
                },
                "performance": {
                    "parallel_workers": 4,
                    "timeout_seconds": 300,
                },
                "backup": {
                    "enabled": True,
                    "max_backups": 10,
                    "backup_on_change": True,
                },
            },
            "allocation": {
                "target": {
                    "stocks": 0.60,
                    "bonds": 0.30,
                    "alternatives": 0.10,
                },
                "bands": {
                    "stocks": 0.05,
                    "bonds": 0.03,
                    "alternatives": 0.02,
                },
            },
            "watchlist": [],
        }
    
    def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge configuration with defaults."""
        defaults = self._get_defaults()
        return self._deep_merge(defaults, config or {})
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to config value (e.g., "user.tax.federal_bracket")
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_tax_rates(self) -> Dict[str, Decimal]:
        """Get tax rates as Decimal for accurate calculations."""
        tax_config = self.get("user.tax", {})
        return {
            key: Decimal(str(value))
            for key, value in tax_config.items()
        }
    
    def get_risk_params(self) -> Dict[str, Any]:
        """Get risk parameters."""
        return self.get("user.risk", {})
    
    def get_portfolio_rules(self) -> Dict[str, Any]:
        """Get portfolio management rules."""
        return self.get("user.portfolio", {})
    
    def get_data_config(self) -> Dict[str, Any]:
        """Get data provider configuration."""
        return self.get("user.data", {})
    
    def get_allocation_targets(self) -> Dict[str, float]:
        """Get target asset allocation."""
        return self.get("allocation.target", {})
    
    def get_allocation_bands(self) -> Dict[str, float]:
        """Get allocation rebalancing bands."""
        return self.get("allocation.bands", {})
    
    def get_watchlist(self) -> list:
        """Get watchlist symbols."""
        return self.get("watchlist", [])
    
    def is_aggressive_investor(self) -> bool:
        """Check if user has aggressive risk tolerance."""
        return self.get("user.risk.risk_tolerance") == "aggressive"
    
    def is_conservative_investor(self) -> bool:
        """Check if user has conservative risk tolerance."""
        return self.get("user.risk.risk_tolerance") == "conservative"
    
    def get_max_position_size(self) -> Decimal:
        """Get maximum position size as Decimal."""
        return Decimal(str(self.get("user.risk.max_position_size", 0.20)))
    
    def get_min_trade_value(self) -> Decimal:
        """Get minimum trade value as Decimal."""
        return Decimal(str(self.get("user.portfolio.min_trade_value", 100)))
    
    def reload(self):
        """Reload configuration from file."""
        self._config = None
        self._load_config()
        logger.info("Configuration reloaded")


# Global config instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return config