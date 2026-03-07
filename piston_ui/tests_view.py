import tkinter as tk
from tkinter import ttk
import pandas as pd
from typing import Tuple
import logging


logger = logging.getLogger("piston")


def create_tests_frame(parent) -> Tuple[ttk.Frame, ttk.Treeview]:
    # Use plain frame + label to avoid labelframe title background mismatch
    container = ttk.Frame(parent, style='Uniform.TFrame')
    try:
        lbl = ttk.Label(container, text='Tests (Project/DAG)', style='SectionTitle.TLabel')
        lbl.pack(anchor='w', padx=4, pady=(4,4))
    except Exception:
        pass

    # Create bordered container
    import tkinter as tk
    border_frame = tk.Frame(container, bg='#3c3c3c', relief='solid', borderwidth=1, highlightbackground='#5a5a5a', highlightthickness=1)
    border_frame.pack(fill='both', expand=True, padx=4, pady=0)

    frame = ttk.Frame(border_frame)
    frame.pack(fill='both', expand=True, padx=6, pady=6)

    cols=("Project", "TestID", "TestName", "Station", "TestTimeMin", "DependencyInfo", "Include")
    tree = ttk.Treeview(frame, columns=cols, show='headings', height=14)
    widths = {"Project":150, "TestID":90, "TestName":220, "Station":160, "TestTimeMin":110, "DependencyInfo":180, "Include":80}
    for c in cols:
        display = "Proc #" if c == "TestID" else c
        tree.heading(c, text=display)
        tree.column(c, width=widths.get(c, 100), anchor='center', stretch=True)
    tree.pack(fill='both', expand=True, padx=4, pady=4)
    return container, tree


def refresh_tests_tree(app, tree: ttk.Treeview):
    try:
        # Prefer the already-filtered DataFrame (keeps tests displayed in sync with tests_info/topo)
        if isinstance(getattr(app, 'filtered_tests_df', None), pd.DataFrame):
            df = app.filtered_tests_df
        else:
            df = app.imported_tests_df

        if df is None:
            try:
                tree.delete(*tree.get_children())
            except Exception:
                pass
            return

        proj = (app.project_var.get() or '').strip()
        # If we ended up using the unfiltered imported_tests_df, still respect project selection
        if df is app.imported_tests_df and proj and 'Project' in df.columns:
            try:
                df = df[df['Project'].fillna('').astype(str).str.strip().str.lower() == proj.lower()]
            except Exception:
                df = df[df['Project'] == proj]

        df = df.copy()
        try:
            tree.delete(*tree.get_children())
        except Exception:
            pass

        # log dataframe columns and a sample of dependency-related columns for diagnosis
        try:
            if logger.isEnabledFor(logging.DEBUG):
                try:
                    logger.debug('refresh_tests_tree: df.columns=%r', list(df.columns))
                    cols = [c for c in ('TestID','DependsOn','DependencyInfo','Comments') if c in df.columns]
                    if cols:
                        logger.debug('refresh_tests_tree: dependency columns sample:\n%s', df[cols].head(60).to_string())
                        try:
                            nonempty_depends = int(df['DependsOn'].astype(str).fillna('').str.strip().ne('').sum()) if 'DependsOn' in df.columns else 0
                        except Exception:
                            nonempty_depends = 0
                        try:
                            nonempty_depinfo = int(df['DependencyInfo'].astype(str).fillna('').str.strip().ne('').sum()) if 'DependencyInfo' in df.columns else 0
                        except Exception:
                            nonempty_depinfo = 0
                        logger.debug('refresh_tests_tree: counts - DependsOn non-empty=%d DependencyInfo non-empty=%d rows=%d', nonempty_depends, nonempty_depinfo, len(df))
                except Exception:
                    pass
        except Exception:
            pass

        # debug snapshot for troubleshooting missing dependency info
        try:
            if logger.isEnabledFor(logging.DEBUG):
                sample = df.head(8)[['TestID','DependsOn','DependencyInfo']] if 'TestID' in df.columns else df.head(8)
                logger.debug('refresh_tests_tree: sample rows:\n%s', sample.to_string())
        except Exception:
            pass

        # build a precomputed display column for dependency info to make UI behavior explicit
        try:
            dep_display = pd.Series('', index=df.index)
            try:
                if 'DependencyInfo' in df.columns:
                    dep_display = df['DependencyInfo'].astype(str).fillna('').str.strip()
                else:
                    dep_display = pd.Series([''] * len(df), index=df.index)
            except Exception:
                dep_display = pd.Series([''] * len(df), index=df.index)

            try:
                if 'DependsOn' in df.columns:
                    depends = df['DependsOn'].astype(str).fillna('').str.strip()
                else:
                    depends = pd.Series([''] * len(df), index=df.index)
            except Exception:
                depends = pd.Series([''] * len(df), index=df.index)

            try:
                use_dep_mask = dep_display.eq('') & depends.ne('')
                if use_dep_mask.any():
                    dep_display.loc[use_dep_mask] = depends.loc[use_dep_mask]
            except Exception:
                pass

            # Resolve any remaining via app.tests_info
            try:
                if getattr(app, 'tests_info', None) is not None:
                    for idx in df.index:
                        if dep_display.get(idx, '').strip():
                            continue
                        nid = f"r{idx}"
                        info = app.tests_info.get(nid)
                        if info:
                            deps = info.get('depends_on') or []
                            dep_names = []
                            for d in deps:
                                if isinstance(d, str) and d.startswith('r') and d in app.tests_info:
                                    dep_names.append(app.tests_info[d].get('testid', str(d)))
                                else:
                                    dep_names.append(str(d))
                            if dep_names:
                                dep_display.at[idx] = ", ".join([n for n in dep_names if n])
            except Exception:
                pass

            try:
                if logger.isEnabledFor(logging.DEBUG):
                    di_count = int(dep_display.astype(bool).sum())
                    depends_count = int(depends.astype(bool).sum())
                    logger.debug('refresh_tests_tree: dependency counts - DependencyInfo(non-empty)=%d DependsOn(non-empty)=%d Displayed=%d', di_count, depends_count, di_count)
            except Exception:
                pass
        except Exception:
            dep_display = pd.Series([''] * len(df), index=df.index)

        for idx, r in df.iterrows():
            include = True
            if 'Include' in r and r['Include'] in [False, 0, '0', 'False', '']:
                include = False
            # Use the precomputed dep_display (prefers DependencyInfo, falls back to DependsOn, then tests_info)
            try:
                depinfo = str(dep_display.get(idx, '') or '').strip()
            except Exception:
                depinfo = ''
            # If still empty, try resolving via tests_info
            if not depinfo:
                try:
                    if getattr(app, 'tests_info', None) is not None:
                        nid = f"r{idx}"
                        info = app.tests_info.get(nid)
                        if info:
                            deps = info.get('depends_on') or []
                            dep_names = []
                            for d in deps:
                                if isinstance(d, str) and d.startswith('r') and d in app.tests_info:
                                    dep_names.append(app.tests_info[d].get('testid', str(d)))
                                else:
                                    dep_names.append(str(d))
                            if dep_names:
                                depinfo = ", ".join([n for n in dep_names if n])
                except Exception:
                    depinfo = ''

            # additional debug for rows with no depinfo
            try:
                if logger.isEnabledFor(logging.DEBUG) and not depinfo:
                    logger.debug('refresh_tests_tree: row idx=%r TestID=%r DependencyInfo=%r DependsOn=%r resolved=%r', idx, r.get('TestID'), r.get('DependencyInfo') if 'DependencyInfo' in r else None, r.get('DependsOn') if 'DependsOn' in r else None, depinfo)
            except Exception:
                pass

            row_vals = (
                str(r.get('Project','')),
                app._format_proc_display(r.get('TestID','')),
                str(r.get('TestName','')),
                str(r.get('Station','')),
                app._format_minutes_hhmmss(r.get('TestTimeMin',0)),
                depinfo,
                "Yes" if include else "No",
            )
            tree.insert('', 'end', values=row_vals)

        for c in ["Project", "TestID", "TestName", "Station", "TestTimeMin"]:
            try:
                tree.column(c, anchor='center', stretch=True)
            except Exception:
                pass
        try:
            tree.column("DependencyInfo", stretch=True)
            tree.column("Include", width=80, anchor='center', stretch=False)
        except Exception:
            pass
    except Exception:
        try:
            app.logger.exception("Error in refresh_tests_tree")
        except Exception:
            pass
