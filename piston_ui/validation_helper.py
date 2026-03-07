import re
import pandas as pd
from typing import Tuple, List, Dict, Any, Optional
from piston_core.constants import is_hidden_station


def _normalize_station_name(s: str) -> str:
    """Return a normalized station name for comparison: lowercase, remove non-alphanumeric."""
    try:
        if s is None:
            return ''
        return re.sub(r'[^0-9a-z]', '', str(s).strip().lower())
    except Exception:
        return ''


def find_invalid_tests(df: pd.DataFrame, stations_df: Optional[pd.DataFrame], st_map: Optional[dict]) -> Tuple[List[str], List[int]]:
    """Return (problems, bad_idx) for rows with empty TestID or missing station mapping.
    Does NOT modify input DataFrame.
    """
    problems = []
    bad_idx = []
    # prepare lowercase lookup sets
    station_names_lower = set()
    station_names_norm = set()
    try:
        if stations_df is not None:
            station_names_lower = set(stations_df['Station'].astype(str).str.strip().str.lower().tolist())
            station_names_norm = set([_normalize_station_name(s) for s in station_names_lower])
    except Exception:
        station_names_lower = set()
        station_names_norm = set()

    st_map_keys_lower = set()
    st_map_keys_norm = set()
    try:
        if st_map:
            st_map_keys_lower = set([str(k).strip().lower() for k in st_map.keys()])
            st_map_keys_norm = set([_normalize_station_name(k) for k in st_map_keys_lower])
    except Exception:
        st_map_keys_lower = set()
        st_map_keys_norm = set()

    trailing_1e_re = re.compile(r'^(.*?)(?:\s+1e[0-9a-zA-Z]+)$', re.IGNORECASE)

    for idx, r in df.iterrows():
        tid = str(r.get('TestID', '')).strip()
        if not tid:
            problems.append(f"Row {idx}: empty TestID")
            bad_idx.append(idx)
        st_raw = r.get('Station', None)
        station = None if (pd.isna(st_raw) or str(st_raw).strip().lower() in ('', 'nan', 'none')) else str(st_raw).strip()

        # Skip validation for hidden stations (channel markers) - treat as if station is missing
        if station and is_hidden_station(station):
            # Don't flag as error, just treat as unmapped (will be filtered out by scheduler)
            continue

        if not station:
            problems.append(f"Row {idx} TestID {tid or '(none)'}: missing station mapping")
            bad_idx.append(idx)
            continue

        station_l = station.strip().lower()
        station_norm = _normalize_station_name(station_l)
        valid_station = False
        try:
            if station_l in station_names_lower:
                valid_station = True
        except Exception:
            pass
        try:
            if not valid_station and station_l in st_map_keys_lower:
                valid_station = True
        except Exception:
            pass
        try:
            if not valid_station and station_norm in station_names_norm:
                valid_station = True
        except Exception:
            pass
        try:
            if not valid_station and station_norm in st_map_keys_norm:
                valid_station = True
        except Exception:
            pass

        if not valid_station:
            m = trailing_1e_re.match(station)
            if m:
                base = m.group(1).strip().lower()
                base_norm = _normalize_station_name(base)
                try:
                    if base in station_names_lower or base in st_map_keys_lower or base_norm in station_names_norm or base_norm in st_map_keys_norm:
                        valid_station = True
                except Exception:
                    pass

        if not valid_station:
            problems.append(f"Row {idx} TestID {tid}: Station '{station}' not present in model Stations or station map (allowed base prefix checked, trailing '1E' ignored)")
            bad_idx.append(idx)

    return problems, bad_idx


def build_tests_info(df: pd.DataFrame, deps: Dict[str, List[str]], parse_time_to_minutes) -> Dict[str, Any]:
    """Build tests_info mapping used by scheduler. Returns dict keyed by node id 'r<index>'."""
    # Get hidden stations helper
    def _get_hidden_stations():
        """Get the set of hidden station names (case-insensitive)."""
        try:
            import Piston as main_app_mod
            hidden = getattr(main_app_mod, 'HIDDEN_STATIONS', None)
            if hidden:
                return {str(s).strip().lower() for s in hidden}
        except Exception:
            pass
        # Fallback to default list
        return {
            'racer channel',
            'vxg channel',
            'transfer ei (ys loading)',
            'transfer el (ys loading)',
            'ys loading gate',
        }

    def _is_hidden_station(station_name):
        """Check if a station should be hidden."""
        if not station_name or pd.isna(station_name):
            return False
        return str(station_name).strip().lower() in _get_hidden_stations()

    tests_info = {}
    for idx, r in df.iterrows():
        nid = f"r{idx}"
        tid_raw = str(r.get('TestID', '')).strip()
        st_raw = r.get('Station', None)
        station = None if (pd.isna(st_raw) or str(st_raw).strip().lower() in ('', 'nan', 'none')) else str(st_raw).strip()

        # Filter out hidden stations (channel markers) - treat as unmapped
        if station and _is_hidden_station(station):
            station = None

        tmin_val = r.get('TestTimeMin', 0)
        tmin = 0.0
        try:
            tmin = float(tmin_val)
        except Exception:
            try:
                tmin = float(parse_time_to_minutes(tmin_val))
            except Exception:
                tmin = 0.0
        depends = deps.get(nid, [])
        tests_info[nid] = {'testid': tid_raw, 'station': station, 'time_min': tmin, 'depends_on': depends}
    return tests_info
