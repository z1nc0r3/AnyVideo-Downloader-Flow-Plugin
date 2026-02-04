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


def main():
    try:
        os.makedirs(LIB_PATH, exist_ok=True)
        with open(LOCK_FILE, "w") as f:
            f.write("updating")
    except Exception as e:
        time.sleep(5)
        sys.exit(1)

    try:
        success, result = download_ytdlp_from_pypi()

        if success:
            with open(UPDATE_MARKER, "w") as f:
                f.write("updated")
            print(f"Success! Updated to version {result}")
        else:
            print(f"Update failed: {result}")
    finally:
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except Exception:
            pass

    time.sleep(5)


if __name__ == "__main__":
    main()
