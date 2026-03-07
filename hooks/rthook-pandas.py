# runtime hook to ensure pandas native extensions included on some platforms
try:
    import pandas as _pd
    # force reference to some extension modules
    _ = _pd._libs.tslibs.timedeltas
    _ = _pd._libs.tslibs.timestamps
except Exception:
    pass
