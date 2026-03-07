"""
Filters module - handles data filtering and UI refresh.

Extracted from Piston.py for better code organization.
"""
import logging
import pandas as pd
from piston_core.scheduler import build_dag
from piston_core.io import _extract_k_groups_from_comments
from piston_ui.validation_helper import build_tests_info
from piston_ui.stations_view import refresh_stations_tree
from piston_ui.tests_view import refresh_tests_tree

logger = logging.getLogger("piston")


def refresh_filters(app):
    """Apply UI filters and build filtered_tests_df/tests_info.
    
    Args:
        app: PlannerApp instance
    """
    # Ensure we have imported_tests_df
    if not isinstance(getattr(app, 'imported_tests_df', None), pd.DataFrame):
        app.filtered_tests_df = None
        app.tests_info = None
        app.topo = None
        return
    
    proj = (app.project_var.get() or '').strip()
    df = app.imported_tests_df.copy()
    
    # Apply project filter
    if proj and 'Project' in df.columns:
        df = df[df['Project'].fillna('').astype(str).str.strip().str.lower() == proj.lower()]
    
    # Apply Include filter if enabled
    if getattr(app, 'use_include_var', None) and app.use_include_var.get() and 'Include' in df.columns:
        df = df[df['Include'].astype(str).apply(lambda v: str(v).strip().lower() not in ('false', '0'))]
    
    app.filtered_tests_df = df
    
    # Annotate K-groups if missing
    _annotate_if_missing(app, df, proj)
    
    # Ensure DependencyInfo fallback from DependsOn
    _ensure_dependency_info(app)
    
    # Normalize TestID/DependsOn
    _normalize_imported_tests(app, proj)
    
    # Build DAG and tests_info
    _build_dag_and_tests_info(app, df, proj)


def refresh_tables(app):
    """Refresh stations and tests treeviews and update status.
    
    Args:
        app: PlannerApp instance
    """
    # Refresh stations view
    if hasattr(app, 'st_tree') and getattr(app, 'st_tree') is not None:
        refresh_stations_tree(app, app.st_tree)
    
    # Refresh tests view
    if hasattr(app, 'tests_tree') and getattr(app, 'tests_tree') is not None:
        refresh_tests_tree(app, app.tests_tree)
    
    # Update status
    _update_status_counts(app)


def _annotate_if_missing(app, df, proj):
    """Annotate K-groups if DependencyInfo is missing."""
    if 'Comments' not in getattr(app, 'imported_tests_df', pd.DataFrame()).columns:
        return
    
    # Check if DependencyInfo is present
    no_depinfo = True
    if 'DependencyInfo' in df.columns:
        if df['DependencyInfo'].astype(str).fillna('').str.strip().str.len().gt(0).any():
            no_depinfo = False
    
    if not no_depinfo:
        return
    
    # Annotate
    try:
        annotated, _skipped = app._annotate_k_groups_safe(app.imported_tests_df)
        if annotated is not None and 'DependencyInfo' in annotated.columns:
            if annotated['DependencyInfo'].astype(str).fillna('').str.strip().str.len().gt(0).any():
                app.imported_tests_df = annotated
                
                # Log for debugging
                if logger.isEnabledFor(logging.DEBUG):
                    cols = [c for c in ('TestID','DependsOn','DependencyInfo','Comments') if c in annotated.columns]
                    if cols:
                        logger.debug('annotated (refresh_filters) sample:\n%s', annotated[cols].head(40).to_string())
                
                # Log group_map
                if 'Comments' in annotated.columns:
                    comments_series = annotated['Comments'].fillna('').astype(str)
                    gm = _extract_k_groups_from_comments(pd.Series(comments_series.values, index=annotated.index))
                    logger.debug('group_map (refresh_filters): %r', gm)
                
                # Reapply project filter
                df = app.imported_tests_df.copy()
                if proj and 'Project' in df.columns:
                    df = df[df['Project'].fillna('').astype(str).str.strip().str.lower() == proj.lower()]
                app.filtered_tests_df = df
    except Exception:
        logger.exception("Failed annotating K-groups in refresh_filters")


def _ensure_dependency_info(app):
    """Ensure DependencyInfo is populated from DependsOn when blank."""
    if not isinstance(app.imported_tests_df, pd.DataFrame):
        return
    if 'DependsOn' not in app.imported_tests_df.columns:
        return
    
    if 'DependencyInfo' not in app.imported_tests_df.columns:
        app.imported_tests_df['DependencyInfo'] = ''
    
    dep = app.imported_tests_df['DependsOn'].astype(str).fillna('')
    info = app.imported_tests_df['DependencyInfo'].astype(str).fillna('')
    mask = info.str.strip().eq('') & dep.str.strip().ne('')
    
    try:
        app.imported_tests_df.loc[mask, 'DependencyInfo'] = app.imported_tests_df.loc[mask, 'DependsOn']
    except Exception:
        # Rowwise fallback
        for idx, m in enumerate(mask.tolist() if hasattr(mask, 'tolist') else mask):
            if m:
                app.imported_tests_df.at[app.imported_tests_df.index[idx], 'DependencyInfo'] = str(
                    app.imported_tests_df.at[app.imported_tests_df.index[idx], 'DependsOn']
                )


def _normalize_imported_tests(app, proj):
    """Normalize TestID/DependsOn in imported_tests_df."""
    if not isinstance(app.imported_tests_df, pd.DataFrame):
        return
    
    from piston_ui.project_mgmt import normalize_testid_and_depends
    app.imported_tests_df = normalize_testid_and_depends(app.imported_tests_df)
    
    # Rebuild filtered view from normalized data
    df = app.imported_tests_df.copy()
    if proj and 'Project' in df.columns:
        df = df[df['Project'].fillna('').astype(str).str.strip().str.lower() == proj.lower()]
    
    # Apply Include filter
    if getattr(app, 'use_include_var', None) and app.use_include_var.get() and 'Include' in df.columns:
        df = df[df['Include'].astype(str).apply(lambda v: str(v).strip().lower() not in ('false', '0'))]
    
    app.filtered_tests_df = df


def _build_dag_and_tests_info(app, df, proj):
    """Build DAG and tests_info for filtered tests.
    
    Falls back to global DAG if building on filtered rows fails.
    """
    try:
        deps, succs, topo = build_dag(df)
        app.tests_info = build_tests_info(df, deps, app._parse_time_to_minutes)
        app.topo = topo
        logger.debug("refresh_filters: project=%r rows=%d tests_info_keys=%r", 
                    proj, len(df), list(app.tests_info.keys())[:10])
    except Exception:
        # Fallback: build global DAG
        try:
            full_df = app.imported_tests_df
            gdeps, gsuccessors, gtopo = build_dag(full_df)
            rows = list(df.index)
            node_ids = [f"r{r}" for r in rows]
            node_ids_set = set(node_ids)
            
            deps_filtered = {}
            for nid in node_ids:
                provs = gdeps.get(nid, [])
                deps_filtered[nid] = [p for p in provs if p in node_ids_set]
            
            app.tests_info = build_tests_info(df, deps_filtered, app._parse_time_to_minutes)
            app.topo = [n for n in gtopo if n in node_ids]
            logger.debug("refresh_filters(fallback): project=%r rows=%d tests_info_keys=%r",
                        proj, len(df), list(app.tests_info.keys())[:10])
        except Exception:
            logger.exception('Failed building DAG for filtered tests')
            app.tests_info = None
            app.topo = None


def _update_status_counts(app):
    """Update status bar with test counts."""
    tests_count = 0
    if isinstance(getattr(app, 'imported_tests_df', None), pd.DataFrame):
        df = app.imported_tests_df
        proj = (app.project_var.get() or '').strip()
        if proj and 'Project' in df.columns:
            df = df[df['Project'].fillna('').astype(str).str.strip().str.lower() == proj.lower()]
        tests_count = len(df) if df is not None else 0
    
    if hasattr(app, 'status_var'):
        app.status_var.set(f"Tests: {tests_count}")
