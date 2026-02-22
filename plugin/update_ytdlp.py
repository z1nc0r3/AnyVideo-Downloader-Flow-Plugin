#!/usr/bin/env python3
"""
Standalone script to update yt-dlp library from PyPI.
Runs in its own terminal window, independent of Flow Launcher.
"""

import os
import sys
import json
import shutil
import glob
import zipfile
import time
from urllib.request import urlopen, Request
from urllib.error import URLError

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_PATH = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "lib"))
UPDATE_MARKER = os.path.join(LIB_PATH, ".ytdlp_last_update")
LOCK_FILE = os.path.join(LIB_PATH, ".ytdlp_updating")


def download_ytdlp_from_pypi():
    """Download yt-dlp directly from PyPI."""
    pypi_url = "https://pypi.org/pypi/yt-dlp/json"

    try:
        req = Request(pypi_url, headers={"User-Agent": "AnyVideo-Downloader-Plugin"})
        with urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except URLError as e:
        return False, f"Network error: {e}"
    except Exception as e:
        return False, f"Failed to fetch package info: {e}"

    # Find compatible wheel
    wheel_url = None
    for file_info in data.get("urls", []):
        if file_info.get("filename", "").endswith("-py3-none-any.whl"):
            wheel_url = file_info.get("url")
            break

    if not wheel_url:
        return False, "No compatible wheel found on PyPI"

    # Download wheel
    wheel_path = os.path.join(LIB_PATH, "yt_dlp_temp.whl")
    os.makedirs(LIB_PATH, exist_ok=True)

    try:
        req = Request(wheel_url, headers={"User-Agent": "AnyVideo-Downloader-Plugin"})
        with urlopen(req, timeout=120) as response:
            with open(wheel_path, "wb") as f:
                f.write(response.read())
    except Exception as e:
        if os.path.exists(wheel_path):
            os.remove(wheel_path)
        return False, f"Download failed: {e}"

    # Install using atomic swap to prevent partial-module import crashes.
    # Extract to a staging dir first, then rename into place, so the live
    # yt_dlp directory is never in a half-deleted/half-extracted state.
    staging_dir = os.path.join(LIB_PATH, "_yt_dlp_staging")
    old_ytdlp = os.path.join(LIB_PATH, "yt_dlp")
    backup_ytdlp = os.path.join(LIB_PATH, "_yt_dlp_old")

    try:
        # Clean up any leftover staging/backup dirs from a previous crash
        for d in (staging_dir, backup_ytdlp):
            if os.path.exists(d):
                shutil.rmtree(d)

        # Extract wheel contents into staging directory
        os.makedirs(staging_dir, exist_ok=True)
        with zipfile.ZipFile(wheel_path, "r") as zip_ref:
            zip_ref.extractall(staging_dir)

        new_ytdlp = os.path.join(staging_dir, "yt_dlp")
        if not os.path.isdir(new_ytdlp):
            shutil.rmtree(staging_dir)
            os.remove(wheel_path)
            return False, "Wheel did not contain yt_dlp package"

        # Atomic swap: old → backup, staging → live
        if os.path.exists(old_ytdlp):
            os.rename(old_ytdlp, backup_ytdlp)
        os.rename(new_ytdlp, old_ytdlp)

        # Move dist-info from staging to lib/
        for item in os.listdir(staging_dir):
            src = os.path.join(staging_dir, item)
            dst = os.path.join(LIB_PATH, item)
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            elif os.path.exists(dst):
                os.remove(dst)
            os.rename(src, dst)

        # Remove old dist-info directories
        for dist_info in glob.glob(os.path.join(LIB_PATH, "yt_dlp-*.dist-info")):
            shutil.rmtree(dist_info)

        # Clean up backup, staging, and wheel
        if os.path.exists(backup_ytdlp):
            shutil.rmtree(backup_ytdlp)
        if os.path.exists(staging_dir):
            shutil.rmtree(staging_dir)
        os.remove(wheel_path)
    except Exception as e:
        # Rollback: if the live dir was moved to backup but new didn't land, restore
        if os.path.exists(backup_ytdlp) and not os.path.exists(old_ytdlp):
            os.rename(backup_ytdlp, old_ytdlp)
        for d in (staging_dir, backup_ytdlp):
            if os.path.exists(d):
                shutil.rmtree(d, ignore_errors=True)
        return False, f"Installation failed: {e}"

    return True, data.get("info", {}).get("version", "unknown")


def main():
    try:
        os.makedirs(LIB_PATH, exist_ok=True)
        with open(LOCK_FILE, "w") as f:
            f.write("updating")
    except Exception as e:
        time.sleep(5)
        sys.exit(1)

    try:
        success, _ = download_ytdlp_from_pypi()

        if success:
            with open(UPDATE_MARKER, "w") as f:
                f.write("updated")
                
    finally:
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except Exception:
            # Ignore errors during lock-file cleanup; failure to remove
            # the lock file is non-fatal and should not affect the user.
            pass

    time.sleep(5)


if __name__ == "__main__":
    main()
