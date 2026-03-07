import json, re, sys
from pprint import pprint

PLAN='plan.json'
try:
    p=json.load(open(PLAN))
except Exception as e:
    print('failed loading plan.json:', e); sys.exit(1)

tests_info=p.get('tests_info',{})
st_map=p.get('st_map',{})

def norm(s):
    try:
        return re.sub(r'[^0-9a-z]','', str(s).strip().casefold())
    except Exception:
        return ''

zero_time=[]
miss_map=[]
per_unit_minutes=0.0
for tid, info in sorted(tests_info.items(), key=lambda x: str(x[0])):
    tm = info.get('time_min')
    st = info.get('station')
    try:
        per_unit_minutes += float(tm or 0.0)
    except Exception:
        pass
    # find mapped station key
    mk=None
    for k in st_map.keys():
        if norm(k)==norm(st):
            mk=k; break
    if tm is None or (isinstance(tm,(int,float)) and tm==0):
        zero_time.append((tid, st, tm, mk))
    if st and mk is None:
        miss_map.append((tid, st))

print('per_unit_minutes=', per_unit_minutes, ' per_unit_hours=', per_unit_minutes/60.0)
print('\nTests with missing/zero time (showing up to 200):')
for r in zero_time[:200]:
    print(' ',r)
print('\nTests with station not found in st_map (showing up to 200):')
for r in miss_map[:200]:
    print(' ',r)

print('\nSample tests_info entries (5):')
cnt=0
for tid,info in tests_info.items():
    print(tid, info)
    cnt+=1
    if cnt>=5: break
