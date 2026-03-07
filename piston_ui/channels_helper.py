from typing import Any, Callable, Optional, Union, List


def build_channels_spec(single_val: Any, dual_val: Any, quad_val: Any, freeform_spec: str = '', n_units: Optional[int] = None, parse_channels_fn: Optional[Callable] = None) -> Union[int, List[int]]:
    """Build channels specification from three per-unit counts or a free-form spec.

    Parameters:
      single_val, dual_val, quad_val: values (strings/numbers) for 1/2/4-channel unit counts
      freeform_spec: fallback free-form channels spec string
      n_units: if provided, pad or truncate the resulting list to this length
      parse_channels_fn: callable(spec, n_units) -> parsed spec (used when counts sum to zero)

    Returns either a single int (uniform channels per unit) or a list of ints.
    """
    try:
        s = int(float(single_val or 0))
    except Exception:
        s = 0
    try:
        d = int(float(dual_val or 0))
    except Exception:
        d = 0
    try:
        q = int(float(quad_val or 0))
    except Exception:
        q = 0
    s = max(0, s); d = max(0, d); q = max(0, q)
    total = s + d + q
    if total == 0:
        spec = (freeform_spec or '').strip()
        if spec == '':
            return 1
        if parse_channels_fn:
            try:
                return parse_channels_fn(spec, n_units=n_units)
            except Exception:
                return 1
        # no parser; attempt simple integer parse
        try:
            return int(spec)
        except Exception:
            return 1
    result = []
    result.extend([1] * s)
    result.extend([2] * d)
    result.extend([4] * q)
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
