#!/usr/bin/env python3
"""
Standalone script to download and extract FFmpeg binaries.
Runs in its own process, independent of Flow Launcher.
"""

import os
import sys
import subprocess
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCK_FILE = os.path.join(SCRIPT_DIR, "ffmpeg_setup.lock")
BIN_URL = "https://github.com/z1nc0r3/ffmpeg-binaries/blob/main/ffmpeg-bin.zip?raw=true"
FFMPEG_ZIP = os.path.join(SCRIPT_DIR, "ffmpeg.zip")


def download_and_extract():
    """Download ffmpeg binaries from GitHub and extract them."""
    # Download
    try:
        subprocess.run(
            ["curl", "-L", BIN_URL, "-o", FFMPEG_ZIP],
            check=True,
        )
    except Exception:
        try:
            subprocess.run(
                f'curl -L "{BIN_URL}" -o "{FFMPEG_ZIP}"', shell=True, check=True
            )
        except Exception:
            return False

    if not os.path.exists(FFMPEG_ZIP):
        return False

    # Validate zip
    try:
        with zipfile.ZipFile(FFMPEG_ZIP, "r") as zip_ref:
            members = zip_ref.namelist()
            if not members:
                os.remove(FFMPEG_ZIP)
                return False

            required = ("ffmpeg.exe", "ffprobe.exe")
            missing = [
                exe
                for exe in required
                if not any(os.path.basename(name) == exe for name in members)
            ]
            if missing:
                os.remove(FFMPEG_ZIP)
                return False
    except (zipfile.BadZipFile, Exception):
        if os.path.exists(FFMPEG_ZIP):
            os.remove(FFMPEG_ZIP)
        return False

    # Extract
    try:
        with zipfile.ZipFile(FFMPEG_ZIP, "r") as zip_ref:
            zip_ref.extractall(SCRIPT_DIR)
        os.remove(FFMPEG_ZIP)
    except Exception:
        return False

    return True


def main():
    # Create lock file
    try:
        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            f.write("in-progress")
    except Exception:
        sys.exit(1)

    try:
        download_and_extract()
    finally:
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except Exception:
            pass


if __name__ == "__main__":
    main()
