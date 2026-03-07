import tkinter as tk
from tkinter import ttk
import pandas as pd
from typing import Tuple
import logging

logger = logging.getLogger('piston')

# Import hidden stations from main module
def _get_hidden_stations_set():
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


def _normalize_name(s: str) -> str:
    if s is None:
        return ''
    try:
        return str(s).strip().lower()
    except Exception:
        return ''


def _is_hidden_station(station_name: str) -> bool:
    """Check if a station should be hidden."""
    if not station_name or pd.isna(station_name):
        return True
    normalized = _normalize_name(station_name)
    return normalized in _get_hidden_stations_set()


def create_stations_frame(parent) -> Tuple[ttk.Frame, ttk.Treeview]:
    container = ttk.Frame(parent, style='Uniform.TFrame')
    ttk.Label(container, text='Stations', style='SectionTitle.TLabel').pack(anchor='w', padx=4, pady=(4, 0))
    ttk.Label(container, text='(Double-click count to edit)', 
             font=('TkDefaultFont', 8), foreground='#d4d4d4').pack(anchor='w', padx=4, pady=(0, 4))

    # Create bordered container
    import tkinter as tk
    border_frame = tk.Frame(container, bg='#3c3c3c', relief='solid', borderwidth=1, highlightbackground='#5a5a5a', highlightthickness=1)
    border_frame.pack(fill='both', expand=True, padx=4, pady=0)

    frame = ttk.Frame(border_frame, width=320)  # wider to accommodate both columns
    frame.pack(fill='both', expand=True, padx=6, pady=6)

    tree = ttk.Treeview(frame, columns=("Station", "Count"), show='headings', height=10)
    tree.heading("Station", text="Station", anchor='w')
    tree.column("Station", width=200, minwidth=140, stretch=True, anchor='w')
    tree.heading("Count", text="Count", anchor='center')
    tree.column("Count", width=80, minwidth=70, stretch=False, anchor='center')
    tree.pack(fill='both', expand=True, padx=4, pady=4)
    return container, tree


def refresh_stations_tree(app, tree: ttk.Treeview):
    """Populate the stations tree from app.stations_df and app.st_map.
    This implementation is intentionally straightforward to avoid deep nesting
    and reduce chance of syntax/indentation errors.
    """
    # Clear tree
    try:
        tree.delete(*tree.get_children())
    except Exception:
        pass

    if getattr(app, 'stations_df', None) is None or getattr(app, 'st_map', None) is None:
        return

    # Build counts map from app.st_map (normalized keys)
    counts = {}
    for k, v in (app.st_map or {}).items():
        nk = _normalize_name(k)
        # Skip hidden stations
        if _is_hidden_station(k):
            continue
        if isinstance(v, dict):
            try:
                counts[nk] = int(v.get('count', 0) or 0)
            except Exception:
                counts[nk] = 0
        else:
            try:
                counts[nk] = int(v)
            except Exception:
                counts[nk] = 0

    # Build stations DataFrame view
    stations = app.stations_df.copy()
    # Filter out hidden stations
    stations = stations[~stations['Station'].astype(str).apply(_is_hidden_station)].copy()
    stations['_station_norm'] = stations['Station'].astype(str).apply(_normalize_name)
    stations['Count'] = stations['_station_norm'].map(counts).fillna(0).astype(int)

    # Apply manual ET overrides if any
    try:
        if getattr(app, 'manual_et_override_df', None) is not None and not getattr(app.manual_et_override_df, 'empty', True):
            from piston_core.mapping import load_manual_et
            overrides = load_manual_et(app.manual_et_override_df, getattr(app, 'station_map_df', None), app.stations_df)
            if isinstance(overrides, dict):
                for st, info in overrides.items():
                    # Skip hidden stations
                    if _is_hidden_station(st):
                        continue
                    stn = _normalize_name(st)
                    mask = stations['_station_norm'] == stn
                    if mask.any():
                        try:
                            c = int(info.get('count', stations.loc[mask, 'Count'].iloc[0]))
                        except Exception:
                            c = int(stations.loc[mask, 'Count'].iloc[0])
                        stations.loc[mask, 'Count'] = c
                        # persist to app.st_map
                        matched = False
                        for k in list(app.st_map.keys()):
                            if _normalize_name(k) == stn:
                                val = app.st_map.get(k)
                                if isinstance(val, dict):
                                    app.st_map[k]['count'] = c
                                else:
                                    app.st_map[k] = {'count': c, 'uptime': 1.0}
                                matched = True
                                break
                        if not matched:
                            app.st_map[st] = {'count': c, 'uptime': 1.0}
    except Exception:
        logger.exception('Failed applying manual ET overrides')

    # Sort stations for display (do not filter out hidden stations so counts remain editable)
    try:
        stations = stations.sort_values(by='Station', key=lambda c: c.str.lower())
    except Exception:
        pass

    # Insert rows
    for _, r in stations.iterrows():
        try:
            tree.insert('', 'end', values=(str(r['Station']), int(r['Count'])))
        except Exception:
            continue

    # Ensure column layout is preserved
    try:
        tree.column("Count", stretch=False, anchor='center', width=80)
        tree.column("Station", stretch=True, anchor='w')
    except Exception:
        pass

    # Double-click editing for StationCount
    def _on_double_click(event):
        item = tree.identify_row(event.y)
        col = tree.identify_column(event.x)
        if not item or col != '#2':
            return
        bbox = tree.bbox(item, col)
        if not bbox:
            return
        x, y, width, height = bbox
        vals = tree.item(item, 'values')
        station_name = vals[0] if vals and len(vals) > 0 else ''
        try:
            cur_count = int(vals[1]) if vals and len(vals) > 1 else 0
        except Exception:
            cur_count = 0

        edit = None
        try:
            edit = tk.Spinbox(tree, from_=0, to=999, width=8)
        except Exception:
            edit = ttk.Entry(tree, width=8)
        edit.place(x=x, y=y, width=width, height=height)
        try:
            edit.delete(0, tk.END)
        except Exception:
            pass
        edit.insert(0, str(cur_count))
        edit.focus_set()

        def _commit(event=None):
            try:
                new_val = edit.get().strip()
            except Exception:
                new_val = ''
            if new_val == '':
                try:
                    edit.destroy()
                except Exception:
                    pass
                return
            try:
                new_count = int(float(new_val))
            except Exception:
                new_count = cur_count

            # update view
            try:
                tree.item(item, values=(station_name, new_count))
            except Exception:
                pass

            # persist to app.st_map (case-insensitive match)
            try:
                matched = False
                for k in list(app.st_map.keys()):
                    if _normalize_name(k) == _normalize_name(station_name):
                        v = app.st_map.get(k)
                        if isinstance(v, dict):
                            app.st_map[k]['count'] = int(new_count)
                        else:
                            app.st_map[k] = {'count': int(new_count), 'uptime': 1.0}
                        matched = True
                        break
                if not matched:
                    app.st_map[station_name] = {'count': int(new_count), 'uptime': 1.0}
            except Exception:
                logger.exception('Failed persisting to app.st_map')

            # persist to stations_df if present
            try:
                if isinstance(app.stations_df, pd.DataFrame) and not app.stations_df.empty:
                    found = False
                    for i, row in app.stations_df.iterrows():
                        if _normalize_name(row.get('Station', '')) == _normalize_name(station_name):
                            if 'StationCount' in app.stations_df.columns:
                                app.stations_df.at[i, 'StationCount'] = int(new_count)
                            else:
                                app.stations_df.at[i, 'Count'] = int(new_count)
                            found = True
                            break
                    if not found:
                        try:
                            app.stations_df = pd.concat([app.stations_df, pd.DataFrame([{'Station': station_name, 'StationCount': int(new_count)}])], ignore_index=True)
                        except Exception:
                            pass
            except Exception:
                logger.exception('Failed persisting to stations_df')

            try:
                edit.destroy()
            except Exception:
                pass

            # refresh UI
            try:
                if hasattr(app, 'refresh_tables'):
                    app.refresh_tables()
            except Exception:
                pass

        edit.bind('<Return>', _commit)
        edit.bind('<FocusOut>', _commit)

    # bind once
    try:
        tree.unbind('<Double-1>')
    except Exception:
        pass
    tree.bind('<Double-1>', _on_double_click)
