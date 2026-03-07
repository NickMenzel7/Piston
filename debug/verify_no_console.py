#!/usr/bin/env python
"""
Verify Console Window Configuration

Run this to check if your build is configured correctly.
"""
import os

def check_spec_file():
    """Check if piston.spec has console=False"""
    print("="*60)
    print("Console Window Configuration Check")
    print("="*60)
    
    spec_path = 'piston.spec'
    if not os.path.exists(spec_path):
        print(f"\n❌ ERROR: {spec_path} not found!")
        print("   Make sure you're in the project root directory.")
        return False
    
    print(f"\n✓ Found {spec_path}")
    
    # Read and check console setting
    with open(spec_path, 'r') as f:
        content = f.read()
    
    if 'console=False' in content:
        print("✓ piston.spec has console=False")
        print("\n  This is CORRECT - no console window will appear")
    elif 'console=True' in content:
        print("❌ piston.spec has console=True")
        print("\n  ACTION NEEDED: Change line 39 to: console=False,")
        return False
    else:
        print("⚠ Could not find console= setting in piston.spec")
        return False
    
    return True

def check_logger_config():
    """Check if logger is configured correctly"""
    print("\n" + "="*60)
    print("Logger Configuration Check")
    print("="*60)
    
    piston_path = 'Piston.py'
    if not os.path.exists(piston_path):
        print(f"\n❌ ERROR: {piston_path} not found!")
        return False
    
    print(f"\n✓ Found {piston_path}")
    
    with open(piston_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'PISTON_DEBUG_CONSOLE' in content:
        print("✓ Logger has optional console output")
        print("\n  Console logging only enabled if PISTON_DEBUG_CONSOLE=1")
    else:
        print("⚠ Logger might still output to console")
        print("\n  ACTION NEEDED: Update logger to use PISTON_DEBUG_CONSOLE check")
        return False
    
    return True

def show_build_instructions():
    """Show how to build correctly"""
    print("\n" + "="*60)
    print("How to Build Without Console Window")
    print("="*60)
    
    print("\n1. Clean old builds:")
    print("   Remove-Item -Recurse -Force dist, build")
    
    print("\n2. Build with PyInstaller:")
    print("   pyinstaller --noconfirm piston.spec")
    
    print("\n3. Test the built executable:")
    print("   .\\dist\\piston\\piston.exe")
    
    print("\n" + "="*60)
    print("IMPORTANT NOTES")
    print("="*60)
    
    print("\n⚠  Running 'python Piston.py' will ALWAYS show a console")
    print("   This is Windows behavior - you must run the built .exe")
    
    print("\n✓  After building, run: dist\\piston\\piston.exe")
    print("   Only the GUI window should appear!")

def check_build_exists():
    """Check if there's an existing build"""
    print("\n" + "="*60)
    print("Existing Build Check")
    print("="*60)
    
    exe_path = os.path.join('dist', 'piston', 'piston.exe')
    if os.path.exists(exe_path):
        print(f"\n✓ Found existing build: {exe_path}")
        
        # Check modification time
        import datetime
        spec_time = os.path.getmtime('piston.spec')
        exe_time = os.path.getmtime(exe_path)
        
        spec_date = datetime.datetime.fromtimestamp(spec_time)
        exe_date = datetime.datetime.fromtimestamp(exe_time)
        
        print(f"\n  piston.spec modified: {spec_date}")
        print(f"  piston.exe built:     {exe_date}")
        
        if exe_time < spec_time:
            print("\n  ⚠ WARNING: piston.exe is OLDER than piston.spec")
            print("  ⚠ You need to rebuild!")
            print("\n  ACTION: Run 'pyinstaller --noconfirm piston.spec'")
            return False
        else:
            print("\n  ✓ Build is up to date")
            print("\n  Test it: .\\dist\\piston\\piston.exe")
            return True
    else:
        print(f"\n❌ No build found at: {exe_path}")
        print("\n  ACTION: Run 'pyinstaller --noconfirm piston.spec'")
        return False

def main():
    print("\n" + "="*60)
    print("PISTON CONSOLE WINDOW VERIFICATION")
    print("="*60)
    
    all_good = True
    
    # Check spec file
    if not check_spec_file():
        all_good = False
    
    # Check logger
    if not check_logger_config():
        all_good = False
    
    # Check existing build
    if not check_build_exists():
        all_good = False
    
    # Show instructions
    show_build_instructions()
    
    print("\n" + "="*60)
    if all_good:
        print("✅ CONFIGURATION LOOKS GOOD!")
        print("="*60)
        print("\nIf you still see a console window:")
        print("  1. Make sure you're running the .exe, not python Piston.py")
        print("  2. Try: .\\dist\\piston\\piston.exe")
        print("  3. If it still appears, rebuild: pyinstaller --noconfirm piston.spec")
    else:
        print("⚠ ACTION NEEDED - See above")
        print("="*60)
    
    print("\n")

if __name__ == '__main__':
    main()
