import pytest
from piston_core.scheduler import build_dag, schedule_n_units, units_completed_in_time
import pandas as pd


def make_simple_plan():
    df = pd.DataFrame([
        {'TestID': 'A', 'Station': 'S1', 'TestTimeMin': 60, 'DependsOn': ''},
        {'TestID': 'B', 'Station': 'S2', 'TestTimeMin': 30, 'DependsOn': 'A'},
    ])
    return df


def test_build_dag_and_schedule():
    df = make_simple_plan()
    deps, succs, topo = build_dag(df)
    assert len(topo) == 2
    # build tests_info
    tests_info = {
        'r0': {'testid': 'A', 'station': 'S1', 'time_min': 60, 'depends_on': []},
        'r1': {'testid': 'B', 'station': 'S2', 'time_min': 30, 'depends_on': ['r0']},
    }
    st_map = {'S1': {'count': 1, 'uptime': 1.0}, 'S2': {'count': 1, 'uptime': 1.0}}
    mk, finishes, util = schedule_n_units(tests_info, topo, st_map, 1, channels_per_unit=1)
    assert mk > 0
    assert len(finishes) == 1
    assert 'S1' in util and 'S2' in util


def test_units_completed_in_time():
    df = make_simple_plan()
    deps, succs, topo = build_dag(df)
    tests_info = {
        'r0': {'testid': 'A', 'station': 'S1', 'time_min': 60, 'depends_on': []},
        'r1': {'testid': 'B', 'station': 'S2', 'time_min': 30, 'depends_on': ['r0']},
    }
    st_map = {'S1': {'count': 1, 'uptime': 1.0}, 'S2': {'count': 1, 'uptime': 1.0}}
    completed, cp, util = units_completed_in_time(tests_info, topo, st_map, 2.0, channels_per_unit=1)
    assert isinstance(completed, int)
    assert cp > 0.0

