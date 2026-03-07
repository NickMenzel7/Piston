"""
Project Management module - handles project/variant selection and data loading.

Extracted from Piston.py for better code organization.
"""
import re
import logging
import pandas as pd
from piston_core.mapping import read_plan_schema, auto_map_plan_schema, plan_to_tests_rows, read_station_map

logger = logging.getLogger("piston")


def on_project_changed(app):
    """Handle project selection changes.
    
    Picks the first variant for the selected project, maps raw plans to Tests rows
    if needed, annotates K-groups, and refreshes UI.
    
    Args:
        app: PlannerApp instance
    """
    proj = (app.project_var.get() or '').strip()
    if not proj:
        return
    
    # Sync UI comboboxes
    if hasattr(app, 'top_proj_combo'):
        app.top_proj_combo.set(proj)
    if hasattr(app, 'proj_combo'):
        app.proj_combo.set(proj)
    
    # Update variant UI for project
    update_variant_ui_for_project(app, proj)
    
    # Pick first non-empty variant for the selected project
    lst = app.project_plans.get(proj, [])
    chosen = _pick_variant(app, lst, proj, first_only=True)
    app.imported_tests_df = chosen
    
    # Annotate K-groups if present
    if isinstance(app.imported_tests_df, pd.DataFrame) and not app.imported_tests_df.empty:
        try:
            annotated, _skipped = app._annotate_k_groups_safe(app.imported_tests_df)
            app.imported_tests_df = annotated
        except Exception:
            try:
                app.imported_tests_df = app._annotate_k_groups(app.imported_tests_df)
            except Exception:
                pass
    
    # Refresh UI
    app.refresh_filters()
    app.refresh_tables()


def on_variant_changed(app):
    """Handle variant selection changes.
    
    Args:
        app: PlannerApp instance
    """
    proj = (app.project_var.get() or '').strip()
    if not proj:
        return
    
    lst = app.project_plans.get(proj, []) if app.project_plans else []
    variant = (app.plan_variant_var.get() or '').strip()
    
    # Select appropriate variant
    if variant.startswith('Variant'):
        m = re.search(r'([1-3])', variant)
        idx = int(m.group(1)) - 1 if m else 0
        chosen = lst[idx].copy() if 0 <= idx < len(lst) and lst[idx] is not None else None
    elif variant == 'Average':
        chosen = build_average_variant(app, proj, lst)
        if not isinstance(chosen, pd.DataFrame) or chosen.empty:
            # Fallback to first available variant
            chosen = next((itm.copy() for itm in lst if itm is not None), None)
    else:
        chosen = next((itm.copy() for itm in lst if itm is not None), None)
    
    # If not found, try first available
    if chosen is None and lst:
        chosen = next((itm.copy() for itm in lst if itm is not None), None)
    
    # Map to Tests rows if needed
    if isinstance(chosen, pd.DataFrame) and not chosen.empty:
        if 'TestID' not in chosen.columns and 'TestTimeMin' not in chosen.columns:
            chosen = _map_plan_to_tests(app, chosen, proj)
    
    app.imported_tests_df = chosen
    
    # Normalize TestID/DependsOn
    if isinstance(app.imported_tests_df, pd.DataFrame):
        app.imported_tests_df = normalize_testid_and_depends(app.imported_tests_df)
    
    # Refresh UI
    app.refresh_filters()
    app.refresh_tables()


def update_variant_ui_for_project(app, proj_name):
    """Update the Plan Variant combobox for a given project.
    
    Args:
        app: PlannerApp instance
        proj_name: Project name
    """
    lst = app.project_plans.get(proj_name, []) if app.project_plans else []
    variants = ['Variant 1', 'Variant 2', 'Variant 3', 'Average']
    
    app.plan_variant_combo['values'] = variants
    
    # Pick first variant that has data
    sel = 'Variant 1'
    for i in range(min(3, len(lst))):
        if lst and i < len(lst) and lst[i] is not None:
            sel = f'Variant {i+1}'
            break
    
    app.plan_variant_var.set(sel)
    app.plan_variant_combo.set(sel)


def normalize_testid_and_depends(df):
    """Normalize numeric-looking TestID and DependsOn values to plain strings.
    
    Converts values like 3.0 -> '3' and normalizes comma-separated DependsOn lists.
    
    Args:
        df: DataFrame with TestID/DependsOn columns
        
    Returns:
        Copy of df with normalized values
    """
    if not isinstance(df, pd.DataFrame):
        return df
    
    out = df.copy()
    
    def _norm_tid(val):
        if pd.isna(val):
            return ''
        s = str(val).strip()
        # Convert floats like '3.0' to '3'
        if re.match(r'^\d+(?:\.0+)?$', s):
            return str(int(float(s)))
        return s
    
    def _norm_dep(val):
        if pd.isna(val):
            return ''
        s = str(val).strip()
        if not s:
            return ''
        parts = [p.strip() for p in s.split(',') if p.strip()]
        normed = []
        for p in parts:
            if re.match(r'^\d+(?:\.0+)?$', p):
                normed.append(str(int(float(p))))
            else:
                normed.append(p)
        return ','.join(normed)
    
    if 'TestID' in out.columns:
        out['TestID'] = out['TestID'].apply(_norm_tid)
    if 'DependsOn' in out.columns:
        out['DependsOn'] = out['DependsOn'].apply(_norm_dep)
    
    # Log sample for debugging
    if logger.isEnabledFor(logging.DEBUG):
        cols = [c for c in ('TestID', 'DependsOn', 'DependencyInfo') if c in out.columns]
        if cols:
            logger.debug("normalize: sample after normalization:\n%s", out[cols].head(20).to_string())
    
    return out


def build_average_variant(app, proj_name, variants):
    """Build an averaged Tests DataFrame from up to three variants.
    
    Strategy:
    - Map raw plans to Tests rows if necessary
    - Compute total test minutes for each variant
    - Scale first variant by (average_total / base_total)
    
    Args:
        app: PlannerApp instance
        proj_name: Project name
        variants: List of variant DataFrames
        
    Returns:
        Averaged DataFrame or None
    """
    if not variants:
        return None
    
    # Map variants to Tests rows
    mapped_variants = [_map_variant_to_tests(app, v, proj_name) for v in variants[:3]]
    
    # Compute totals for each variant
    totals = []
    for mv in mapped_variants:
        if mv is not None:
            total = _compute_variant_total(app, mv)
            if total > 0:
                totals.append(total)
    
    if not totals:
        return None
    
    avg_total = sum(totals) / len(totals)
    
    # Pick first non-empty as base
    base = next((mv.copy() for mv in mapped_variants if isinstance(mv, pd.DataFrame) and not mv.empty), None)
    if base is None:
        return None
    
    # Scale base to match average
    base_total = _compute_variant_total(app, base)
    if base_total <= 0:
        return base
    
    multiplier = avg_total / base_total
    if abs(multiplier - 1.0) < 1e-9:
        return base
    
    # Apply multiplier to TestTimeMin
    return _scale_variant_times(app, base, multiplier)


def _pick_variant(app, lst, proj, first_only=False):
    """Pick and map a variant from list.
    
    Args:
        app: PlannerApp instance
        lst: List of variant DataFrames
        proj: Project name
        first_only: If True, only pick first non-empty variant
        
    Returns:
        Mapped DataFrame or None
    """
    chosen = None
    for itm in lst:
        if itm is not None:
            chosen = itm.copy()
            break
    
    if chosen is None:
        return None
    
    # Map to Tests rows if needed
    if isinstance(chosen, pd.DataFrame) and not chosen.empty:
        if 'TestID' not in chosen.columns and 'TestTimeMin' not in chosen.columns:
            chosen = _map_plan_to_tests(app, chosen, proj)
    
    return chosen


def _map_plan_to_tests(app, df, proj_name):
    """Map a raw plan DataFrame to Tests rows.
    
    Args:
        app: PlannerApp instance
        df: Raw plan DataFrame
        proj_name: Project name
        
    Returns:
        Mapped DataFrame or original df if mapping fails
    """
    try:
        # Get plan schema
        plan_schema_map = {}
        if getattr(app, 'plan_schema_df', None) is not None:
            plan_schema_map = read_plan_schema(app.plan_schema_df)
        
        # Auto-map headers
        mapped, warnings = auto_map_plan_schema(df, plan_schema_map)
        
        # Get station rules
        station_rules = []
        if getattr(app, 'station_map_df', None) is not None:
            station_rules = read_station_map(app.station_map_df)
        
        # Convert to Tests rows
        out_df, issues = plan_to_tests_rows(
            df, mapped, station_rules,
            app.stations_df if app.stations_df is not None else pd.DataFrame(),
            project_override=proj_name,
            scenario_override=None,
            sheet_name=None
        )
        return out_df
        
    except Exception:
        logger.exception("Failed mapping plan to tests rows")
        return df


def _map_variant_to_tests(app, variant, proj_name):
    """Map a variant to Tests rows (used by average calculation).
    
    Args:
        app: PlannerApp instance
        variant: Variant DataFrame or None
        proj_name: Project name
        
    Returns:
        Mapped DataFrame or None
    """
    if variant is None:
        return None
    
    df = variant.copy()
    
    # Already Tests rows?
    if 'TestID' in df.columns or 'TestTimeMin' in df.columns:
        return df
    
    # Map it
    return _map_plan_to_tests(app, df, proj_name)


def _compute_variant_total(app, variant_df):
    """Compute total test minutes for a variant DataFrame.
    
    Args:
        app: PlannerApp instance
        variant_df: DataFrame with test times
        
    Returns:
        Total minutes (float)
    """
    if not isinstance(variant_df, pd.DataFrame):
        return 0.0
    
    total = 0.0
    
    # Try TestTimeMin column
    if 'TestTimeMin' in variant_df.columns:
        for v in variant_df['TestTimeMin']:
            try:
                total += float(v)
            except (ValueError, TypeError):
                try:
                    total += float(app._parse_time_to_minutes(v))
                except Exception:
                    pass
        return total
    
    # Fallback: try other time columns
    for col in ('TestTimeSec', 'TestTime', 'Time'):
        if col in variant_df.columns:
            for v in variant_df[col]:
                try:
                    total += float(v)
                except (ValueError, TypeError):
                    try:
                        total += float(app._parse_time_to_minutes(v))
                    except Exception:
                        pass
            break
    
    return total


def _scale_variant_times(app, base_df, multiplier):
    """Scale TestTimeMin in a variant by a multiplier.
    
    Args:
        app: PlannerApp instance
        base_df: Base variant DataFrame
        multiplier: Scale factor
        
    Returns:
        DataFrame with scaled times
    """
    if 'TestTimeMin' in base_df.columns:
        new_times = []
        for v in base_df['TestTimeMin']:
            try:
                minutes = float(v)
            except (ValueError, TypeError):
                try:
                    minutes = float(app._parse_time_to_minutes(v))
                except Exception:
                    minutes = 0.0
            new_times.append(minutes * multiplier)
        base_df['TestTimeMin'] = new_times
    else:
        # Create TestTimeMin from other columns
        parsed = []
        for idx, row in base_df.iterrows():
            val = None
            for col in ('TestTimeSec', 'TestTime', 'Time'):
                if col in base_df.columns:
                    val = row.get(col)
                    break
            try:
                minutes = float(val)
            except (ValueError, TypeError):
                try:
                    minutes = float(app._parse_time_to_minutes(val))
                except Exception:
                    minutes = 0.0
            parsed.append(minutes * multiplier)
        base_df['TestTimeMin'] = parsed
    
    return base_df
