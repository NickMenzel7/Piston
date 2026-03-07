# -*- coding: utf-8 -*-
"""
Update checking and downloading for Piston.

Checks GitHub releases for new versions and handles download/installation.
"""
import os
import sys
import json
import logging
import pathlib
import tempfile
import shutil
import subprocess

logger = logging.getLogger("piston.updater")

# GitHub API endpoint for checking releases
# Your repository: https://github.com/NickMenzel7/Piston
GITHUB_API = "https://api.github.com/repos/NickMenzel7/Piston/releases/latest"


def get_current_version():
    """Read current version from version.txt or return default."""
    try:
        # Try multiple locations for version.txt
        candidates = []
        
        # Check if running from PyInstaller bundle
        if getattr(sys, '_MEIPASS', None):
            candidates.append(os.path.join(sys._MEIPASS, 'version.txt'))
        
        # Check next to executable
        try:
            exe_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)
            candidates.append(os.path.join(exe_dir, 'version.txt'))
        except Exception:
            pass
        
        # Check script directory
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            candidates.append(os.path.join(script_dir, '..', 'version.txt'))
        except Exception:
            pass
        
        # Try each candidate
        for path in candidates:
            try:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        version = f.read().strip()
                        if version:
                            logger.info("Version read from: %s -> %s", path, version)
                            return version
            except Exception:
                continue
        
        # Default fallback
        logger.warning("version.txt not found, using default 1.0.0")
        return "1.0.0"
        
    except Exception:
        logger.exception("Error reading version")
        return "1.0.0"


def check_for_updates(current_version):
    """
    Check GitHub for new releases.
    
    Args:
        current_version: Current version string (e.g., "1.0.0")
    
    Returns:
        dict: {
            'available': bool,
            'version': str,
            'url': str,
            'notes': str,
            'size_mb': float,
            'error': str (optional)
        }
    """
    try:
        # Import requests (included in your requirements.txt already)
        try:
            import requests
        except ImportError:
            logger.warning("requests module not available - update check disabled")
            return {'available': False, 'error': 'requests not installed'}
        
        # Query GitHub API (public, no auth needed)
        try:
            logger.info("Checking for updates (current: %s)...", current_version)
            resp = requests.get(GITHUB_API, timeout=5)
            
            if resp.status_code != 200:
                logger.warning("GitHub API returned status %d", resp.status_code)
                return {'available': False, 'error': f'API returned {resp.status_code}'}
            
            data = resp.json()
            
        except requests.exceptions.Timeout:
            logger.warning("Update check timed out")
            return {'available': False, 'error': 'timeout'}
        except requests.exceptions.ConnectionError:
            logger.warning("Update check failed - no internet connection")
            return {'available': False, 'error': 'no connection'}
        except Exception as e:
            logger.warning("Update check failed: %s", e)
            return {'available': False, 'error': str(e)}
        
        # Parse response
        try:
            latest_version = data.get('tag_name', '').strip().lstrip('v')
            release_notes = data.get('body', 'No release notes available.')
            
            # Find piston.exe asset
            assets = data.get('assets', [])
            exe_asset = None
            for asset in assets:
                if asset.get('name', '').lower() == 'piston.exe':
                    exe_asset = asset
                    break
            
            if not exe_asset:
                logger.warning("No piston.exe found in latest release")
                return {'available': False, 'error': 'No piston.exe in release'}
            
            download_url = exe_asset.get('browser_download_url', '')
            size_bytes = exe_asset.get('size', 0)
            size_mb = size_bytes / (1024 * 1024)
            
            # Compare versions
            if _version_greater(latest_version, current_version):
                logger.info("Update available: %s -> %s", current_version, latest_version)
                return {
                    'available': True,
                    'version': latest_version,
                    'url': download_url,
                    'notes': release_notes,
                    'size_mb': size_mb
                }
            else:
                logger.info("Already up to date: %s", current_version)
                return {'available': False}
            
        except Exception as e:
            logger.exception("Error parsing GitHub response")
            return {'available': False, 'error': f'Parse error: {e}'}
    
    except Exception as e:
        logger.exception("Update check failed")
        return {'available': False, 'error': str(e)}


def _version_greater(v1, v2):
    """
    Compare two semantic version strings.
    
    Examples:
        "1.0.1" > "1.0.0" -> True
        "1.1.0" > "1.0.9" -> True
        "2.0.0" > "1.9.9" -> True
    """
    try:
        # Split into parts and compare numerically
        parts1 = [int(x) for x in v1.split('.')]
        parts2 = [int(x) for x in v2.split('.')]
        
        # Pad to same length
        while len(parts1) < len(parts2):
            parts1.append(0)
        while len(parts2) < len(parts1):
            parts2.append(0)
        
        return parts1 > parts2
        
    except Exception:
        # Fallback to string comparison
        return v1 > v2


def download_update(url, progress_callback=None):
    """
    Download new piston.exe from URL.
    
    Args:
        url: Direct download URL
        progress_callback: Optional function(percent) for progress updates
    
    Returns:
        str: Path to downloaded file, or None if failed
    """
    try:
        import requests
        
        # Download to temp directory
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, 'piston_update.exe')
        
        logger.info("Downloading update from: %s", url)
        
        # Stream download with progress
        with requests.get(url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            
            total_size = int(resp.headers.get('content-length', 0))
            downloaded = 0
            
            with open(temp_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Report progress
                        if progress_callback and total_size > 0:
                            percent = (downloaded / total_size) * 100
                            progress_callback(percent)
        
        # Verify file exists and is reasonable size (>5 MB)
        if os.path.exists(temp_path):
            size = os.path.getsize(temp_path)
            if size < 5 * 1024 * 1024:
                logger.error("Downloaded file too small: %d bytes", size)
                return None
            
            logger.info("Download complete: %s (%d bytes)", temp_path, size)
            return temp_path
        
        return None
        
    except Exception as e:
        logger.exception("Download failed: %s", e)
        return None


def apply_update_and_restart(new_exe_path):
    """
    Replace current piston.exe with new version and restart.
    
    Uses a PowerShell script that runs after this process exits.
    
    Args:
        new_exe_path: Path to downloaded update exe
    """
    try:
        # Get path to current executable
        if getattr(sys, 'frozen', False):
            current_exe = sys.executable
        else:
            # Running from Python - use script path for testing
            current_exe = os.path.abspath(__file__)
        
        backup_exe = current_exe + '.old'
        
        logger.info("Preparing update: %s -> %s", current_exe, new_exe_path)
        
        # Create PowerShell script for post-exit replacement
        ps_script = f"""
# Wait for Piston to exit
Start-Sleep -Seconds 2

# Backup old version (for rollback)
if (Test-Path '{current_exe}') {{
    if (Test-Path '{backup_exe}') {{
        Remove-Item '{backup_exe}' -Force
    }}
    Move-Item -Path '{current_exe}' -Destination '{backup_exe}' -Force
}}

# Install new version
Move-Item -Path '{new_exe_path}' -Destination '{current_exe}' -Force

# Launch new version
Start-Process '{current_exe}'

# Wait before cleanup
Start-Sleep -Seconds 5

# Delete backup if new version launched successfully
if (Test-Path '{backup_exe}') {{
    Remove-Item '{backup_exe}' -Force -ErrorAction SilentlyContinue
}}

# Delete this script
Remove-Item $PSCommandPath -Force -ErrorAction SilentlyContinue
"""
        
        # Write script to temp directory
        script_path = os.path.join(tempfile.gettempdir(), '_piston_update.ps1')
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(ps_script)
        
        logger.info("Update script created: %s", script_path)
        
        # Launch PowerShell script (hidden window)
        subprocess.Popen(
            ['powershell', '-WindowStyle', 'Hidden', '-ExecutionPolicy', 'Bypass', '-File', script_path],
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        
        logger.info("Update script launched - exiting Piston")
        
        # Exit Piston (script will replace and relaunch)
        sys.exit(0)
        
    except Exception as e:
        logger.exception("Failed to apply update")
        raise Exception(f"Update failed: {e}")


def stage_update_for_next_launch(new_exe_path):
    """
    Stage update to be applied on next launch.
    
    Creates a marker file that tells next launch to apply the update.
    
    Args:
        new_exe_path: Path to downloaded update exe
    """
    try:
        # Create staging directory
        staging_dir = os.path.join(pathlib.Path.home(), '.piston', 'updates')
        os.makedirs(staging_dir, exist_ok=True)
        
        # Move update to staging
        staged_path = os.path.join(staging_dir, 'piston_staged.exe')
        shutil.move(new_exe_path, staged_path)
        
        # Create marker file
        marker_path = os.path.join(staging_dir, 'pending_update.txt')
        with open(marker_path, 'w') as f:
            f.write(staged_path)
        
        logger.info("Update staged for next launch: %s", staged_path)
        return True
        
    except Exception as e:
        logger.exception("Failed to stage update")
        return False


def check_for_staged_update():
    """
    Check if there's a staged update from previous session.
    
    Returns:
        str: Path to staged update exe, or None
    """
    try:
        staging_dir = os.path.join(pathlib.Path.home(), '.piston', 'updates')
        marker_path = os.path.join(staging_dir, 'pending_update.txt')
        
        if not os.path.exists(marker_path):
            return None
        
        # Read staged update path
        with open(marker_path, 'r') as f:
            staged_path = f.read().strip()
        
        # Verify staged exe exists
        if os.path.exists(staged_path):
            logger.info("Found staged update: %s", staged_path)
            return staged_path
        
        # Clean up stale marker
        os.remove(marker_path)
        return None
        
    except Exception:
        logger.exception("Error checking for staged update")
        return None


def clear_staged_update():
    """Remove staged update and marker file."""
    try:
        staging_dir = os.path.join(pathlib.Path.home(), '.piston', 'updates')
        marker_path = os.path.join(staging_dir, 'pending_update.txt')
        
        if os.path.exists(marker_path):
            os.remove(marker_path)
        
        staged_path = os.path.join(staging_dir, 'piston_staged.exe')
        if os.path.exists(staged_path):
            os.remove(staged_path)
            
        logger.info("Cleared staged update")
        
    except Exception:
        logger.exception("Error clearing staged update")
