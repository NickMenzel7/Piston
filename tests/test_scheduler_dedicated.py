import math
from piston_core.scheduler import schedule_n_units, critical_path_hours


def test_fully_dedicated_makespan_equals_single_unit_critical_path():
    # simple linear plan of three tests that must run sequentially
    tests_info = {
        't1': {'depends_on': [], 'station': 'A', 'time_min': 60, 'testid': 't1'},
        't2': {'depends_on': ['t1'], 'station': 'B', 'time_min': 120, 'testid': 't2'},
        't3': {'depends_on': ['t2'], 'station': 'C', 'time_min': 30, 'testid': 't3'},
    }
    topo = ['t1', 't2', 't3']
    # station map: each station has count >= n_units (fully dedicated)
    n_units = 10
    st_map = {'A': {'count': n_units, 'uptime': 1.0},
              'B': {'count': n_units, 'uptime': 1.0},
              'C': {'count': n_units, 'uptime': 1.0}}

    cp = critical_path_hours(tests_info, topo, st_map)

    # run with default (weak) bias
    mk, unit_finishes, util = schedule_n_units(tests_info, topo, st_map, n_units, channels_per_unit=1, unit_bias=None)
    assert math.isclose(mk, cp, rel_tol=1e-9), f"makespan {mk} != critical_path {cp}"
    for f in unit_finishes:
        assert math.isclose(f, cp, rel_tol=1e-9)

    # run with a strong bias value, results should be identical in fully-dedicated case
    mk2, unit_finishes2, util2 = schedule_n_units(tests_info, topo, st_map, n_units, channels_per_unit=1, unit_bias=1.0)
    assert math.isclose(mk2, cp, rel_tol=1e-9)
    for f in unit_finishes2:
        assert math.isclose(f, cp, rel_tol=1e-9)
