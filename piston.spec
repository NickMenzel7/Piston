# -*- mode: python ; coding: utf-8 -*-
import os

# Build datas list without relying on Tree (compatibility across PyInstaller versions).
# Include the embedded folder and embedded/plans (mapped to 'plans' at runtime) when present.
datas_list = []
if os.path.isdir('embedded'):
    datas_list.append(('embedded', 'embedded'))
plans_src = os.path.join('embedded', 'plans')
if os.path.isdir(plans_src):
    # Map embedded/plans -> plans at runtime so code referencing module_dir/plans still works
    datas_list.append((plans_src, 'plans'))

# Include Icon directory for runtime window icons
if os.path.isdir('Icon'):
    datas_list.append(('Icon', 'Icon'))

# Include version.txt for update checking
if os.path.isfile('version.txt'):
    datas_list.append(('version.txt', '.'))

a = Analysis(
    ['Piston.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='piston',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Changed to False - no console window will appear
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Icon/piston.ico' if os.path.exists('Icon/piston.ico') else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='piston',
)
