import re
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from typing import Optional
from piston_ui.icon_helper import set_window_icon
from piston_core.scheduler import build_dag, schedule_n_units, critical_path_hours, units_completed_in_time
from piston_core.validation import validate_import_rows
from piston_core.constants import is_hidden_station


def open_manual_et_allocator(app):
    """Show Capacity Estimator dialog and apply results to `app.manual_et_override_df`.
    Enhanced UI: allows editing counts and ET (hours) per ET pattern, plus a lightweight capacity
    calculator to estimate units/month or total test time for N units when a full plan is not present.
    """
    if app.station_map_df is None or app.stations_df is None:
        messagebox.showwarning('No model', 'Load the planning Excel first.')
        return
    sm = app.station_map_df.copy()
    sm['Pattern'] = sm['Pattern'].astype(str)
    et_list = sorted([p for p in sm['Pattern'].unique().tolist() if p])
    if not et_list:
        messagebox.showwarning('No ET patterns', 'StationMap has no patterns to configure.')
        return

    # Load existing overrides if present
    existing = {}
    existing_et = {}
    if app.manual_et_override_df is not None and not getattr(app.manual_et_override_df, 'empty', True):
        for _, r in app.manual_et_override_df.iterrows():
            pat = str(r.get('Pattern', '')).strip()
            try:
                existing[pat] = int(r.get('Count', 0) or 0)
            except Exception:
                existing[pat] = 0
            try:
                # stored column is ETMin (minutes) in the dataframe - convert to hours for display
                raw_min = float(r.get('ETMin', r.get('ET', '')) or 0.0)
                existing_et[pat] = raw_min / 60.0 if raw_min else 0.0
            except Exception:
                existing_et[pat] = 0.0

    dlg = tk.Toplevel(app)
    dlg.title('Capacity Estimator')
    # Set custom icon
    set_window_icon(dlg)
    # Compact window size - removed scrollbar, fits content snugly
    dlg.geometry('820x620')
    try:
        dlg.minsize(700, 520)
    except Exception:
        pass

    # Use consistent dark theme colors
    bg = '#1e1e1e'          # dark background
    frame_bg = '#252526'    # slightly lighter
    text_fg = '#d4d4d4'     # light text

    # Apply dark background to dialog
    try:
        dlg.configure(bg=bg)
    except Exception:
        pass

    # Use a plain tk.Label for the descriptive header with dark theme
    try:
        tk.Label(dlg, text="Capacity Estimator - set ET pattern counts and per-pattern test time (hours). Click Calculate to evaluate capacity.", 
                bg=frame_bg, fg=text_fg, anchor='w').pack(fill='x', padx=10, pady=8)
    except Exception:
        pass

    # Simple frame (no scrollbar needed) - content fits in window
    frame = tk.Frame(dlg, bg=frame_bg)
    frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

    hdr = tk.Frame(frame, bg=frame_bg)
    hdr.pack(fill='x', padx=8, pady=4)
    tk.Label(hdr, text='ET Pattern', width=36, bg=frame_bg, fg=text_fg, anchor='w').grid(row=0, column=0, padx=4)
    tk.Label(hdr, text='Maps to Station', width=30, bg=frame_bg, fg=text_fg, anchor='w').grid(row=0, column=1, padx=4)
    tk.Label(hdr, text='Count', width=10, bg=frame_bg, fg=text_fg, anchor='w').grid(row=0, column=2, padx=4)
    tk.Label(hdr, text='Test Time (hrs)', width=12, bg=frame_bg, fg=text_fg, anchor='w').grid(row=0, column=3, padx=4)

    def map_et_to_station(et):
        pat = str(et).strip().lower()
        # exact matches first
        for _, r in app.station_map_df.iterrows():
            if str(r.get('MatchType', '')).strip().lower() == 'exact' and str(r.get('Pattern', '')).strip().lower() == pat:
                return str(r.get('Station', '')).strip()
        # contains matches next
        for _, r in app.station_map_df.iterrows():
            if str(r.get('MatchType', '')).strip().lower() == 'contains' and str(r.get('Pattern', '')).strip().lower() in pat:
                return str(r.get('Station', '')).strip()
        return ''

    rows = []
    choices = [str(i) for i in range(0, 101)]
    # station_link_vars maps station -> StringVar used for the Count column (green column).
    # For patterns mapped to the same station, this ensures a single shared control (first occurrence editable, others disabled/display-only).
    station_link_vars = {}
    station_first_seen = set()
    for et in et_list:
        # Hide patterns that are placeholder insertions (e.g. 'Insert test plan: ...')
        if re.search(r'insert\s+test\s+plan', str(et), flags=re.IGNORECASE):
            continue

        st = map_et_to_station(et)
        # Skip hidden stations (channel markers)
        if st and is_hidden_station(st):
            continue
        line = tk.Frame(frame, bg=frame_bg)
        line.pack(fill='x', padx=8, pady=2)
        cnt_val = existing.get(et, 0)
        et_val = existing_et.get(et, 0.0)
        lbl_et = tk.Label(line, text=et, width=36, anchor='w', bg=frame_bg, fg=text_fg)
        lbl_et.pack(side='left', padx=(4, 8))
        lbl_st = tk.Label(line, text=st, width=30, anchor='w', bg=frame_bg, fg=text_fg)
        lbl_st.pack(side='left', padx=(0, 8))
        # If this pattern maps to a station, reuse a station-level StringVar so the Count column becomes the station override
        if st:
            if st not in station_link_vars:
                # first occurrence: initialize from existing pattern count (best-effort)
                try:
                    init = str(max(0, min(100, int(cnt_val))))
                except Exception:
                    init = '0'
                station_link_vars[st] = tk.StringVar(value=init)
            cnt_var = station_link_vars[st]
            # editable only on first occurrence
            state = 'readonly' if st not in station_first_seen else 'disabled'
            if st not in station_first_seen:
                station_first_seen.add(st)
        else:
            cnt_var = tk.StringVar(value=str(max(0, min(100, int(cnt_val)))))
            state = 'readonly'

        cnt_combo = ttk.Combobox(line, values=choices, textvariable=cnt_var, width=6, state=state)
        cnt_combo.pack(side='left', padx=4)
        et_entry_var = tk.StringVar(value=str(et_val))
        et_entry = ttk.Entry(line, textvariable=et_entry_var, width=12)
        et_entry.pack(side='left', padx=6)
        rows.append((et, cnt_var, et_entry_var))

    # Calculator controls section - mirror main window Run Controls layout
    calc_frame = tk.Frame(frame, bg=frame_bg)
    calc_frame.pack(fill='x', padx=8, pady=(12, 8))

    # Mode selection radio buttons (row 0)
    mode_var = tk.StringVar(value='time_for_n')
    mode_frame = tk.Frame(calc_frame, bg=frame_bg)
    mode_frame.grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 4))
    tk.Radiobutton(mode_frame, text='Time to finish N units', variable=mode_var, value='time_for_n',
                   bg=frame_bg, fg=text_fg, selectcolor='#3c3c3c', activebackground=frame_bg, activeforeground=text_fg).pack(side='left', padx=(0, 12))
    tk.Radiobutton(mode_frame, text='Units completed in T hours', variable=mode_var, value='n_for_time',
                   bg=frame_bg, fg=text_fg, selectcolor='#3c3c3c', activebackground=frame_bg, activeforeground=text_fg).pack(side='left')

    # Input fields (row 1)
    inputs_frame = tk.Frame(calc_frame, bg=frame_bg)
    inputs_frame.grid(row=1, column=0, columnspan=3, sticky='w', pady=(0, 4))

    tk.Label(inputs_frame, text='N:', bg=frame_bg, fg=text_fg).pack(side='left', padx=(0, 4))
    n_var = tk.StringVar(value='10')
    n_entry = ttk.Entry(inputs_frame, textvariable=n_var, width=8)
    n_entry.pack(side='left', padx=(0, 12))

    tk.Label(inputs_frame, text='T (hrs):', bg=frame_bg, fg=text_fg).pack(side='left', padx=(0, 4))
    t_var = tk.StringVar(value='24')
    t_entry = ttk.Entry(inputs_frame, textvariable=t_var, width=8)
    t_entry.pack(side='left', padx=(0, 12))

    # Spins input
    try:
        spins_init = '0'
        if getattr(app, 'spins_var', None):
            try:
                spins_init = str(int(float(app.spins_var.get() or 0)))
            except Exception:
                spins_init = str(app.spins_var.get() or '0')
        spins_var = tk.StringVar(value=spins_init)
        tk.Label(inputs_frame, text='Spins:', bg=frame_bg, fg=text_fg).pack(side='left', padx=(0, 4))
        ttk.Entry(inputs_frame, textvariable=spins_var, width=6).pack(side='left', padx=(0, 12))
    except Exception:
        spins_var = tk.StringVar(value='0')

    # Yield percent input
    try:
        yield_init = '100'
        if getattr(app, 'yield_var', None):
            try:
                yield_init = str(float(app.yield_var.get() or 100.0))
            except Exception:
                yield_init = str(app.yield_var.get() or '100')
        yield_var = tk.StringVar(value=yield_init)
        tk.Label(inputs_frame, text='Yield %:', bg=frame_bg, fg=text_fg).pack(side='left', padx=(0, 4))
        ttk.Entry(inputs_frame, textvariable=yield_var, width=6).pack(side='left', padx=(0, 12))
    except Exception:
        yield_var = tk.StringVar(value='100')

    # Calculate button (row 1, right side - moved from row 2)
    button_frame = tk.Frame(calc_frame, bg=frame_bg)
    button_frame.grid(row=1, column=3, sticky='e', pady=(0, 4), padx=(12, 0))

    # Results display (row 2)
    result_var = tk.StringVar(value='')
    tk.Label(calc_frame, textvariable=result_var, fg='#6eb5ff', bg=frame_bg, anchor='w', justify='left').grid(row=2, column=0, columnspan=4, sticky='w', padx=4, pady=(8, 4))

    def compute_capacity():
        """
        Compute capacity using the scheduler - REDESIGNED to work like main window.

        Key behavior:
        - Each unit goes through ALL tests sequentially (one test at a time per unit)
        - Multiple units can run in parallel based on station availability (Count column)
        - Uses Auto serialization mode (same as main window)
        - No Smart Mode - relies on scheduler's built-in resource management
        """
        # Get mode
        mode = mode_var.get()

        # Parse spins
        try:
            spins = int(float(spins_var.get() or 0))
            if spins < 0:
                spins = 0
        except Exception:
            spins = 0

        # Parse yield percent
        try:
            y_pct = float(yield_var.get() or 100.0)
        except Exception:
            y_pct = 100.0
        if y_pct <= 0:
            messagebox.showerror('Input error', 'Invalid Yield % value (must be > 0)')
            return
        yield_frac = min(100.0, max(0.0, y_pct)) / 100.0

        # Build a synthetic tests DataFrame from the ET patterns
        # Each row represents a test operation that EVERY unit must complete
        # CRITICAL: Chain tests with dependencies so each unit runs them SEQUENTIALLY
        test_rows = []
        prev_test_id = None
        for et, cnt_var, et_var in rows:
            try:
                et_hours = float(et_var.get() or 0.0)
            except Exception:
                et_hours = 0.0

            # Skip tests with zero time
            if et_hours <= 0:
                continue

            st = map_et_to_station(et)
            if not st:
                continue  # Skip unmapped patterns

            # Chain this test to the previous one so tests run sequentially per unit
            test_rows.append({
                'TestID': et,  # Use ET pattern name as TestID
                'TestName': et,
                'Station': st,
                'TestTimeMin': et_hours * 60.0,  # Convert hours to minutes
                'DependsOn': prev_test_id if prev_test_id else '',  # Chain to previous test
                'Include': True
            })
            prev_test_id = et  # This test becomes the dependency for the next one

        if not test_rows:
            result_var.set('No capacity: ensure positive Test Time (hrs) > 0')
            return

        tests_df = pd.DataFrame(test_rows)

        # Build station map from Count column (station_link_vars)
        # This is CRITICAL - the Count column determines how many stations are available
        st_map_calc = {}
        for st in tests_df['Station'].unique():
            # Get count from station_link_vars (the Count column in UI)
            if st in station_link_vars:
                try:
                    cnt = int(float(station_link_vars[st].get() or 0))
                    cnt = max(0, cnt)
                except Exception:
                    cnt = 0
            else:
                # Fallback: shouldn't happen in capacity estimator
                cnt = 1

            st_map_calc[st] = {'count': cnt, 'uptime': 1.0}

        # Validate we have stations with positive counts
        if all(st_map_calc[st]['count'] == 0 for st in st_map_calc):
            result_var.set('No capacity: all station counts are 0. Set Count > 0 for stations.')
            return

        # Build DAG
        try:
            deps, succs, topo = build_dag(tests_df)
        except Exception as e:
            result_var.set(f"Failed to build DAG: {e}")
            return

        # Build tests_info using row-based node IDs to match build_dag output
        # This is the same format used in the main window
        tests_info = {}
        for idx, row in tests_df.iterrows():
            node_id = f"r{idx}"
            # Get actual dependencies from the DAG
            test_depends_on = deps.get(node_id, [])
            tests_info[node_id] = {
                'id': node_id,
                'station': str(row['Station']),
                'time_min': float(row['TestTimeMin']),
                'depends_on': test_depends_on,  # Use actual dependencies from DAG
            }

        # DEBUG: Print test structure to diagnose issue
        try:
            import sys
            print("\n=== CAPACITY ESTIMATOR DEBUG ===", file=sys.stderr)
            print(f"Number of tests: {len(tests_info)}", file=sys.stderr)
            print(f"Topology order: {topo}", file=sys.stderr)
            print("\nTest details:", file=sys.stderr)
            for tid in topo:
                info = tests_info[tid]
                print(f"  {tid}: station={info['station']}, time={info['time_min']:.1f}min, depends_on={info['depends_on']}", file=sys.stderr)
            print(f"\nStation map: {st_map_calc}", file=sys.stderr)
            print("=== END DEBUG ===\n", file=sys.stderr)
        except Exception as e:
            print(f"Debug print failed: {e}", file=sys.stderr)

        # Parse mode inputs
        if mode == 'time_for_n':
            # Time to finish N units mode
            try:
                units_target = int(float(n_var.get() or 0))
                if units_target <= 0:
                    messagebox.showerror('Input error', 'N (units) must be positive')
                    return
            except Exception:
                messagebox.showerror('Input error', 'Invalid N value')
                return
        else:
            # Units completed in T hours mode
            try:
                hours_target = float(t_var.get() or 0)
                if hours_target <= 0:
                    messagebox.showerror('Input error', 'T (hours) must be positive')
                    return
            except Exception:
                messagebox.showerror('Input error', 'Invalid T value')
                return

        # CORRECTED MODEL (based on manual model analysis):
        # - "Spins" parameter does NOT control test iterations
        # - Each unit runs tests exactly ONCE
        # - Yield is applied as time multiplier (test_time / yield)
        # - Multiple units flow through pipeline in parallel
        # Therefore: DO NOT replicate tests based on spins value

        # Calculate capacity based on mode
        if mode == 'time_for_n':
            # Apply yield: Each unit takes longer due to retries (not more units!)
            # With 30% yield, average attempts = 1/0.30 = 3.33 per unit
            # So effective_time_per_test = base_time / yield_frac

            units_required = units_target  # We complete exactly the target (after retries)

            # PIPELINE SIMULATION: Model how units flow through sequential tests
            # with yield-adjusted test times
            try:
                # Build ordered list of tests from topology with yield adjustment
                # Skip tests at stations with 0 count (unavailable)
                test_sequence = []
                for node_id in topo:
                    info = tests_info[node_id]
                    station = info['station']
                    # Skip if station has no resources available
                    if station not in st_map_calc or st_map_calc[station]['count'] == 0:
                        continue
                    base_time = info['time_min']
                    # Adjust for yield: with Y% pass rate, average attempts = 1/Y
                    effective_time = base_time / yield_frac if yield_frac > 0 else base_time
                    test_sequence.append({
                        'node_id': node_id,
                        'station': station,
                        'time_min': effective_time  # Yield-adjusted time
                    })

                if not test_sequence:
                    result_var.set('No capacity: all tests map to stations with Count=0. Set Count > 0.')
                    return

                # Calculate critical path (sum of all test times since they're sequential)
                # This represents the minimum time for one unit to complete all tests
                cp_minutes = sum(test['time_min'] for test in test_sequence)
                cp_hours_adjusted = cp_minutes / 60.0

                # DEBUG: Show test sequence details
                import sys
                print(f"\n=== TEST SEQUENCE DEBUG ===", file=sys.stderr)
                print(f"Number of tests in sequence: {len(test_sequence)}", file=sys.stderr)
                print(f"Critical path: {cp_hours_adjusted:.2f} hours ({cp_minutes:.1f} minutes)", file=sys.stderr)
                print(f"Yield fraction: {yield_frac} (multiplier: {1.0/yield_frac:.2f}×)", file=sys.stderr)
                print(f"Tests per unit (without spins): {len([t for t in tests_info.keys() if '_spin' not in t])}", file=sys.stderr)
                print(f"First few tests:", file=sys.stderr)
                for i, test in enumerate(test_sequence[:5]):
                    print(f"  {i}: {test['node_id']} at {test['station']}, {test['time_min']:.1f} min", file=sys.stderr)
                print(f"=== END DEBUG ===\n", file=sys.stderr)

                # Simulate pipeline: track when each station's resources become available
                from heapq import heappush, heappop
                station_queues = {}
                for st in st_map_calc:
                    st_count = st_map_calc[st]['count']
                    if st_count > 0:  # Only create queues for stations with resources
                        station_queues[st] = [(0.0, i) for i in range(st_count)]

                # Track completion time for each unit
                unit_finish_times = []

                # For each unit, simulate its flow through the test sequence
                for unit_idx in range(units_required):
                    current_time = 0.0

                    # Process each test in sequence
                    for test in test_sequence:
                        station = test['station']
                        test_time = test['time_min']  # Already yield-adjusted

                        # Get the earliest available resource at this station
                        available_time, resource_idx = heappop(station_queues[station])

                        # Unit can start this test when both ready
                        start_time = max(current_time, available_time)
                        finish_time = start_time + test_time

                        # Return this resource to the queue
                        heappush(station_queues[station], (finish_time, resource_idx))

                        # Update current time for next test
                        current_time = finish_time

                    # Unit completed all tests (after retries)
                    unit_finish_times.append(current_time)

                # Makespan is when the last unit finishes
                total_minutes = max(unit_finish_times) if unit_finish_times else 0
                total_hours = total_minutes / 60.0

                # Calculate utilization: (total work done) / (makespan × station_count)
                util = {}
                for st in st_map_calc:
                    st_count = st_map_calc[st]['count']
                    # Sum up work for this station (yield-adjusted)
                    station_work = sum(
                        test['time_min'] * units_required 
                        for test in test_sequence 
                        if test['station'] == st
                    )
                    if total_minutes > 0 and st_count > 0:
                        util[st] = station_work / (total_minutes * st_count)
                    else:
                        util[st] = 0.0

                # Build utilization summary
                util_lines = []
                for st, u in sorted(util.items()):
                    if st in st_map_calc:
                        cnt = st_map_calc[st]['count']
                        util_lines.append(f"  {st} ({cnt} stations): {u*100:.1f}%")
                util_summary = '\n'.join(util_lines) if util_lines else '  (no data)'

                result_msg = (
                    f"For {units_target} units (yield {y_pct}%) → {total_hours:.2f} hrs total\n"
                    f"All {units_target} units complete (with retries)\n"
                    f"Avg attempts per unit: {1.0/yield_frac:.2f}× (due to {y_pct}% yield)\n"
                    f"Critical path (1 unit, with retries): {cp_hours_adjusted:.2f} hrs\n"
                    f"Tests per unit: {len(tests_info)}\n"
                    f"Total test operations: {len(tests_info) * units_target}\n\n"
                    f"Station Utilization:\n{util_summary}\n\n"
                    f"Pipeline simulation (models parallel flow with yield-adjusted times)"
                )
                result_var.set(result_msg)

            except Exception as e:
                import traceback
                result_var.set(f"Calculation error: {e}\n{traceback.format_exc()}")
                return
        else:
            # Units completed in T hours mode
            # Use the SAME pipeline simulation as "Time to finish N units" mode
            # This ensures units flow sequentially through tests (not aggressive parallelism)

            try:
                # Build ordered list of tests from topology with yield adjustment
                # Skip tests at stations with 0 count (unavailable)
                test_sequence = []
                for node_id in topo:
                    info = tests_info[node_id]
                    station = info['station']
                    # Skip if station has no resources available
                    if station not in st_map_calc or st_map_calc[station]['count'] == 0:
                        continue
                    base_time = info['time_min']
                    # Adjust for yield: with Y% pass rate, average attempts = 1/Y
                    effective_time = base_time / yield_frac if yield_frac > 0 else base_time
                    test_sequence.append({
                        'node_id': node_id,
                        'station': station,
                        'time_min': effective_time  # Yield-adjusted time
                    })

                if not test_sequence:
                    result_var.set('No capacity: all tests map to stations with Count=0. Set Count > 0.')
                    return

                # Calculate critical path (sum of all test times since they're sequential)
                cp_minutes = sum(test['time_min'] for test in test_sequence)
                cp_hours_adjusted = cp_minutes / 60.0

                # Simulate pipeline: track when each station's resources become available
                from heapq import heappush, heappop
                station_queues = {}
                for st in st_map_calc:
                    st_count = st_map_calc[st]['count']
                    if st_count > 0:  # Only create queues for stations with resources
                        station_queues[st] = [(0.0, i) for i in range(st_count)]

                # Binary search to find how many units complete in target time
                # Start with a reasonable upper bound
                max_units = 1000  # Arbitrary large number
                units_completed = 0

                # Simulate units until we exceed the time budget
                target_minutes = hours_target * 60.0
                for unit_idx in range(max_units):
                    current_time = 0.0

                    # Process each test in sequence for this unit
                    for test in test_sequence:
                        station = test['station']
                        test_time = test['time_min']  # Already yield-adjusted

                        # Get the earliest available resource at this station
                        available_time, resource_idx = heappop(station_queues[station])

                        # Unit can start this test when both ready
                        start_time = max(current_time, available_time)
                        finish_time = start_time + test_time

                        # Return this resource to the queue
                        heappush(station_queues[station], (finish_time, resource_idx))

                        # Update current time for next test
                        current_time = finish_time

                    # Check if this unit finished within time budget
                    if current_time <= target_minutes:
                        units_completed = unit_idx + 1
                    else:
                        # This unit exceeds budget, stop simulation
                        break

                # Calculate utilization based on actual work done
                # (cp_hours_adjusted already calculated earlier from test_sequence)

                # Build utilization summary
                util = {}
                for st in st_map_calc:
                    st_count = st_map_calc[st]['count']
                    # Sum up work for this station (yield-adjusted)
                    station_work = sum(
                        test['time_min'] * units_completed
                        for test in test_sequence 
                        if test['station'] == st
                    )
                    if target_minutes > 0 and st_count > 0:
                        util[st] = station_work / (target_minutes * st_count)
                    else:
                        util[st] = 0.0

                util_lines = []
                for st, u in sorted(util.items()):
                    if st in st_map_calc:
                        cnt = st_map_calc[st]['count']
                        util_lines.append(f"  {st} ({cnt} stations): {u*100:.1f}%")
                util_summary = '\n'.join(util_lines) if util_lines else '  (no data)'

                result_msg = (
                    f"In {hours_target} hours → {units_completed} good units completed\n"
                    f"All {units_completed} units complete (with retries)\n"
                    f"Avg attempts per unit: {1.0/yield_frac:.2f}× (due to {y_pct}% yield)\n"
                    f"Critical path (1 unit, with retries): {cp_hours_adjusted:.2f} hrs\n"
                    f"Tests per unit: {len(tests_info)}\n"
                    f"Total test operations: {len(tests_info) * units_completed}\n\n"
                    f"Station Utilization:\n{util_summary}\n\n"
                    f"Pipeline simulation (models parallel flow with yield-adjusted times)"
                )
                result_var.set(result_msg)

            except Exception as e:
                import traceback
                result_var.set(f"Calculation error: {e}\n{traceback.format_exc()}")
                return

        # Sync spins and yield back to main app
        try:
            if getattr(app, 'spins_var', None):
                app.spins_var.set(str(spins))
        except Exception:
            pass
        try:
            if getattr(app, 'yield_var', None):
                app.yield_var.set(str(y_pct))
        except Exception:
            pass

    ttk.Button(button_frame, text='Calculate', command=compute_capacity, width=12).pack(side='right', padx=6)

    # allow Enter to trigger calculate
    try:
        dlg.bind('<Return>', lambda e: compute_capacity())
    except Exception:
        pass
