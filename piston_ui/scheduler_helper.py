from typing import Dict, Any, Tuple
from piston_core.scheduler import schedule_n_units, units_completed_in_time, critical_path_hours


def compute_schedule(tests_info: Dict[str, Any], topo, st_map: Dict[str, Any], mode: str, n_req: int = None, hours_avail: float = None, channels_per_unit=None, unit_bias: float = None, bias_max_frac: float = 0.05, bias_window_frac: float = 1.0, serialization_mode: str = 'Auto'):
    """
    Compute schedule outputs given prepared inputs.
    Returns mode-specific tuple:
      - time_for_n -> (mk, finishes, util, cp)
      - units_in_t  -> (completed, cp_lb, util)
    channels_per_unit is forwarded to core scheduler functions. unit_bias if provided overrides internal bias.
    """
    if mode == 'time_for_n':
        if n_req is None or n_req <= 0:
            raise ValueError('Invalid n_req')
        mk, finishes, util = schedule_n_units(
            tests_info, topo, st_map, n_req,
            channels_per_unit=channels_per_unit,
            unit_bias=unit_bias,
            bias_max_frac=bias_max_frac,
            bias_window_frac=bias_window_frac,
            serialization_mode=serialization_mode,
        )
        cp = critical_path_hours(tests_info, topo, st_map)
        return mk, finishes, util, cp
    else:
        if hours_avail is None or hours_avail <= 0.0:
            raise ValueError('Invalid hours_avail')
        completed, cp_lb, util = units_completed_in_time(tests_info, topo, st_map, hours_avail, channels_per_unit=channels_per_unit, unit_bias=unit_bias)
        return completed, cp_lb, util
