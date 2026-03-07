import json, re
with open('plan.json','r',encoding='utf-8') as f:
    plan=json.load(f)

st_map=plan['st_map']
tests_info=plan['tests_info']

# normalization copied from scheduler
def _norm(s):
    try:
        return re.sub(r'[^0-9a-z]','',str(s).strip().casefold())
    except Exception:
        try:
            return re.sub(r'[^0-9a-z]','',str(s).strip().lower())
        except Exception:
            return ''

st_map_norm = { _norm(k): k for k in st_map.keys() }

stations_in_tests = set()
for tid, info in tests_info.items():
    st = info.get('station')
    if st and str(st).strip():
        stations_in_tests.add(st)

print('stations_in_tests sample:', list(stations_in_tests)[:10])

# Force counts to N_UNITS
N_UNITS = 10
for k in list(st_map.keys()):
    st_map[k]['count'] = N_UNITS

# function to find key
trailing_1e_re = re.compile(r'^(.*?)(?:\s+1e[0-9a-zA-Z]+)$', re.IGNORECASE)

def _find_st_map_key_for(sname):
    mk = st_map_norm.get(_norm(sname))
    if mk is not None:
        return mk
    m = trailing_1e_re.match(str(sname).strip())
    if m:
        base = m.group(1)
        mk2 = st_map_norm.get(_norm(base))
        if mk2 is not None:
            return mk2
    return None

missing=[]
for s in stations_in_tests:
    mk = _find_st_map_key_for(s)
    if mk is None:
        missing.append(s)

print('missing matches:', missing)

low_counts=[]
for s in stations_in_tests:
    mk=_find_st_map_key_for(s)
    if mk is None:
        continue
    val = st_map.get(mk,{}).get('count',0)
    try:
        parsed=int(val)
    except Exception:
        try:
            parsed=int(float(val))
        except Exception:
            parsed=0
    if parsed < N_UNITS:
        low_counts.append((mk,parsed))

print('low_counts:', low_counts)

fully_dedicated = all(_find_st_map_key_for(s) is not None and int(st_map[_find_st_map_key_for(s)]['count']) >= N_UNITS for s in stations_in_tests) if stations_in_tests else False
print('fully_dedicated inferred:', fully_dedicated)
print('st_map_norm keys:', list(st_map_norm.keys())[:20])
