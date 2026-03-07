"""Smoke tests for high-level UI plumbing.

These tests avoid instantiating the full Tk application (which requires a display)
and instead verify the `PlannerApp` class exposes the expected public methods that
other parts of the code call at startup. This helps catch accidental regressions
where methods were removed or renamed.
"""

import importlib
import inspect


def test_plannerapp_has_expected_methods():
    mod = importlib.import_module('Piston')
    assert hasattr(mod, 'PlannerApp'), 'PlannerApp class missing from Piston module'
    cls = getattr(mod, 'PlannerApp')

    required = [
        'refresh_tables',
        'refresh_filters',
        '_build_widgets',
        '_load_default_model',
        'import_test_plan',
        'calculate',
        '_on_project_changed',
        '_on_variant_changed',
    ]

    missing = []
    for name in required:
        if not hasattr(cls, name) or not inspect.isfunction(getattr(cls, name)):
            missing.append(name)
    assert not missing, f"PlannerApp is missing required methods: {missing}"


def test_manual_et_allocator_exported():
    # ensure the manual ET helper is importable and callable
    mod = importlib.import_module('piston_ui.manual_et')
    assert hasattr(mod, 'open_manual_et_allocator') and callable(mod.open_manual_et_allocator)
