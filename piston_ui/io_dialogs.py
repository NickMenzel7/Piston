import os
import subprocess
import sys
import logging
from tkinter import filedialog, messagebox
from piston_core.io import load_model
import pandas as pd

logger = logging.getLogger('piston')


def open_template(app):
    """Open the bundled planning template workbook using platform defaults.
    `app` is the PlannerApp instance (used for any UI feedback).
    """
    template_path = os.path.abspath('planning_template_from_plan_v3.xlsx')
    if not os.path.exists(template_path):
        messagebox.showerror("Missing", "Template not found in current folder.")
        return
    try:
        os.startfile(template_path)
    except AttributeError:
        if sys.platform == 'darwin':
            subprocess.call(['open', template_path])
        else:
            subprocess.call(['xdg-open', template_path])
    except Exception as ex:
        logger.exception("Failed opening template")
        messagebox.showerror("Error", f"Failed opening template: {ex}")


def load_excel(app):
    """Show file picker and load selected planning model into `app` state.
    Mirrors previous logic from Piston.load_excel.
    """
    path = filedialog.askopenfilename(title='Select planning Excel', filetypes=[('Excel', '*.xlsx')])
    if not path:
        return
    try:
        stations, tests, st_map, station_map, plan_schema, non_test = load_model(path)
    except Exception as e:
        messagebox.showerror("Load error", str(e))
        return

    app.model_path = path
    app.stations_df = stations
    app.tests_df = tests
    app.station_map_df = station_map
    app.plan_schema_df = plan_schema
    app.non_test_df = non_test
    app.st_map = st_map

    try:
        app.path_label.configure(text=path)
    except Exception:
        pass

    # Keep UI project/scenario blank until user imports a plan
    try:
        app.project_var.set('')
        app.scenario_var.set('')
    except Exception:
        pass

    # Ensure tests view is suppressed until an import occurs
    app.filtered_tests_df = None
    try:
        app.refresh_tables()
    except Exception:
        pass
