# helper to create a wheel and then run pyinstaller
Set-StrictMode -Version Latest

python -m pip install --upgrade pip
pip install build pyinstaller

# build wheel
python -m build --wheel

# run pyinstaller onefile
pyinstaller --noconfirm --onefile --windowed --name piston Piston.py

Write-Host "Artifacts: dist/*.whl and dist/piston.exe (or dist/piston on *nix)"