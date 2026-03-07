import pandas as pd
from typing import Tuple, List
from piston_core.io import _extract_k_groups_from_comments
from piston_core.scheduler import build_dag

def _format_group_labels(gid: str):
    clean_gid = str(gid).strip()
    parent_label = f"K ({clean_gid} Parent)"
    child_label = f"K ({clean_gid} Child)"
    member_label = f"K ({clean_gid})"
    return parent_label, child_label, member_label

def annotate_k_groups(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if 'DependencyInfo' not in out.columns:
        out['DependencyInfo'] = ''
    if 'DependsOn' not in out.columns:
        out['DependsOn'] = ''

    if 'Comments' not in out.columns:
        return out

    comments = out['Comments'].fillna('').astype(str)
    group_map = _extract_k_groups_from_comments(comments)

    for gid, entries in group_map.items():
        if len(entries) < 2:
            continue
        parent_idx = None
        for idx, role in entries:
            if role == 'parent':
                tid = out.at[idx, 'TestID'] if idx in out.index else ''
                if isinstance(tid, str) and tid.strip():
                    parent_idx = idx
                    break
        if parent_idx is None:
            for idx, _ in entries:
                tid = out.at[idx, 'TestID'] if idx in out.index else ''
                if isinstance(tid, str) and tid.strip():
                    parent_idx = idx
                    break
        if parent_idx is None:
            continue
        parent_tid = str(out.at[parent_idx, 'TestID']).strip()

        parent_label, child_label, member_label = _format_group_labels(gid)

        if parent_idx in out.index:
            out.at[parent_idx, 'DependencyInfo'] = parent_label
        for idx, role in entries:
            if idx == parent_idx:
                continue
            if idx not in out.index:
                continue
            existing = str(out.at[idx, 'DependsOn'] or '').strip()
            deps = [d.strip() for d in existing.split(',') if d.strip()] if existing else []
            if parent_tid and parent_tid not in deps:
                deps.append(parent_tid)
                out.at[idx, 'DependsOn'] = ','.join(deps)
            if role == 'parent':
                out.at[idx, 'DependencyInfo'] = parent_label
            elif role == 'child':
                out.at[idx, 'DependencyInfo'] = child_label
            else:
                out.at[idx, 'DependencyInfo'] = member_label
    return out

def annotate_k_groups_safe(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[tuple]]:
    out = df.copy()
    if 'DependencyInfo' not in out.columns:
        out['DependencyInfo'] = ''
    if 'DependsOn' not in out.columns:
        out['DependsOn'] = ''

    skipped = []
    if 'Comments' not in out.columns:
        return out, skipped

    comments = out['Comments'].fillna('').astype(str)
    group_map = _extract_k_groups_from_comments(comments)

    for gid, entries in group_map.items():
        if len(entries) < 2:
            continue
        parent_idx = None
        for idx, role in entries:
            if role == 'parent':
                tid = out.at[idx, 'TestID'] if idx in out.index else ''
                if isinstance(tid, str) and tid.strip():
                    parent_idx = idx
                    break
        if parent_idx is None:
            for idx, _ in entries:
                tid = out.at[idx, 'TestID'] if idx in out.index else ''
                if isinstance(tid, str) and tid.strip():
                    parent_idx = idx
                    break
        if parent_idx is None:
            continue

        parent_tid = str(out.at[parent_idx, 'TestID']).strip()

        parent_label, child_label, member_label = _format_group_labels(gid)

        if parent_idx in out.index:
            out.at[parent_idx, 'DependencyInfo'] = parent_label

        for idx, role in entries:
            if idx == parent_idx:
                continue
            if idx not in out.index:
                continue
            existing = str(out.at[idx, 'DependsOn'] or '').strip()
            deps = [d.strip() for d in existing.split(',') if d.strip()] if existing else []

            if parent_tid and parent_tid not in deps:
                temp = out.copy()
                temp.at[idx, 'DependsOn'] = ','.join(deps + [parent_tid])
                try:
                    build_dag(temp)
                    out.at[idx, 'DependsOn'] = ','.join(deps + [parent_tid])
                except ValueError:
                    child_tid = str(out.at[idx, 'TestID']) if idx in out.index else ''
                    skipped.append((gid, parent_tid, child_tid))
            if role == 'parent':
                out.at[idx, 'DependencyInfo'] = parent_label
            elif role == 'child':
                out.at[idx, 'DependencyInfo'] = child_label
            else:
                out.at[idx, 'DependencyInfo'] = member_label

    return out, skipped