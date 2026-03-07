"""
Calculate module - extracted from Piston.py for better organization.

Handles schedule calculation for both modes:
- Time to finish N units
- Units completed in T hours
"""
import re
import logging
from tkinter import messagebox
import tkinter as tk
import pandas as pd

from piston_core.scheduler import build_dag, schedule_n_units
from piston_core.constants import is_hidden_station
from piston_ui.validation_helper import build_tests_info
from piston_ui.scheduler_helper import compute_schedule
from piston_ui.channels_helper import build_channels_spec

logger = logging.getLogger("piston")


def calculate(app):
    """Trigger schedule calculation using current UI state.
    
    Args:
        app: PlannerApp instance with all state and UI widgets
        
    Uses `piston_ui.scheduler_helper.compute_schedule` when sufficient data is present.
    If inputs are missing the user is shown an informative dialog.
    """
    # Ensure we have imported tests
    if getattr(app, 'imported_tests_df', None) is None:
        messagebox.showwarning("No data", "No imported tests available. Import a plan first.")
        return
        
    # Ensure station map available
    st_map = getattr(app, 'st_map', None) or {}
    if not st_map and getattr(app, 'stations_df', None) is None:
        messagebox.showerror("No stations", "No station map available for scheduling.")
        return
        
    # Pull current station counts from the Stations tree so UI edits are respected
    st_map = _merge_station_counts_from_ui(app, st_map)
    
    # Build tests_info and topo for scheduling
    try:
        df = app.filtered_tests_df if getattr(app, 'filtered_tests_df', None) is not None else app.imported_tests_df
        
        # Apply YellowStone-only filter if requested
        if getattr(app, 'ys_only_var', None) and app.ys_only_var.get():
            df = _apply_yellowstone_filter(app, df)
            if df is None:
                return  # Filter showed message and returned None
        
        # Build tests_info if not already set by filter
        if getattr(app, 'tests_info', None) is None:
            deps, succs, topo = build_dag(df)
            app.tests_info = build_tests_info(df, deps, app._parse_time_to_minutes)
            app.topo = topo
    except Exception:
        logger.exception("Failed preparing tests for scheduling")
        messagebox.showerror("Calculation error", "Failed preparing tests for scheduling. Ensure imported plan is valid.")
        return
    
    mode = app.mode_var.get() if getattr(app, 'mode_var', None) is not None else 'time_for_n'
    
    # Parse N or estimate for units_in_t mode
    n_req = _parse_n_req(app, mode)
    if n_req is None:
        return  # Error message already shown
    
    # SMART MODE: Detect sufficient stations for parallel execution
    sufficient_stations = _check_sufficient_stations(st_map, n_req)
    
    # Build channels specification
    channels_spec = _build_channels_spec_validated(app, mode, n_req)
    
    # Execute appropriate calculation mode
    if mode == 'time_for_n':
        _calculate_time_for_n(app, st_map, n_req, channels_spec, sufficient_stations)
    else:
        _calculate_units_in_t(app, st_map, channels_spec)


def _merge_station_counts_from_ui(app, st_map):
    """Merge station counts from UI tree into st_map."""
    if getattr(app, 'st_tree', None) is None or not isinstance(st_map, dict):
        return st_map
        
    logger.info("=== STATION COUNT MERGE START ===")
    logger.info("st_map before merge: %r", {k: v.get('count', v) if isinstance(v, dict) else v for k, v in list(st_map.items())[:5]})
    
    displayed_map = {}
    for iid in app.st_tree.get_children():
        vals = app.st_tree.item(iid, 'values')
        if not vals or len(vals) < 2:
            continue
        name = str(vals[0]).strip()
        
        # Skip hidden stations (channel markers)
        if is_hidden_station(name):
            continue
            
        try:
            cnt = int(vals[1])
        except (ValueError, TypeError):
            try:
                cnt = int(float(str(vals[1] or '0')))
            except (ValueError, TypeError):
                cnt = 0
        displayed_map[name] = {'count': cnt, 'uptime': 1.0}
    
    logger.info("displayed_map from UI: %r", {k: v['count'] for k, v in list(displayed_map.items())[:5]})
    
    # Normalizer: strip non-alphanumeric and casefold to match scheduler normalization
    def _norm(s):
        try:
            return re.sub(r'[^0-9a-z]', '', str(s).strip().casefold())
        except Exception:
            return re.sub(r'[^0-9a-z]', '', str(s).strip().lower())
    
    # Merge displayed_map into st_map by matching normalized names
    for disp_name, v in displayed_map.items():
        cnt = v.get('count', 0) if isinstance(v, dict) else int(v)
        
        # Find matching existing key
        match = None
        for existing_key in list(st_map.keys()):
            if _norm(existing_key) == _norm(disp_name):
                match = existing_key
                logger.debug("Matched UI '%s' -> st_map '%s' (count=%d)", disp_name, existing_key, cnt)
                break
        
        if match is not None:
            val = st_map.get(match)
            if isinstance(val, dict):
                st_map[match]['count'] = cnt
            else:
                st_map[match] = {'count': cnt, 'uptime': 1.0}
        else:
            logger.warning("No match for UI station '%s' (norm=%s), adding as new key with count=%d", disp_name, _norm(disp_name), cnt)
            st_map[disp_name] = {'count': cnt, 'uptime': 1.0}
    
    logger.info("st_map after merge: %r", {k: v.get('count', v) if isinstance(v, dict) else v for k, v in list(st_map.items())[:5]})
    logger.info("=== STATION COUNT MERGE END ===")
    
    return st_map


def _apply_yellowstone_filter(app, df):
    """Apply YellowStone-only filter to tests DataFrame.
    
    Returns filtered DataFrame or None if no tests remain.
    """
    try:
        from piston_ui.stations_view import _normalize_name
        
        marker_subs = {'transfergate', 'transfer', 'loadinggattest', 'loadinggate', 'ysloadinggate', 'loading'}
        
        if not isinstance(df, pd.DataFrame) or df.empty or 'TestName' not in df.columns:
            messagebox.showinfo('YellowStone filter', 'Current plan has no TestName column to apply Yellowstone-only filter. No filtering applied.')
            return df
        
        gdeps, gsuccessors, gtopo = build_dag(df)
        
        # Find marker nodes
        markers = []
        for idx, row in df.iterrows():
            tn = _normalize_name(str(row.get('TestName', '')))
            if tn and any(sub in tn for sub in marker_subs):
                markers.append(f"r{idx}")
        
        if not markers:
            messagebox.showinfo('YellowStone filter', 'No TransferGate/LoadingGateTest entries found in the current plan. No filtering applied.')
            return df
        
        # Include all tests at-or-after the earliest marker
        marker_idxs = [int(m[1:]) for m in markers if isinstance(m, str) and m.startswith('r')]
        if marker_idxs:
            min_marker_idx = min(marker_idxs)
            keep_nodes = set(f"r{idx}" for idx in df.index if int(idx) >= min_marker_idx)
        else:
            # Fallback: compute reachable successors
            reachable = set()
            stack = list(markers)
            while stack:
                nid = stack.pop()
                if nid in reachable:
                    continue
                reachable.add(nid)
                for s in gsuccessors.get(nid, []):
                    if s not in reachable:
                        stack.append(s)
            keep_nodes = reachable
        
        keep_idx = [int(n[1:]) for n in keep_nodes if isinstance(n, str) and n.startswith('r')]
        if not keep_idx:
            messagebox.showinfo('YellowStone filter', 'No tests remain after applying Yellowstone-only filter.')
            return None
        
        # Filter DataFrame
        new_df = df.loc[df.index.isin(keep_idx)].copy()
        
        # Build reduced deps mapping
        deps_filtered = {}
        node_ids_set = set(f"r{r}" for r in keep_idx)
        for nid in [f"r{r}" for r in keep_idx]:
            provs = gdeps.get(nid, [])
            deps_filtered[nid] = [p for p in provs if p in node_ids_set]
        
        app.tests_info = build_tests_info(new_df, deps_filtered, app._parse_time_to_minutes)
        app.topo = [n for n in gtopo if n in node_ids_set]
        return new_df
        
    except Exception:
        logger.exception('Error applying Yellowstone-only filter')
        # Fallback: build global DAG
        deps, succs, topo = build_dag(df)
        app.tests_info = build_tests_info(df, deps, app._parse_time_to_minutes)
        app.topo = topo
        return df


def _parse_n_req(app, mode):
    """Parse n_req from UI inputs based on mode.
    
    Returns n_req or None if invalid (error message shown to user).
    """
    if mode == 'time_for_n':
        try:
            n_req = int(float(app.n_var.get() or 0))
            if n_req <= 0:
                messagebox.showerror("Input error", "N must be positive")
                return None
            return n_req
        except (ValueError, TypeError):
            messagebox.showerror("Input error", "Invalid N value")
            return None
    else:
        # For units_in_t mode, estimate n_req from channel quantities or use default
        try:
            single = int(app.single_var.get() or 0)
            dual = int(app.dual_var.get() or 0)
            quad = int(app.quad_var.get() or 0)
            total_units = single + dual + quad
            return total_units if total_units > 0 else 10  # Default search space
        except (ValueError, TypeError):
            return 10  # Default fallback


def _check_sufficient_stations(st_map, n_req):
    """Check if we have sufficient stations for parallel execution (Smart Mode).
    
    Returns True if minimum station count >= n_req.
    """
    if not n_req or not isinstance(st_map, dict):
        return False
    
    min_count = float('inf')
    for stn, info in st_map.items():
        try:
            cnt = info.get('count', 0) if isinstance(info, dict) else int(info)
            if cnt > 0:
                min_count = min(min_count, cnt)
        except (ValueError, TypeError, AttributeError):
            pass
    
    sufficient = min_count != float('inf') and min_count >= n_req
    if sufficient:
        logger.info("SMART MODE: Detected sufficient stations (min=%d >= units=%d), disabling serialization bias", min_count, n_req)
    return sufficient


def _build_channels_spec_validated(app, mode, n_req):
    """Build and validate channels specification from UI inputs.
    
    Returns channels_spec (int or list).
    """
    try:
        channels_spec = build_channels_spec(
            app.single_var.get(), 
            app.dual_var.get(), 
            app.quad_var.get(), 
            freeform_spec=app.channels_var.get(), 
            n_units=n_req, 
            parse_channels_fn=app._parse_channels_spec
        )
        logger.info("build_channels_spec returned: %r (type=%s)", channels_spec, type(channels_spec))
    except Exception:
        logger.exception("build_channels_spec failed, using default")
        channels_spec = 1
    
    # Validate: If user specified explicit quantities, build explicit list
    if mode == 'time_for_n' and n_req:
        try:
            single = int(app.single_var.get() or 0)
            dual = int(app.dual_var.get() or 0)
            quad = int(app.quad_var.get() or 0)
            
            if single > 0 or dual > 0 or quad > 0:
                expected_units = single + dual + quad
                if expected_units != n_req:
                    logger.warning("Channel unit count (%d) != N (%d), using N", expected_units, n_req)
                
                # Build explicit list: [1,1,...] for single, [2,2,...] for dual, [4,4,...] for quad
                explicit_spec = [1] * single + [2] * dual + [4] * quad
                
                # Pad or trim to match n_req
                if len(explicit_spec) < n_req:
                    explicit_spec.extend([1] * (n_req - len(explicit_spec)))
                elif len(explicit_spec) > n_req:
                    explicit_spec = explicit_spec[:n_req]
                
                logger.info("Overriding channels_spec with explicit: %r", explicit_spec)
                channels_spec = explicit_spec
        except Exception:
            logger.exception("Failed building explicit channels_spec, using returned value")
    
    return channels_spec


def _calculate_time_for_n(app, st_map, n_req, channels_spec, sufficient_stations):
    """Calculate time to finish N units."""
    # Parse spins and yield
    spins = _parse_spins(app)
    yfrac, ypct = _parse_yield(app)
    factor = 1 + spins
    
    effective_tests = n_req  # Run exactly n_req units
    
    # Adjust test times for yield (models retry overhead)
    tests_info_adjusted = {}
    for tid, info in app.tests_info.items():
        tests_info_adjusted[tid] = {
            'testid': info['testid'],
            'station': info['station'],
            'time_min': info['time_min'] / yfrac,  # Adjust for retries
            'depends_on': info['depends_on']
        }
    
    # Parse bias parameters
    unit_bias_val, bias_max_frac, bias_window_frac, serialization_mode, ub_raw = _parse_bias_params(app)
    
    # SMART MODE: Override bias when sufficient stations detected
    if sufficient_stations and ub_raw == '' and serialization_mode == 'Auto':
        unit_bias_val = 0.0
        serialization_mode = 'Relaxed'
        logger.info("SMART MODE: Forcing zero bias and Relaxed mode for parallel execution")
    
    try:
        mk, finishes, util, cp = compute_schedule(
            tests_info_adjusted, app.topo, st_map, 'time_for_n',
            n_req=effective_tests, 
            channels_per_unit=channels_spec,
            unit_bias=unit_bias_val,
            bias_max_frac=bias_max_frac,
            bias_window_frac=bias_window_frac,
            serialization_mode=serialization_mode
        )
        
        mk_total = mk * factor
        
        # Sanity check against critical path
        _sanity_check_makespan(app, mk_total, cp, st_map, effective_tests, channels_spec)
        
        # Format and display results
        _display_time_for_n_results(app, mk_total, finishes, util, n_req, factor, ypct, yfrac, sufficient_stations)
        
    except Exception as ex:
        logger.exception("Scheduler failed")
        messagebox.showerror("Calculation error", f"Schedule computation failed: {ex}")


def _calculate_units_in_t(app, st_map, channels_spec):
    """Calculate units completed in T hours."""
    try:
        hours_avail = float(app.t_var.get() or 0.0)
        if hours_avail <= 0:
            messagebox.showerror("Input error", "T must be positive")
            return
    except (ValueError, TypeError):
        messagebox.showerror("Input error", "Invalid T (hours) value")
        return
    
    # Parse spins and yield
    spins = _parse_spins(app)
    yfrac, ypct = _parse_yield(app)
    factor = 1 + spins
    
    # Parse bias parameters
    unit_bias_val, bias_max_frac, bias_window_frac, serialization_mode, ub_raw = _parse_bias_params(app)
    
    # SMART MODE: Check station availability for parallel execution
    if ub_raw == '' and serialization_mode == 'Auto' and isinstance(st_map, dict):
        min_count = float('inf')
        for stn, info in st_map.items():
            try:
                cnt = info.get('count', 0) if isinstance(info, dict) else int(info)
                if cnt > 0:
                    min_count = min(min_count, cnt)
            except (ValueError, TypeError, AttributeError):
                pass
        
        if min_count != float('inf') and min_count >= 5:
            unit_bias_val = 0.0
            serialization_mode = 'Relaxed'
            logger.info("SMART MODE (units_in_t): Forcing zero bias for parallel execution (min_stations=%d)", min_count)
    
    try:
        completed, cp_lb, util = compute_schedule(
            app.tests_info, app.topo, st_map, 'units_in_t',
            hours_avail=hours_avail,
            channels_per_unit=channels_spec,
            unit_bias=unit_bias_val,
            bias_max_frac=bias_max_frac,
            bias_window_frac=bias_window_frac,
            serialization_mode=serialization_mode
        )
        
        # Adjust for spins and yield
        effective_completed = int((completed / factor) * yfrac) if factor > 0 else int(completed * yfrac)
        
        # Format and display results
        _display_units_in_t_results(app, hours_avail, effective_completed, completed, util, factor, yfrac)
        
    except Exception as ex:
        logger.exception("Scheduler failed")
        messagebox.showerror("Calculation error", f"Schedule computation failed: {ex}")


def _parse_spins(app):
    """Parse spins value from UI (defaults to 0 if invalid)."""
    try:
        spins = int(float(app.spins_var.get() or 0))
        return max(0, spins)
    except (ValueError, TypeError):
        return 0


def _parse_yield(app):
    """Parse yield percentage from UI (defaults to 100% if invalid).
    
    Returns (fraction, percent) tuple.
    """
    try:
        ypct = float(app.yield_var.get() or 100.0)
        if ypct <= 0:
            return 1.0, 100.0
        yfrac = max(0.0, min(100.0, ypct)) / 100.0
        return yfrac, ypct
    except (ValueError, TypeError):
        return 1.0, 100.0


def _parse_bias_params(app):
    """Parse bias-related parameters from UI.
    
    Returns (unit_bias_val, bias_max_frac, bias_window_frac, serialization_mode, ub_raw).
    """
    try:
        ub_raw = (app.unit_bias_var.get() or '').strip()
        unit_bias_val = None if ub_raw == '' else float(ub_raw)
    except (ValueError, TypeError, AttributeError):
        ub_raw = ''
        unit_bias_val = None
    
    try:
        bm_raw = (app.bias_max_var.get() or '').strip()
        bias_max_frac = float(bm_raw) / 100.0 if bm_raw != '' else 0.05
    except (ValueError, TypeError, AttributeError):
        bias_max_frac = 0.05
    
    try:
        bw_raw = (app.bias_window_var.get() or '').strip()
        bias_window_frac = float(bw_raw) if bw_raw != '' else 1.0
    except (ValueError, TypeError, AttributeError):
        bias_window_frac = 1.0
    
    try:
        serialization_mode = app.serialization_var.get() or 'Auto'
    except AttributeError:
        serialization_mode = 'Auto'
    
    return unit_bias_val, bias_max_frac, bias_window_frac, serialization_mode, ub_raw


def _sanity_check_makespan(app, mk_total, cp, st_map, effective_tests, channels_spec):
    """Check if makespan is shorter than critical path (diagnostic)."""
    try:
        cp_hours = float(cp) if cp is not None else None
    except (ValueError, TypeError):
        cp_hours = None
    
    if cp_hours is None or mk_total + 1e-6 >= cp_hours:
        return  # OK
    
    # Unexpected: makespan < critical path - gather trace
    logger.warning("Computed makespan (%.6f hrs) is less than critical-path lower bound (%.6f hrs)", mk_total, cp_hours)
    
    try:
        # Run traced schedule for debugging
        try:
            trace_mk, trace_finishes, trace_util, trace_events = schedule_n_units(
                app.tests_info, app.topo, st_map, effective_tests,
                channels_per_unit=channels_spec, trace=True
            )
        except TypeError:
            # Fallback without trace kwarg
            trace_mk, trace_finishes, trace_util, trace_events = schedule_n_units(
                app.tests_info, app.topo, st_map, effective_tests,
                channels_per_unit=channels_spec
            )
        
        # Build compact trace summary
        ev_lines = [
            f"SanityTrace: mk_total={mk_total:.6f} hrs, critical_path={cp_hours:.6f} hrs",
            "First schedule events:"
        ]
        
        for e in (trace_events[:80] if isinstance(trace_events, (list, tuple)) else []):
            if isinstance(e, dict):
                typ = e.get('event')
                tid = e.get('tid') or e.get('node') or ''
                stn = e.get('station') or ''
                flow = e.get('flow', '')
                start = e.get('start')
                finish = e.get('finish')
                ev_lines.append(f"  {typ} tid={tid} st={stn} flow={flow} start={start} finish={finish}")
            else:
                ev_lines.append(f"  {str(e)}")
        
        # Display trace
        out = "\n".join(ev_lines)
        app.out_text.configure(state='normal')
        app.out_text.delete('1.0', tk.END)
        app.out_text.insert(tk.END, out)
        app.out_text.configure(state='disabled')
        
        logger.debug("Sanity trace events (first 80): %s", trace_events[:80] if isinstance(trace_events, (list, tuple)) else trace_events)
        messagebox.showwarning("Scheduling sanity check", "Computed makespan is shorter than the critical-path lower bound. A scheduler trace has been written to the results box and debug log for investigation.")
        
    except Exception:
        logger.exception("Failed producing sanity trace")


def _display_time_for_n_results(app, mk_total, finishes, util, n_req, factor, ypct, yfrac, sufficient_stations):
    """Format and display results for time_for_n mode."""
    lines = []
    
    # Smart Mode indicator
    if sufficient_stations:
        lines.append("🚀 SMART MODE: Parallel execution enabled (sufficient stations detected)")
        lines.append("")
    
    lines.append(f"Total test time for qty of selected units (hours): {mk_total}")
    lines.append("Per-unit finishes:")
    
    # Build per-unit finish times
    good_finishes = []
    try:
        for i in range(min(len(finishes), n_req)):
            good_finishes.append(finishes[i] * factor)
        # Pad if needed
        while len(good_finishes) < n_req:
            good_finishes.append(mk_total)
    except Exception:
        # Fallback: evenly spaced
        good_finishes = [mk_total * (i / n_req) for i in range(1, n_req + 1)]
    
    for i, ft in enumerate(good_finishes, start=1):
        lines.append(f"  Unit {i}: {ft:.3f} hrs")
    lines.append("")
    
    # Yield information
    if yfrac < 1.0:
        avg_attempts = 1.0 / yfrac
        lines.append(f"Yield: {ypct:.1f}% (avg {avg_attempts:.2f} attempts per unit)")
        lines.append("")
    
    # Station utilization
    lines.append("Station utilization (hours per machine):")
    shown = False
    for s, v in sorted(util.items()):
        hours = v * mk_total
        if hours > 0.000:
            lines.append(f"  {s}: {hours:.3f} hrs")
            shown = True
    if not shown:
        lines.append("  (none)")
    
    out = "\n".join(lines)
    app.out_text.configure(state='normal')
    app.out_text.delete('1.0', tk.END)
    app.out_text.insert(tk.END, out)
    app.out_text.configure(state='disabled')


def _display_units_in_t_results(app, hours_avail, effective_completed, completed, util, factor, yfrac):
    """Format and display results for units_in_t mode."""
    lines = [
        f"Hours available: {hours_avail}",
        f"Estimated completed units: {effective_completed} (raw attempts: {completed})",
        "",
        "Station utilization (hours per machine during T):"
    ]
    
    shown = False
    for s, v in sorted(util.items()):
        # Scale utilization by hours, spins, and yield
        hours = v * hours_avail * factor * (1.0 / yfrac if yfrac > 0 else 1.0)
        if hours > 0.000:
            lines.append(f"  {s}: {hours:.3f} hrs")
            shown = True
    
    if not shown:
        lines.append("  (none)")
    
    out = "\n".join(lines)
    app.out_text.configure(state='normal')
    app.out_text.delete('1.0', tk.END)
    app.out_text.insert(tk.END, out)
    app.out_text.configure(state='disabled')
