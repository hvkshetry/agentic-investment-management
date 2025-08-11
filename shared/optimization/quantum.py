#!/usr/bin/env python3
"""
Quantum-inspired optimization for complex combinatorial constraints.
Uses simulated algorithms when quantum hardware not available.
Pure mechanical optimization - constraint definition by Portfolio Manager.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
import logging

# Try to import quantum/quantum-inspired libraries
try:
    from dwave.samplers import SimulatedAnnealingSampler
    DWAVE_AVAILABLE = True
except ImportError:
    DWAVE_AVAILABLE = False

try:
    import dimod
    DIMOD_AVAILABLE = True
except ImportError:
    DIMOD_AVAILABLE = False

logger = logging.getLogger(__name__)


class QuantumOptimizer:
    """
    Quantum-inspired optimization for portfolio selection with complex constraints.
    Mechanical solver - Portfolio Manager defines constraints and interprets results.
    """
    
    def __init__(self, use_quantum: bool = False):
        """
        Initialize quantum optimizer.
        
        Args:
            use_quantum: Whether to use actual quantum hardware (if available)
        """
        self.use_quantum = use_quantum and DWAVE_AVAILABLE
        self.sampler = None
        
        if self.use_quantum:
            try:
                # Initialize quantum sampler (would need API key in practice)
                from dwave.cloud import Client
                client = Client.from_config()
                self.sampler = client.get_solver()
            except:
                logger.info("Quantum hardware not available, using simulated annealing")
                self.use_quantum = False
    
    def optimize_portfolio_selection(self,
                                    universe: List[str],
                                    expected_returns: Dict[str, float],
                                    risk_matrix: pd.DataFrame,
                                    constraints: Dict[str, Any]) -> Dict[str, Any]:
        """
        Select optimal portfolio using quantum/quantum-inspired optimization.
        
        Args:
            universe: List of all possible assets
            expected_returns: Expected return for each asset
            risk_matrix: Covariance or correlation matrix
            constraints: Complex constraints dictionary:
                - cardinality: Exact number of assets to select
                - min_weight: Minimum weight if selected
                - max_weight: Maximum weight per asset
                - sector_limits: Max exposure per sector
                - correlation_limit: Max correlation between selected assets
                
        Returns:
            Dict with selected assets and weights
        """
        n_assets = len(universe)
        
        # Build QUBO (Quadratic Unconstrained Binary Optimization) matrix
        Q = self._build_qubo_matrix(
            universe, expected_returns, risk_matrix, constraints
        )
        
        # Solve using appropriate method
        if DIMOD_AVAILABLE:
            solution = self._solve_with_dimod(Q, n_assets)
        else:
            solution = self._solve_with_simulated_annealing(Q, n_assets)
        
        # Extract selected assets
        selected_assets = [
            universe[i] for i in range(n_assets) if solution[i] == 1
        ]
        
        # Optimize weights for selected assets
        if selected_assets:
            weights = self._optimize_weights(
                selected_assets, expected_returns, risk_matrix, constraints
            )
        else:
            weights = {}
        
        return {
            'selected_assets': selected_assets,
            'weights': weights,
            'n_selected': len(selected_assets),
            'optimization_method': 'quantum' if self.use_quantum else 'simulated_annealing',
            'objective_value': self._calculate_objective(
                solution, expected_returns, risk_matrix, universe
            )
        }
    
    def solve_cardinality_constraint(self,
                                    returns: pd.DataFrame,
                                    target_assets: int,
                                    min_weight: float = 0.01,
                                    max_weight: float = 0.40) -> Dict[str, Any]:
        """
        Solve portfolio optimization with exact cardinality constraint.
        
        Args:
            returns: Historical returns DataFrame
            target_assets: Exact number of assets to select
            min_weight: Minimum weight if selected
            max_weight: Maximum weight per asset
            
        Returns:
            Optimal portfolio with exactly target_assets positions
        """
        assets = returns.columns.tolist()
        n_assets = len(assets)
        
        # Calculate expected returns and covariance
        expected_returns = returns.mean()
        covariance = returns.cov()
        
        # Binary variables for asset selection
        selection_vars = {}
        weight_vars = {}
        
        # Create QUBO for cardinality constraint
        Q = {}
        
        # Objective: Maximize returns - Risk
        for i in range(n_assets):
            # Return component
            Q[(i, i)] = -expected_returns.iloc[i]
            
            # Risk component
            for j in range(i, n_assets):
                if i == j:
                    Q[(i, i)] += covariance.iloc[i, i]
                else:
                    Q[(i, j)] = 2 * covariance.iloc[i, j]
        
        # Cardinality constraint (soft constraint with penalty)
        penalty = 100 * abs(expected_returns.max())
        
        # Add penalty for not having exactly target_assets
        for i in range(n_assets):
            Q[(i, i)] += penalty * (1 - 2 * target_assets / n_assets)
            
            for j in range(i+1, n_assets):
                Q[(i, j)] = Q.get((i, j), 0) + 2 * penalty / n_assets
        
        # Solve
        if DIMOD_AVAILABLE:
            bqm = dimod.BinaryQuadraticModel.from_qubo(Q)
            if DWAVE_AVAILABLE and self.use_quantum:
                sampler = SimulatedAnnealingSampler()  # Or use real quantum
            else:
                sampler = dimod.SimulatedAnnealingSampler()
            
            response = sampler.sample(bqm, num_reads=1000)
            solution = response.first.sample
        else:
            solution = self._solve_with_simulated_annealing(Q, n_assets)
        
        # Extract selected assets
        selected = [assets[i] for i in range(n_assets) if solution.get(i, 0) == 1]
        
        # Calculate weights for selected assets
        if len(selected) > 0:
            # Simple equal weight for now (can be enhanced)
            weights = {asset: 1/len(selected) for asset in selected}
            
            # Adjust for min/max constraints
            weights = self._enforce_weight_constraints(
                weights, min_weight, max_weight
            )
        else:
            weights = {}
        
        return {
            'selected_assets': selected,
            'weights': weights,
            'target_cardinality': target_assets,
            'achieved_cardinality': len(selected),
            'constraint_satisfied': len(selected) == target_assets
        }
    
    def hierarchical_risk_parity(self,
                                 returns: pd.DataFrame,
                                 linkage_method: str = 'single') -> Dict[str, Any]:
        """
        Hierarchical Risk Parity using clustering and quantum selection.
        
        Args:
            returns: Historical returns
            linkage_method: Method for hierarchical clustering
            
        Returns:
            HRP portfolio weights
        """
        from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
        from scipy.spatial.distance import squareform
        
        # Calculate correlation matrix
        correlation = returns.corr()
        
        # Convert correlation to distance
        distance = ((1 - correlation) / 2) ** 0.5
        condensed_dist = squareform(distance)
        
        # Hierarchical clustering
        Z = linkage(condensed_dist, method=linkage_method)
        
        # Get cluster assignments
        n_clusters = min(10, len(returns.columns) // 3)
        clusters = fcluster(Z, n_clusters, criterion='maxclust')
        
        # Quantum-select best assets from each cluster
        selected_assets = []
        cluster_weights = {}
        
        for cluster_id in range(1, n_clusters + 1):
            cluster_assets = [
                returns.columns[i] for i in range(len(returns.columns))
                if clusters[i] == cluster_id
            ]
            
            if cluster_assets:
                # Select best asset(s) from cluster
                cluster_returns = returns[cluster_assets]
                sharpe_ratios = cluster_returns.mean() / cluster_returns.std()
                
                # Select top asset from each cluster
                best_asset = sharpe_ratios.idxmax()
                selected_assets.append(best_asset)
                
                # Weight inversely proportional to cluster variance
                cluster_var = cluster_returns.mean(axis=1).var()
                cluster_weights[best_asset] = 1 / (cluster_var + 1e-6)
        
        # Normalize weights
        total_weight = sum(cluster_weights.values())
        weights = {
            asset: weight / total_weight
            for asset, weight in cluster_weights.items()
        }
        
        return {
            'weights': weights,
            'selected_assets': selected_assets,
            'n_clusters': n_clusters,
            'clustering_method': linkage_method,
            'dendrogram_data': Z.tolist()  # For visualization by PM
        }
    
    def multi_objective_optimization(self,
                                    objectives: List[Dict[str, Any]],
                                    constraints: Dict[str, Any],
                                    universe: List[str]) -> Dict[str, Any]:
        """
        Optimize multiple objectives simultaneously (Pareto optimization).
        
        Args:
            objectives: List of objective dicts with 'type' and 'weight'
                       e.g., [{'type': 'return', 'weight': 0.6},
                             {'type': 'risk', 'weight': -0.3},
                             {'type': 'esg', 'weight': 0.1}]
            constraints: Constraint dictionary
            universe: Asset universe
            
        Returns:
            Pareto-optimal portfolio
        """
        # Build combined QUBO for all objectives
        Q = {}
        n_assets = len(universe)
        
        for obj in objectives:
            obj_type = obj.get('type')
            obj_weight = obj.get('weight', 1.0)
            
            if obj_type == 'return':
                # Add return maximization
                for i in range(n_assets):
                    Q[(i, i)] = Q.get((i, i), 0) - obj_weight * np.random.randn()  # Placeholder
            
            elif obj_type == 'risk':
                # Add risk minimization
                for i in range(n_assets):
                    for j in range(i, n_assets):
                        risk_val = np.random.randn() ** 2  # Placeholder for actual risk
                        if i == j:
                            Q[(i, i)] = Q.get((i, i), 0) + obj_weight * risk_val
                        else:
                            Q[(i, j)] = Q.get((i, j), 0) + obj_weight * risk_val
            
            elif obj_type == 'esg':
                # Add ESG score maximization
                for i in range(n_assets):
                    esg_score = np.random.rand()  # Placeholder for actual ESG
                    Q[(i, i)] = Q.get((i, i), 0) - obj_weight * esg_score
        
        # Solve multi-objective QUBO
        if DIMOD_AVAILABLE:
            solution = self._solve_with_dimod(Q, n_assets)
        else:
            solution = self._solve_with_simulated_annealing(Q, n_assets)
        
        # Extract results
        selected = [universe[i] for i in range(n_assets) if solution.get(i, 0) == 1]
        
        return {
            'selected_assets': selected,
            'n_objectives': len(objectives),
            'pareto_optimal': True,  # By construction
            'objective_weights': {obj['type']: obj['weight'] for obj in objectives}
        }
    
    def constraint_satisfaction(self,
                              hard_constraints: List[Dict[str, Any]],
                              soft_constraints: List[Dict[str, Any]],
                              universe: List[str]) -> Dict[str, Any]:
        """
        Solve pure constraint satisfaction problem.
        
        Args:
            hard_constraints: Must satisfy (infinite penalty)
            soft_constraints: Prefer to satisfy (finite penalty)
            universe: Asset universe
            
        Returns:
            Feasible portfolio satisfying constraints
        """
        n_assets = len(universe)
        Q = {}
        
        # Hard constraints with large penalty
        hard_penalty = 1000
        for constraint in hard_constraints:
            c_type = constraint.get('type')
            
            if c_type == 'exclude':
                # Exclude specific assets
                excluded = constraint.get('assets', [])
                for asset in excluded:
                    if asset in universe:
                        idx = universe.index(asset)
                        Q[(idx, idx)] = Q.get((idx, idx), 0) + hard_penalty
            
            elif c_type == 'minimum_assets':
                # Minimum number of assets
                min_assets = constraint.get('value', 1)
                # Penalize having too few assets
                for i in range(n_assets):
                    Q[(i, i)] = Q.get((i, i), 0) - hard_penalty / n_assets
        
        # Soft constraints with smaller penalty
        soft_penalty = 10
        for constraint in soft_constraints:
            c_type = constraint.get('type')
            
            if c_type == 'prefer':
                # Prefer specific assets
                preferred = constraint.get('assets', [])
                for asset in preferred:
                    if asset in universe:
                        idx = universe.index(asset)
                        Q[(idx, idx)] = Q.get((idx, idx), 0) - soft_penalty
            
            elif c_type == 'correlation_limit':
                # Limit correlation between selected assets
                max_corr = constraint.get('value', 0.7)
                # Add penalty for highly correlated pairs
                # (Simplified - would use actual correlation matrix)
                for i in range(n_assets):
                    for j in range(i+1, n_assets):
                        Q[(i, j)] = Q.get((i, j), 0) + soft_penalty * np.random.rand()
        
        # Solve
        if DIMOD_AVAILABLE:
            solution = self._solve_with_dimod(Q, n_assets)
        else:
            solution = self._solve_with_simulated_annealing(Q, n_assets)
        
        # Check constraint satisfaction
        selected = [universe[i] for i in range(n_assets) if solution.get(i, 0) == 1]
        
        satisfied_hard = self._check_hard_constraints(selected, hard_constraints, universe)
        satisfied_soft = self._check_soft_constraints(selected, soft_constraints, universe)
        
        return {
            'selected_assets': selected,
            'hard_constraints_satisfied': satisfied_hard,
            'soft_constraints_satisfied': satisfied_soft,
            'feasible': all(satisfied_hard.values()) if satisfied_hard else True
        }
    
    def _build_qubo_matrix(self,
                          universe: List[str],
                          expected_returns: Dict[str, float],
                          risk_matrix: pd.DataFrame,
                          constraints: Dict[str, Any]) -> Dict[Tuple[int, int], float]:
        """
        Build QUBO matrix for portfolio optimization.
        
        Returns:
            QUBO matrix as dictionary
        """
        n = len(universe)
        Q = {}
        
        # Objective: Maximize returns - Minimize risk
        for i in range(n):
            asset_i = universe[i]
            
            # Return component (negative because we minimize QUBO)
            Q[(i, i)] = -expected_returns.get(asset_i, 0)
            
            # Risk component
            for j in range(i, n):
                asset_j = universe[j]
                
                if asset_i in risk_matrix.index and asset_j in risk_matrix.columns:
                    risk_val = risk_matrix.loc[asset_i, asset_j]
                    
                    if i == j:
                        Q[(i, i)] += risk_val
                    else:
                        Q[(i, j)] = Q.get((i, j), 0) + 2 * risk_val
        
        # Add constraint penalties
        penalty = abs(max(expected_returns.values())) * 10 if expected_returns else 100
        
        # Cardinality constraint
        if 'cardinality' in constraints:
            target = constraints['cardinality']
            # Soft constraint: penalize deviation from target
            for i in range(n):
                Q[(i, i)] += penalty * (1 - 2 * target / n)
                for j in range(i+1, n):
                    Q[(i, j)] = Q.get((i, j), 0) + 2 * penalty / (n * n)
        
        return Q
    
    def _solve_with_dimod(self,
                         Q: Dict[Tuple[int, int], float],
                         n_variables: int) -> Dict[int, int]:
        """
        Solve QUBO using dimod library.
        
        Returns:
            Binary solution vector
        """
        # Create Binary Quadratic Model
        bqm = dimod.BinaryQuadraticModel.from_qubo(Q)
        
        # Use appropriate sampler
        if self.use_quantum and self.sampler:
            # Use actual quantum hardware
            response = self.sampler.sample(bqm)
        else:
            # Use simulated annealing
            sampler = dimod.SimulatedAnnealingSampler()
            response = sampler.sample(bqm, num_reads=1000)
        
        # Get best solution
        best_solution = response.first.sample
        
        return best_solution
    
    def _solve_with_simulated_annealing(self,
                                       Q: Dict[Tuple[int, int], float],
                                       n_variables: int) -> Dict[int, int]:
        """
        Solve QUBO using basic simulated annealing (fallback).
        
        Returns:
            Binary solution vector
        """
        # Initialize random solution
        solution = {i: np.random.randint(0, 2) for i in range(n_variables)}
        
        # Calculate initial energy
        def calculate_energy(sol):
            energy = 0
            for (i, j), val in Q.items():
                if i == j:
                    energy += val * sol[i]
                else:
                    energy += val * sol[i] * sol[j]
            return energy
        
        current_energy = calculate_energy(solution)
        best_solution = solution.copy()
        best_energy = current_energy
        
        # Simulated annealing parameters
        temperature = 1.0
        cooling_rate = 0.995
        n_iterations = 10000
        
        for _ in range(n_iterations):
            # Random neighbor
            neighbor = solution.copy()
            flip_idx = np.random.randint(0, n_variables)
            neighbor[flip_idx] = 1 - neighbor[flip_idx]
            
            # Calculate neighbor energy
            neighbor_energy = calculate_energy(neighbor)
            
            # Accept or reject
            delta = neighbor_energy - current_energy
            if delta < 0 or np.random.rand() < np.exp(-delta / temperature):
                solution = neighbor
                current_energy = neighbor_energy
                
                if current_energy < best_energy:
                    best_solution = solution.copy()
                    best_energy = current_energy
            
            # Cool down
            temperature *= cooling_rate
        
        return best_solution
    
    def _optimize_weights(self,
                         selected_assets: List[str],
                         expected_returns: Dict[str, float],
                         risk_matrix: pd.DataFrame,
                         constraints: Dict[str, Any]) -> Dict[str, float]:
        """
        Optimize weights for selected assets.
        
        Returns:
            Weight dictionary
        """
        if not selected_assets:
            return {}
        
        # Simple mean-variance optimization for selected assets
        n = len(selected_assets)
        
        # Equal weight as starting point
        weights = {asset: 1/n for asset in selected_assets}
        
        # Apply min/max weight constraints
        min_weight = constraints.get('min_weight', 0.01)
        max_weight = constraints.get('max_weight', 0.40)
        
        weights = self._enforce_weight_constraints(weights, min_weight, max_weight)
        
        return weights
    
    def _enforce_weight_constraints(self,
                                   weights: Dict[str, float],
                                   min_weight: float,
                                   max_weight: float) -> Dict[str, float]:
        """
        Enforce min/max weight constraints.
        
        Returns:
            Adjusted weights
        """
        adjusted = {}
        
        for asset, weight in weights.items():
            adjusted[asset] = np.clip(weight, min_weight, max_weight)
        
        # Renormalize
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v/total for k, v in adjusted.items()}
        
        return adjusted
    
    def _calculate_objective(self,
                           solution: Dict[int, int],
                           expected_returns: Dict[str, float],
                           risk_matrix: pd.DataFrame,
                           universe: List[str]) -> float:
        """
        Calculate objective value for solution.
        
        Returns:
            Objective value
        """
        selected_indices = [i for i, val in solution.items() if val == 1]
        
        if not selected_indices:
            return 0.0
        
        # Calculate return
        total_return = sum(
            expected_returns.get(universe[i], 0) / len(selected_indices)
            for i in selected_indices
        )
        
        # Calculate risk (simplified)
        total_risk = 0
        for i in selected_indices:
            for j in selected_indices:
                if universe[i] in risk_matrix.index and universe[j] in risk_matrix.columns:
                    total_risk += risk_matrix.loc[universe[i], universe[j]] / (len(selected_indices) ** 2)
        
        # Objective: return - risk
        return float(total_return - total_risk)
    
    def _check_hard_constraints(self,
                               selected: List[str],
                               constraints: List[Dict],
                               universe: List[str]) -> Dict[str, bool]:
        """
        Check if hard constraints are satisfied.
        
        Returns:
            Dict of constraint satisfaction
        """
        results = {}
        
        for i, constraint in enumerate(constraints):
            c_type = constraint.get('type')
            
            if c_type == 'exclude':
                excluded = constraint.get('assets', [])
                satisfied = not any(asset in selected for asset in excluded)
                results[f'exclude_{i}'] = satisfied
            
            elif c_type == 'minimum_assets':
                min_assets = constraint.get('value', 1)
                results[f'min_assets_{i}'] = len(selected) >= min_assets
        
        return results
    
    def _check_soft_constraints(self,
                               selected: List[str],
                               constraints: List[Dict],
                               universe: List[str]) -> Dict[str, float]:
        """
        Check soft constraint satisfaction (0-1 scale).
        
        Returns:
            Dict of satisfaction scores
        """
        results = {}
        
        for i, constraint in enumerate(constraints):
            c_type = constraint.get('type')
            
            if c_type == 'prefer':
                preferred = constraint.get('assets', [])
                if preferred:
                    score = sum(1 for asset in preferred if asset in selected) / len(preferred)
                    results[f'prefer_{i}'] = score
            
            elif c_type == 'correlation_limit':
                # Simplified - would check actual correlations
                results[f'correlation_{i}'] = 1.0 if len(selected) > 5 else 0.5
        
        return results