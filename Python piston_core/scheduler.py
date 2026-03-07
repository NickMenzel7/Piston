def build_dag(tests_df: pd.DataFrame) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], List[str]]:
    """
    Build dependency graph for tests DataFrame with 'TestID' and 'DependsOn' columns.
    Returns (deps, succs, topo).
    This implementation preserves the first occurrence order of TestID and ignores duplicate TestID rows
    (duplicates should already be validated/handled by the caller).
    """
    raw_ids = [str(t).strip() for t in tests_df['TestID']]
    # preserve first occurrence and drop duplicates while keeping order
    seen = set()
    test_ids: List[str] = []
    for tid in raw_ids:
        if tid not in seen:
            seen.add(tid)
            test_ids.append(tid)

    id_index = {tid: i for i, tid in enumerate(test_ids)}
    deps: Dict[str, List[str]] = {tid: [] for tid in test_ids}
    succs: Dict[str, List[str]] = {tid: [] for tid in test_ids}

    for _, r in tests_df.iterrows():
        tid = str(r['TestID']).strip()
        if tid not in id_index:
            # skip duplicate/empty rows (caller should have validated these)
            continue
        dep_val = r.get('DependsOn', '')
        if pd.isna(dep_val):
            continue
        dep_str = str(dep_val).strip()
        if not dep_str:
            continue
        for dep in [d.strip() for d in dep_str.split(',') if d and d.strip() and d.strip().lower() not in ('nan', 'none')]:
            if dep not in id_index:
                raise ValueError(f"Test '{tid}' depends on unknown TestID '{dep}' in selected filters.")
            deps[tid].append(dep)
            succs[dep].append(tid)

    indeg = {tid: len(deps[tid]) for tid in test_ids}
    queue = deque([tid for tid in test_ids if indeg[tid] == 0])
    topo: List[str] = []
    while queue:
        t = queue.popleft()
        topo.append(t)
        for s in succs[t]:
            indeg[s] -= 1
            if indeg[s] == 0:
                queue.append(s)
    if len(topo) != len(test_ids):
        raise ValueError("Dependency cycle detected among Tests for selected filters.")
    return deps, succs, topo