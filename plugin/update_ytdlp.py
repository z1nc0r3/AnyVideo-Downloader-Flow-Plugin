#!/usr/bin/env python3
"""
Standalone script to update yt-dlp library from PyPI and the yt-dlp binary.
Runs in its own terminal window, independent of Flow Launcher.
"""

import os
import sys
import json
import shutil
import glob
import zipfile
import time
import subprocess
from urllib.request import urlopen, Request
from urllib.error import URLError

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_PATH = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "lib"))
EXE_PATH = os.path.join(SCRIPT_DIR, "yt-dlp.exe")
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

    # Install
    try:
        old_ytdlp = os.path.join(LIB_PATH, "yt_dlp")
        if os.path.exists(old_ytdlp):
            shutil.rmtree(old_ytdlp)

        for dist_info in glob.glob(os.path.join(LIB_PATH, "yt_dlp-*.dist-info")):
            shutil.rmtree(dist_info)

        with zipfile.ZipFile(wheel_path, "r") as zip_ref:
            zip_ref.extractall(LIB_PATH)

        os.remove(wheel_path)
    except Exception as e:
        return False, f"Installation failed: {e}"

    return True, data.get("info", {}).get("version", "unknown")


def update_ytdlp_binary():
    """Update the yt-dlp binary using its built-in self-update (-U flag)."""
    if not os.path.isfile(EXE_PATH):
        return False, "yt-dlp.exe not found"

    try:
        result = subprocess.run(
            [EXE_PATH, "-U"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return True, "Binary updated successfully"
        return False, f"Binary update failed: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "Binary update timed out"
    except Exception as e:
        return False, f"Binary update error: {e}"


def main():
    try:
        os.makedirs(LIB_PATH, exist_ok=True)
        with open(LOCK_FILE, "w") as f:
            f.write("updating")
    except Exception as e:
        time.sleep(5)
        sys.exit(1)

    try:
        # Update yt-dlp library from PyPI
        lib_success, lib_result = download_ytdlp_from_pypi()

        if lib_success:
            print(f"Library: Updated to version {lib_result}")
        else:
            print(f"Library: Update failed: {lib_result}")

        # Update yt-dlp binary using self-update
        bin_success, bin_result = update_ytdlp_binary()

        if bin_success:
            print(f"Binary: {bin_result}")
        else:
            print(f"Binary update skipped: {bin_result}")

        # Mark as updated if at least the library update succeeded
        if lib_success:
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
