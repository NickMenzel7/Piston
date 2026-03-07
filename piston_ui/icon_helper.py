import os
import tkinter as tk
import logging

logger = logging.getLogger("piston")


def set_window_icon(window):
    """
    Set the custom Piston icon on any tkinter window (Tk or Toplevel).
    Looks for icon files in the Icon directory relative to the main script.
    Works both in development and when packaged with PyInstaller.
    """
    try:
        # Determine the base directory
        # When frozen by PyInstaller, use sys._MEIPASS
        # Otherwise use the script's directory
        import sys
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller bundle
            base_dir = sys._MEIPASS
        else:
            # Running as script
            base_dir = os.path.dirname(os.path.dirname(__file__))

        icon_dir = os.path.join(base_dir, 'Icon')

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

        if chosen:
            try:
                if chosen.lower().endswith('.ico'):
                    try:
                        # Windows: prefer iconbitmap for .ico
                        window.iconbitmap(chosen)
                    except Exception:
                        # fallback to PhotoImage if iconbitmap fails
                        img = tk.PhotoImage(file=chosen)
                        window.iconphoto(True, img)
                        # keep a reference to avoid GC
                        if not hasattr(window, '_icon_image'):
                            window._icon_image = img
                else:
                    # use PhotoImage for PNG/GIF/JPEG
                    img = tk.PhotoImage(file=chosen)
                    window.iconphoto(True, img)
                    # keep a reference to avoid GC
                    if not hasattr(window, '_icon_image'):
                        window._icon_image = img
                logger.debug("Dialog icon set from: %s", chosen)
            except Exception:
                logger.exception("Failed setting dialog icon from %s", chosen)
    except Exception:
        logger.exception("Unexpected error while setting dialog icon")
