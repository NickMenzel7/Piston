from collections import deque
from typing import Dict, List, Tuple, Union
import heapq
import pandas as pd
import logging

# use the same named logger as the UI so logs go to the same file/handler
logger = logging.getLogger("piston")


def build_dag(tests_df: pd.DataFrame) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], List[str]]:
    """
    Build dependency graph for tests DataFrame where each DataFrame row is a distinct node.
    Node ids are 'r<index>' (DataFrame index). DependsOn tokens (TestID values) map to
    the most recent provider row that appears before the dependent row (preserves import order,
    avoids grouping duplicates). Topological sort is stable: when multiple nodes are ready
    (indegree 0) we choose the node that appears earlier in the provided DataFrame.
    Returns (deps, succs, topo) where keys are node ids.
    """
    # Use DataFrame index to create stable per-row node ids and preserve row order
    rows = list(tests_df.index)
    nodes = [f"r{r}" for r in rows]
    node_for_index = {r: f"r{r}" for r in rows}
    # position map used as deterministic tie-breaker (lower == earlier in DataFrame)
    pos_map = {node_for_index[r]: i for i, r in enumerate(rows)}

    # map TestID value -> list of row indices (preserve order of rows)
    tid_to_row_indices: Dict[str, List[int]] = {}
    for r in rows:
        tid = str(tests_df.at[r, 'TestID']).strip() if 'TestID' in tests_df.columns else ''
        tid_to_row_indices.setdefault(tid, []).append(r)

    deps: Dict[str, List[str]] = {n: [] for n in nodes}
    succs: Dict[str, List[str]] = {n: [] for n in nodes}

    # Build dependencies: for each row, for each DependsOn token,
    # link the dependent row to the most recent provider row that comes earlier.
    for r in rows:
        nid = node_for_index[r]
        dep_val = tests_df.at[r, 'DependsOn'] if 'DependsOn' in tests_df.columns else ''
        if pd.isna(dep_val):
            continue
        dep_str = str(dep_val).strip()
        if not dep_str:
            continue
        for dep in [d.strip() for d in dep_str.split(',') if d and d.strip() and d.strip().lower() not in ('nan', 'none')]:
            provider_rows = tid_to_row_indices.get(dep)
            if not provider_rows:
                raise ValueError(f"Test row {r} (TestID='{tests_df.at[r, 'TestID']}') depends on unknown TestID '{dep}' in selected filters.")
            # choose the provider row with highest index < current row index
            prior_providers = [pr for pr in provider_rows if pr < r]
            if not prior_providers:
                # No prior provider exists; this dependency cannot be satisfied from earlier rows
                raise ValueError(f"Test row {r} (TestID='{tests_df.at[r, 'TestID']}') depends on TestID '{dep}' but no earlier occurrence of '{dep}' exists in the selected plan.")
            chosen_row = max(prior_providers)
            prov_node = node_for_index[chosen_row]
            deps[nid].append(prov_node)
            succs[prov_node].append(nid)

    # topological sort on per-row nodes using a heap keyed by original position to preserve order
    indeg = {n: len(deps[n]) for n in nodes}
    heap: List[Tuple[int, str]] = []
    for n in nodes:
        if indeg[n] == 0:
            heapq.heappush(heap, (pos_map[n], n))

    topo: List[str] = []
    while heap:
        _, t = heapq.heappop(heap)
        topo.append(t)
        for s in succs[t]:
            indeg[s] -= 1
            if indeg[s] == 0:
                heapq.heappush(heap, (pos_map[s], s))

    if len(topo) != len(nodes):
        raise ValueError("Dependency cycle detected among Tests for selected filters.")
    return deps, succs, topo


def critical_path_hours(tests_info: Dict[str, dict], topo: List[str], st_map: Dict[str, dict]) -> float:
    eff_time_h = {}
    for tid, info in tests_info.items():
        up = st_map.get(info['station'], {}).get('uptime', 1.0)
        eff_time_h[tid] = (info['time_min'] / 60.0) / up
    dist = {tid: 0.0 for tid in tests_info}
    # helper: resolve dependency token robustly (accept numeric tokens like '112.0')
    def _resolve_pred_token(tok: object) -> str:
        d_key = str(tok).strip()
        if d_key in tests_info:
            return d_key
        try:
            f = float(d_key)
            if f.is_integer():
                alt = str(int(f))
                if alt in tests_info:
                    return alt
        except Exception:
            pass
        # not resolvable
        raise KeyError(f"Dependency token '{tok}' (normalized '{d_key}') does not match any TestID keys")

    for tid in topo:
        preds_raw = tests_info[tid]['depends_on']
        if not preds_raw:
            dist[tid] = max(dist[tid], eff_time_h[tid])
        else:
            resolved = [_resolve_pred_token(d) for d in preds_raw]
            dist[tid] = max(dist[d] for d in resolved) + eff_time_h[tid]
    return max(dist.values()) if dist else 0.0


def schedule_n_units(
    tests_info: Dict[str, dict],
    topo: List[str],
    st_map: Dict[str, dict],
    n_units: int,
    channels_per_unit: Union[int, List[int]] = 1,
    channel_marker: Union[str, List[str]] = None,
    unit_bias: Union[float, None] = None,
    trace: bool = False,
    bias_max_frac: float = 0.05,
    bias_window_frac: float = 1.0,
    serialization_mode: str = 'Auto',
) -> Union[Tuple[float, List[float], Dict[str, float]], Tuple[float, List[float], Dict[str, float], List[dict]]]:
    """
    Schedule n_units where channels_per_unit may be:
     - single int (uniform channels per unit)
     - list[int] of length n_units specifying channels for each unit

    Supports multi-channel units where tests up to a 'channel marker' run once per unit
    (shared), and tests below the marker repeat per channel. Marker detected by station
    name equal to any of values in `channel_marker` (case-insensitive) by default.

    Returns makespan (hours), per-unit finish times list, station utilization dict.
    """
    # default markers: include VXG and Racer channel names
    if channel_marker is None:
        channel_marker = ["VXG Channel", "Racer Channel"]

    # Normalize channels_per_unit to per-unit list
    if isinstance(channels_per_unit, int):
        channels_list = [max(1, min(int(channels_per_unit), 4)) for _ in range(n_units)]
    else:
        # list-like: ensure integer and clamp 1..4, pad/truncate to n_units
        channels_list = [max(1, min(int(c), 4)) for c in list(channels_per_unit or [])]
        if len(channels_list) < n_units:
            pad_val = channels_list[-1] if channels_list else 1
            channels_list.extend([pad_val] * (n_units - len(channels_list)))
        elif len(channels_list) > n_units:
            channels_list = channels_list[:n_units]

    # Validate station references
    missing = []
    # Build a robust normalization removing non-alphanumeric characters so
    # station labels like "Transfer EI (YS loading)" and "Transfer EI YS loading"
    # match reliably.
    import re as _re
    def _norm(s):
        try:
            return _re.sub(r'[^0-9a-z]', '', str(s).strip().casefold())
        except Exception:
            try:
                return _re.sub(r'[^0-9a-z]', '', str(s).strip().lower())
            except Exception:
                return ''

    # Fallback normalization: try stripping common machine-instance suffixes such as
    # trailing "1E", " 1E", " 1e", or numeric instance identifiers that some plans
    # append to station names. This mirrors validation_helper's tolerant checks.
    _trailing_instance_re = _re.compile(r"^(.*?)(?:\s+1e[0-9a-zA-Z]+)$", _re.IGNORECASE)
    def _norm_flexible(s):
        n = _norm(s)
        if n in st_map_norm:
            return n
        # try removing trailing instance marker like ' 1E'
        try:
            m = _trailing_instance_re.match(str(s).strip())
            if m:
                base = m.group(1)
                nb = _norm(base)
                if nb in st_map_norm:
                    try:
                        logger.debug("_norm_flexible: stripped trailing instance from %r -> %r", s, base)
                    except Exception:
                        pass
                    return nb
        except Exception:
            pass
        return n

    # Map st_map normalized keys to original keys for fast lookup
    st_map_norm = { _norm(k): k for k in st_map.keys() }

    # Validate station references and collect stations used in tests
    missing = []
    stations_in_tests = set()
    for tid, info in tests_info.items():
        st = info.get('station')
        if st and str(st).strip():
            stations_in_tests.add(st)
            # use flexible normalization to tolerate trailing instance suffixes
            if _norm_flexible(st) not in st_map_norm:
                missing.append((tid, st))
    if missing:
        unknown_vals = sorted(set(s for _, s in missing))
        example_tids = ', '.join(t for t, _ in missing[:10])
        raise ValueError(f"Tests reference unknown Stations: {unknown_vals}. Example TestIDs: {example_tids}")

    # Check for zero-count stations among those referenced by tests (use mapped keys)
    zero_count = []
    for s in stations_in_tests:
        mk = st_map_norm.get(_norm_flexible(s))
        if mk is None:
            continue
        try:
            if int(st_map.get(mk, {}).get('count', 0)) <= 0:
                zero_count.append(mk)
        except Exception:
            zero_count.append(mk)
    zero_count = sorted(zero_count)
    if zero_count:
        raise ValueError(f"The following Stations have zero count in station map: {zero_count}")

    if n_units <= 0:
        if trace:
            return 0.0, [], {s: 0.0 for s in st_map}, []
        return 0.0, [], {s: 0.0 for s in st_map}

    # effective durations (hours)
    eff_time_h = {}
    for tid, info in tests_info.items():
        # Resolve station using normalized mapping to handle differences in casing/whitespace
        st_name = info.get('station')
        if st_name and str(st_name).strip():
            mk = st_map_norm.get(_norm(st_name))
            if mk and mk in st_map:
                try:
                    up = float(st_map[mk].get('uptime', 1.0) or 1.0)
                except Exception:
                    up = 1.0
                eff_time_h[tid] = (info['time_min'] / 60.0) / up
            else:
                # Station not found in station map -> treat duration as 0 and rely on earlier validation
                eff_time_h[tid] = 0.0
        else:
            eff_time_h[tid] = 0.0

    # Heuristic unit bias: prefer earlier units by adding a small time delta per unit index
    try:
        mean_dur = sum(eff_time_h.values()) / len(eff_time_h) if eff_time_h else 0.0
    except Exception:
        mean_dur = 0.0

    # Defer fully-dedicated decision until station_avail is constructed so we use
    # the same parsed machine counts that scheduling uses. We'll compute
    # `enforce_unit_serialization` after station_avail is built.
    # For now, compute a provisional unit_bias_val that will be adjusted below.
    provisional_unit_bias = None
    if unit_bias is None:
        provisional_unit_bias = mean_dur * 0.01 if mean_dur else 0.0
    else:
        try:
            ub = float(unit_bias)
            # Backwards-compatible convenience: if user provides a small fractional
            # value between 0 and 1 treat it as a fraction of the mean task duration
            # (matching the default behaviour which uses mean_dur * 0.01). This makes
            # entering `0.01` mean "1% of mean duration" rather than an absolute 0.01h.
            if 0.0 < ub < 1.0:
                provisional_unit_bias = mean_dur * ub if mean_dur else 0.0
            else:
                provisional_unit_bias = ub
        except Exception:
            provisional_unit_bias = mean_dur * 0.01 if mean_dur else 0.0

    # Helper: compute effective priority for a push, applying cap and attenuation
    # (defined here so it can reference mean_dur and unit_bias_val after finalization)
    def _effective_priority(ready_time: float, unit_idx: int, current_queue_ready_times: List[float]) -> float:
        # absolute bias in hours
        try:
            abs_bias = float(unit_bias_val or 0.0)
        except Exception:
            abs_bias = 0.0
        if abs_bias <= 0.0:
            return ready_time
        # cap bias to bias_max_frac * mean_dur
        try:
            cap = max(0.0, float(bias_max_frac or 0.0)) * (mean_dur if mean_dur else 0.0)
        except Exception:
            cap = 0.0
        if cap <= 0.0:
            eff_unit_bias = abs_bias
        else:
            eff_unit_bias = min(abs_bias, cap)
        # find min ready among current queue and this ready_time
        try:
            min_ready = ready_time
            if current_queue_ready_times:
                mr = min(current_queue_ready_times)
                if mr < min_ready:
                    min_ready = mr
            # attenuation based on distance from min_ready; scaled by mean_dur * bias_window_frac
            window = (mean_dur if mean_dur else 0.0) * (float(bias_window_frac) if bias_window_frac else 1.0)
            if window <= 0.0:
                att = 1.0
            else:
                delta = max(0.0, ready_time - min_ready)
                att = max(0.0, 1.0 - (delta / window))
        except Exception:
            att = 1.0
        offset = unit_idx * eff_unit_bias * att
        return ready_time + offset

    # build machine availability per station (single canonical construction)
    station_avail = {}
    for s, v in st_map.items():
        # robustly parse counts (accept int, float, or numeric strings like '10.0')
        raw_cnt = v.get('count', 0)
        try:
            cnt = int(raw_cnt)
        except Exception:
            try:
                cnt = int(float(raw_cnt))
            except Exception:
                cnt = 0
        cnt = max(0, cnt)
        station_avail[s] = [0.0 for _ in range(cnt)]
    station_busy = {s: 0.0 for s in st_map}

    # Now determine if stations are fully dedicated (enough machines for each unit to run independently)
    # and adjust unit_bias_val accordingly. When fully dedicated, set bias to 0 so units don't serialize.
    fully_dedicated = False
    try:
        if stations_in_tests and n_units > 1:
            # Consider machines fully dedicated when station count is at least n_units.
            # This allows different units to run concurrently on separate machines when
            # there are enough machines to assign one machine per unit.
            fully_dedicated = True
            for s in stations_in_tests:
                mk_key = st_map_norm.get(_norm_flexible(s))
                cnt_parsed = len(station_avail.get(mk_key, [])) if mk_key is not None else 0
                if cnt_parsed < n_units:
                    fully_dedicated = False
                    try:
                        logger.debug("schedule_n_units: station %r parsed_count=%r < n_units=%r (resolved key=%r)", s, cnt_parsed, n_units, mk_key)
                    except Exception:
                        pass
                    break
        else:
            fully_dedicated = False
    except Exception:
        fully_dedicated = False

    # Finalize unit_bias_val based on fully_dedicated status:
    # When fully dedicated, ALWAYS disable bias so units run in parallel without artificial ordering,
    # even if user explicitly requested bias (bias is only useful for contended resources).
    # When contended (not fully dedicated), apply bias to reduce thrashing.
    if fully_dedicated:
        # Fully dedicated: no bias needed, units have dedicated machines
        unit_bias_val = 0.0
    else:
        # Use provisional bias computed earlier (respects user override or default)
        unit_bias_val = provisional_unit_bias

    # Log parsed station counts, channels_list and final unit bias to aid debugging
    try:
        parsed_counts = {s: len(station_avail.get(s, [])) for s in station_avail}
        try:
            logger.debug("schedule_n_units debug: n_units=%r, channels_list=%r, fully_dedicated=%s, unit_bias_val=%.6f", n_units, channels_list, fully_dedicated, unit_bias_val)
        except Exception:
            logger.debug("schedule_n_units debug: n_units=%r, channels_list=%r, fully_dedicated=%s, unit_bias_val=%r", n_units, channels_list, fully_dedicated, unit_bias_val)
        try:
            logger.debug("schedule_n_units debug: st_map_keys=%r, st_map_norm_keys=%r, stations_in_tests=%r, parsed_counts=%r",
                         list(st_map.keys()), list(st_map_norm.keys()), list(stations_in_tests), parsed_counts)
        except Exception:
            logger.debug("schedule_n_units debug: parsed_counts=%r stations_in_tests=%r", parsed_counts, list(stations_in_tests))
    except Exception:
        pass

    # log stations whose parsed count is less than requested n_units when referenced by tests
    try:
        low_counts = []
        for s in stations_in_tests:
            mk = st_map_norm.get(_norm(s))
            if mk is None:
                continue
            parsed = len(station_avail.get(mk, []))
            if parsed < n_units:
                low_counts.append((mk, parsed))
        if low_counts:
            try:
                logger.warning("schedule_n_units: some referenced stations have parsed counts < n_units: %r", low_counts)
            except Exception:
                pass
    except Exception:
        pass

    # Determine enforcement based on serialization_mode and fully_dedicated status.
    # fully_dedicated was already computed above when finalizing unit_bias_val.
    try:
        # When stations are fully dedicated (enough machines for each unit to have its own),
        # units can run in parallel. Within-unit serialization is still needed to prevent
        # channel flows from overlapping, but CROSS-UNIT serialization should be disabled.
        # The serialization_mode allows explicit override:
        #   'Auto' (default): disable serialization when fully_dedicated
        #   'Strict': always serialize units (legacy behavior)
        #   'Relaxed': never serialize (experimental)
        if serialization_mode == 'Strict':
            enforce_unit_serialization = True
        elif serialization_mode == 'Relaxed':
            enforce_unit_serialization = False
        else:  # 'Auto'
            # When fully dedicated, different units don't share machines -> no serialization needed
            enforce_unit_serialization = not fully_dedicated
        try:
            logger.debug("schedule_n_units: fully_dedicated=%s unit_bias_val=%.6f n_units=%r enforce_unit_serialization=%s serialization_mode=%s",
                         fully_dedicated, unit_bias_val, n_units, enforce_unit_serialization, serialization_mode)
        except Exception:
            pass
    except Exception:
        enforce_unit_serialization = True

    # optional trace of scheduling events for debugging
    events: List[dict] = []

    # succs map: normalize dependency tokens robustly (handle numeric tokens like '112.0')
    succs = {tid: [] for tid in tests_info}
    for tid, info in tests_info.items():
        for d in info['depends_on']:
            d_key = str(d).strip()
            if d_key in succs:
                succs[d_key].append(tid)
                continue
            # try numeric normalization: e.g. '112.0' -> '112'
            try:
                f = float(d_key)
                if f.is_integer():
                    alt = str(int(f))
                    if alt in succs:
                        succs[alt].append(tid)
                        continue
            except Exception:
                pass
            # dependency not found; raise helpful error
            raise ValueError(f"Test '{tid}' depends on unknown TestID '{d}' (normalized '{d_key}'). Available TestIDs: {sorted(succs.keys())}")

    # Detect channel marker test id(s). Accept a single name or list of names.
    if isinstance(channel_marker, str):
        markers = [channel_marker]
    else:
        markers = list(channel_marker or [])
    # Normalize marker names the same way station names are normalized so comparisons match
    markers_norm = set(_norm(m) for m in markers if m and str(m).strip())
    # also accept a common alternative marker for YS Loading Gate to support existing plans
    markers_norm.add(_norm('ys loading gate'))
    # use flexible normalization for station matching when detecting marker tids
    marker_tids = [tid for tid, info in tests_info.items() if _norm_flexible(info.get('station', '')) in markers_norm]

    # If multiple marker candidates exist, prefer the one that partitions the
    # DAG meaningfully: choose the marker with the largest reachable successor
    # closure (including itself). This avoids selecting an early/no-deps marker
    # that would cause the channel block to include the entire plan.
    marker_tid = None
    if marker_tids:
        # succs map already computed below; build a temporary successors map here
        _succs_tmp = {tid: [] for tid in tests_info}
        for tid, info in tests_info.items():
            for d in info['depends_on']:
                d_key = str(d).strip()
                if d_key in _succs_tmp:
                    _succs_tmp[d_key].append(tid)
                    continue
                try:
                    f = float(d_key)
                    if f.is_integer():
                        alt = str(int(f))
                        if alt in _succs_tmp:
                            _succs_tmp[alt].append(tid)
                            continue
                except Exception:
                    pass

        def _closure_size(start):
            seen = set()
            stack = [start]
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                for s in _succs_tmp.get(cur, []):
                    if s not in seen:
                        stack.append(s)
            return len(seen)

        # pick marker with maximum closure size; tie-breaker: prefer marker with non-empty depends_on
        best = None
        best_size = -1
        for m in marker_tids:
            try:
                sz = _closure_size(m)
            except Exception:
                sz = 0
            try:
                has_preds = bool(tests_info.get(m, {}).get('depends_on'))
            except Exception:
                has_preds = False
            score = (sz, 1 if has_preds else 0)
            if score > (best_size, 0):
                best = m
                best_size = sz
        marker_tid = best

    if not marker_tid:
        # no marker found: fall back to original behavior (duplicate whole plan per flow)
        # create flow-per-unit mapping: contiguous flow indices per unit
        starts = []
        total_flows = 0
        for ch in channels_list:
            starts.append(total_flows)
            total_flows += ch

        # map each flow index to its originating unit index so we can bias the ready-queue
        flow_unit = [0] * total_flows
        for u, ch in enumerate(channels_list):
            start = starts[u]
            for f in range(start, start + ch):
                if 0 <= f < total_flows:
                    flow_unit[f] = u

        # initial indegrees / ready times / per-flow trackers for duplicate-plan (no marker) case
        # In this mode each duplicated flow contains all tests (no per-flow partitioning),
        # so define flow_tasks accordingly to avoid referencing an undefined variable.
        flow_tasks = [set(tests_info.keys()) for _ in range(total_flows)]

        flow_indeg = [{tid: len(tests_info[tid]['depends_on']) for tid in tests_info} for _ in range(total_flows)]
        flow_ready_time = [{tid: 0.0 for tid in tests_info} for _ in range(total_flows)]
        flow_last_finish = [0.0] * total_flows

        # per-unit next-available time to enforce serial execution across flows belonging to same unit
        unit_next_available = [0.0] * n_units

        # CRITICAL: Track when each unit is busy with ANY test (intra-unit serialization).
        # A physical unit can only execute one test at a time, even if it has multiple channels
        # and even if there are multiple stations available. This prevents the scheduler from
        # assigning a unit to multiple stations simultaneously (e.g., running Test A on Station X
        # while also running Test B on Station Y for the same unit).
        unit_busy_until = [0.0] * n_units

        # If every station has at least `n_units` machines then units are fully dedicated
        # and different flows belonging to the same unit should be allowed to run
        # concurrently on their dedicated machines. In that case we should not
        # enforce serialization across flows of the same unit.
        # enforce_unit_serialization is already computed above; don't overwrite it here.

        # initialize ready queue only for tasks that belong to the flow and have indeg 0
        ready_q = []
        for f in range(total_flows):
            for tid in tests_info:
                if flow_indeg[f][tid] == 0:
                    # compute current queue ready times for attenuation
                    current_ready_times = [t[0] for t in ready_q] if ready_q else []
                    pri = _effective_priority(0.0, flow_unit[f], current_ready_times)
                    sec = flow_unit[f] if unit_bias_val != 0.0 else 0
                    # push tuple where unit index is last element so it doesn't affect ordering when bias==0
                    tup = (pri, sec if unit_bias_val != 0.0 else 0, f, tid, flow_unit[f])
                    try:
                        logger.debug("PUSH ready_q: %r (raw_ready=0.0)", tup)
                    except Exception:
                        pass
                    events.append({'event': 'push', 'pri': pri, 'flow': f, 'tid': tid, 'unit': flow_unit[f]})
                    heapq.heappush(ready_q, tup)

        while ready_q:
            # unpack: second element is only used for ordering when unit_bias_val != 0.0
            tup = heapq.heappop(ready_q)
            try:
                logger.debug("POP ready_q: %r", tup)
            except Exception:
                pass
            # record pop
            try:
                events.append({'event': 'pop', 'tup': tup})
            except Exception:
                pass
            ready_time, _, f, tid, unit_idx = tup
            # skip tasks that don't belong to this flow (guard - should not happen)
            if tid not in flow_tasks[f]:
                continue

            station = tests_info[tid]['station']
            dur = eff_time_h[tid]
            mapped_station = st_map_norm.get(_norm(station)) if station else None
            machines = station_avail.get(mapped_station) if mapped_station is not None else None
            if machines:
                # OPTION A (DEDICATED LINES): When fully_dedicated=True, each unit gets assigned
                # to specific machines that only it uses. Unit i uses machine indices that equal
                # i modulo the station count. This creates N independent parallel test lines.
                if fully_dedicated and len(machines) >= n_units:
                    # Dedicated mode: unit i always uses machine i (or i % machine_count)
                    m_idx = unit_idx % len(machines)
                else:
                    # Shared pool mode: pick the earliest available machine
                    m_idx = min(range(len(machines)), key=lambda i: machines[i])

                # ALWAYS enforce that a single unit can only run one test at a time (intra-unit serialization).
                # This is the physical constraint that a unit must move from station to station.
                # Additional constraint: enforce_unit_serialization controls whether different channels/flows
                # of the same unit must also wait for each other (channel serialization).
                base_ready = max(ready_time, machines[m_idx], unit_busy_until[unit_idx])
                if enforce_unit_serialization:
                    # Also enforce serial execution across flows/channels of the same unit
                    start_time = max(base_ready, unit_next_available[unit_idx])
                else:
                    start_time = base_ready
                finish_time = start_time + dur
                machines[m_idx] = finish_time
                # charge busy time using canonical key
                station_busy[mapped_station] += dur
                # Update per-unit busy tracker so this unit cannot start another test until this one finishes
                unit_busy_until[unit_idx] = finish_time
                unit_next_available[unit_idx] = finish_time

                # DEBUG trace: show exact assignment
                try:
                    testid = tests_info.get(tid, {}).get('testid', None)
                except Exception:
                    testid = None
                try:
                    logger.debug("SCHEDULE_ASSIGN: node=%r testid=%r station=%r machine=%r start=%.6f finish=%.6f flow=%r dur=%.6f",
                                 tid, testid, station, m_idx, start_time, finish_time, f, dur)
                except Exception:
                    pass
                # record assignment
                try:
                    events.append({'event': 'assign', 'tid': tid, 'flow': f, 'unit': unit_idx, 'station': station, 'machine': m_idx, 'start': start_time, 'finish': finish_time, 'dur': dur})
                except Exception:
                    pass
            else:
                start_time = ready_time
                finish_time = start_time + dur

                # DEBUG trace for tasks without machines (station missing or not in station_avail)
                try:
                    testid = tests_info.get(tid, {}).get('testid', None)
                except Exception:
                    testid = None
                try:
                    logger.debug("SCHEDULE_ASSIGN: node=%r testid=%r station=%r machine=%r start=%.6f finish=%.6f flow=%r dur=%.6f",
                                 tid, testid, station, None, start_time, finish_time, f, dur)
                except Exception:
                    pass
                try:
                    events.append({'event': 'assign', 'tid': tid, 'flow': f, 'unit': unit_idx, 'station': mapped_station or station, 'machine': None, 'start': start_time, 'finish': finish_time, 'dur': dur})
                except Exception:
                    pass

            for s in succs[tid]:
                flow_ready_time[f][s] = max(flow_ready_time[f][s], finish_time)
                flow_indeg[f][s] -= 1
                if flow_indeg[f][s] == 0:
                    current_ready_times = [t[0] for t in ready_q] if ready_q else []
                    pri = _effective_priority(flow_ready_time[f][s], flow_unit[f], current_ready_times)
                    sec = flow_unit[f] if unit_bias_val != 0.0 else 0
                    tup = (pri, sec if unit_bias_val != 0.0 else 0, f, s, flow_unit[f])
                    try:
                        logger.debug("PUSH ready_q: %r (raw_ready=%.6f)", tup, flow_ready_time[f][s])
                    except Exception:
                        pass
                    events.append({'event': 'push', 'pri': pri, 'flow': f, 'tid': s, 'unit': flow_unit[f]})
                    heapq.heappush(ready_q, tup)
            flow_last_finish[f] = max(flow_last_finish[f], finish_time)

        unit_last_finish = []
        for u in range(n_units):
            start = starts[u]
            end = start + channels_list[u]
            unit_last_finish.append(max(flow_last_finish[start:end]) if end > start else 0.0)
        makespan = max(unit_last_finish) if unit_last_finish else 0.0

        station_util = {}
        for s in st_map:
            try:
                cnt = int(st_map[s].get('count', 0))
            except Exception:
                cnt = 0
            if makespan > 0 and cnt > 0:
                station_util[s] = station_busy.get(s, 0.0) / (makespan * cnt)
            else:
                station_util[s] = 0.0

        if trace:
            return makespan, unit_last_finish, station_util, events
        return makespan, unit_last_finish, station_util

    # If we have a marker: partition tests into pre_channel (ancestors of marker, NOT including marker)
    # and channel_block (marker and its descendants). Reflects the behaviours where the
    # tests above the marker are executed once per unit, and tests at/after the marker are
    # repeated per channel.
    pre_channel = set()
    if marker_tid:
        # start from marker's predecessors so marker itself is part of channel_block (repeated)
        stack = list(tests_info[marker_tid]['depends_on']) if tests_info.get(marker_tid) else []
        while stack:
            cur = stack.pop()
            if cur in pre_channel:
                continue
            pre_channel.add(cur)
            for p in tests_info[cur]['depends_on']:
                if p not in pre_channel:
                    stack.append(p)
    channel_block = set(tests_info.keys()) - pre_channel

    # build per-flow task membership. For each unit: first flow is shared (pre_channel), then channel flows
    starts = []
    total_flows = 0
    for ch in channels_list:
        starts.append(total_flows)
        total_flows += 1 + ch  # 1 shared + ch channel flows

    # map each flow index to its originating unit so ready-queue can bias by unit
    flow_unit = [0] * total_flows
    for u, ch in enumerate(channels_list):
        start = starts[u]
        for f in range(start, start + 1 + ch):
            if 0 <= f < total_flows:
                flow_unit[f] = u

    flow_tasks: List[set] = []
    for u in range(n_units):
        # shared flow tasks
        flow_tasks.append(set(pre_channel))
        # channel flows
        for _ in range(channels_list[u]):
            flow_tasks.append(set(channel_block))

    # initial indegrees count only dependencies that exist for that task (global deps)
    flow_indeg = []
    flow_ready_time = []
    for f in range(total_flows):
        indeg_map = {}
        for tid in tests_info:
            # indegree is number of predecessors irrespective of where they will run
            indeg_map[tid] = len(tests_info[tid]['depends_on'])
        flow_indeg.append(indeg_map)
        flow_ready_time.append({tid: 0.0 for tid in tests_info})
    flow_last_finish = [0.0] * total_flows

    # track next-available time per flow to enforce serial execution within a flow
    # replaced with per-unit next-available to ensure channels of same unit don't overlap
    unit_next_available = [0.0] * n_units

    # CRITICAL: Track when each unit is busy with ANY test (intra-unit serialization).
    # A physical unit can only execute one test at a time, even if it has multiple channels
    # and even if there are multiple stations available. This prevents the scheduler from
    # assigning a unit to multiple stations simultaneously.
    unit_busy_until = [0.0] * n_units

    # initialize ready queue only for tasks that belong to the flow and have indeg 0
    ready_q = []
    for f in range(total_flows):
        for tid in flow_tasks[f]:
            if flow_indeg[f][tid] == 0:
                pri = 0.0 + flow_unit[f] * unit_bias_val
                sec = flow_unit[f] if unit_bias_val != 0.0 else 0
                tup = (pri, sec if unit_bias_val != 0.0 else 0, f, tid, flow_unit[f])
                try:
                    logger.debug("PUSH ready_q: %r", tup)
                except Exception:
                    pass
                events.append({'event': 'push', 'pri': pri, 'flow': f, 'tid': tid, 'unit': flow_unit[f]})
                heapq.heappush(ready_q, tup)

    while ready_q:
        tup = heapq.heappop(ready_q)
        try:
            logger.debug("POP ready_q: %r", tup)
        except Exception:
            pass
        try:
            events.append({'event': 'pop', 'tup': tup})
        except Exception:
            pass
        # unpack
        ready_time, _, f, tid, unit_idx = tup
        # skip tasks that don't belong to this flow (guard - should not happen)
        if tid not in flow_tasks[f]:
            continue

        station = tests_info[tid]['station']
        dur = eff_time_h[tid]
        mapped_station = st_map_norm.get(_norm(station)) if station else None
        machines = station_avail.get(mapped_station) if mapped_station is not None else None
        if machines:
            # OPTION A (DEDICATED LINES): When fully_dedicated=True, each unit gets assigned
            # to specific machines that only it uses. Unit i uses machine indices that equal
            # i modulo the station count. This creates N independent parallel test lines.
            if fully_dedicated and len(machines) >= n_units:
                # Dedicated mode: unit i always uses machine i (or i % machine_count)
                m_idx = unit_idx % len(machines)
            else:
                # Shared pool mode: pick the earliest available machine
                m_idx = min(range(len(machines)), key=lambda i: machines[i])

            # ALWAYS enforce that a single unit can only run one test at a time (intra-unit serialization).
            # This is the physical constraint that a unit must move from station to station.
            # Additional constraint: enforce_unit_serialization controls whether different channels/flows
            # of the same unit must also wait for each other (channel serialization).
            base_ready = max(ready_time, machines[m_idx], unit_busy_until[unit_idx])
            if enforce_unit_serialization:
                # Also enforce serial execution across flows/channels of the same unit
                start_time = max(base_ready, unit_next_available[unit_idx])
            else:
                start_time = base_ready
            finish_time = start_time + dur
            machines[m_idx] = finish_time
            station_busy[mapped_station] += dur
            # Update per-unit busy tracker so this unit cannot start another test until this one finishes
            unit_busy_until[unit_idx] = finish_time
            unit_next_available[unit_idx] = finish_time
            try:
                testid = tests_info.get(tid, {}).get('testid', None)
            except Exception:
                testid = None
            try:
                logger.debug("SCHEDULE_ASSIGN: node=%r testid=%r station=%r machine=%r start=%.6f finish=%.6f flow=%r dur=%.6f",
                             tid, testid, station, m_idx, start_time, finish_time, f, dur)
            except Exception:
                pass
            try:
                events.append({'event': 'assign', 'tid': tid, 'flow': f, 'unit': unit_idx, 'station': station, 'machine': m_idx, 'start': start_time, 'finish': finish_time, 'dur': dur})
            except Exception:
                pass
        else:
            start_time = ready_time
            finish_time = start_time + dur
            try:
                testid = tests_info.get(tid, {}).get('testid', None)
            except Exception:
                testid = None
            try:
                logger.debug("SCHEDULE_ASSIGN: node=%r testid=%r station=%r machine=%r start=%.6f finish=%.6f flow=%r dur=%.6f",
                             tid, testid, station, None, start_time, finish_time, f, dur)
            except Exception:
                pass
            try:
                events.append({'event': 'assign', 'tid': tid, 'flow': f, 'unit': unit_idx, 'station': mapped_station or station, 'machine': None, 'start': start_time, 'finish': finish_time, 'dur': dur})
            except Exception:
                pass

        # propagate to successors across all flows where successor is present
        for s in succs[tid]:
            for g in range(total_flows):
                if s in flow_tasks[g]:
                    flow_ready_time[g][s] = max(flow_ready_time[g][s], finish_time)
                    flow_indeg[g][s] -= 1
                    if flow_indeg[g][s] == 0:
                        current_ready_times = [t[0] for t in ready_q] if ready_q else []
                        pri = _effective_priority(flow_ready_time[g][s], flow_unit[g], current_ready_times)
                        sec = flow_unit[g] if unit_bias_val != 0.0 else 0
                        tup2 = (pri, sec if unit_bias_val != 0.0 else 0, g, s, flow_unit[g])
                        try:
                            logger.debug("PUSH ready_q: %r (raw_ready=%.6f)", tup2, flow_ready_time[g][s])
                        except Exception:
                            pass
                        events.append({'event': 'push', 'pri': pri, 'flow': g, 'tid': s, 'unit': flow_unit[g]})
                        heapq.heappush(ready_q, tup2)
        flow_last_finish[f] = max(flow_last_finish[f], finish_time)

    # compute per-unit finish times: shared + its channels
    unit_last_finish = []
    for u in range(n_units):
        start = starts[u]
        end = start + 1 + channels_list[u]
        unit_last_finish.append(max(flow_last_finish[start:end]) if end > start else 0.0)
    makespan = max(unit_last_finish) if unit_last_finish else 0.0

    # station utilization
    station_util = {}
    for s in st_map:
        try:
            cnt = int(st_map[s].get('count', 0))
        except Exception:
            cnt = 0
        if makespan > 0 and cnt > 0:
            station_util[s] = station_busy.get(s, 0.0) / (makespan * cnt)
        else:
            station_util[s] = 0.0

    if trace:
        return makespan, unit_last_finish, station_util, events
    return makespan, unit_last_finish, station_util


def units_completed_in_time(tests_info: Dict[str, dict], topo: List[str], st_map: Dict[str, dict], hours_available: float, channels_per_unit: Union[int, List[int]] = 1, unit_bias: Union[float, None] = None) -> Tuple[int, float, Dict[str, float]]:
    if hours_available <= 0:
        return 0, 0.0, {}
    # For lower bound we do not need channels mix; keep semantics: critical path per single-channel unit
    cp_one_channel = critical_path_hours(tests_info, topo, st_map)
    cp_per_unit_lower_bound = cp_one_channel
    if hours_available < cp_per_unit_lower_bound:
        mk, finishes, util = schedule_n_units(tests_info, topo, st_map, 1, channels_per_unit if isinstance(channels_per_unit, int) else [channels_per_unit[0] if channels_per_unit else 1], unit_bias=unit_bias)
        return 0, cp_per_unit_lower_bound, util
    # binary / incremental search: pick an upper bound
    N_upper = max(1, int(hours_available / (cp_per_unit_lower_bound * 0.5)))
    N_upper = min(N_upper, 1000)
    # If channels_per_unit provided as a list pattern, repeat/pad it to length N_upper
    if isinstance(channels_per_unit, list):
        pattern = channels_per_unit
        # build channels list for N_upper
        ch_list = []
        idx = 0
        while len(ch_list) < N_upper:
            ch_list.append(pattern[idx % len(pattern)])
            idx += 1
        mk, finishes, util = schedule_n_units(tests_info, topo, st_map, N_upper, ch_list, unit_bias=unit_bias)
    else:
        mk, finishes, util = schedule_n_units(tests_info, topo, st_map, N_upper, channels_per_unit, unit_bias=unit_bias)
    completed = sum(1 for f in finishes if f <= hours_available)
    return completed, cp_per_unit_lower_bound, util