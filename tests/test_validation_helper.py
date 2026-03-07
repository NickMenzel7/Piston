import pandas as pd
from piston_ui.validation_helper import find_invalid_tests, build_tests_info


def test_find_invalid_tests_empty_and_missing_station():
    df = pd.DataFrame([
        {'TestID': '', 'Station': 'A', 'TestTimeMin': 10},
        {'TestID': 'T2', 'Station': None, 'TestTimeMin': 5},
    ])
    problems, bad_idx = find_invalid_tests(df, pd.DataFrame([{'Station': 'A'}]), {})
    assert len(problems) == 2
    assert set(bad_idx) == {0, 1}


def test_build_tests_info_parses_time():
    df = pd.DataFrame([
        {'TestID': 'T1', 'Station': 'S1', 'TestTimeMin': '00:30:00'},
        {'TestID': 'T2', 'Station': 'S2', 'TestTimeMin': 45},
    ])
    deps = {'r0': [], 'r1': ['r0']}

    def parse_time_to_minutes(x):
        # simple parser for HH:MM:SS -> minutes
        if isinstance(x, (int, float)):
            return float(x)
        h, m, s = str(x).split(':')
        return int(h) * 60 + int(m) + int(s) / 60.0

    info = build_tests_info(df, deps, parse_time_to_minutes)
    assert 'r0' in info and 'r1' in info
    assert abs(info['r0']['time_min'] - 30.0) < 1e-6
    assert abs(info['r1']['time_min'] - 45.0) < 1e-6
    assert info['r1']['depends_on'] == ['r0']
