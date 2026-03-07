param(
  [string]$pyinstaller = "pyinstaller",
  [switch]$onefile
)

# PowerShell helper to build Windows executable using PyInstaller
Set-StrictMode -Version Latest

Write-Host "Installing build deps..."
python -m pip install --upgrade pip

# If requirements.txt exists, install from it; otherwise install common deps explicitly
$req = Join-Path -Path (Get-Location) -ChildPath 'requirements.txt'
if (Test-Path $req) {
    Write-Host "Installing from requirements.txt"
    pip install -r $req
} else {
    Write-Host "requirements.txt not found; installing common runtime deps"
    pip install pandas openpyxl pytest
}

# Ensure PyInstaller is available
pip install pyinstaller

if ($onefile) {
  Write-Host "Building single-file executable..."
  & $pyinstaller --noconfirm --onefile --windowed --name piston Piston.py
} else {
  Write-Host "Building directory-based bundle (using piston.spec for configuration)..."
  # Note: piston.spec is configured with console=False to hide console window
  if (Test-Path "piston.spec") {
    & $pyinstaller --noconfirm piston.spec
  } else {
    & $pyinstaller --noconfirm --name piston Piston.py
  }
}
}

Write-Host "Build complete. Check 'dist' and 'build' directories."