import os
import re
from typing import Dict, Tuple
import pandas as pd

# delegate to io.import_plan_file to avoid duplicate implementations
from piston_core.io import import_plan_file
from piston_core.validation import parse_duration_to_minutes
from piston_core.constants import get_hidden_stations_normalized


def read_station_map(station_map_df: pd.DataFrame):
    rules = []
    for _, r in station_map_df.iterrows():
        pattern = str(r['Pattern']).strip().lower()
        station = str(r['Station']).strip()
        mtype = str(r['MatchType']).strip().lower()
        rules.append((mtype, pattern, station))
    return rules


def map_resource_to_station(resource: str, rules, stations_set):
    if resource is None:
        return None
    res = str(resource).strip().lower()
    # exact matches first
    for mtype, pattern, station in rules:
        if mtype == 'exact' and res == pattern:
            return station
    # contains matches next
    for mtype, pattern, station in rules:
        if mtype == 'contains' and pattern in res:
            return station
    res_title = str(resource).strip()
    if res_title in stations_set:
        return res_title
    return None


def load_manual_et(manual_df, station_map_df, stations_df):
    if manual_df is None or manual_df.empty:
        return None
    if station_map_df is None or stations_df is None:
        return None

    def _is_hidden_station(station_name):
        """Check if a station should be hidden."""
        if not station_name or pd.isna(station_name):
            return True
        return str(station_name).strip().lower() in get_hidden_stations_normalized()

    rules = read_station_map(station_map_df)
    # Filter out hidden stations from the stations set
    stations_set = {s for s in stations_df['Station'].astype(str) if not _is_hidden_station(s)}
    st_counts = {r['Station']: int(r['StationCount']) for _, r in stations_df.iterrows() if not _is_hidden_station(r['Station'])}

    for _, r in manual_df.iterrows():
        pat = str(r.get('Pattern', '')).strip().lower()
        try:
            cnt = int(float(r.get('Count', 0) or 0))
        except Exception:
            cnt = 0
        cnt = max(0, cnt)
        if not pat:
            continue

        mapped_station = None
        for mtype, pattern, station in rules:
            if mtype == 'exact' and pattern == pat:
                mapped_station = station
                break
        if mapped_station is None:
            for mtype, pattern, station in rules:
                if mtype == 'contains' and pattern in pat:
                    mapped_station = station
                    break
        if mapped_station is None and pat in (s.lower() for s in stations_set):
            for s in stations_set:
                if s.lower() == pat:
                    mapped_station = s
                    break

        if mapped_station and not _is_hidden_station(mapped_station):
            st_counts[mapped_station] = cnt

    st_map = {s: {'count': int(st_counts.get(s, 0)), 'uptime': 1.0} for s in stations_set if not _is_hidden_station(s)}
    return st_map


def read_plan_schema(plan_schema_df: pd.DataFrame):
    m = {}
    for _, r in plan_schema_df.iterrows():
        field = str(r['Field']).strip()
        col = str(r['ColumnName']).strip()
        if field:
            m[field] = col
    required_fields = ["Project", "StepID", "StepName", "DurationMin", "StationResource"]
    for f in required_fields:
        if f not in m:
            raise ValueError(f"PlanSchema missing required Field '{f}'.")
    return m


def import_plan_file(plan_path: str, plan_schema_map: dict):
    """
    Delegate plan file reading to piston_core.io.import_plan_file (keeps a single IO implementation).
    Returns (df, sheet_name).
    """
    return import_plan_file(plan_path, plan_schema_map)


def plan_to_tests_rows(plan_df: pd.DataFrame, plan_schema_map: dict, station_rules, stations_df: pd.DataFrame, project_override: str = None, scenario_override: str = None, sheet_name: str = None):
    def _is_hidden_station(station_name):
        """Check if a station should be hidden."""
        if not station_name or pd.isna(station_name):
            return True
        return str(station_name).strip().lower() in get_hidden_stations_normalized()

    fld = plan_schema_map
    predecessors_col = fld.get('Predecessors')
    scenario_col = fld.get('Scenario')
    project_col = fld.get('Project')
    # Filter out hidden stations (channel markers) from stations_set
    stations_set = {s for s in stations_df['Station'].astype(str) if not _is_hidden_station(s)}

    rows = []
    unknown_resources = set()
    missing_durations = []
    for _, r in plan_df.iterrows():
        proc_col_val = None
        try:
            if 'Proc #' in plan_df.columns and pd.notna(r.get('Proc #', None)) and str(r.get('Proc #', '')).strip() != '':
                proc_col_val = str(r.get('Proc #')).strip()
        except Exception:
            proc_col_val = None

        if proc_col_val:
            step_id = proc_col_val
        else:
            try:
                mapped_col = fld.get('StepID', '')
                step_id = str(r.get(mapped_col, '')).strip() if mapped_col and mapped_col in plan_df.columns else str(r.get(mapped_col, '')).strip()
            except Exception:
                step_id = str(r.get(fld.get('StepID', ''), '')).strip()
            step_id = step_id or None

        step_name = str(r.get(fld['StepName'], '')).strip()
        dur_raw = r.get(fld['DurationMin'], None)
        dur = parse_duration_to_minutes(dur_raw)
        if dur is None:
            missing_durations.append(step_id or step_name)
        resource_val = r.get(fld['StationResource'], None)
        station = map_resource_to_station(resource_val, station_rules, stations_set)
        if station is None:
            unknown_resources.add(str(resource_val))
        depends_on = ''
        if predecessors_col and predecessors_col in plan_df.columns:
            dep_str = r.get(predecessors_col, '')
            if pd.notna(dep_str):
                depends_on = ','.join([d.strip() for d in str(dep_str).split(',') if d and d.strip()])
        if project_override:
            project = project_override
        else:
            if project_col == '<SHEET_NAME>':
                project = sheet_name if sheet_name is not None else ''
            elif project_col in plan_df.columns:
                project = str(r.get(project_col, '')).strip()
            else:
                project = ''
        if scenario_override is not None:
            scenario = scenario_override
        else:
            if scenario_col == '<SHEET_NAME>':
                scenario = sheet_name if sheet_name is not None else ''
            elif scenario_col in plan_df.columns:
                scenario = str(r.get(scenario_col, '')).strip()
            else:
                scenario = ''
        test_id = step_id or f"AUTO_{len(rows)+1}"
        rows.append({
            'Project': project,
            'Scenario': scenario,
            'TestID': test_id,
            'TestName': step_name,
            'Station': station,
            'TestTimeMin': dur,
            'DependsOn': depends_on,
            'Comments': str(r.get('Comments', '') if 'Comments' in plan_df.columns else '').strip(),
            'Include': True
        })
    out_df = pd.DataFrame(rows)
    issues = {
        'unknown_resources': sorted(list(unknown_resources)),
        'missing_durations': missing_durations,
    }
    return out_df, issues


def auto_map_plan_schema(plan_df: pd.DataFrame, plan_schema_map: dict):
    import difflib

    def norm(s):
        if s is None:
            return ""
        return re.sub(r'[^a-z0-9]', '', str(s).strip().lower())

    headers = list(plan_df.columns)
    nheaders = {norm(h): h for h in headers}

    synonyms = {
        'StepID': ['testid', 'stepid', 'id', 'seq', 'sequence', 'taskid', 'step'],
        'StepName': ['testname', 'stepname', 'name', 'description', 'summary'],
        'DurationMin': ['testtime', 'test_time', 'duration', 'durationmin', 'time', 'runtime', 'test time', 'duration(min)'],
        'StationResource': ['station', 'resource', 'stationresource', 'stationname', 'station_name', 'station_type', 'resourcename'],
        'Predecessors': ['predecessors', 'depends', 'depends_on', 'dependency', 'prev', 'predecessor'],
        'Project': ['project', 'proj'],
        'Scenario': ['scenario', 'scen']
    }

    mapped = {}
    warnings = []

    for field, requested_col in plan_schema_map.items():
        chosen = None
        if requested_col and requested_col in headers:
            chosen = requested_col
        else:
            req_norm = norm(requested_col) if requested_col else ''
            if req_norm and req_norm in nheaders:
                chosen = nheaders[req_norm]
            else:
                cand_names = synonyms.get(field, [])
                for syn in cand_names:
                    if syn in nheaders:
                        chosen = nheaders[syn]
                        break
                if not chosen:
                    norm_header_list = list(nheaders.keys())
                    query = req_norm if req_norm else norm(field)
                    matches = difflib.get_close_matches(query, norm_header_list, n=2, cutoff=0.75)
                    if matches:
                        chosen = nheaders[matches[0]]
                if not chosen:
                    for h in headers:
                        hl = h.lower()
                        for token in cand_names:
                            if token in hl:
                                chosen = h
                                break
                        if chosen:
                            break
        if chosen:
            mapped[field] = chosen
        else:
            mapped[field] = ''
            warnings.append(f"No column mapped for Field '{field}' (PlanSchema requested: '{requested_col}')")

    core_missing = [f for f in ('StepID', 'DurationMin', 'StationResource') if not mapped.get(f)]
    if core_missing:
        warnings.insert(0, f"Core mapping missing: {core_missing}")

    return mapped, warnings