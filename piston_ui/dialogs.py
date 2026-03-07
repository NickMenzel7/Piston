import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
import pandas as pd
from piston_ui.icon_helper import set_window_icon


def show_dataframe_dialog(parent, title: str, df: pd.DataFrame):
    """
    Show a read-only dialog presenting a DataFrame `df`.
    Falls back to a ScrolledText dump if building a Treeview fails.

    UI adjustments: hide rows with Pattern containing 'Insert test plan' and
    remove technical columns 'cnt' and 'MatchType' and 'Notes' from display.
    Also remove scrollbars; Treeview will expand to fill the dialog.
    Special-case: for `NonTestGroups` drop the 'Field' column so only the pattern
    column is shown.
    """
    try:
        if df is None:
            messagebox.showwarning(title, f"{title} is not loaded or is empty.")
            return

        # Work on a copy and apply UI-friendly filtering/removals
        df2 = df.copy()
        # remove technical columns if present
        for _c in ('cnt', 'MatchType', 'Notes'):
            if _c in df2.columns:
                try:
                    df2 = df2.drop(columns=[_c])
                except Exception:
                    pass

        # Special-case NonTestGroups: drop the 'Field' column to show only Pattern
        try:
            if title == 'NonTestGroups' and 'Field' in df2.columns:
                try:
                    df2 = df2.drop(columns=['Field'])
                except Exception:
                    pass
        except Exception:
            pass

        # hide rows added as placeholders like 'Insert test plan: ...'
        try:
            if 'Pattern' in df2.columns:
                mask = ~df2['Pattern'].astype(str).fillna('').str.contains(r'insert test plan', case=False, na=False)
                df2 = df2.loc[mask]
        except Exception:
            pass

        if df2 is None or df2.empty:
            messagebox.showwarning(title, f"{title} is not loaded or has no visible rows.")
            return

        dlg = tk.Toplevel(parent)
        dlg.title(title)
        # Set custom icon
        set_window_icon(dlg)

        # Apply dark theme colors to dialog
        bg = '#1e1e1e'
        frame_bg = '#252526'
        input_bg = '#3c3c3c'
        text_fg = '#d4d4d4'
        heading_bg = '#2d2d30'
        border = '#2d2d30'

        try:
            dlg.configure(bg=bg)
        except Exception:
            pass

        # Choose a more appropriate default size depending on number of columns.
        # If there's a single column (common for NonTestGroups), use a narrow dialog.
        cols = [str(c) for c in df2.columns]
        if len(cols) == 1:
            dlg.geometry('420x360')
        elif len(cols) <= 3:
            dlg.geometry('620x380')
        else:
            dlg.geometry('780x420')

        frame = ttk.Frame(dlg)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        # cols already determined above when sizing the dialog
        # ensure only the named columns are displayed (hide the implicit #0 tree column)
        tree = ttk.Treeview(frame, columns=cols, show='headings', displaycolumns=cols)
        # hide the implicit tree column (#0) so no empty column appears
        try:
            tree.column('#0', width=0, stretch=False)
        except Exception:
            pass

        for c in cols:
            tree.heading(c, text=c)
            # For single-column displays allow the column to stretch to fill the dialog
            # to avoid a visible empty area to the right. For multi-column use sensible defaults.
            if len(cols) == 1:
                tree.column(c, width=300, anchor='center', stretch=True)
            else:
                tree.column(c, width=150, anchor='center', stretch=True)

        try:
            for _, r in df2.iterrows():
                vals = ["" if pd.isna(r.get(c, "")) else str(r.get(c, "")) for c in cols]
                tree.insert("", "end", values=vals)
        except Exception:
            # fallback to plain text
            txt = ScrolledText(frame, wrap='none')
            txt.pack(fill='both', expand=True)
            try:
                txt.insert('1.0', df2.to_string(index=False))
            except Exception:
                txt.insert('1.0', str(df2))
            txt.configure(state='disabled')
            ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=6)
            return

        # Pack the tree to fill the dialog (no scrollbars)
        tree.pack(fill='both', expand=True, side='left')

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill='x', padx=8, pady=(4,8))
        ttk.Button(btn_frame, text="Close", command=dlg.destroy).pack(side='right')

    except Exception:
        messagebox.showerror("Error", f"Failed to show {title}.")
