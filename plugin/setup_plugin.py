#!/usr/bin/env python3
"""
Combined first-run setup: downloads FFmpeg binaries and updates yt-dlp.
Runs in a visible terminal window, independent of Flow Launcher.
"""

import os
import sys
import subprocess
import zipfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_PATH = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "lib"))
LOCK_FILE = os.path.join(SCRIPT_DIR, "plugin_setup.lock")
BIN_URL = "https://github.com/z1nc0r3/ffmpeg-binaries/blob/main/ffmpeg-bin.zip?raw=true"


def is_ffmpeg_needed():
    """Check if FFmpeg binaries are missing or empty."""
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        path = os.path.join(SCRIPT_DIR, name)
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            return True
    return False


def download_ffmpeg():
    """Download, validate, and extract FFmpeg binaries."""
    ffmpeg_zip = os.path.join(SCRIPT_DIR, "ffmpeg.zip")

    try:
        subprocess.run(["curl", "-L", BIN_URL, "-o", ffmpeg_zip], check=True)
    except Exception:
        try:
            subprocess.run(
                f'curl -L "{BIN_URL}" -o "{ffmpeg_zip}"', shell=True, check=True
            )
        except Exception:
            return False

    if not os.path.exists(ffmpeg_zip):
        return False

    # Validate zip
    try:
        if os.path.getsize(ffmpeg_zip) == 0:
            os.remove(ffmpeg_zip)
            return False

        with zipfile.ZipFile(ffmpeg_zip, "r") as zip_ref:
            members = zip_ref.namelist()
            required = ("ffmpeg.exe", "ffprobe.exe")
            missing = [
                exe
                for exe in required
                if not any(os.path.basename(name) == exe for name in members)
            ]
            if missing:
                os.remove(ffmpeg_zip)
                return False

            empty_binaries = [
                info.filename
                for info in zip_ref.infolist()
                if info.filename.lower().endswith(".exe") and info.file_size == 0
            ]
            if empty_binaries:
                os.remove(ffmpeg_zip)
                return False

            zip_ref.extractall(SCRIPT_DIR)

        os.remove(ffmpeg_zip)
    except zipfile.BadZipFile:
        try:
            os.remove(ffmpeg_zip)
        except Exception:
            pass
        return False
    except Exception as e:
        try:
            os.remove(ffmpeg_zip)
        except Exception:
            pass
        return False

    return True


def is_ytdlp_update_needed():
    """Check if yt-dlp needs to be installed/updated (first-run check)."""
    ytdlp_path = os.path.join(LIB_PATH, "yt_dlp")
    update_marker = os.path.join(LIB_PATH, ".ytdlp_last_update")
    
    if not os.path.exists(ytdlp_path):
        return True
    if not os.path.exists(update_marker):
        return True
    
    return False


def update_ytdlp():
    """Update yt-dlp library from PyPI."""

    sys.path.insert(0, SCRIPT_DIR)
    from update_ytdlp import download_ytdlp_from_pypi

    success, _ = download_ytdlp_from_pypi()

    if success:
        update_marker = os.path.join(LIB_PATH, ".ytdlp_last_update")
        os.makedirs(LIB_PATH, exist_ok=True)
        with open(update_marker, "w") as f:
            f.write("updated")
        return True
    else:
        return False


def main():
    print("=" * 50)
    print("AnyVideo Downloader - Plugin Setup")
    print("=" * 50)
    print()

    try:
        with open(LOCK_FILE, "w") as f:
            f.write("in-progress")
    except Exception as e:
        print(f"Failed to create lock file: {e}")
        time.sleep(5)
        sys.exit(1)

    try:
        ffmpeg_ok = True
        ytdlp_ok = True

        if is_ffmpeg_needed():
            ffmpeg_ok = download_ffmpeg()
        else:
            print("FFmpeg binaries already present. Skipping.")

        print()

        if is_ytdlp_update_needed():
            ytdlp_ok = update_ytdlp()
        else:
            print("yt-dlp is up to date. Skipping.")

        print()
        if ffmpeg_ok and ytdlp_ok:
            print("Setup completed successfully!")
        else:
            print("Setup completed with errors. Some components may not work.")
        print("You can close this window and use the plugin now.")
    finally:
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except Exception:
            pass

    time.sleep(5)


if __name__ == "__main__":
    main()
