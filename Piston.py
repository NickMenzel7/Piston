# -*- coding: utf-8 -*-
import re
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import os
from tkinter.scrolledtext import ScrolledText
import logging
import pathlib

# Use the extracted core modules for logic
from piston_core.scheduler import build_dag, schedule_n_units, units_completed_in_time, critical_path_hours
from piston_core.io import load_model, commit_import_to_tests, import_plan_file, _extract_k_groups_from_comments
from piston_core.mapping import (
    read_plan_schema, plan_to_tests_rows, read_station_map, auto_map_plan_schema,
    load_manual_et
)
from piston_core.validation import (
    validate_import_rows, read_non_test, apply_non_test_filter
)

# Shared helpers moved into core modules
from piston_core.utils import (
    format_minutes_hhmmss as _core_format_minutes_hhmmss,
    format_hours_hhmmss as _core_format_hours_hhmmss,
    format_proc_display as _core_format_proc_display,
    parse_channels_spec as _core_parse_channels_spec,
    parse_time_to_minutes as _core_parse_time_to_minutes
)
from piston_core.groups import (
    annotate_k_groups as _core_annotate_k_groups,
    annotate_k_groups_safe as _core_annotate_k_groups_safe
)

# import shared UI dialogs
from piston_ui.dialogs import show_dataframe_dialog
from piston_ui.stations_view import create_stations_frame, refresh_stations_tree
from piston_ui.tests_view import create_tests_frame, refresh_tests_tree
from piston_ui.manual_et import open_manual_et_allocator
from piston_ui.scheduler_helper import compute_schedule
from piston_ui.io_dialogs import open_template, load_excel
from piston_ui.validation_helper import find_invalid_tests, build_tests_info
from piston_ui.channels_helper import build_channels_spec
from piston_ui.calculate import calculate as calculate_impl
from piston_ui.project_mgmt import (
    on_project_changed as on_project_changed_impl,
    on_variant_changed as on_variant_changed_impl,
    normalize_testid_and_depends,
    build_average_variant
)
from piston_ui.filters import (
    refresh_filters as refresh_filters_impl,
    refresh_tables as refresh_tables_impl
)

# Import centralized constants
from piston_core.constants import HIDDEN_STATIONS, is_hidden_station

# single logger for the app — writes debug to file only (no console window clutter)
# Set PISTON_DEBUG_CONSOLE=1 environment variable to enable console logging for debugging
# Set PISTON_LOG_LEVEL=DEBUG environment variable to enable verbose debug logging (default: INFO)
logger = logging.getLogger("piston")
if not logger.handlers:
    # Default to INFO level for production performance (can override with PISTON_LOG_LEVEL env var)
    log_level_str = os.environ.get('PISTON_LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logger.setLevel(log_level)

    log_path = pathlib.Path(__file__).resolve().with_name("piston_debug.log")
    fh = logging.FileHandler(str(log_path), mode="a", encoding="utf-8")
    fh.setLevel(log_level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Only add console handler if explicitly requested (for debugging)
    if os.environ.get('PISTON_DEBUG_CONSOLE', '').strip() in ('1', 'true', 'True', 'yes'):
        sh = logging.StreamHandler()
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

    # help the user locate the log file even when stdout isn't visible
    try:
        # best-effort write a short marker so file exists and user can inspect it
        logger.debug("piston debug log created at: %s", str(log_path))
    except Exception:
        pass

# Path to the permanently attached model workbook.
# Update this to the full path of the spreadsheet you want bundled with the app.
# Changed to None for packaged distribution (no built-in model path)
DEFAULT_MODEL_NAME = 'default_model.xlsx'

def _resolve_bundled_resource(fname: str):
    """Return an absolute path to a bundled resource if present, otherwise None.

    Checks common locations used for PyInstaller one-file extraction (`sys._MEIPASS`),
    an `embedded/` folder next to the script, and the current working directory.
    Logs each candidate path so startup logs show what was attempted.
    """
    candidates = []
    # Check PyInstaller's temporary extraction folder first
    try:
        import sys
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            candidates.append(os.path.join(meipass, 'embedded', fname))
            candidates.append(os.path.join(meipass, fname))
    except Exception:
        pass

    # Check locations next to this module
    try:
        module_dir = os.path.dirname(__file__)
        candidates.append(os.path.join(module_dir, 'embedded', fname))
        candidates.append(os.path.join(module_dir, fname))
    except Exception:
        pass

    # Check current working directory as a last resort
    try:
        cwd = os.getcwd()
        candidates.append(os.path.join(cwd, 'embedded', fname))
        candidates.append(os.path.join(cwd, fname))
    except Exception:
        pass

    # Probe candidates and log attempts
    for c in candidates:
        try:
            logger.debug("Checking bundled resource candidate: %s", c)
        except Exception:
            pass
        try:
            if c and os.path.exists(c):
                try:
                    logger.info("Bundled resource resolved: %s -> %s", fname, c)
                except Exception:
                    pass
                return c
        except Exception:
            pass

    try:
        logger.debug("Bundled resource %s not found among %d candidates", fname, len(candidates))
    except Exception:
        pass
    return None

# Default to resolved bundled model if present; otherwise None (no built-in model)
DEFAULT_MODEL_PATH = _resolve_bundled_resource(DEFAULT_MODEL_NAME)

# NOTE: Core data/io/mapping/validation logic has been moved into piston_core.
# This file now contains only the UI and wiring code. Keep the UI-only logic below


# -------------------- UI --------------------
class PlannerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        logger.debug("PlannerApp.__init__ start")
        # Window title (updated)
        self.title("Piston V1.0")
        # keep the fixed size you requested — enlarged default so Tests columns are visible on launch
        self.geometry("1400x900")   # initial size only; let user resize
        self.resizable(True, True)

        # Try to set a custom window icon from local Icon path (best-effort)
        try:
            # Use relative path from script location for portability
            icon_dir = os.path.join(os.path.dirname(__file__), 'Icon')
            chosen = None
            if os.path.isdir(icon_dir):
                # prefer .ico then common image formats
                for ext in ('.ico', '.png', '.gif', '.jpg', '.jpeg'):
                    for fn in os.listdir(icon_dir):
                        if fn.lower().endswith(ext):
                            chosen = os.path.join(icon_dir, fn)
                            break
                    if chosen:
                        break
            else:
                # Check if Icon is a file (not directory)
                if os.path.exists(icon_dir):
                    chosen = icon_dir

            if chosen:
                try:
                    if chosen.lower().endswith('.ico'):
                        try:
                            # Windows: prefer iconbitmap for .ico
                            self.iconbitmap(chosen)
                        except Exception:
                            # fallback to PhotoImage if iconbitmap fails
                            img = tk.PhotoImage(file=chosen)
                            self.iconphoto(True, img)
                            self._icon_image = img
                    else:
                        # use PhotoImage for PNG/GIF/JPEG (may require Tk with PNG support)
                        img = tk.PhotoImage(file=chosen)
                        self.iconphoto(True, img)
                        # keep a reference to avoid GC
                        self._icon_image = img
                    logger.debug("Window icon set from: %s", chosen)
                except Exception:
                    logger.exception("Failed setting window icon from %s", chosen)
            else:
                logger.debug("No icon found at icon_dir: %s", icon_dir)
        except Exception:
            logger.exception("Unexpected error while setting window icon")

        # Core model/state containers
        self.model_path = None
        self.stations_df = None
        self.tests_df = None           # model Tests sheet (kept but not displayed)
        self.imported_tests_df = None  # imported plan rows (UI + calculations source)
        self.station_map_df = None
        self.plan_schema_df = None
        self.non_test_df = pd.DataFrame()

        self.st_map = None

        # UI variables (created after root exists)
        self.project_var = tk.StringVar(value='')
        # Note: do not use StringVar.trace callbacks here (can invoke Tk internals oddly).
        # We'll bind combobox selection events in _build_widgets instead.

        self.scenario_var = tk.StringVar(value='')
        self.mode_var = tk.StringVar(value='time_for_n')
        self.n_var = tk.StringVar(value='10')
        self.t_var = tk.StringVar(value='24')
        # channels_var accepts free-form spec (kept for backwards compatibility)
        self.channels_var = tk.StringVar(value='1')

        # Include/exclude controls (kept for compatibility)
        self.use_include_var = tk.BooleanVar(value=True)
        self.exclude_non_test_var = tk.BooleanVar(value=False)

        # New explicit per-channel-unit quantity controls (defaults 0)
        self.single_var = tk.StringVar(value='0')   # single-channel units
        self.dual_var = tk.StringVar(value='0')     # dual-channel units
        self.quad_var = tk.StringVar(value='0')     # quad-channel units

        # Spins: number of full re-test spins to include per unit (0 = none)
        self.spins_var = tk.StringVar(value='0')
        # Yield percent used by calculations (0-100)
        self.yield_var = tk.StringVar(value='100')

        # Scheduling tie-breaker bias (optional float, hours). Empty = use default computed bias.
        self.unit_bias_var = tk.StringVar(value='')
        # Bias cap (percent) and window multiplier for attenuation, and serialization mode
        self.bias_max_var = tk.StringVar(value='5')   # percent (5% default)
        self.bias_window_var = tk.StringVar(value='1.0')  # multiplier of mean duration
        self.serialization_var = tk.StringVar(value='Auto')  # 'Auto'|'Strict'|'Relaxed'

        # YellowStone only filter: when checked, calculate only tests assigned to specific channel stations
        self.ys_only_var = tk.BooleanVar(value=False)

        # Derived/cached state
        self.filtered_tests_df = None
        self.tests_info = None
        self.topo = None

        # Manual ET (button-only): an ET-pattern table; presence => Active
        self.manual_et_override_df = pd.DataFrame()

        # New: control automatic commit behavior (no prompts)
        # Default to True to avoid popups unless user explicitly unchecks the option
        self.auto_commit_var = tk.BooleanVar(value=True)

        # UI status variable for refreshed counts/info (status widget created in _build_widgets)
        self.status_var = tk.StringVar(value='')
        # Human-readable bias summary shown in status bar
        self.bias_summary_var = tk.StringVar(value='')

        # store up to 3 imported plan variants per project: { project_name: [DataFrame, ...] }
        self.project_plans = {}
        self._plans_loaded = False  # Track if plans have been lazily loaded

        # Plan variant selector (Variant 1..3 or Average)
        self.plan_variant_var = tk.StringVar(value='Variant 1')
        # We'll handle variant changes via the combobox selection event in _build_widgets.

        # --- Delegate helpers to core implementations to avoid duplication ----
        # Bind instance methods to core helpers (removes duplicated code from this file)
        self._format_minutes_hhmmss = _core_format_minutes_hhmmss
        self._format_hours_hhmmss = _core_format_hours_hhmmss
        self._format_proc_display = _core_format_proc_display
        self._parse_channels_spec = _core_parse_channels_spec
        self._parse_time_to_minutes = _core_parse_time_to_minutes
        self._annotate_k_groups = _core_annotate_k_groups
        self._annotate_k_groups_safe = _core_annotate_k_groups_safe
        # --------------------------------------------------------------------

        # Defer loading embedded plans until first access for faster startup
        # Plans will be auto-loaded when project combobox is populated
        logger.info("Skipping plan load at startup (lazy load on first access)")

        logger.debug("Building widgets...")
        self._build_widgets()
        # Enforce dark styling on mixed ttk/tk widgets to avoid visual mismatches
        try:
            self._enforce_dark_theme()
        except Exception:
            logger.exception('Failed enforcing dark theme')
        logger.debug("Widgets built")

        # Attempt to load the permanently attached model workbook at startup.
        # If the default file is missing or fails to load we'll leave the UI usable
        # but without model data (the user will see an explanatory path_label).
        logger.debug("Loading default model (if present) ...")
        try:
            self._load_default_model()
            logger.debug("Default model load attempted (model_path=%r)", getattr(self, 'model_path', None))
            # If a project was pre-selected (e.g. VXG 54GHz) map it again now that the model
            # is loaded so plan -> Tests mapping can use station data. This ensures the UI
            # shows the selected plan on startup as if chosen from the dropdown.
            try:
                if getattr(self, 'project_var', None) and (self.project_var.get() or '').strip():
                    try:
                        self._on_project_changed()
                    except Exception:
                        logger.exception('_on_project_changed failed after default model load')
                try:
                    self.refresh_filters()
                except Exception:
                    logger.exception('refresh_filters failed after default model load')
                try:
                    self.refresh_tables()
                except Exception:
                    logger.exception('refresh_tables failed after default model load')
            except Exception:
                logger.exception('Post-load mapping failed')
        except Exception:
            logger.exception("_load_default_model raised")

        # write a small startup debug file so user can inspect when GUI doesn't appear
        try:
            startup_path = pathlib.Path(__file__).resolve().with_name("piston_startup_debug.txt")
            try:
                with open(startup_path, 'w', encoding='utf-8') as sf:
                    sf.write(f"log_path={log_path}\n")
                    sf.write(f"projects={sorted(list(self.project_plans.keys()))}\n")
                    sf.write(f"model_path={getattr(self, 'model_path', None)}\n")
                logger.debug("Wrote startup debug file: %s", str(startup_path))
            except Exception:
                logger.exception("Failed writing startup debug file to %s", str(startup_path))
            logger.debug("Startup debug file location: %s", str(startup_path))
        except Exception:
            logger.exception("Startup debug file creation failed")

        # Check for updates in background (non-blocking)
        try:
            import threading
            threading.Thread(target=self._check_updates_async, daemon=True).start()
            logger.debug("Update check thread started")
        except Exception:
            logger.exception("Failed starting update check thread")

    def _post_init_layout(self):
        """Optional post-initialization layout method.

        Can be overridden by subclasses to perform additional layout
        after all widgets are created and the main loop has started.
        """
        logger.debug("PlannerApp._post_init_layout start")
        # Example: self.geometry("800x600")  # set a different default size
        logger.debug("PlannerApp._post_init_layout end")

    def _enforce_dark_theme(self):
        """Apply a modern dark theme with consistent styling.

        Uses a professional dark color scheme similar to VS Code Dark+
        with good contrast and visual hierarchy.
        """
        # Modern dark theme colors (VS Code inspired with softer accents)
        bg = '#1e1e1e'          # dark background for main window
        frame_bg = '#252526'    # slightly lighter for content frames
        input_bg = '#3c3c3c'    # medium dark for input fields
        text_fg = '#d4d4d4'     # light grey text
        heading_bg = '#2d2d30'  # darker grey for headers
        button_bg = '#37373d'   # muted dark grey for buttons (softer than blue)
        button_hover = '#45454b'  # slightly lighter grey for hover
        button_accent = '#0d7fa5'  # muted teal accent (optional for primary actions)
        border = '#2d2d30'      # darker border that blends better
        selection = '#094771'   # blue for selections

        try:
            s = ttk.Style(self)
            try:
                s.theme_use('clam')  # clam theme gives us good control
            except Exception:
                try:
                    s.theme_use('default')
                except Exception:
                    pass

            # Configure main window background
            try:
                self.configure(bg=bg)
            except Exception:
                pass

            # Define uniform styles
            try:
                # Frames: consistent dark backgrounds
                s.configure('TFrame', background=frame_bg)
                s.configure('Uniform.TFrame', background=bg)

                # LabelFrames: completely flat, no border, dark background
                # Add padding to push content down so title has space
                s.configure('TLabelframe', background=bg, bordercolor=bg, 
                           darkcolor=bg, lightcolor=bg, relief='flat', borderwidth=0,
                           labelmargins=4)
                s.configure('TLabelframe.Label', background=bg, foreground=text_fg, 
                           font=('TkDefaultFont', 9, 'bold'), padding=(0, 2, 0, 4))
                s.configure('Uniform.TLabelframe', background=bg, bordercolor=bg, 
                           darkcolor=bg, lightcolor=bg, relief='flat', borderwidth=0,
                           labelmargins=4)
                s.configure('Uniform.TLabelframe.Label', background=bg, foreground=text_fg,
                           font=('TkDefaultFont', 9, 'bold'), padding=(0, 2, 0, 4))

                # Labels: dark background
                s.configure('TLabel', background=frame_bg, foreground=text_fg)
                s.configure('Uniform.TLabel', background=frame_bg, foreground=text_fg)
                # Section title labels (outside content frames)
                s.configure('SectionTitle.TLabel', background=bg, foreground=text_fg,
                           font=('TkDefaultFont', 9, 'bold'))

                # Buttons: muted dark grey with subtle hover (no harsh blue)
                s.configure('TButton', background=button_bg, foreground=text_fg, 
                           bordercolor=border, darkcolor=border, lightcolor=border,
                           relief='flat', padding=(10, 5))
                s.map('TButton', 
                      background=[('active', button_hover), ('pressed', heading_bg), ('disabled', heading_bg)],
                      foreground=[('disabled', '#707070')])

                # Checkbuttons and Radiobuttons: dark background
                s.configure('TCheckbutton', background=frame_bg, foreground=text_fg)
                s.configure('TRadiobutton', background=frame_bg, foreground=text_fg)

                # Entry fields: medium dark with subtle border
                s.configure('TEntry', fieldbackground=input_bg, background=input_bg, 
                           foreground=text_fg, bordercolor=border, 
                           darkcolor=border, lightcolor=border,
                           insertcolor=text_fg, relief='flat', borderwidth=0)

                # Combobox: medium dark with subtle styling
                s.configure('TCombobox', fieldbackground=input_bg, background=input_bg,
                           foreground=text_fg, bordercolor=border,
                           darkcolor=border, lightcolor=border,
                           arrowcolor=text_fg, relief='flat', borderwidth=0)
                s.map('TCombobox', 
                      fieldbackground=[('readonly', input_bg), ('disabled', heading_bg)],
                      foreground=[('disabled', '#808080')])

                # Treeview: medium dark with darker headers, subtle borders
                s.configure('Treeview', background=input_bg, fieldbackground=input_bg, 
                           foreground=text_fg, bordercolor=border, relief='flat', borderwidth=0)
                s.configure('Treeview.Heading', background=heading_bg, foreground=text_fg,
                           font=('TkDefaultFont', 9, 'bold'), relief='flat', borderwidth=0)
                s.map('Treeview', 
                      background=[('selected', selection)],
                      foreground=[('selected', '#ffffff')])
                s.map('Treeview.Heading', 
                      background=[('active', input_bg)])

                # Scrollbar: dark styling with no light elements
                s.configure('Vertical.TScrollbar', 
                           background=input_bg,      # scrollbar thumb color
                           troughcolor=heading_bg,   # background track color (dark)
                           bordercolor=border,
                           arrowcolor=text_fg,
                           darkcolor=input_bg,       # prevent light edges
                           lightcolor=input_bg,      # prevent light edges
                           relief='flat')
                s.configure('Horizontal.TScrollbar', 
                           background=input_bg,      # scrollbar thumb color
                           troughcolor=heading_bg,   # background track color (dark)
                           bordercolor=border,
                           arrowcolor=text_fg,
                           darkcolor=input_bg,       # prevent light edges
                           lightcolor=input_bg,      # prevent light edges
                           relief='flat')
                # Map hover states for scrollbar
                s.map('Vertical.TScrollbar',
                      background=[('active', button_hover)])
                s.map('Horizontal.TScrollbar',
                      background=[('active', button_hover)])

            except Exception:
                logger.exception('Error configuring ttk styles')
        except Exception:
            s = None

        # Apply to all plain tk widgets recursively
        def apply(w):
            try:
                wc = str(w.winfo_class()).lower()

                # Main window and frames
                if wc == 'tk':
                    try:
                        w.configure(bg=bg)
                    except Exception:
                        pass
                elif 'frame' in wc:
                    try:
                        if not isinstance(w, ttk.Widget):
                            w.configure(bg=frame_bg)
                    except Exception:
                        pass

                # Labels
                if 'label' in wc and not isinstance(w, ttk.Widget):
                    try:
                        w.configure(bg=frame_bg, fg=text_fg)
                    except Exception:
                        pass

                # Buttons
                if 'button' in wc and not isinstance(w, ttk.Widget):
                    try:
                        w.configure(bg=button_bg, fg=text_fg, relief='flat', 
                                   borderwidth=0, highlightthickness=0,
                                   activebackground=button_hover, activeforeground=text_fg)
                    except Exception:
                        pass

                # Checkbuttons and Radiobuttons
                if ('checkbutton' in wc or 'radiobutton' in wc) and not isinstance(w, ttk.Widget):
                    try:
                        w.configure(bg=frame_bg, fg=text_fg, selectcolor=input_bg,
                                   highlightthickness=0, activebackground=frame_bg,
                                   activeforeground=text_fg)
                    except Exception:
                        pass

                # Text widgets
                if isinstance(w, (tk.Text, ScrolledText)) or 'text' in wc:
                    try:
                        w.configure(bg=input_bg, fg=text_fg, insertbackground=text_fg,
                                   relief='flat', borderwidth=0, highlightthickness=0,
                                   selectbackground=selection, selectforeground='#ffffff')
                    except Exception:
                        pass

                # Entry widgets (including Spinbox)
                if ('entry' in wc or 'spinbox' in wc) and not isinstance(w, ttk.Widget):
                    try:
                        w.configure(bg=input_bg, fg=text_fg, insertbackground=text_fg,
                                   relief='flat', borderwidth=0, highlightthickness=0,
                                   selectbackground=selection, selectforeground='#ffffff')
                        # Special handling for Spinbox arrow buttons
                        if 'spinbox' in wc:
                            try:
                                w.configure(buttonbackground=button_bg,  # background of arrow buttons
                                           buttonforeground=text_fg,     # color of the arrows
                                           buttoncursor='arrow')         # cursor over buttons
                            except Exception:
                                pass
                    except Exception:
                        pass

                # Canvas widgets
                if 'canvas' in wc:
                    try:
                        w.configure(bg=frame_bg, highlightthickness=0)
                    except Exception:
                        pass

                # Scrollbars
                if 'scrollbar' in wc and not isinstance(w, ttk.Widget):
                    try:
                        w.configure(bg=heading_bg, troughcolor=bg, 
                                   highlightthickness=0, activebackground=input_bg)
                    except Exception:
                        pass

                # PanedWindow
                if 'panedwindow' in wc:
                    try:
                        w.configure(bg=bg, sashwidth=4, relief='flat', 
                                   bd=0, sashrelief='flat')
                    except Exception:
                        pass

            except Exception:
                pass

            # Recursively apply to children
            try:
                for ch in w.winfo_children():
                    apply(ch)
            except Exception:
                pass

        try:
            apply(self)
        except Exception:
            logger.exception('Error applying dark theme')

        # Global options for dropdown menus and listboxes
        try:
            self.option_add('*Listbox.background', input_bg)
            self.option_add('*Listbox.foreground', text_fg)
            self.option_add('*Listbox.selectBackground', selection)
            self.option_add('*Listbox.selectForeground', '#ffffff')
            self.option_add('*Menu.background', frame_bg)
            self.option_add('*Menu.foreground', text_fg)
            self.option_add('*Menu.activeBackground', selection)
            self.option_add('*Menu.activeForeground', '#ffffff')
        except Exception:
            pass

    # -------------------- Core logic --------------------
    def _ensure_plans_loaded(self):
        """Lazy-load embedded plans on first access for faster startup."""
        if not self._plans_loaded:
            try:
                logger.info("Lazy-loading embedded plans...")
                self._load_embedded_plans()
                logger.info("Embedded plans loaded: %d projects", len(self.project_plans))
                self._plans_loaded = True
            except Exception:
                logger.exception("Failed loading embedded plans")
                self._plans_loaded = True  # Don't retry on every access

    def _load_embedded_plans(self):
        """Discover and load plan files under embedded `plans/` and user override `~/.piston/plans`.
        Populates `self.project_plans` as { project_name: [DataFrame|None, ...] } with up to 3 variants.
        This does not attempt complex mapping; it reads CSV/XLS files and assigns project/variant
        based on parent folder or filename containing 'variantN'.
        """
        plans = {}
        # use pathlib.Path.home() for override dir
        override_dir = os.path.join(str(pathlib.Path.home()), '.piston', 'plans')
        embedded_dir = os.path.join(os.path.dirname(__file__), 'plans')

        def iter_files(root):
            for dirpath, dirnames, filenames in os.walk(root):
                for fn in filenames:
                    if fn.lower().endswith(('.csv', '.xlsx', '.xls')):
                        yield os.path.join(dirpath, fn)

        def load_file_into_map(fp, plans_map):
            try:
                fn = os.path.basename(fp)
                stem = os.path.splitext(fn)[0]
                parent = os.path.basename(os.path.dirname(fp))
                project = None
                variant_idx = None
                m = re.search(r'variant[_\-\s]*([1-3])', stem, re.IGNORECASE)
                if m:
                    try:
                        variant_idx = int(m.group(1)) - 1
                    except Exception:
                        variant_idx = None
                    # Prefer using parent folder name as project if available
                    if parent and parent.lower() not in ('plans', ''):
                        project = parent
                    else:
                        project = re.sub(r'variant[_\-\s]*[1-3]', '', stem, flags=re.IGNORECASE).strip(' _-')
                else:
                    if parent and parent.lower() not in ('plans', ''):
                        project = parent
                if not project:
                    project = stem

                # read file
                df = None
                try:
                    if fn.lower().endswith('.csv'):
                        df = pd.read_csv(fp)
                    else:
                        df = pd.read_excel(fp, sheet_name=0)
                except Exception:
                    logger.exception('Failed reading plan file %s', fp)
                    return

                if df is None or df.empty:
                    return

                # ensure Project column exists
                try:
                    if 'Project' not in df.columns:
                        df['Project'] = project
                except Exception:
                    pass

                lst = plans_map.get(project, [])
                if variant_idx is not None and 0 <= variant_idx < 3:
                    while len(lst) <= variant_idx:
                        lst.append(None)
                    lst[variant_idx] = df.copy()
                else:
                    lst.insert(0, df.copy())
                    if len(lst) > 3:
                        lst = lst[:3]
                plans_map[project] = lst
            except Exception:
                logger.exception('Error loading plan file into map: %s', fp)

        # load override then embedded
        try:
            if os.path.isdir(override_dir):
                for f in iter_files(override_dir):
                    load_file_into_map(f, plans)
        except Exception:
            logger.exception('Error scanning override plans')

        try:
            if os.path.isdir(embedded_dir):
                for f in iter_files(embedded_dir):
                    # embedded files add if not present or to fill variants
                    load_file_into_map(f, plans)
        except Exception:
            logger.exception('Error scanning embedded plans')

        self.project_plans = plans
        try:
            if hasattr(self, 'proj_combo'):
                projects = sorted(list(self.project_plans.keys())) if self.project_plans else []
                self.proj_combo['values'] = projects
        except Exception:
            pass

    def _load_default_model(self):
        logger.debug("_load_default_model")
        default_path = DEFAULT_MODEL_PATH
        if not default_path or not os.path.exists(default_path):
            try:
                self.path_label.configure(text=f"Default model not found: {default_path}")
            except Exception:
                pass
            return

        try:
            stations, tests, st_map, station_map, plan_schema, non_test = load_model(default_path)
        except Exception as e:
            logger.exception("Error loading model")
            try:
                self.path_label.configure(text=f"Failed to load default model: {default_path}")
            except Exception:
                pass
            return

        self.model_path = default_path
        self.stations_df = stations
        self.tests_df = tests
        self.station_map_df = station_map
        self.plan_schema_df = plan_schema
        self.non_test_df = non_test
        self.st_map = st_map

        try:
            self.path_label.configure(text=default_path)
        except Exception:
            pass

        # Keep UI project/scenario blank until user imports a plan
        # Do not overwrite project/scenario selection here — preserve any selection set during widget init
        try:
            # ensure scenario_var initialized if missing but don't clear existing selection
            if not (self.scenario_var.get() or '').strip():
                self.scenario_var.set('')
        except Exception:
            pass

        self.filtered_tests_df = None
        try:
            fn = getattr(self, 'refresh_tables', None)
            if callable(fn):
                fn()
        except Exception:
            pass

    def _build_widgets(self):
        """Build the main application widgets (compact but functional).
        This restores the essential controls: file/import, project/plan/scenario selectors,
        mode input, channel quantity boxes, paned preview with stations/tests, results area,
        and status bar.
        """
        try:
            # Menu bar with Tools menu (for standalone tools like Capacity Estimator)
            try:
                menubar = tk.Menu(self, bg='#252526', fg='#d4d4d4', 
                                 activebackground='#094771', activeforeground='#ffffff',
                                 relief='flat', borderwidth=0)

                # Tools menu for standalone utilities
                tools_menu = tk.Menu(menubar, tearoff=0, 
                                    bg='#252526', fg='#d4d4d4',
                                    activebackground='#094771', activeforeground='#ffffff',
                                    relief='flat', borderwidth=1)
                tools_menu.add_command(label="Capacity Estimator", 
                                      command=lambda: open_manual_et_allocator(self))
                menubar.add_cascade(label="Tools", menu=tools_menu)

                # Help menu (placeholder for future)
                help_menu = tk.Menu(menubar, tearoff=0,
                                   bg='#252526', fg='#d4d4d4',
                                   activebackground='#094771', activeforeground='#ffffff',
                                   relief='flat', borderwidth=1)
                help_menu.add_command(label="View Debug Log", command=lambda: self._show_debug_log())
                help_menu.add_command(label="Check for Updates", command=lambda: self._manual_update_check())
                help_menu.add_separator()
                help_menu.add_command(label="About Piston", command=lambda: messagebox.showinfo(
                    "About Piston", 
                    "Piston V1.0\n\nTest scheduling and capacity planning tool.\n\nSmart Mode enables automatic parallel execution."
                ))
                menubar.add_cascade(label="Help", menu=help_menu)

                self.config(menu=menubar)
            except Exception:
                logger.exception('Failed creating menu bar')

            # Compact top toolbar: project/variant selectors and action buttons
            try:
                header_outer = ttk.Frame(self, style='Uniform.TFrame')
                header_outer.pack(fill='x', padx=10, pady=6)

                # Create bordered container for the toolbar
                header_border = tk.Frame(header_outer, bg='#3c3c3c', relief='solid', borderwidth=1, highlightbackground='#5a5a5a', highlightthickness=1)
                header_border.pack(fill='x', padx=4, pady=0)

                header = ttk.Frame(header_border)
                header.pack(fill='x', padx=6, pady=6)

                # Left: Action buttons (View buttons only - Capacity Estimator moved to Tools menu)
                try:
                    toolbar = ttk.Frame(header)
                    toolbar.grid(row=0, column=0, sticky='w')
                    ttk.Button(toolbar, text="View StationMap", command=lambda: self._safe_call('view_stationmap')).pack(side='left', padx=(0,4))
                    ttk.Button(toolbar, text="View NonTestGroups", command=lambda: self._safe_call('view_nontest')).pack(side='left', padx=4)
                    try:
                        ttk.Button(toolbar, text="Inspect Dependencies", command=lambda: self._safe_call('view_dependency_debug')).pack(side='left', padx=4)
                    except Exception:
                        pass
                except Exception:
                    logger.exception('Failed creating toolbar buttons')

                # Center: Project and Variant selectors
                try:
                    sel_frame = ttk.Frame(header)
                    sel_frame.grid(row=0, column=1, sticky='w', padx=12)
                    self.top_proj_combo = ttk.Combobox(sel_frame, textvariable=self.project_var, state='readonly', width=28)
                    self.top_proj_combo.grid(row=0, column=0, padx=(0,6))
                    # Populate top project combobox from embedded plans (lazy load on first access)
                    try:
                        self._ensure_plans_loaded()  # Lazy load plans now
                        projects = sorted(list(self.project_plans.keys())) if self.project_plans else []
                        if projects:
                            self.top_proj_combo['values'] = projects
                            # auto-select preferred default project if present (prefer 'VXG 54GHz')
                            if not (self.project_var.get() or '').strip():
                                try:
                                    pref = None
                                    for p in projects:
                                        if str(p).strip().lower() == 'vxg 54ghz':
                                            pref = p
                                            break
                                    if pref is None:
                                        pref = projects[0]
                                    self.project_var.set(pref)
                                    self._on_project_changed()
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    self.plan_variant_combo = ttk.Combobox(sel_frame, textvariable=self.plan_variant_var, state='readonly', width=14)
                    self.plan_variant_combo.grid(row=0, column=1, padx=(0,6))
                    try:
                        self.plan_variant_combo['values'] = ['Variant 1', 'Variant 2', 'Variant 3', 'Average']
                    except Exception:
                        pass
                    # self.top_scenario_combo removed (scenarios not used)
                    try:
                        _proj_handler = getattr(self, '_on_project_changed')
                        _variant_handler = getattr(self, '_on_variant_changed')
                        self.top_proj_combo.bind('<<ComboboxSelected>>', lambda e, h=_proj_handler: h())
                        self.plan_variant_combo.bind('<<ComboboxSelected>>', lambda e, h=_variant_handler: h())
                        # top_scenario_combo binding removed
                    except Exception:
                        pass
                except Exception:
                    logger.exception('Failed creating header selectors')

                # Right: Calculate button and mode selector
                try:
                    # reserve right_frame in header but move controls into the status/info area below
                    right_frame = ttk.Frame(header)
                    right_frame.grid(row=0, column=2, sticky='e')
                    # controls moved to Status / Info area for improved layout
                except Exception:
                    logger.exception('Failed creating header right-side controls')

                # make middle column expand so right_frame sticks right
                header.columnconfigure(1, weight=1)

                # Remove Alt+L Load Excel accelerator since loading is automatic at startup
                try:
                    pass
                except Exception:
                    pass
            except Exception:
                logger.exception('Failed creating header')

            # Compact controls header: channel quantities | mode/inputs | actions
            try:
                controls_container = ttk.Frame(self, style='Uniform.TFrame')
                controls_container.pack(fill='x', padx=10, pady=8)
                ttk.Label(controls_container, text='Run Controls', style='SectionTitle.TLabel').pack(anchor='w', padx=4, pady=(0, 4))

                # Create bordered container for the controls
                controls_border = tk.Frame(controls_container, bg='#3c3c3c', relief='solid', borderwidth=1, highlightbackground='#5a5a5a', highlightthickness=1)
                controls_border.pack(fill='x', padx=4, pady=0)

                controls_frame = ttk.Frame(controls_border)
                controls_frame.pack(fill='x', padx=6, pady=6)

                # left: channel quantities
                ch_frame = ttk.Frame(controls_frame)
                ch_frame.grid(row=0, column=0, sticky='w', padx=(6,12))
                ttk.Label(ch_frame, text='Channel Quantities', font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w')
                ttk.Label(ch_frame, text='Single').grid(row=1, column=0, padx=6, pady=(6,2))
                ttk.Label(ch_frame, text='Dual').grid(row=1, column=1, padx=6, pady=(6,2))
                ttk.Label(ch_frame, text='Quad').grid(row=1, column=2, padx=6, pady=(6,2))
                # use Spinbox for compact constrained integer input
                try:
                    # Create spinboxes with minimal styling to ensure arrows are visible
                    # Keep configuration simple for cross-platform compatibility
                    self.single_spin = tk.Spinbox(ch_frame, from_=0, to=99, width=5, 
                                                  textvariable=self.single_var,
                                                  bg='#3c3c3c', fg='#d4d4d4',
                                                  buttonbackground='#707070',
                                                  insertbackground='#d4d4d4',
                                                  selectbackground='#094771',
                                                  selectforeground='#ffffff')
                    self.dual_spin = tk.Spinbox(ch_frame, from_=0, to=99, width=5,
                                                textvariable=self.dual_var,
                                                bg='#3c3c3c', fg='#d4d4d4',
                                                buttonbackground='#707070',
                                                insertbackground='#d4d4d4',
                                                selectbackground='#094771',
                                                selectforeground='#ffffff')
                    self.quad_spin = tk.Spinbox(ch_frame, from_=0, to=99, width=5,
                                                textvariable=self.quad_var,
                                                bg='#3c3c3c', fg='#d4d4d4',
                                                buttonbackground='#707070',
                                                insertbackground='#d4d4d4',
                                                selectbackground='#094771',
                                                selectforeground='#ffffff')
                    self.single_spin.grid(row=2, column=0, padx=6, pady=(0,6))
                    self.dual_spin.grid(row=2, column=1, padx=6, pady=(0,6))
                    self.quad_spin.grid(row=2, column=2, padx=6, pady=(0,6))
                except Exception:
                    # fallback to Entry if Spinbox unavailable
                    ttk.Entry(ch_frame, textvariable=self.single_var, width=6).grid(row=2, column=0, padx=6, pady=(0,6))
                    ttk.Entry(ch_frame, textvariable=self.dual_var, width=6).grid(row=2, column=1, padx=6, pady=(0,6))
                    ttk.Entry(ch_frame, textvariable=self.quad_var, width=6).grid(row=2, column=2, padx=6, pady=(0,6))

                # center: mode and inputs
                mid_frame = ttk.Frame(controls_frame)
                mid_frame.grid(row=0, column=1, sticky='ew', padx=6)

                # mode radios in compact form
                rb_frame = ttk.Frame(mid_frame)
                rb_frame.grid(row=0, column=0, sticky='w')
                ttk.Radiobutton(rb_frame, text='Time to finish N units', variable=self.mode_var, value='time_for_n', command=self._toggle_inputs).grid(row=0, column=0, sticky='w')
                ttk.Radiobutton(rb_frame, text='Units completed in T hours', variable=self.mode_var, value='n_for_time', command=self._toggle_inputs).grid(row=0, column=1, sticky='w', padx=(12,0))

                # inputs row
                inputs = ttk.Frame(mid_frame)
                inputs.grid(row=1, column=0, sticky='w', pady=(6,0))
                ttk.Label(inputs, text='N:').grid(row=0, column=0, padx=(0,4))
                self.n_entry = ttk.Entry(inputs, textvariable=self.n_var, width=8)
                self.n_entry.grid(row=0, column=1, padx=(0,8))
                ttk.Label(inputs, text='T (hrs):').grid(row=0, column=2, padx=(0,4))
                self.t_entry = ttk.Entry(inputs, textvariable=self.t_var, width=8)
                self.t_entry.grid(row=0, column=3, padx=(0,8))
                ttk.Label(inputs, text='Spins:').grid(row=0, column=4, padx=(0,4))
                self.spins_entry = ttk.Entry(inputs, textvariable=self.spins_var, width=6)
                self.spins_entry.grid(row=0, column=5, padx=(0,8))
                ttk.Label(inputs, text='Yield %:').grid(row=0, column=6, padx=(0,4))
                self.yield_entry = ttk.Entry(inputs, width=6)
                try:
                    # wire yield input to proper var
                    self.yield_entry.configure(textvariable=self.yield_var)
                except Exception:
                    pass
                self.yield_entry.grid(row=0, column=7, padx=(0,8))

                # Advanced controls (Unit bias, Serialization, etc.) removed - Smart Mode handles automatically
                # Set internal variables to None so code doesn't break
                self.unit_bias_entry = None
                self.bias_max_entry = None
                self.bias_window_entry = None
                self.serialization_combo = None
                self.preset_frame = None
                self.adv_btn = None

                # right: actions (Calculate button only)
                try:
                    act_frame = ttk.Frame(controls_frame)
                    act_frame.grid(row=0, column=2, sticky='e', padx=(6,12))
                    self.calc_button = ttk.Button(act_frame, text='Calculate', command=lambda: self._safe_call('calculate'), width=12)
                    self.calc_button.grid(row=0, column=0, padx=(0,8))
                    # Yellowstone-only option hidden for now; keep variable for future use
                    self.ys_check = None
                except Exception:
                    self.calc_button = None

                # details always shown (no toggle)
            except Exception:
                logger.exception('Failed building compact run controls')
            # validate controls initially and bind change handlers
            try:
                def _on_input_change(event=None):
                    try:
                        self._validate_controls()
                    except Exception:
                        pass

                def _on_enter_key(event=None):
                    """Trigger calculate when Enter is pressed in any input field."""
                    try:
                        self._safe_call('calculate')
                    except Exception:
                        pass

                # bind key events for entries
                for ent in (self.n_entry, self.t_entry, self.spins_entry, self.yield_entry):
                    try:
                        ent.bind('<KeyRelease>', _on_input_change)
                        ent.bind('<FocusOut>', _on_input_change)
                        ent.bind('<Return>', _on_enter_key)  # Trigger calculate on Enter
                    except Exception:
                        pass
                # bind spinbox changes if present
                try:
                    self.single_spin.bind('<KeyRelease>', _on_input_change)
                    self.dual_spin.bind('<KeyRelease>', _on_input_change)
                    self.quad_spin.bind('<KeyRelease>', _on_input_change)
                    # Also bind Enter key for spinboxes
                    self.single_spin.bind('<Return>', _on_enter_key)
                    self.dual_spin.bind('<Return>', _on_enter_key)
                    self.quad_spin.bind('<Return>', _on_enter_key)
                except Exception:
                    pass
                # Advanced controls removed - no bindings needed
            except Exception:
                pass

            # Top filters bar: visible project/plan/scenario controls for quick access
            # (kept minimal; detailed top filters implementation intentionally omitted to avoid UI duplication)
            # try:
            #     top_filters = ttk.Frame(self)
            #     top_filters.pack(fill='x', padx=10, pady=(0,8))
            #     # Project combobox etc. (omitted)
            # except Exception:
            #     logger.exception('Failed creating top filters bar')

            # Filters frame (removed, replaced by compact controls header)
            # filt_frame = ttk.LabelFrame(self, text="Project / Scenario / Filters")
            # filt_frame.pack(fill='x', padx=10, pady=8)
            # ttk.Label(filt_frame, text="Project:").pack(side='left', padx=5)
            #
            # # Project combobox (created earlier in __init__ as self.proj_combo if present)
            # try:
            #     self.proj_combo = getattr(self, 'proj_combo', None) or ttk.Combobox(filt_frame, textvariable=self.project_var, state='readonly', width=28)
            #     self.proj_combo.pack(side='left', padx=5)
            #     projects = sorted(list(self.project_plans.keys())) if self.project_plans : []
            #     if projects:
            #         self.proj_combo['values'] = projects
            #     # bind selection event to update scenarios/variants
            #     try:
            #         _proj_handler_2 = getattr(self, '_on_project_changed')
            #         self.proj_combo.bind('<<ComboboxSelected>>', lambda e, h=_proj_handler_2: h())
            #     except Exception:
            #         pass
            #     # Add a visible label for the plan dropdown so it's easier to find
            #     try:
            #         ttk.Label(filt_frame, text="Plan:").pack(side='left', padx=(8,2))
            #     except Exception:
            #         pass
            # except Exception:
            #     pass

            # Computed status/info area (removed per request)
            try:
                pass
            except Exception:
                logger.exception("Error building status/info area")

            # Paned window for stations/tests view
            try:
                # Use a horizontal PanedWindow and build the Stations/Tests views via shared UI helpers
                paned = tk.PanedWindow(self, orient='horizontal', sashrelief='raised', sashwidth=6)
                paned.pack(fill='both', expand=True, padx=10, pady=8)

                # Left: Stations + Right: Tests (created by UI view modules)
                try:
                    self.st_frame, self.st_tree = create_stations_frame(paned)
                    self.tests_frame, self.tests_tree = create_tests_frame(paned)
                    paned.add(self.st_frame, minsize=180)
                    paned.add(self.tests_frame, minsize=300)
                except Exception:
                    # fallback to simple frames if helpers fail
                    logger.exception('Failed creating station/tests frames via helper')
                    self.st_frame = ttk.Frame(self)
                    self.tests_frame = ttk.Frame(self)
                    paned.add(self.st_frame)
                    paned.add(self.tests_frame)

                # Bind station-tree double-click to edit handler
                try:
                    if hasattr(self, 'st_tree') and self.st_tree is not None:
                        self.st_tree.bind('<Double-1>', lambda e: self._on_station_double_click(e))
                except Exception:
                    pass

                # minimal tests tree configure binding to avoid spurious errors elsewhere
                try:
                    if hasattr(self, 'tests_tree') and self.tests_tree is not None:
                        self.tests_tree.bind('<Configure>', lambda e: None)
                except Exception:
                    pass
            except Exception:
                logger.exception("Error creating paned window for stations/tests")

            # Dedicated Calculation Results frame (ensure visible below paned window)
            try:
                # Make the results area larger and allow it to expand with the window
                results_container = ttk.Frame(self, style='Uniform.TFrame')
                results_container.pack(fill='both', expand=True, padx=10, pady=(4,8))
                ttk.Label(results_container, text='Calculation Results', style='SectionTitle.TLabel').pack(anchor='w', padx=4, pady=(0, 4))

                # Create bordered container for the results
                results_border = tk.Frame(results_container, bg='#3c3c3c', relief='solid', borderwidth=1, highlightbackground='#5a5a5a', highlightthickness=1)
                results_border.pack(fill='both', expand=True, padx=4, pady=0)

                self.results_frame = ttk.Frame(results_border)
                self.results_frame.pack(fill='both', expand=True, padx=6, pady=6)
                # If an existing results widget exists, reparent it; otherwise create a new one
                try:
                    self.result_box = ScrolledText(self.results_frame, wrap='word', height=12, font=('TkDefaultFont', 10))
                    self.result_box.pack(fill='both', expand=True)
                    self.out_text = self.result_box
                except Exception:
                    logger.exception('Failed creating calculation results box')
            except Exception:
                logger.exception('Failed creating results frame')
            # results visibility: always shown (no toggle)

            # Status bar (simplified - bias controls removed)
            try:
                status_bar = ttk.Frame(self)
                status_bar.pack(fill='x', padx=10, pady=0)

                # Model path label hidden for cleaner interface (still created for compatibility)
                self.path_label = ttk.Label(status_bar, text="No file loaded", anchor='w')
                # self.path_label.pack(side='left', padx=10)  # Hidden

                # compact calc summary on right of status bar
                try:
                    self.calc_summary_var = tk.StringVar(value='')
                    self.calc_summary_label = ttk.Label(status_bar, textvariable=self.calc_summary_var, anchor='e')
                    self.calc_summary_label.pack(side='right', padx=10)
                except Exception:
                    pass

                ttk.Button(status_bar, text="Exit", command=self.quit).pack(side='right', padx=10)
            except Exception:
                logger.exception("Error creating status bar")

            # Default focus
            try:
                # Focus on project combobox (first logical control)
                try:
                    self.proj_combo.focus_set()
                except Exception:
                    # fallback: focus the first child widget if available
                    try:
                        children = self.proj_combo.winfo_children()
                        if children:
                            children[0].focus_set()
                    except Exception:
                        pass
            except Exception:
                logger.exception("Error setting default focus")

        except Exception:
            logger.exception("Error building widgets")
        # set default project if available (after widgets created)
        try:
            self._ensure_plans_loaded()  # Ensure plans loaded before accessing
            projects = sorted(list(self.project_plans.keys())) if self.project_plans else []
            if projects and not (self.project_var.get() or '').strip():
                proj0 = projects[0]
                self.project_var.set(proj0)

                # Pick a candidate variant (first non-empty) and map to Tests rows if needed
                chosen = None
                try:
                    lst = self.project_plans.get(proj0, [])
                    if lst:
                        # prefer first non-None variant
                        for itm in lst:
                            if itm is not None:
                                candidate = itm.copy()
                                break
                        else:
                            candidate = None
                    else:
                        candidate = None

                    if candidate is not None:
                        # If candidate already looks like Tests rows, use directly
                        if isinstance(candidate, pd.DataFrame) and ('TestID' in candidate.columns or 'TestTimeMin' in candidate.columns):
                            chosen = candidate
                        else:
                            # attempt to map using PlanSchema / StationMap
                            plan_schema_map = {}
                            try:
                                if getattr(self, 'plan_schema_df', None) is not None:
                                    plan_schema_map = read_plan_schema(self.plan_schema_df)
                            except Exception:
                                plan_schema_map = {}

                            try:
                                mapped, warnings = auto_map_plan_schema(candidate, plan_schema_map)
                            except Exception:
                                mapped = plan_schema_map if plan_schema_map else {}

                            station_rules = []
                            try:
                                if getattr(self, 'station_map_df', None) is not None:
                                    station_rules = read_station_map(self.station_map_df)
                            except Exception:
                                station_rules = []

                            try:
                                out_df, issues = plan_to_tests_rows(candidate, mapped, station_rules, self.stations_df if self.stations_df is not None else pd.DataFrame(), project_override=proj0, scenario_override=None, sheet_name=None)
                                chosen = out_df
                            except Exception:
                                # fallback to raw candidate
                                chosen = candidate
                except Exception:
                    chosen = None

                self.imported_tests_df = chosen

                try:
                    # Annotate K-groups from Comments if present so DependencyInfo is visible in UI
                    if isinstance(self.imported_tests_df, pd.DataFrame):
                        try:
                            annotated, _skipped = self._annotate_k_groups_safe(self.imported_tests_df)
                            self.imported_tests_df = annotated
                            # Log annotated sample and group_map for default variant selection
                            try:
                                if logger.isEnabledFor(logging.DEBUG) and isinstance(annotated, pd.DataFrame):
                                    cols = [c for c in ('TestID','DependsOn','DependencyInfo','Comments') if c in annotated.columns]
                                    if cols:
                                        logger.debug('annotated (default-variant) sample:\n%s', annotated[cols].head(40).to_string())
                            except Exception:
                                pass
                            try:
                                if 'Comments' in annotated.columns:
                                    comments_series = annotated['Comments'].fillna('').astype(str)
                                    gm = _extract_k_groups_from_comments(pd.Series(comments_series.values, index=annotated.index))
                                    logger.debug('group_map (default-variant) from _extract_k_groups_from_comments: %r', gm)
                            except Exception:
                                pass
                        except Exception:
                            pass
                except Exception:
                    pass
                # Fallback copy: ensure DependencyInfo populated from DependsOn when blank
                try:
                    if isinstance(self.imported_tests_df, pd.DataFrame) and 'DependsOn' in self.imported_tests_df.columns:
                        if 'DependencyInfo' not in self.imported_tests_df.columns:
                            self.imported_tests_df['DependencyInfo'] = ''
                        dep = self.imported_tests_df['DependsOn'].astype(str).fillna('')
                        info = self.imported_tests_df['DependencyInfo'].astype(str).fillna('')
                        mask = info.str.strip().eq('') & dep.str.strip().ne('')
                        try:
                            self.imported_tests_df.loc[mask, 'DependencyInfo'] = self.imported_tests_df.loc[mask, 'DependsOn']
                        except Exception:
                            for idx, m in enumerate(mask.tolist() if hasattr(mask, 'tolist') else mask):
                                if m:
                                    self.imported_tests_df.at[self.imported_tests_df.index[idx], 'DependencyInfo'] = str(self.imported_tests_df.at[self.imported_tests_df.index[idx], 'DependsOn'])
                except Exception:
                    pass

                # Normalize TestID/DependsOn for the initial chosen variant so UI shows plain IDs
                try:
                    if isinstance(self.imported_tests_df, pd.DataFrame):
                        self.imported_tests_df = self._normalize_testid_and_depends(self.imported_tests_df)
                except Exception:
                    pass

                try:
                    self._on_project_changed()
                except Exception:
                    pass
                try:
                    self.refresh_filters()
                except Exception:
                    pass
        except Exception:
            logger.exception('Error setting default project')

        # Ensure views are populated at startup when embedded plans or model are present
        try:
            try:
                if hasattr(self, 'st_tree') and getattr(self, 'st_tree') is not None:
                    refresh_stations_tree(self, self.st_tree)
            except Exception:
                logger.exception('Failed refreshing stations tree at startup')
            try:
                if hasattr(self, 'tests_tree') and getattr(self, 'tests_tree') is not None:
                    refresh_tests_tree(self, self.tests_tree)
            except Exception:
                logger.exception('Failed refreshing tests tree at startup')
        except Exception:
            pass

    def _make_tree_sortable(self, tree):
        """
        Bind a few column headers to sort handlers safely.
        """
        try:
            try:
                tree.tag_configure('sort_asc', foreground='black')
                tree.tag_configure('sort_desc', foreground='black')
            except Exception:
                pass
            try:
                tree.heading("Project", command=lambda: self._sort_tree(tree, "Project", False))
            except Exception:
                pass
            try:
                tree.heading("TestID", command=lambda: self._sort_tree(tree, "TestID", True))
            except Exception:
                pass
        except Exception:
            logger.exception("Error making tree sortable")

    def _adjust_station_cols(self, event=None):
        """
        Adjust the station tree columns to keep them visible and readable during resizes.
        Reserve a stable width for the count column so it is not squeezed,
        and give the Station column the remaining space.
        """
        try:
            # ensure geometry updated
            self.update_idletasks()

            # Prefer the frame width (more stable than tree width which can include scrollbar)
            frame_width = max(200, self.st_frame.winfo_width())
            # Reserve a fixed fraction for the count column but enforce a sensible minimum
            reserved = max(80, int(frame_width * 0.18))  # prefer ~18% but at least 80px
            # Compute station column width from remaining space (leave some padding)
            col1 = max(120, frame_width - reserved - 12)
            col2 = reserved

            # Apply computed widths; keep Station stretchable, Count fixed so it remains readable
            self.st_tree.column("Station", width=col1, minwidth=140, stretch=True, anchor='w')
            self.st_tree.column("Count", width=col2, minwidth=70, stretch=False, anchor='center')

            # keep heading anchors appropriate
            try:
                self.st_tree.heading("Station", anchor='w')
                self.st_tree.heading("Count", anchor='center')
            except Exception:
                pass
        except Exception:
            pass

    def _set_station_columns_fixed(self):
        """Ensure station tree columns do not stretch (small tolerance wrapper)."""
        try:
            # keep this as a no-op to avoid conflicting with auto-resize behavior
            self.st_tree.column("Station", stretch=True)
            self.st_tree.column("Count", stretch=False)
        except Exception:
            pass

    def _toggle_inputs(self):
        try:
            if self.mode_var.get() == 'time_for_n':
                self.n_entry.configure(state='normal')
                self.t_entry.configure(state='disabled')
                try:
                    self.top_n_entry.configure(state='normal')
                except Exception:
                    pass
                try:
                    self.top_t_entry.configure(state='disabled')
                except Exception:
                    pass
            else:
                self.n_entry.configure(state='disabled')
                self.t_entry.configure(state='normal')
                try:
                    self.top_n_entry.configure(state='disabled')
                except Exception:
                    pass
                try:
                    self.top_t_entry.configure(state='normal')
                except Exception:
                    pass

            # Re-validate controls after mode change to update Calculate button state
            try:
                self._validate_controls()
            except Exception:
                pass
        except Exception:
            pass

    def _apply_preset(self, name: str):
        try:
            if name == 'none':
                self.unit_bias_var.set('')
                self.bias_max_var.set('5')
                self.bias_window_var.set('1.0')
                self.serialization_var.set('Auto')
            elif name == 'weak':
                self.unit_bias_var.set('0.01')
                self.bias_max_var.set('5')
                self.bias_window_var.set('1.0')
                self.serialization_var.set('Auto')
            elif name == 'strong':
                self.unit_bias_var.set('0.05')
                self.bias_max_var.set('10')
                self.bias_window_var.set('0.5')
                self.serialization_var.set('Auto')
            try:
                self._validate_controls()
            except Exception:
                pass
        except Exception:
            logger.exception("_apply_preset failed")

    def _toggle_advanced(self):
        try:
            visible = getattr(self, '_adv_visible', True)
            if visible:
                # hide advanced widgets
                for w in (getattr(self, 'unit_bias_label', None), getattr(self, 'unit_bias_entry', None), getattr(self, 'bias_max_label', None), getattr(self, 'bias_max_entry', None), getattr(self, 'bias_window_label', None), getattr(self, 'bias_window_entry', None), getattr(self, 'serialization_label', None), getattr(self, 'serialization_combo', None)):
                    try:
                        if w is not None:
                            w.grid_remove()
                    except Exception:
                        pass
                try:
                    if getattr(self, 'preset_frame', None) is not None:
                        self.preset_frame.grid_remove()
                except Exception:
                    pass
                try:
                    self.adv_btn.configure(text='Advanced >>')
                except Exception:
                    pass
                self._adv_visible = False
            else:
                # show advanced widgets
                for w in (getattr(self, 'unit_bias_label', None), getattr(self, 'unit_bias_entry', None), getattr(self, 'bias_max_label', None), getattr(self, 'bias_max_entry', None), getattr(self, 'bias_window_label', None), getattr(self, 'bias_window_entry', None), getattr(self, 'serialization_label', None), getattr(self, 'serialization_combo', None)):
                    try:
                        if w is not None:
                            w.grid()
                    except Exception:
                        pass
                try:
                    if getattr(self, 'preset_frame', None) is not None:
                        self.preset_frame.grid()
                except Exception:
                    pass
                try:
                    self.adv_btn.configure(text='Advanced <<')
                except Exception:
                    pass
                self._adv_visible = True
        except Exception:
            logger.exception('_toggle_advanced failed')

    def _update_bias_summary_from_inputs(self):
        try:
            ub_raw = (self.unit_bias_var.get() or '').strip()
            ub_desc = ub_raw if ub_raw != '' else 'auto'
            bm = (self.bias_max_var.get() or '').strip() or '5'
            bw = (self.bias_window_var.get() or '').strip() or '1.0'
            sm = (self.serialization_var.get() or 'Auto')
            self.bias_summary_var.set(f"Bias={ub_desc}h cap={bm}% window={bw} mode={sm}")
        except Exception:
            pass

    def _update_bias_summary(self, unit_bias_val, bias_max_frac, bias_window_frac, serialization_mode):
        try:
            ub = unit_bias_val if unit_bias_val is not None else 'auto'
            try:
                cap_pct = float(bias_max_frac) * 100.0 if isinstance(bias_max_frac, (int, float)) else float(bias_max_frac) * 100.0
            except Exception:
                cap_pct = 5.0
            self.bias_summary_var.set(f"Bias={ub}h cap={cap_pct:.1f}% window={bias_window_frac} mode={serialization_mode}")
        except Exception:
            pass

    def _validate_controls(self):
        """Validate numeric inputs and enable/disable Calculate button and update summary."""
        try:
            ok = True
            # Validate N if required
            if self.mode_var.get() == 'time_for_n':
                try:
                    n = int(float(self.n_var.get() or 0))
                    if n <= 0:
                        ok = False
                except Exception:
                    ok = False
            else:
                try:
                    t = float(self.t_var.get() or 0.0)
                    if t <= 0.0:
                        ok = False
                except Exception:
                    ok = False

            # spins (optional, defaults to 0 if invalid)
            try:
                sp = int(float(self.spins_var.get() or 0))
                if sp < 0:
                    ok = False
            except Exception:
                # Don't fail validation for invalid spins - just use default
                pass

            # yield (optional, defaults to 100% if invalid)
            try:
                y = float(self.yield_var.get() or 100.0)
                if y <= 0 or y > 10000:
                    ok = False
            except Exception:
                # Don't fail validation for invalid yield - just use default
                pass

            # Advanced controls removed - validation no longer needed

            # update button state
            try:
                if ok:
                    self.calc_button.state(['!disabled'])
                else:
                    self.calc_button.state(['disabled'])
            except Exception:
                pass

            # update compact summary
            try:
                if self.mode_var.get() == 'time_for_n':
                    self.calc_summary_var.set(f"Mode: Time for N | N={self.n_var.get()} | Spins={self.spins_var.get()} | Yield={self.yield_var.get()}%")
                else:
                    self.calc_summary_var.set(f"Mode: Units in T | T={self.t_var.get()} hrs | Spins={self.spins_var.get()} | Yield={self.yield_var.get()}%")
            except Exception:
                pass

            return ok
        except Exception:
            return False

    def _clear_results(self):
        """Clear the results output area (Text widget) safely."""
        try:
            self.out_text.configure(state='normal')
            self.out_text.delete('1.0', tk.END)
            self.out_text.configure(state='disabled')
        except Exception:
            pass

    def _on_station_double_click(self, event):
        """Stub for station double-click binding (edit count)."""
        try:
            item = self.st_tree.selection()
            if not item:
                return
            # ensure item is a single selected row (not multiple or invalid)
            item = item[0] if isinstance(item, (tuple, list)) and len(item) >= 1 else None
            if not item:
                return

            # Get the current values for the row
            vals = self.st_tree.item(item, 'values')
            station_name = str(vals[0]).strip() if vals else ''
            count = vals[1] if vals and len(vals) > 1 else ''

            # Switch to entry mode: create an Entry widget over the cell
            # bbox returns coordinates relative to the tree widget, so parent the edit
            # widget to the tree itself and place using the bbox values. Use a
            # tk.Spinbox so the user gets up/down arrows like the channel controls.
            x, y, width, height = self.st_tree.bbox(item, '#2')
            if x < 0 or y < 0 or width <= 0 or height <= 0:
                return

            try:
                # Prefer a Spinbox to give up/down arrows for easy editing
                entry = tk.Spinbox(self.st_tree, from_=0, to=999, width=8)
            except Exception:
                # Fallback to a plain Entry if Spinbox is unavailable
                entry = ttk.Entry(self.st_tree, width=8)

            # Place the widget inside the tree at the cell bbox (coords are relative to tree)
            entry.place(x=x, y=y, width=width, height=height)
            try:
                entry.delete(0, tk.END)
            except Exception:
                pass
            entry.insert(0, str(count))
            entry.focus_set()

            def on_commit_edit(event=None):
                try:
                    new_val = entry.get().strip()
                    if not new_val:
                        return
                    # simple validation: check if new value is an integer
                    if not re.match(r'^\d+$', new_val):
                        messagebox.showwarning("Invalid input", "Please enter a valid integer value.")
                        return
                    new_count = int(new_val)

                    # Update the treeview item (UI)
                    self.st_tree.item(item, values=(station_name, new_count))

                    # Persist to self.st_map if present (case-insensitive match)
                    try:
                        if isinstance(self.st_map, dict):
                          matched = False
                          for k in list(self.st_map.keys()):
                            if str(k).strip().lower() == station_name.lower():
                              # some maps store dicts with 'count' key
                              v = self.st_map[k]
                              if isinstance(v, dict):
                                v['count'] = new_count
                              else:
                                # fallback: replace value with dict
                                self.st_map[k] = {'count': new_count, 'uptime': 1.0}
                              matched = True
                              break
                          if not matched:
                            # insert if missing
                            self.st_map[station_name] = {'count': new_count, 'uptime': 1.0}
                    except Exception:
                        logger.exception("Failed updating self.st_map with new station count")

                    # Persist to self.stations_df if present
                    try:
                        if isinstance(self.stations_df, pd.DataFrame) and not self.stations_df.empty:
                            for i, row in self.stations_df.iterrows():
                                if str(row.get('Station', '')).strip().lower() == station_name.lower():
                                    # update existing row
                                    self.stations_df.at[i, 'Count'] = new_count
                                    break
                            else:
                                # insert new row (appends to end)
                                self.stations_df = pd.concat([self.stations_df, pd.DataFrame([{'Station': station_name, 'Count': new_count}])], ignore_index=True)
                    except Exception:
                        logger.exception("Failed persisting station count change to stations_df")

                    try:
                        entry.destroy()
                    except Exception:
                        pass

                    # trigger a refresh of dependent calculations/tables
                    try:
                        self.refresh_tables()
                    except Exception:
                        logger.exception("Error refreshing tables after station count edit")
                except Exception:
                    logger.exception("Error committing station count edit")
                    try:
                        entry.destroy()
                    except Exception:
                        pass

            def on_cancel_edit(event=None):
                try:
                    # Treat cancel as commit on focus loss to match channel controls behavior
                    on_commit_edit()
                except Exception:
                    pass

            # Commit on Enter, save on focus loss
            try:
                entry.bind('<Return>', lambda e: on_commit_edit())
                entry.bind('<FocusOut>', lambda e: on_commit_edit())
            except Exception:
                pass

            # Remove selection (for aesthetics)
            try:
                self.st_tree.selection_remove(self.st_tree.selection())
            except Exception:
                pass
        except Exception:
            logger.exception("Error handling station double-click")

    def import_test_plan(self):
        """Import a plan file, map to Tests rows, and optionally commit into the attached workbook.

        Simplified, robust flow: read plan (CSV/XLS), map headers via PlanSchema if available,
        convert to Tests rows using plan_to_tests_rows, publish to UI and optionally commit to
        the loaded model workbook (if present and auto-commit enabled).
        """
        try:
            if not getattr(self, 'model_path', None):
                messagebox.showwarning("No model", "Load the planning Excel first (use 'Load Excel...').")
                return

            path = filedialog.askopenfilename(title='Select plan file', filetypes=[('Excel/CSV', '*.xlsx;*.xls;*.csv;*.tsv'), ('All files', '*.*')])
            if not path:
                return

            try:
                plan_df, sheet_name = import_plan_file(path, None)
            except Exception as ex:
                logger.exception("Failed reading plan file")
                messagebox.showerror("Import error", f"Failed reading plan file: {ex}")
                return

            # PlanSchema mapping if available
            plan_schema_map = {}
            try:
                if getattr(self, 'plan_schema_df', None) is not None:
                    plan_schema_map = read_plan_schema(self.plan_schema_df)
            except Exception:
                plan_schema_map = {}

            try:
                mapped, warnings = auto_map_plan_schema(plan_df, plan_schema_map)
                if warnings:
                    logger.info("Auto-map warnings: %r", warnings)
            except Exception:
                mapped = plan_schema_map if plan_schema_map else {}

            # Station mapping rules if available
            station_rules = []
            try:
                if getattr(self, 'station_map_df', None) is not None:
                    station_rules = read_station_map(self.station_map_df)
            except Exception:
                station_rules = []

            try:
                out_df, issues = plan_to_tests_rows(plan_df, mapped, station_rules, self.stations_df if self.stations_df is not None else pd.DataFrame(), project_override=None, scenario_override=None, sheet_name=sheet_name)
            except Exception as ex:
                logger.exception("Mapping plan to tests failed")
                messagebox.showerror("Mapping error", f"Failed mapping plan to tests: {ex}")
                return

            # Annotate K-groups from Comments so DependencyInfo is present for UI
            try:
                try:
                    annotated, _skipped = self._annotate_k_groups_safe(out_df)
                    out_df = annotated
                    # Log annotated sample for debugging why DependencyInfo may be missing
                    try:
                        if logger.isEnabledFor(logging.DEBUG) and isinstance(annotated, pd.DataFrame):
                            cols = [c for c in ('TestID','DependsOn','DependencyInfo','Comments') if c in annotated.columns]
                            if cols:
                                logger.debug('annotated (post-annotate_k_groups_safe) sample:\n%s', annotated[cols].head(40).to_string())
                    except Exception:
                        pass
                except Exception:
                    # fallback to annotate_k_groups
                    try:
                        out_df = self._annotate_k_groups(out_df)
                        try:
                            if logger.isEnabledFor(logging.DEBUG) and isinstance(out_df, pd.DataFrame):
                                cols = [c for c in ('TestID','DependsOn','DependencyInfo','Comments') if c in out_df.columns]
                                if cols:
                                    logger.debug('annotated (post-annotate_k_groups fallback) sample:\n%s', out_df[cols].head(40).to_string())
                        except Exception:
                            pass
                    except Exception:
                        pass
                # Normalize numeric TestID/DependsOn to plain strings so UI shows readable values
                try:
                    out_df = self._normalize_testid_and_depends(out_df)
                except Exception:
                    pass
            except Exception:
                pass

            # Publish to UI and cache
            try:
                proj_name = sheet_name or os.path.splitext(os.path.basename(path))[0]
            except Exception:
                proj_name = ''
            try:
                if 'Project' not in out_df.columns:
                    out_df['Project'] = proj_name
                else:
                    # Fill blanks with detected project name if present
                    if proj_name:
                        out_df['Project'] = out_df['Project'].replace('', proj_name)
            except Exception:
                pass

            try:
                lst = self.project_plans.get(proj_name, [])
                lst.insert(0, out_df.copy())
                if len(lst) > 3:
                    lst = lst[:3]
                self.project_plans[proj_name] = lst
                self.imported_tests_df = lst[0].copy() if lst else out_df
            except Exception:
                self.imported_tests_df = out_df

            # log imported sample (helpful to debug missing DependencyInfo)
            try:
                if logger.isEnabledFor(logging.DEBUG) and isinstance(self.imported_tests_df, pd.DataFrame):
                    cols = [c for c in ('TestID','DependsOn','DependencyInfo') if c in self.imported_tests_df.columns]
                    if cols:
                        logger.debug('imported_tests_df: sample after import/annotate:\n%s', self.imported_tests_df[cols].head(30).to_string())
            except Exception:
                pass

            # Fallback: if DependencyInfo is blank but DependsOn contains data, copy DependsOn -> DependencyInfo
            try:
                if isinstance(self.imported_tests_df, pd.DataFrame) and 'DependsOn' in self.imported_tests_df.columns:
                    if 'DependencyInfo' not in self.imported_tests_df.columns:
                        self.imported_tests_df['DependencyInfo'] = ''
                    try:
                        dep = self.imported_tests_df['DependsOn'].astype(str).fillna('')
                        info = self.imported_tests_df['DependencyInfo'].astype(str).fillna('')
                        # use bitwise & for pandas Series comparisons
                        mask = info.str.strip().eq('') & dep.str.strip().ne('')
                    except Exception:
                        # pandas bitwise ops require &; fall back to elementwise
                        mask = [(str(i).strip() == '' and str(d).strip() != '') for d, i in zip(self.imported_tests_df.get('DependsOn', []), self.imported_tests_df.get('DependencyInfo', []))]
                    try:
                        self.imported_tests_df.loc[mask, 'DependencyInfo'] = self.imported_tests_df.loc[mask, 'DependsOn']
                    except Exception:
                        # best-effort rowwise copy
                        try:
                            for idx, m in enumerate(mask):
                                if m:
                                    self.imported_tests_df.at[self.imported_tests_df.index[idx], 'DependencyInfo'] = str(self.imported_tests_df.at[self.imported_tests_df.index[idx], 'DependsOn'])
                        except Exception:
                            pass
            except Exception:
                pass

            # Auto-commit into workbook if enabled
            try:
                if getattr(self, 'auto_commit_var', None) and self.auto_commit_var.get() and getattr(self, 'model_path', None):
                    try:
                        added, total = commit_import_to_tests(self.model_path, out_df)
                        logger.info("Auto-committed import: added=%s total=%s", added, total)
                    except Exception:
                        logger.exception("Auto-commit failed")
            except Exception:
                pass

            # Refresh UI
            try:
                self.refresh_filters()
                self.refresh_tables()
            except Exception:
                pass

        except Exception as ex:
            logger.exception("import_test_plan failed")
            try:
                messagebox.showerror("Import error", f"Import failed: {ex}")
            except Exception:
                pass

    def view_stationmap(self):
        try:
            if getattr(self, 'station_map_df', None) is None or self.station_map_df.empty:
                messagebox.showinfo('StationMap', 'No StationMap loaded in the model.')
                return
            # Filter out hidden stations (channel markers)
            filtered_df = self.station_map_df[
                ~self.station_map_df['Station'].astype(str).apply(is_hidden_station)
            ].copy()
            if filtered_df.empty:
                messagebox.showinfo('StationMap', 'StationMap is empty after filtering.')
                return
            show_dataframe_dialog(self, 'StationMap', filtered_df)
        except Exception:
            logger.exception('error in view_stationmap')

    def view_nontest(self):
        try:
            if getattr(self, 'non_test_df', None) is None or self.non_test_df.empty:
                messagebox.showinfo('NonTestGroups', 'No NonTestGroups loaded in the model.')
                return
            show_dataframe_dialog(self, 'NonTestGroups', self.non_test_df)
        except Exception:
            logger.exception('error in view_nontest')

    def view_dependency_debug(self):
        try:
            if not isinstance(getattr(self, 'imported_tests_df', None), pd.DataFrame):
                messagebox.showinfo('Dependency Debug', 'No imported variant loaded.')
                return
            df = self.imported_tests_df.copy()
            cols = [c for c in ('TestID','Comments','DependsOn','DependencyInfo') if c in df.columns]
            if not cols:
                messagebox.showinfo('Dependency Debug', 'No dependency-related columns found on current variant')
                return
            show_dataframe_dialog(self, 'Dependency Debug', df[cols])
        except Exception:
            logger.exception('Failed showing dependency debug dialog')

    def _show_debug_log(self):
        """Show the debug log file in a dialog window."""
        try:
            log_path = pathlib.Path(__file__).resolve().with_name("piston_debug.log")

            if not log_path.exists():
                messagebox.showinfo('Debug Log', f'Log file not found at:\n{log_path}')
                return

            # Create log viewer dialog
            log_dlg = tk.Toplevel(self)
            log_dlg.title('Piston Debug Log')
            log_dlg.geometry('900x600')

            # Set icon
            try:
                from piston_ui.icon_helper import set_window_icon
                set_window_icon(log_dlg)
            except Exception:
                pass

            # Apply dark theme
            bg = '#1e1e1e'
            text_fg = '#d4d4d4'
            log_dlg.configure(bg=bg)

            # Info label
            info_frame = ttk.Frame(log_dlg)
            info_frame.pack(fill='x', padx=8, pady=8)
            ttk.Label(info_frame, text=f'Log file: {log_path}', 
                     font=('TkDefaultFont', 9)).pack(anchor='w')

            # Text widget with scrollbar
            text_frame = ttk.Frame(log_dlg)
            text_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))

            scrollbar = ttk.Scrollbar(text_frame)
            scrollbar.pack(side='right', fill='y')

            text_widget = tk.Text(text_frame, wrap='none', 
                                 bg='#1e1e1e', fg='#d4d4d4',
                                 insertbackground='#d4d4d4',
                                 selectbackground='#094771',
                                 font=('Consolas', 9),
                                 yscrollcommand=scrollbar.set)
            text_widget.pack(side='left', fill='both', expand=True)
            scrollbar.config(command=text_widget.yview)

            # Load and display log content
            try:
                # Read last 10000 lines to avoid loading huge files
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # Show last 10000 lines
                    content = ''.join(lines[-10000:]) if len(lines) > 10000 else ''.join(lines)
                    text_widget.insert('1.0', content)
                    # Scroll to bottom
                    text_widget.see('end')
            except Exception as e:
                text_widget.insert('1.0', f'Error reading log file: {e}')

            # Make read-only
            text_widget.config(state='disabled')

            # Buttons
            btn_frame = ttk.Frame(log_dlg)
            btn_frame.pack(fill='x', padx=8, pady=(0, 8))

            def open_in_notepad():
                try:
                    import subprocess
                    subprocess.Popen(['notepad.exe', str(log_path)])
                except Exception:
                    try:
                        # Fallback: try default application
                        os.startfile(str(log_path))
                    except Exception:
                        messagebox.showerror('Error', 'Could not open log file')

            ttk.Button(btn_frame, text='Open in Notepad', 
                      command=open_in_notepad).pack(side='left', padx=4)
            ttk.Button(btn_frame, text='Refresh', 
                      command=lambda: self._show_debug_log()).pack(side='left', padx=4)
            ttk.Button(btn_frame, text='Close', 
                      command=log_dlg.destroy).pack(side='right', padx=4)

        except Exception:
            logger.exception('Failed showing debug log')
            messagebox.showerror('Error', 'Failed to open debug log viewer')

    def _safe_call(self, name: str):
        """Call a PlannerApp method by name safely and surface errors to the user."""
        fn = getattr(self, name, None)
        if callable(fn):
            try:
                return fn()
            except Exception as ex:
                logger.exception("Safe call failed: %s", ex)
                try:
                    messagebox.showerror("Error", f"Failed to run '{name}':\n\n{ex}")
                except Exception:
                    pass
        else:
            try:
                messagebox.showerror("Not implemented", f"'{name}' is not implemented in this build.")
            except Exception:
                pass

    def _update_manual_et_status(self):
        """Update the Manual ET status label based on override presence."""
        try:
            active = self.manual_et_override_df is not None and not getattr(self.manual_et_override_df, 'empty', True)
            if hasattr(self, 'manual_et_status') and self.manual_et_status is not None:
                if active:
                    self.manual_et_status.configure(text='Manual ET: Active', foreground='green')
                else:
                    self.manual_et_status.configure(text='Manual ET: Off', foreground='gray')
        except Exception:
            logger.exception("Error updating manual ET status")

    def clear_manual_et(self):
        try:
            self.manual_et_override_df = pd.DataFrame()
            try:
                self._update_manual_et_status()
            except Exception:
                pass
            try:
                self.refresh_filters()
            except Exception:
                pass
        except Exception:
            logger.exception("Error clearing manual ET")

    def set_range_current(self):
        try:
            messagebox.showinfo('Set Range', 'Range current setting is not implemented in this build. Use Manual ET Allocator for overrides.')
        except Exception:
            pass

    def calculate(self):
        """Trigger schedule calculation using current UI state.

        Delegates to piston_ui.calculate module for cleaner code organization.
        """
        try:
            calculate_impl(self)
        except Exception:
            logger.exception("Error in calculate")
            messagebox.showerror("Calculation error", "Calculation failed unexpectedly.")

    def refresh_filters(self):
        """Apply UI filters and build filtered_tests_df/tests_info.

        Delegates to piston_ui.filters module.
        """
        try:
            refresh_filters_impl(self)
        except Exception:
            logger.exception('Error in refresh_filters')

    def refresh_tables(self):
        """Refresh stations and tests treeviews and update status.

        Delegates to piston_ui.filters module.
        """
        try:
            refresh_tables_impl(self)
        except Exception:
            logger.exception('Error in refresh_tables')

    def _on_project_changed(self):
        """Handle project selection changes.

        Delegates to piston_ui.project_mgmt module.
        """
        try:
            on_project_changed_impl(self)
        except Exception:
            logger.exception("Error in _on_project_changed")

    def _on_variant_changed(self):
        """Handle variant selection changes.

        Delegates to piston_ui.project_mgmt module.
        """
        try:
            on_variant_changed_impl(self)
        except Exception:
            logger.exception("Error in _on_variant_changed")

    def _update_variant_ui_for_project(self, proj_name: str):
        """Update the Plan Variant combobox for a given project.

        Delegates to piston_ui.project_mgmt module.
        """
        from piston_ui.project_mgmt import update_variant_ui_for_project
        try:
            update_variant_ui_for_project(self, proj_name)
        except Exception:
            logger.exception('Error updating variant UI for project')

    def _normalize_testid_and_depends(self, df):
        """Normalize numeric-looking TestID and DependsOn values.

        Delegates to piston_ui.project_mgmt module.
        """
        return normalize_testid_and_depends(df)

    def _build_average_variant(self, proj_name: str, variants: list):
        """Build an averaged Tests DataFrame from variants.

        Delegates to piston_ui.project_mgmt module.
        """
        return build_average_variant(self, proj_name, variants)

    # -------------------- Update Checking --------------------

    def _check_updates_async(self):
        """Check for updates in background thread (non-blocking)."""
        try:
            # Wait 2 seconds after launch so UI shows first
            import time
            time.sleep(2)

            from piston_core.updater import check_for_updates, get_current_version

            current = get_current_version()
            logger.info("Checking for updates (current version: %s)...", current)

            update_info = check_for_updates(current)

            if update_info.get('available'):
                # Show notification banner in main thread (Tkinter requires this)
                self.after(0, lambda: self._show_update_banner(update_info))
            else:
                logger.info("No update available")

        except Exception:
            # Silent failure - don't bother user if update check fails
            logger.exception("Update check failed (silent)")

    def _show_update_banner(self, info):
        """Show update notification banner at top of window."""
        try:
            # DEBUG: Confirm this method is being called
            logger.info("_show_update_banner called with version: %s", info.get('version', 'unknown'))

            # Create banner at very top (above header)
            banner = tk.Frame(self, bg='#0d7fa5', height=40)

            # Try to pack before first child, fallback to just packing at top
            try:
                children = self.winfo_children()
                logger.info("Window has %d children", len(children))
                if children:
                    banner.pack(side='top', fill='x', before=children[0])
                else:
                    banner.pack(side='top', fill='x')
            except Exception as e:
                logger.warning("Failed packing with before, using fallback: %s", e)
                banner.pack(side='top', fill='x')

            banner.pack_propagate(False)
            banner.lift()  # Ensure banner is visible on top

            logger.info("Banner frame created and packed")

            # Icon + Message
            msg = f"  📦  Piston {info['version']} is available  ({info.get('size_mb', 0):.1f} MB)"
            tk.Label(
                banner,
                text=msg,
                bg='#0d7fa5', fg='white',
                font=('Segoe UI', 9, 'bold')
            ).pack(side='left', padx=15, pady=8)

            logger.info("Banner message label created")

            # Update Now button
            tk.Button(
                banner,
                text='Update Now',
                command=lambda: self._on_update_now(banner, info),
                bg='#094771', fg='white',
                relief='flat',
                padx=15, pady=5,
                cursor='hand2',
                font=('Segoe UI', 9, 'bold'),
                borderwidth=0,
                highlightthickness=0
            ).pack(side='left', padx=5)

            # View Details button
            tk.Button(
                banner,
                text='What\'s New',
                command=lambda: self._show_update_details(info),
                bg='#0a5f80', fg='white',
                relief='flat',
                padx=15, pady=5,
                cursor='hand2',
                font=('Segoe UI', 9),
                borderwidth=0,
                highlightthickness=0
            ).pack(side='left', padx=5)

            # Dismiss button (X)
            tk.Button(
                banner,
                text='✕',
                command=banner.destroy,
                bg='#0d7fa5', fg='white',
                relief='flat',
                padx=10, pady=5,
                cursor='hand2',
                font=('Segoe UI', 11, 'bold'),
                borderwidth=0,
                highlightthickness=0
            ).pack(side='right', padx=10)

            logger.info("Update banner shown for version %s", info['version'])

        except Exception:
            logger.exception("Failed showing update banner")

    def _show_update_details(self, info):
        """Show release notes dialog."""
        try:
            from piston_core.updater import get_current_version

            # Create dialog
            dlg = tk.Toplevel(self)
            dlg.title(f"Piston {info['version']} Release Notes")
            dlg.geometry("600x500")
            dlg.transient(self)
            dlg.resizable(True, True)

            # Apply dark theme
            bg = '#1e1e1e'
            text_fg = '#d4d4d4'
            dlg.configure(bg=bg)

            # Set icon
            try:
                from piston_ui.icon_helper import set_window_icon
                set_window_icon(dlg)
            except Exception:
                pass

            # Header
            header = tk.Frame(dlg, bg='#0d7fa5', height=60)
            header.pack(fill='x')
            header.pack_propagate(False)

            tk.Label(
                header,
                text=f"🚀 Piston {info['version']}",
                bg='#0d7fa5', fg='white',
                font=('Segoe UI', 14, 'bold')
            ).pack(side='left', padx=20, pady=15)

            # Version info
            info_frame = tk.Frame(dlg, bg=bg)
            info_frame.pack(fill='x', padx=20, pady=15)

            current = get_current_version()
            info_text = f"Current version:  {current}\nNew version:      {info['version']}\nDownload size:    {info.get('size_mb', 0):.1f} MB"

            tk.Label(
                info_frame,
                text=info_text,
                bg=bg, fg=text_fg,
                font=('Consolas', 10),
                justify='left'
            ).pack(anchor='w')

            # Release notes
            notes_frame = tk.Frame(dlg, bg=bg)
            notes_frame.pack(fill='both', expand=True, padx=20, pady=(10, 15))

            tk.Label(
                notes_frame,
                text="What's New:",
                bg=bg, fg=text_fg,
                font=('Segoe UI', 10, 'bold')
            ).pack(anchor='w', pady=(0, 8))

            # Scrollable text for release notes
            notes_container = tk.Frame(notes_frame, bg='#2d2d30', relief='solid', bd=1)
            notes_container.pack(fill='both', expand=True)

            scrollbar = tk.Scrollbar(notes_container)
            scrollbar.pack(side='right', fill='y')

            notes_text = tk.Text(
                notes_container,
                bg='#1e1e1e', fg=text_fg,
                font=('Segoe UI', 9),
                wrap='word',
                relief='flat',
                padx=15, pady=15,
                yscrollcommand=scrollbar.set
            )
            notes_text.pack(side='left', fill='both', expand=True)
            scrollbar.config(command=notes_text.yview)

            # Insert release notes
            notes_text.insert('1.0', info.get('notes', 'No release notes available.'))
            notes_text.config(state='disabled')

            # Buttons
            btn_frame = tk.Frame(dlg, bg=bg)
            btn_frame.pack(fill='x', padx=20, pady=(0, 15))

            tk.Button(
                btn_frame,
                text='Close',
                command=dlg.destroy,
                bg='#3c3c3c', fg=text_fg,
                relief='flat',
                padx=20, pady=8,
                cursor='hand2',
                font=('Segoe UI', 9)
            ).pack(side='right')

        except Exception:
            logger.exception("Failed showing update details")

    def _on_update_now(self, banner, info):
        """Handle 'Update Now' button click."""
        try:
            banner.destroy()

            # Show progress dialog
            self._download_and_install_update(info)

        except Exception:
            logger.exception("Update failed")
            messagebox.showerror("Update Failed", "Could not download update.")

    def _download_and_install_update(self, info):
        """Download update with progress dialog and apply on restart."""
        try:
            # Create progress dialog
            progress_dlg = tk.Toplevel(self)
            progress_dlg.title("Downloading Update")
            progress_dlg.geometry("450x180")
            progress_dlg.resizable(False, False)
            progress_dlg.transient(self)

            # Apply dark theme
            bg = '#1e1e1e'
            text_fg = '#d4d4d4'
            progress_dlg.configure(bg=bg)

            # Set icon
            try:
                from piston_ui.icon_helper import set_window_icon
                set_window_icon(progress_dlg)
            except Exception:
                pass

            # Message
            msg = tk.Label(
                progress_dlg,
                text=f"Downloading Piston {info['version']}...",
                bg=bg, fg=text_fg,
                font=('Segoe UI', 11)
            )
            msg.pack(pady=(25, 15))

            # Progress bar
            progress_var = tk.DoubleVar(value=0)
            progress_bar = ttk.Progressbar(
                progress_dlg,
                variable=progress_var,
                maximum=100,
                mode='determinate',
                length=350
            )
            progress_bar.pack(padx=30, pady=10)

            # Status label
            status_label = tk.Label(
                progress_dlg,
                text="Starting download...",
                bg=bg, fg=text_fg,
                font=('Segoe UI', 9)
            )
            status_label.pack(pady=(5, 20))

            # Update progress callback
            def update_progress(percent):
                try:
                    progress_var.set(percent)
                    status_label.config(text=f"{percent:.0f}% complete")
                    progress_dlg.update()
                except Exception:
                    pass

            # Download in separate thread
            import threading
            result = {'success': False, 'path': None}

            def download_thread():
                try:
                    from piston_core.updater import download_update
                    temp_path = download_update(info['url'], update_progress)
                    result['success'] = temp_path is not None
                    result['path'] = temp_path
                except Exception:
                    logger.exception("Download thread failed")

            thread = threading.Thread(target=download_thread, daemon=False)
            thread.start()

            # Wait for completion (with UI updates)
            while thread.is_alive():
                progress_dlg.update()
                thread.join(timeout=0.1)

            progress_dlg.destroy()

            # Handle result
            if result['success'] and result['path']:
                # Offer restart now or later
                response = messagebox.askyesno(
                    "Update Ready",
                    f"Piston {info['version']} has been downloaded.\n\n"
                    "Restart now to apply the update?\n\n"
                    "(If you choose 'No', the update will apply next time you launch Piston)",
                    icon='info'
                )

                if response:
                    # Apply now and restart
                    from piston_core.updater import apply_update_and_restart
                    apply_update_and_restart(result['path'])
                    # apply_update_and_restart calls sys.exit() - won't reach here
                else:
                    # Stage for next launch
                    from piston_core.updater import stage_update_for_next_launch
                    if stage_update_for_next_launch(result['path']):
                        messagebox.showinfo(
                            "Update Staged",
                            "The update will be applied the next time you launch Piston."
                        )
            else:
                messagebox.showerror(
                    "Download Failed",
                    "Could not download the update. Please check your internet connection and try again."
                )

        except Exception:
            logger.exception("Update download/install failed")
            messagebox.showerror("Update Failed", "An error occurred during the update process.")

    def _manual_update_check(self):
        """Manually trigger update check (for testing/debugging)."""
        try:
            from piston_core.updater import check_for_updates, get_current_version
            import threading

            current = get_current_version()

            # Show checking message
            messagebox.showinfo("Check for Updates", f"Checking for updates...\nCurrent version: {current}")

            # Check in background
            def check_thread():
                try:
                    update_info = check_for_updates(current)

                    # Show result in main thread
                    def show_result():
                        if update_info.get('available'):
                            self._show_update_banner(update_info)
                            messagebox.showinfo("Update Available", 
                                f"Piston {update_info['version']} is available!\nSee banner at top of window.")
                        elif update_info.get('error'):
                            messagebox.showwarning("Update Check", 
                                f"Could not check for updates:\n{update_info.get('error')}")
                        else:
                            messagebox.showinfo("Up to Date", 
                                f"You're running the latest version ({current})")

                    self.after(0, show_result)

                except Exception as e:
                    logger.exception("Manual update check failed")
                    self.after(0, lambda: messagebox.showerror("Error", f"Update check failed: {e}"))

            threading.Thread(target=check_thread, daemon=True).start()

        except Exception:
            logger.exception("Error starting manual update check")
            messagebox.showerror("Error", "Failed to start update check")

def main():
    # Robust startup wrapper: run the app and ensure any exceptions are visible
    import traceback, sys
    try:
        # Create the app and expose it as a module-level variable so external
        # diagnostic code can access `Piston.app` when the GUI is running.
        global app
        app = PlannerApp()
        try:
            app._post_init_layout()
        except Exception:
            pass
        app.mainloop()
    except Exception as ex:
        # Log full traceback, show modal if possible, and pause console so user can read it
        try:
            logger.exception('Unhandled exception running PlannerApp')
        except Exception:
            pass
        try:
            traceback.print_exc()
        except Exception:
            pass
        try:
            messagebox.showerror('Startup error', f'Failed to start application:\n\n{ex}')
        except Exception:
            pass
        try:
            # keep console open so user can copy the error
            input('Press Enter to exit...')
        except Exception:
            pass


if __name__ == '__main__':
    main()