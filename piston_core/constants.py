"""
Centralized constants for Piston application.

This module provides a single source of truth for application-wide constants,
particularly for hidden stations (organizational markers that should not appear
in UI or affect calculations).
"""

# Hidden stations: these are organizational markers, not actual test stations
# They should not appear in UI or affect calculations
HIDDEN_STATIONS = {
    'Racer Channel',
    'VXG Channel',
    'Transfer EI (YS loading)',
    'Transfer El (YS loading)',  # Case variation (El vs EI)
    'YS Loading Gate',
    'YS loading gate',  # Case variation
}


def get_hidden_stations():
    """Get the set of hidden station names.
    
    Returns:
        set: Set of station names that should be hidden from UI and calculations
    """
    return HIDDEN_STATIONS.copy()


def get_hidden_stations_normalized():
    """Get hidden stations as lowercase normalized set for case-insensitive matching.
    
    Returns:
        set: Set of lowercase hidden station names
    """
    return {str(s).strip().lower() for s in HIDDEN_STATIONS}


def is_hidden_station(station_name, case_sensitive=False):
    """Check if a station should be hidden from UI and calculations.
    
    Args:
        station_name: Station name to check
        case_sensitive: If True, use exact case matching (default: False)
        
    Returns:
        bool: True if station should be hidden
    """
    if not station_name or (hasattr(station_name, '__len__') and len(str(station_name).strip()) == 0):
        return True
    
    try:
        import pandas as pd
        if pd.isna(station_name):
            return True
    except Exception:
        pass
    
    name = str(station_name).strip()
    
    if case_sensitive:
        return name in HIDDEN_STATIONS
    else:
        return name.lower() in get_hidden_stations_normalized()
