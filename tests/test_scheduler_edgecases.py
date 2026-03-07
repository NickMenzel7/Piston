from piston_core.scheduler import schedule_n_units, units_completed_in_time


def test_multi_channel_units_no_marker():
    # Two independent tests (no dependencies) executed across multi-channel units
    tests_info = {
        'r0': {'testid': 'A', 'station': 'S1', 'time_min': 60.0, 'depends_on': []},
        'r1': {'testid': 'B', 'station': 'S2', 'time_min': 30.0, 'depends_on': []},
    }
    topo = ['r0', 'r1']
    st_map = {'S1': {'count': 1, 'uptime': 1.0}, 'S2': {'count': 1, 'uptime': 1.0}}

    # channels_per_unit is a list: first unit has 2 channels, second has 1
    mk, finishes, util = schedule_n_units(tests_info, topo, st_map, 2, channels_per_unit=[2, 1])
    assert isinstance(mk, float)
    assert isinstance(finishes, list) and len(finishes) == 2
    assert mk >= max(finishes)
    assert 'S1' in util and 'S2' in util


def test_marker_based_channel_flows():
    # Marker-based flow: marker task on 'VXG Channel', other tasks repeat per channel
    tests_info = {
        'r0': {'testid': 'M', 'station': 'VXG Channel', 'time_min': 10.0, 'depends_on': []},
        'r1': {'testid': 'C1', 'station': 'S1', 'time_min': 5.0, 'depends_on': ['r0']},
        'r2': {'testid': 'C2', 'station': 'S1', 'time_min': 5.0, 'depends_on': ['r0']},
    }
    topo = ['r0', 'r1', 'r2']
    st_map = {'VXG Channel': {'count': 1, 'uptime': 1.0}, 'S1': {'count': 1, 'uptime': 1.0}}

    # Single unit with two channels -> shared pre-channel + two channel flows
    mk, finishes, util = schedule_n_units(tests_info, topo, st_map, 1, channels_per_unit=[2])
    assert isinstance(mk, float) and mk > 0.0
    assert isinstance(finishes, list) and len(finishes) == 1
    assert 'S1' in util and 'VXG Channel' in util


def test_units_completed_in_time_with_list_pattern():
    tests_info = {
        'r0': {'testid': 'A', 'station': 'S1', 'time_min': 30.0, 'depends_on': []},
        'r1': {'testid': 'B', 'station': 'S2', 'time_min': 30.0, 'depends_on': ['r0']},
    }
    topo = ['r0', 'r1']
    st_map = {'S1': {'count': 1, 'uptime': 1.0}, 'S2': {'count': 1, 'uptime': 1.0}}

    # Pattern repeats: [2,1] will be extended/padded by the implementation
    completed, cp, util = units_completed_in_time(tests_info, topo, st_map, 5.0, channels_per_unit=[2, 1])
    assert isinstance(completed, int)
    assert cp > 0.0
    assert isinstance(util, dict)
