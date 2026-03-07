Piston - Alpha release

This repository contains the Piston NPI planning GUI and core scheduling logic.

Run:

python Piston.py

Building a single-file executable (Windows)

Requirements:
- Python 3.8+ installed
- pip

Steps (PowerShell):

1. Create and activate a virtualenv (recommended):
   python -m venv .venv
   .\\.venv\\Scripts\\Activate.ps1

2. Install PyInstaller and runtime deps
   python -m pip install --upgrade pip
   pip install -r requirements.txt pyinstaller

   Note: If you get the error "Could not open requirements file" the included PowerShell helper will automatically install a minimal set of runtime packages (pandas, openpyxl, pytest). You can also create a requirements.txt yourself.

3. Build single-file executable:
   .\\build_windows.ps1 -onefile

4. Output executable will be at `dist\\piston.exe`.

Building a single-file executable (Linux/macOS)

1. Create and activate venv (optional):
   python -m venv .venv
   source .venv/bin/activate

2. Install PyInstaller:
   python -m pip install --upgrade pip
   pip install pyinstaller

3. Build:
   ./build_unix.sh onefile

4. Output executable will be at `dist/piston`.

Troubleshooting
- If the build fails with missing import errors, run the debug build command (Windows):
  pyinstaller --noconfirm --onefile --console --clean --log-level DEBUG --name piston `
    --add-data "plans;plans" --add-data "Icon;Icon" `
    --hidden-import=pandas._libs.tslibs.timedeltas `
    --hidden-import=pandas._libs.tslibs.timestamps `
    Piston.py

- Attach the PyInstaller build log or paste the Action run logs and I will update the spec and hooks to include missing modules or data.

