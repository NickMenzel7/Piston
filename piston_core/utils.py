import re
from typing import List, Union

def format_minutes_hhmmss(minutes: float) -> str:
    try:
        if minutes is None:
            total_sec = 0
        else:
            total_sec = int(round(float(minutes) * 60.0))
    except Exception:
        total_sec = 0
    hours = total_sec // 3600
    rem = total_sec % 3600
    mins = rem // 60
    secs = rem % 60
    if secs >= 60:
        secs -= 60
        mins += 1
    if mins >= 60:
        mins -= 60
        hours += 1
    return f"{hours:02}:{mins:02}:{secs:02}"

def format_hours_hhmmss(hours: float) -> str:
    try:
        if hours is None:
            return "00:00:00"
        minutes = float(hours) * 60.0
    except Exception:
        return "00:00:00"
    return format_minutes_hhmmss(minutes)

def format_proc_display(tid_raw) -> str:
    try:
        s = str(tid_raw).strip()
        f = float(s)
        if abs(f - round(f)) < 1e-9:
            return str(int(round(f)))
        return s
    except Exception:
        return str(tid_raw)

def parse_channels_spec(spec: str, n_units: int = None) -> Union[int, List[int]]:
    s = '' if spec is None else str(spec).strip()
    if s == '':
        return 1
    try:
        v = int(float(s))
        return max(1, min(4, v))
    except Exception:
        pass

    parts = [p.strip() for p in re.split(r'[,\s]+', s) if p.strip()]
    result = []
    for p in parts:
        if re.search(r'[cC][hH]', p):
            m = re.match(r'^(?P<count>\d+)\s*[x\*]\s*(?P<channels>\d+)\s*[cC][hH]$', p)
            if not m:
                raise ValueError(f"Unrecognized channels token '{p}' (expected e.g. '2x1Ch')")
            cnt = max(0, int(m.group('count')))
            ch = max(1, min(4, int(m.group('channels'))))
            result.extend([ch] * cnt)
            continue

        m2 = re.match(r'^(?P<channels>\d+)\s*[x\*]\s*(?P<count>\d+)$', p)
        if m2:
            ch = max(1, min(4, int(m2.group('channels'))))
            cnt = max(0, int(m2.group('count')))
            result.extend([ch] * cnt)
            continue

        if re.match(r'^\d+$', p):
            ch = max(1, min(4, int(p)))
            result.append(ch)
            continue

        raise ValueError(f"Unrecognized channels token '{p}' (expected formats: '2', '2x5', '2x1Ch', '2,2,4,4')")

    if not result:
        raise ValueError("No channels extracted from specification.")

    if n_units is not None:
        if len(result) < n_units:
            pad = result[-1] if result else 1
            result.extend([pad] * (n_units - len(result)))
        elif len(result) > n_units:
            result = result[:n_units]

    uniq = sorted(set(result))
    if len(uniq) == 1:
        return uniq[0]
    return result

def parse_time_to_minutes(raw) -> float:
    try:
        if raw is None:
            return 0.0
        # pandas NA handled by caller usually; be defensive
        try:
            import pandas as _pd
            if _pd.isna(raw):
                return 0.0
        except Exception:
            pass

        if isinstance(raw, (int, float)):
            return float(raw)

        s = str(raw).strip()
        if s == '':
            return 0.0
        try:
            return float(s)
        except Exception:
            pass

        if ':' in s:
            parts = [p.strip() for p in s.split(':') if p.strip() != '']
            try:
                nums = [float(p) for p in parts]
            except Exception:
                return 0.0
            if len(nums) == 3:
                h, m, sec = nums
            elif len(nums) == 2:
                h = 0.0
                m, sec = nums
            else:
                nums = nums[-3:]
                if len(nums) == 3:
                    h, m, sec = nums
                else:
                    return 0.0
            return float(h) * 60.0 + float(m) + float(sec) / 60.0

        matches = re.findall(r'(\d+(?:\.\d*)?)\s*([hms])', s, flags=re.I)
        if matches:
            total_min = 0.0
            for num_str, unit in matches:
                try:
                    val = float(num_str)
                except Exception:
                    val = 0.0
                u = unit.lower()
                if u == 'h':
                    total_min += val * 60.0
                elif u == 'm':
                    total_min += val
                elif u == 's':
                    total_min += val / 60.0
            return total_min

        return 0.0
    except Exception:
        return 0.0