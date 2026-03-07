# -*- coding: utf-8 -*-
import os
import re
import logging
from typing import Tuple
import pandas as pd

logger = logging.getLogger("piston")


def import_plan_file(plan_path: str, plan_schema_map: dict = None) -> Tuple[pd.DataFrame, str]:
    # Use same implementation as mapping.import_plan_file (kept here for IO responsibilities)
    ext = os.path.splitext(plan_path)[1].lower()
    sheet_name = None
    if ext in ('.xlsx', '.xls'):
        engine = 'openpyxl' if ext == '.xlsx' else 'xlrd'
        xl = pd.ExcelFile(plan_path, engine=engine)
        sheet_names = xl.sheet_names or []
        sheet_name = sheet_names[0] if sheet_names else None
        df = xl.parse(sheet_name)
    elif ext in ('.csv', '.tsv'):
        sep = ',' if ext == '.csv' else '\t'
        df = pd.read_csv(plan_path, sep=sep)
        sheet_name = os.path.splitext(os.path.basename(plan_path))[0]
    else:
        raise ValueError("Unsupported plan file type. Use .xlsx, .xls, .csv, or .tsv")
    df.columns = [str(c).strip() for c in df.columns]
    return df, sheet_name


def load_model(path: str):
    try:
        stations = pd.read_excel(path, sheet_name='Stations', engine='openpyxl')
        try:
            tests = pd.read_excel(path, sheet_name='Tests', engine='openpyxl')
        except Exception:
            tests = pd.DataFrame(columns=['Project', 'Scenario', 'TestID', 'TestName', 'Station', 'TestTimeMin', 'DependsOn', 'Include'])
        station_map = pd.read_excel(path, sheet_name='StationMap', engine='openpyxl')
        plan_schema = pd.read_excel(path, sheet_name='PlanSchema', engine='openpyxl')
        try:
            non_test = pd.read_excel(path, sheet_name='NonTestGroups', engine='openpyxl')
        except Exception:
            non_test = pd.DataFrame(columns=['Field','Pattern','MatchType','Notes'])
    except Exception as e:
        raise RuntimeError(f"Failed to read Excel: {e}")

    required_st_cols = {"Station", "StationCount"}
    if not required_st_cols.issubset(stations.columns):
        raise ValueError(f"Stations sheet must contain columns: {sorted(required_st_cols)}")

    stations = stations.copy()
    stations['Station'] = stations['Station'].astype(str).str.strip()
    stations['StationCount'] = stations['StationCount'].astype(float)

    # Get hidden stations list from main module
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
            return True
        return str(station_name).strip().lower() in _get_hidden_stations()

    for _, r in stations.iterrows():
        if r['StationCount'] <= 0:
            raise ValueError(f"Station '{r['Station']}' has non-positive StationCount.")

    st_map = {}
    for _, r in stations.iterrows():
        st_name = str(r['Station']).strip()
        # Skip hidden stations (channel markers) - they shouldn't affect calculations
        if _is_hidden_station(st_name):
            continue
        st_map[st_name] = {"count": int(r['StationCount']), "uptime": 1.0}

    required_test_cols = {"Project", "Scenario", "TestID", "TestName", "Station", "TestTimeMin", "DependsOn", "Include"}
    tests = tests.copy()
    if not tests.empty:
        if not required_test_cols.issubset(tests.columns):
            raise ValueError(f"Tests sheet must contain columns: {sorted(required_test_cols)}")
        for col in ['Project', 'Scenario', 'TestID', 'TestName', 'Station', 'DependsOn']:
            if col in tests.columns:
                tests[col] = tests[col].where(pd.notna(tests[col]), '').astype(str).str.strip()
        if 'TestTimeMin' in tests.columns:
            tests['TestTimeMin'] = pd.to_numeric(tests['TestTimeMin'], errors='coerce')
    else:
        tests = pd.DataFrame(columns=list(required_test_cols))

    required_sm_cols = {"Pattern", "Station", "MatchType"}
    if not required_sm_cols.issubset(station_map.columns):
        raise ValueError(f"StationMap sheet must contain columns: {sorted(required_sm_cols)}")
    station_map = station_map.copy()
    station_map['Pattern'] = station_map['Pattern'].astype(str).str.strip()
    # Normalize Station values robustly: treat missing/NaN as empty string, strip, then drop empty rows
    station_map['Station'] = station_map['Station'].where(pd.notna(station_map['Station']), '').astype(str).str.strip()
    # drop rows with empty Station (they are not meaningful)
    station_map = station_map[station_map['Station'].astype(bool)].copy()
    station_map['MatchType'] = station_map.get('MatchType', '').astype(str).str.strip().str.lower()
    if not set(station_map['Station']).issubset(set(stations['Station'])):
        unknown = set(station_map['Station']) - set(stations['Station']);
        raise ValueError(f"StationMap references unknown Stations: {sorted(list(unknown))}")

    required_ps_cols = {"Field", "ColumnName"}
    if not required_ps_cols.issubset(plan_schema.columns):
        raise ValueError(f"PlanSchema sheet must contain columns: {sorted(required_ps_cols)}")
    plan_schema = plan_schema.copy()

    non_test = non_test.copy()
    if not non_test.empty:
        non_test['Field'] = non_test['Field'].astype(str).str.strip()
        non_test['Pattern'] = non_test['Pattern'].astype(str).str.strip()
        non_test['MatchType'] = non_test.get('MatchType', 'contains').astype(str).str.strip().str.lower()

    return stations, tests, st_map, station_map, plan_schema, non_test


def _extract_k_groups_from_comments(comments: pd.Series) -> dict:
    """
    Parse a comments Series for K dependency tokens and return:
      group_map: { group_id: [ (index, role_str_or_empty) , ... ] }
    Recognizes several common styles, and extracts explicit parent/child role when present:
      - K (Dependency group <ID> parent)
      - K (Dependency group <ID> child)
      - K (Group I Parent)
      - K:ID
      - K:ID,parent or K:ID child
    Role is normalized to 'parent' or 'child' when detected, else ''.
    """
    group_map = {}
    if comments is None:
        return group_map

    # precompile regexes
    # full style: K (Dependency group <ID> [role])
    rx_full = re.compile(r'K\s*\(\s*Dependency\s+group\s+([^)]+?)\s*\)', flags=re.IGNORECASE)
    # short style: K:ID or K : ID (optionally with ,parent or ,child after)
    rx_short = re.compile(r'K\s*:\s*([A-Za-z0-9_\- ]+)(?:\s*[,;]\s*(parent|child))?', flags=re.IGNORECASE)
    # generic K (...) fallback
    rx_generic = re.compile(r'K\s*\(\s*([^)]+?)\s*\)', flags=re.IGNORECASE)

    for idx, txt in comments.items():
        if not isinstance(txt, str) or not txt.strip():
            continue
        s = txt.strip()

        found = False
        # try full style first
        for m in rx_full.finditer(s):
            raw = m.group(1).strip()
            gid, role = _parse_gid_and_role(raw)
            group_map.setdefault(gid, []).append((idx, role))
            found = True

        if not found:
            for m in rx_short.finditer(s):
                raw = m.group(1).strip()
                extra_role = (m.group(2) or '').strip().lower()
                gid, role = _parse_gid_and_role(raw)
                if not role and extra_role in ('parent', 'child'):
                    role = extra_role
                group_map.setdefault(gid, []).append((idx, role))
                found = True

        if not found:
            for m in rx_generic.finditer(s):
                raw = m.group(1).strip()
                gid, role = _parse_gid_and_role(raw)
                group_map.setdefault(gid, []).append((idx, role))
                found = True

    return group_map


def _parse_gid_and_role(raw: str) -> tuple:
    """Helper to split a raw group string into (gid, role).
    Recognizes trailing 'parent' or 'child' words and optional leading 'group' token.
    Normalizes whitespace.
    """
    if not isinstance(raw, str):
        return ('', '')
    s = raw.strip()
    role = ''
    # detect trailing parent/child
    m = re.search(r'\b(parent|child)\b\s*$', s, flags=re.IGNORECASE)
    if m:
        role = m.group(1).strip().lower()
        s = re.sub(r'\b(parent|child)\b\s*$', '', s, flags=re.IGNORECASE).strip()
    # remove leading 'group' word if present
    s = re.sub(r'^(group\s+)', '', s, flags=re.IGNORECASE).strip()
    return (s, role)


def commit_import_to_tests(workbook_path: str, import_df: pd.DataFrame, replace_project: str = None, replace_scenario = None):
    if import_df is None:
        raise ValueError("import_df is None")

    try:
        xl = pd.ExcelFile(workbook_path, engine='openpyxl')
    except Exception as ex:
        raise RuntimeError(f"Failed to open workbook '{workbook_path}': {ex}")

    sheets = {}
    for name in xl.sheet_names:
        try:
            sheets[name] = xl.parse(name)
        except Exception:
            sheets[name] = pd.DataFrame()

    tests = sheets.get('Tests', pd.DataFrame(columns=['Project', 'Scenario', 'TestID', 'TestName', 'Station', 'TestTimeMin', 'DependsOn', 'Include']))
    # include DependencyInfo so we persist a human-readable description of K-group linkage
    required_cols = ['Project', 'Scenario', 'TestID', 'TestName', 'Station', 'TestTimeMin', 'DependsOn', 'Include', 'DependencyInfo']
    for c in required_cols:
        if c not in tests.columns:
            tests[c] = ''

    if replace_project:
        if replace_scenario is None:
            tests = tests[tests['Project'] != replace_project]
        else:
            if replace_scenario == '':
                tests = tests[~((tests['Project'] == replace_project) & (tests['Scenario'].astype(str) == ''))]
            else:
                tests = tests[~((tests['Project'] == replace_project) & (tests['Scenario'].astype(str) == replace_scenario))]

    before_count = len(tests)
    import_copy = import_df.copy()

    # Ensure all required columns exist on the import copy (fill with empty strings if missing)
    for c in required_cols:
        if c not in import_copy.columns:
            import_copy[c] = ''
    # Normalize text columns that we will use
    for col in ['Project', 'Scenario', 'TestID', 'TestName', 'Station', 'DependsOn']:
        if col in import_copy.columns:
            import_copy[col] = import_copy[col].where(pd.notna(import_copy[col]), '').astype(str).str.strip()
    # initialize DependencyInfo column visible in UI
    import_copy['DependencyInfo'] = import_copy.get('DependencyInfo', '').fillna('').astype(str)

    # --- NEW: parse Comments column for 'K' dependency groups and append parent TestID to DependsOn ---
    # We support explicit parent/child markers (preferred) and several common shorthand styles.
    if 'Comments' in import_copy.columns:
        comments = import_copy['Comments'].fillna('').astype(str)
        group_map = _extract_k_groups_from_comments(comments)

        # For each group decide parent index (prefer explicit 'parent' role). Fallback: first entry that has a TestID.
        for gid, entries in group_map.items():
            if len(entries) < 2:
                continue  # a single-member group provides no parent/child relationship
            parent_idx = None
            # look for explicit parent
            for idx, role in entries:
                if role == 'parent':
                    # only accept as parent if row has non-empty TestID
                    tid = import_copy.at[idx, 'TestID'] if idx in import_copy.index else ''
                    if isinstance(tid, str) and tid.strip():
                        parent_idx = idx
                        break
            # fallback: first occurrence with a TestID
            if parent_idx is None:
                for idx, _ in entries:
                    tid = import_copy.at[idx, 'TestID'] if idx in import_copy.index else ''
                    if isinstance(tid, str) and tid.strip():
                        parent_idx = idx
                        break
            if parent_idx is None:
                # no usable parent found in the import rows; skip group
                continue
            parent_tid = str(import_copy.at[parent_idx, 'TestID']).strip()

            # set DependencyInfo for the whole group to a readable label and append parent_tid to DependsOn for children
            label = f"Parent Group {gid}"
            # set parent row label
            if parent_idx in import_copy.index:
                import_copy.at[parent_idx, 'DependencyInfo'] = label
            # append parent_tid to DependsOn for all other rows in the group (children or non-parent entries)
            for idx, role in entries:
                if idx == parent_idx:
                    continue
                # ensure row exists in import_copy
                if idx not in import_copy.index:
                    continue
                existing = str(import_copy.at[idx, 'DependsOn'] or '').strip()
                deps = [d.strip() for d in existing.split(',') if d.strip()] if existing else []
                if parent_tid not in deps:
                    deps.append(parent_tid)
                    import_copy.at[idx, 'DependsOn'] = ','.join(deps)
                # set same readable label for visibility in UI
                import_copy.at[idx, 'DependencyInfo'] = label

    # keep only required columns (this ensures Comments isn't persisted unless it's in required_cols)
    import_copy = import_copy[required_cols]

    new_tests = pd.concat([tests, import_copy], ignore_index=True, sort=False)

    # When writing back: skip obviously suspicious sheet names that look like file paths or temporary editor buffers.
    # This avoids accidentally persisting stray sheet names such as "Python piston_core\\scheduler.py".
    def suspicious_sheet_name(name: str) -> bool:
        if not isinstance(name, str):
            return True
        low = name.lower()
        if "\\" in name or "/" in name:
            return True
        if low.endswith(".py") or low.startswith("python "):
            return True
        # very long and containing spaces+slashes is suspicious
        if len(name) > 64 and (" " in name or "." in name):
            return True
        return False

    try:
        with pd.ExcelWriter(workbook_path, engine='openpyxl') as writer:
            for name, df in sheets.items():
                if name == 'Tests':
                    continue
                if suspicious_sheet_name(name):
                    logger.info("Skipping suspicious sheet when writing workbook: %r", name)
                    continue
                try:
                    df.to_excel(writer, sheet_name=name, index=False)
                except Exception:
                    pd.DataFrame().to_excel(writer, sheet_name=name, index=False)
            new_tests.to_excel(writer, sheet_name='Tests', index=False)
    except Exception as ex:
        raise RuntimeError(f"Failed to write workbook '{workbook_path}': {ex}")

    added = len(new_tests) - before_count
    total = len(new_tests)
    return int(added), int(total)