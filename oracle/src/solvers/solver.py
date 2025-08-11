from shutil import which
import pulp
import os
import logging

# Get logger for this module
logger = logging.getLogger(__name__)

COIN_CMD_PATH = which("cbc") or "/opt/homebrew/opt/cbc/bin/cbc"

def solve_optimization_problem(prob, time_limit=60, gap_rel=0.01, warm_start=True):
    """
    Solve a PuLP optimization problem using the CBC solver with optimized parameters.
    Falls back to default solver if CBC is not available.
    
    Args:
        prob (pulp.LpProblem): The PuLP optimization problem to solve
        time_limit (int): Time limit in seconds
        gap_rel (float): Relative optimality gap
        warm_start (bool): Whether to use warm start
        
    Returns:
        tuple: (status, objective_value) - The solution status and objective value
    """
    try:
        # Check if CBC solver exists
        cbc_exists = os.path.exists(COIN_CMD_PATH) or which("cbc") is not None
        
        if cbc_exists:
            # Convert gap_rel to string to avoid type issues
            gap_rel_str = str(gap_rel)
            
            # Configure the solver with optimized parameters
            solver = pulp.COIN_CMD(
                path=COIN_CMD_PATH,
                timeLimit=time_limit,
                warmStart=warm_start,
                options=[
                    'allowableGap', gap_rel_str,
                    'maxSolutions', '1',
                    'maxNodes', '10000'
                    
                ]
            )
        else:
            # Fallback to default PuLP solver
            logger.info("CBC solver not found, using default PuLP solver")
            solver = None  # Will use default solver
        
        # Solve the problem
        if solver:
            status = prob.solve(solver)
        else:
            status = prob.solve()  # Use default solver
            
        objective_value = pulp.value(prob.objective)
        
        return status, objective_value
    
    except Exception as e:
        logger.error(f"Error solving optimization problem: {str(e)}")
        # Try with default solver as last resort
        try:
            status = prob.solve()
            objective_value = pulp.value(prob.objective)
            return status, objective_value
        except Exception as e2:
            logger.error(f"Failed with default solver too: {str(e2)}")
            return None, None
