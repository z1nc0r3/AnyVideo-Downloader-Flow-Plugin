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
LAST_CHECK_MARKER = os.path.join(LIB_PATH, ".ytdlp_last_check")
SUCCESS_MARKER = os.path.join(LIB_PATH, ".ytdlp_last_successful_update")
LEGACY_UPDATE_MARKER = os.path.join(LIB_PATH, ".ytdlp_last_update")
LOCK_FILE = os.path.join(LIB_PATH, ".ytdlp_updating")
TEMP_EXTRACT_DIR = os.path.join(LIB_PATH, "_yt_dlp_update")
BACKUP_DIR = os.path.join(LIB_PATH, "_yt_dlp_backup")


def _safe_extract_zip(zip_ref, destination):
    """Extract a zip file only when every member stays inside destination."""
    destination = os.path.abspath(destination)

    for member in zip_ref.infolist():
        member_path = os.path.abspath(os.path.join(destination, member.filename))
        try:
            is_safe = os.path.commonpath([destination, member_path]) == destination
        except ValueError:
            is_safe = False
        if not is_safe:
            raise ValueError(f"Unsafe archive member path: {member.filename}")

    zip_ref.extractall(destination)


def _remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)


def _managed_ytdlp_paths(base_path):
    paths = [os.path.join(base_path, "yt_dlp")]
    paths.extend(glob.glob(os.path.join(base_path, "yt_dlp-*.dist-info")))
    paths.extend(glob.glob(os.path.join(base_path, "yt_dlp-*.data")))
    return paths


def _install_from_temp(temp_dir):
    package_init = os.path.join(temp_dir, "yt_dlp", "__init__.py")
    if not os.path.isfile(package_init):
        return False, "Downloaded wheel does not contain yt_dlp package"

    for path in (BACKUP_DIR,):
        if os.path.exists(path):
            shutil.rmtree(path)
    os.makedirs(BACKUP_DIR, exist_ok=True)

    moved_old = []
    moved_new = []

    try:
        for old_path in _managed_ytdlp_paths(LIB_PATH):
            if not os.path.exists(old_path):
                continue
            backup_path = os.path.join(BACKUP_DIR, os.path.basename(old_path))
            shutil.move(old_path, backup_path)
            moved_old.append((backup_path, old_path))

        for new_path in _managed_ytdlp_paths(temp_dir):
            if not os.path.exists(new_path):
                continue
            target_path = os.path.join(LIB_PATH, os.path.basename(new_path))
            shutil.move(new_path, target_path)
            moved_new.append(target_path)

        if not os.path.isfile(os.path.join(LIB_PATH, "yt_dlp", "__init__.py")):
            raise RuntimeError("Installed yt_dlp package is incomplete")

        shutil.rmtree(BACKUP_DIR)
        return True, None
    except Exception as e:
        for new_path in moved_new:
            try:
                _remove_path(new_path)
            except Exception:
                pass

        for backup_path, original_path in reversed(moved_old):
            try:
                if os.path.exists(backup_path) and not os.path.exists(original_path):
                    shutil.move(backup_path, original_path)
            except Exception:
                pass

        try:
            if os.path.exists(BACKUP_DIR):
                shutil.rmtree(BACKUP_DIR)
        except Exception:
            pass

        return False, f"Installation failed: {e}"


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
        if os.path.exists(TEMP_EXTRACT_DIR):
            shutil.rmtree(TEMP_EXTRACT_DIR)
        os.makedirs(TEMP_EXTRACT_DIR, exist_ok=True)

        with zipfile.ZipFile(wheel_path, "r") as zip_ref:
            _safe_extract_zip(zip_ref, TEMP_EXTRACT_DIR)

        os.remove(wheel_path)
        ok, message = _install_from_temp(TEMP_EXTRACT_DIR)
        if not ok:
            return False, message
    except Exception as e:
        return False, f"Installation failed: {e}"
    finally:
        try:
            if os.path.exists(TEMP_EXTRACT_DIR):
                shutil.rmtree(TEMP_EXTRACT_DIR)
        except Exception:
            pass

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
            for marker, value in (
                (LAST_CHECK_MARKER, "checked"),
                (SUCCESS_MARKER, "updated"),
                (LEGACY_UPDATE_MARKER, "updated"),
            ):
                with open(marker, "w") as f:
                    f.write(value)

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
