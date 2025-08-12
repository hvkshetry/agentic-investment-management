"""
Helper functions extracted from compute_optimal_trades for better maintainability.
Each function is focused on a single responsibility and is under 100 lines.
"""
import logging
import time
from typing import Dict, Optional, Tuple, Any
import pandas as pd
import pulp
from datetime import datetime

logger = logging.getLogger(__name__)


def setup_optimization_problem(
    strategy,
    weight_tax: float,
    weight_drift: float,
    weight_transaction: float,
    weight_factor_model: float,
    weight_cash_drag: float,
    rank_penalty_factor: float,
    debug: bool = False
) -> Tuple[pulp.LpProblem, Dict]:
    """
    Set up the optimization problem with objective function.
    
    Returns:
        Tuple of (problem, weights_dict)
    """
    prob = pulp.LpProblem("PortfolioOptimization", pulp.LpMaximize)
    
    weights = {
        'tax': weight_tax,
        'drift': weight_drift,
        'transaction': weight_transaction,
        'factor_model': weight_factor_model,
        'cash_drag': weight_cash_drag,
        'rank_penalty': rank_penalty_factor
    }
    
    if debug:
        logger.info(f"Optimization weights: {weights}")
    
    return prob, weights


def apply_optimization_constraints(
    prob: pulp.LpProblem,
    strategy,
    buys: Dict,
    sells: Dict,
    gain_loss: pd.DataFrame,
    holding_time_days: int,
    min_notional: float,
    range_min_weight_multiplier: float,
    range_max_weight_multiplier: float,
    enforce_wash_sale_prevention: bool,
    debug: bool = False
) -> None:
    """
    Apply all constraints to the optimization problem.
    
    Modifies prob in place.
    """
    # Add constraints from constraints manager
    strategy.constraints_manager.add_constraints(
        prob=prob,
        buys=buys,
        sells=sells,
        gain_loss=gain_loss,
        optimization_type=strategy.optimization_type,
        targets=strategy.targets,
        actuals=strategy.actuals,
        prices=strategy.prices,
        holding_time_days=holding_time_days,
        min_notional=min_notional,
        range_min_weight_multiplier=range_min_weight_multiplier,
        range_max_weight_multiplier=range_max_weight_multiplier,
        withdrawal_amount=strategy.withdrawal_amount,
        min_cash_amount=strategy.min_cash_amount(),
        debug=debug
    )
    
    # Add wash sale constraints if needed
    if enforce_wash_sale_prevention and strategy.oracle and strategy.oracle.wash_sale_restrictions:
        if debug:
            logger.info("Applying wash sale prevention constraints")
        strategy.oracle.wash_sale_restrictions.add_constraints(
            prob=prob,
            buys=buys,
            sells=sells,
            gain_loss=gain_loss
        )


def build_objective_function(
    prob: pulp.LpProblem,
    strategy,
    buys: Dict,
    sells: Dict,
    weights: Dict,
    debug: bool = False
) -> Dict[str, Any]:
    """
    Build the objective function for the optimization.
    
    Returns:
        Dictionary of objective components
    """
    components = {}
    
    # Tax objective
    if weights['tax'] > 0:
        tax_obj = strategy.objective_manager.get_tax_objective(
            buys=buys,
            sells=sells,
            gain_loss=strategy.gain_loss,
            weight=weights['tax']
        )
        components['tax'] = tax_obj
    
    # Drift objective
    if weights['drift'] > 0:
        drift_obj = strategy.objective_manager.get_drift_objective(
            buys=buys,
            sells=sells,
            targets=strategy.targets,
            actuals=strategy.actuals,
            prices=strategy.prices,
            weight=weights['drift']
        )
        components['drift'] = drift_obj
    
    # Transaction cost objective
    if weights['transaction'] > 0:
        trans_obj = strategy.objective_manager.get_transaction_objective(
            buys=buys,
            sells=sells,
            spreads=strategy.spreads,
            weight=weights['transaction']
        )
        components['transaction'] = trans_obj
    
    # Factor model objective
    if weights['factor_model'] > 0 and strategy.oracle and strategy.oracle.factor_model:
        factor_obj = strategy.objective_manager.get_factor_model_objective(
            buys=buys,
            sells=sells,
            factor_model=strategy.oracle.factor_model,
            weight=weights['factor_model']
        )
        components['factor_model'] = factor_obj
    
    # Cash drag objective
    if weights['cash_drag'] > 0:
        cash_obj = strategy.objective_manager.get_cash_deployment_objective(
            buys=buys,
            weight=weights['cash_drag']
        )
        components['cash_drag'] = cash_obj
    
    # Build combined objective
    total_objective = sum(components.values())
    prob += total_objective, "TotalObjective"
    
    if debug:
        logger.info(f"Objective components: {list(components.keys())}")
    
    return components


def extract_optimization_results(
    buys: Dict,
    sells: Dict,
    gain_loss: pd.DataFrame,
    trade_rounding: int = 4,
    debug: bool = False
) -> pd.DataFrame:
    """
    Extract and format optimization results into a trades DataFrame.
    
    Returns:
        DataFrame with trade details
    """
    trades_list = []
    
    # Extract buy trades
    for identifier, buy_var in buys.items():
        quantity = round(pulp.value(buy_var), trade_rounding)
        if quantity > 0:
            trades_list.append({
                'identifier': identifier,
                'action': 'BUY',
                'quantity': quantity,
                'lot_id': None
            })
    
    # Extract sell trades
    for idx, lot in gain_loss.iterrows():
        sell_var = sells.get((lot['identifier'], lot['lot_id']))
        if sell_var:
            quantity = round(pulp.value(sell_var), trade_rounding)
            if quantity > 0:
                trades_list.append({
                    'identifier': lot['identifier'],
                    'action': 'SELL',
                    'quantity': quantity,
                    'lot_id': lot['lot_id']
                })
    
    trades_df = pd.DataFrame(trades_list)
    
    if debug:
        logger.info(f"Extracted {len(trades_df)} trades")
        if not trades_df.empty:
            logger.debug(f"Trade summary:\n{trades_df.groupby('action')['quantity'].sum()}")
    
    return trades_df


def calculate_improvement_metrics(
    optimized_value: float,
    no_trades_value: float,
    buy_only_value: Optional[float] = None,
    debug: bool = False
) -> Dict[str, float]:
    """
    Calculate improvement metrics for optimization results.
    
    Returns:
        Dictionary with improvement metrics
    """
    metrics = {
        'optimized_value': optimized_value,
        'no_trades_value': no_trades_value,
        'improvement': optimized_value - no_trades_value if no_trades_value else 0,
        'improvement_pct': ((optimized_value - no_trades_value) / abs(no_trades_value) * 100) 
                          if no_trades_value and no_trades_value != 0 else 0
    }
    
    if buy_only_value is not None:
        metrics['buy_only_value'] = buy_only_value
        metrics['buy_only_improvement'] = buy_only_value - no_trades_value if no_trades_value else 0
    
    if debug:
        logger.info(f"Improvement metrics: {metrics}")
    
    return metrics


def check_trade_thresholds(
    improvement: float,
    rebalance_threshold: Optional[float],
    buy_threshold: Optional[float],
    is_buy_only: bool = False,
    debug: bool = False
) -> bool:
    """
    Check if improvement meets the required thresholds.
    
    Returns:
        True if thresholds are met, False otherwise
    """
    if is_buy_only and buy_threshold is not None:
        threshold_met = improvement >= buy_threshold
        if debug:
            logger.info(f"Buy-only threshold check: {improvement:.4f} >= {buy_threshold:.4f} = {threshold_met}")
        return threshold_met
    
    if rebalance_threshold is not None:
        threshold_met = improvement >= rebalance_threshold
        if debug:
            logger.info(f"Rebalance threshold check: {improvement:.4f} >= {rebalance_threshold:.4f} = {threshold_met}")
        return threshold_met
    
    return True  # No threshold set, always proceed


def log_optimization_summary(
    status: int,
    trades_df: pd.DataFrame,
    metrics: Dict[str, float],
    execution_time: float,
    debug: bool = True
) -> None:
    """
    Log summary of optimization results.
    """
    if not debug:
        return
    
    logger.info("=" * 60)
    logger.info("OPTIMIZATION SUMMARY")
    logger.info("=" * 60)
    
    status_name = pulp.LpStatus[status] if status else "No Solution"
    logger.info(f"Status: {status_name}")
    logger.info(f"Execution time: {execution_time:.2f} seconds")
    
    logger.info(f"Objective value: {metrics.get('optimized_value', 0):.4f}")
    logger.info(f"No-trades value: {metrics.get('no_trades_value', 0):.4f}")
    logger.info(f"Improvement: {metrics.get('improvement', 0):.4f} ({metrics.get('improvement_pct', 0):.2f}%)")
    
    if not trades_df.empty:
        logger.info(f"Total trades: {len(trades_df)}")
        for action in ['BUY', 'SELL']:
            action_trades = trades_df[trades_df['action'] == action]
            if not action_trades.empty:
                logger.info(f"  {action}: {len(action_trades)} trades, total quantity: {action_trades['quantity'].sum():.4f}")
    else:
        logger.info("No trades recommended")
    
    logger.info("=" * 60)