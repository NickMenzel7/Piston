import re
from typing import Dict, List
import pandas as pd

from piston_core.scheduler import build_dag


def parse_duration_to_minutes(val):
    if val is None:
        return 0.0
    try:
        if pd.isna(val):
            return 0.0
    except Exception:
        pass
    try:
        if isinstance(val, pd.Timedelta):
            return val.total_seconds() / 60.0
    except Exception:
        pass
    try:
        if isinstance(val, (int, float)):
            if 0.0 <= val < 1.0:
                return float(val) * 24.0 * 60.0
            return float(val)
    except Exception:
        pass
    s = str(val).strip()
    if s == '':
        return 0.0
    m = re.match(r'^(?:(\d{1,2}):)?(\d{1,2}):(\d{2})$', s)
    if m:
        h = int(m.group(1) or 0)
        mm = int(m.group(2))
        ss = int(m.group(3))
        return h * 60 + mm + ss / 60.0
    m2 = re.match(r'^(\d{1,2}):(\d{2})$', s)
    if m2:
        h_or_mm = int(m2.group(1))
        mm = int(m2.group(2))
        if h_or_mm > 59:
            return h_or_mm * 60 + mm
        return h_or_mm * 60 + mm
    try:
        return float(s)
    except Exception:
        pass
    return None


def read_non_test(non_test_df):
    rules = []
    for _, r in non_test_df.iterrows():
        field = str(r.get('Field','')).strip()
        pattern = str(r.get('Pattern','')).strip().lower()
        mtype = str(r.get('MatchType','contains')).strip().lower()
        if field and pattern:
            rules.append((field, mtype, pattern))
    return rules


def apply_non_test_filter(df: pd.DataFrame, rules):
    if not rules or df is None or df.empty:
        return df
    mask = pd.Series([True]*len(df))
    for field, mtype, pattern in rules:
        if field not in df.columns:
            continue
        vals = df[field].astype(str).str.lower()
        if mtype == 'contains':
            mask &= ~vals.str.contains(pattern, na=False)
        elif mtype == 'exact':
            mask &= ~(vals == pattern)
    return df[mask]


def validate_import_rows(import_df: pd.DataFrame, stations_df: pd.DataFrame):
    errors = []
    if import_df is None or import_df.empty:
        return errors
    df = import_df.copy()
    if 'TestID' not in df.columns:
        errors.append("Import missing required column 'TestID'.")
        return errors
    if 'Station' not in df.columns:
        errors.append("Import missing required column 'Station'.")
        return errors
    if 'TestTimeMin' not in df.columns:
        errors.append("Import missing required column 'TestTimeMin'.")
        return errors
    if 'DependsOn' not in df.columns:
        df['DependsOn'] = ''
    known_stations = set(stations_df['Station'].astype(str)) if stations_df is not None else set()
    testids = set(df['TestID'].astype(str))
    for i, r in df.iterrows():
        tid = str(r.get('TestID', '')).strip()
        st = r.get('Station', None)
        if st is None or str(st).strip().lower() in ('', 'none', 'nan'):
            errors.append(f"Row {i}: Station not mapped for TestID '{tid}'")
        else:
            if str(st) not in known_stations:
                errors.append(f"Row {i}: Station '{st}' not found in Stations sheet (TestID '{tid}')")
        dur = r.get('TestTimeMin', None)
        try:
            if dur is None or pd.isna(dur):
                errors.append(f"Row {i}: Missing duration for TestID '{tid}'")
            else:
                if float(dur) < 0:
                    errors.append(f"Row {i}: Negative duration for TestID '{tid}'")
        except Exception:
            errors.append(f"Row {i}: Unparseable duration for TestID '{tid}'")
        dep_str = str(r.get('DependsOn', '')).strip()
        if dep_str:
            for d in [x.strip() for x in dep_str.split(',') if x.strip()]:
                if d not in testids:
                    errors.append(f"Row {i}: DependsOn '{d}' not present among imported TestIDs (for '{tid}')")
    try:
        _ = build_dag(df)
    except Exception as e:
        errors.append(str(e))
    return errors