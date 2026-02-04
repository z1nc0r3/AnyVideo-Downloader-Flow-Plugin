import re
import os
import zipfile
import sys
import subprocess
from datetime import datetime, timedelta

PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))
LIB_PATH = os.path.abspath(os.path.join(PLUGIN_ROOT, "..", "lib"))
FFMPEG_SETUP_LOCK = os.path.join(PLUGIN_ROOT, "ffmpeg_setup.lock")
URL_REGEX = (
    "((http|https)://)(www.)?"
    + "[a-zA-Z0-9@:%._\\+~#?&//=]"
    + "{1,256}\\.[a-z]"
    + "{2,6}\\b([-a-zA-Z0-9@:%"
    + "._\\+~#?&//=]*)"
)


def is_valid_url(url: str) -> bool:
    """
    Check if the given URL is valid based on a predefined regex pattern.

    Args:
        url (str): The URL string to validate.

    Returns:
        bool: True if the URL matches the regex pattern, False otherwise.
    """

    return bool(re.match(URL_REGEX, url))


def sort_by_resolution(formats):
    """
    Sorts a list of video formats by their resolution in descending order.

    Returns:
        list of dict: The list of video formats sorted by resolution in descending order.
                      Audio-only formats are considered to have the lowest resolution.
    """

    def resolution_to_tuple(resolution):
        if resolution == "audio only":
            return (0, 0)
        return tuple(map(int, resolution.split("x")))

    return sorted(
        formats, key=lambda x: resolution_to_tuple(x["resolution"]), reverse=True
    )


def sort_by_tbr(formats):
    """
    Sort a list of video formats by their 'tbr' (total bitrate) in descending order.

    Returns:
        list: The input list sorted by the 'tbr' value in descending order.
    """
    return sorted(formats, key=lambda x: x["tbr"], reverse=True)


def sort_by_fps(formats):
    """
    Sort a list of video formats by frames per second (fps) in descending order.

    Returns:
        list of dict: The list of video formats sorted by fps in descending order.
                      Formats with None fps values are placed at the end.
    """
    return sorted(
        formats,
        key=lambda x: (
            x["fps"] is None,
            -x["fps"] if x["fps"] is not None else float("-inf"),
        ),
    )


def sort_by_size(formats):
    """
    Sort a list of video formats by their file size in descending order.

    Returns:
        list of dict: The list of video formats sorted by file size in
                      descending order. Formats with no file size information
                      (None) are placed at the end of the list.
    """
    return sorted(
        formats,
        key=lambda x: (
            x["filesize"] is None,
            -x["filesize"] if x["filesize"] is not None else float("-inf"),
        ),
    )


def _is_valid_executable(path: str) -> bool:
    """
    Returns True when the given path points to a non-empty executable file.
    """
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 0
    except OSError:
        return False


def verify_ffmpeg_zip(return_reason: bool = False):
    """
    Checks if a valid ffmpeg.zip file exists in the plugin directory.

    Returns:
        Union[bool, Tuple[bool, Optional[str]]]: Validation status (and optional reason when
        return_reason=True).
    """
    ffmpeg_zip = os.path.join(PLUGIN_ROOT, "ffmpeg.zip")
    build = (
        (lambda ok, reason=None: (ok, reason))
        if return_reason
        else (lambda ok, _reason=None: ok)
    )

    if not os.path.exists(ffmpeg_zip):
        return build(False, "FFmpeg zip is missing.")

    try:
        if os.path.getsize(ffmpeg_zip) == 0:
            return build(False, "Downloaded FFmpeg archive is empty.")
    except OSError:
        return build(False, "Failed to read FFmpeg archive.")

    try:
        with zipfile.ZipFile(ffmpeg_zip, "r") as zip_ref:
            members = zip_ref.namelist()
            if not members:
                return build(False, "Downloaded FFmpeg archive is empty.")

            required = ("ffmpeg.exe", "ffprobe.exe")
            missing = [
                exe
                for exe in required
                if not any(os.path.basename(name) == exe for name in members)
            ]
            if missing:
                return build(False, f"FFmpeg archive is missing {', '.join(missing)}.")

            empty_binaries = [
                info.filename
                for info in zip_ref.infolist()
                if info.filename.lower().endswith(".exe") and info.file_size == 0
            ]
            if empty_binaries:
                return build(
                    False,
                    f"FFmpeg archive contains empty binaries: {', '.join(empty_binaries)}.",
                )
    except zipfile.BadZipFile:
        return build(False, "Downloaded FFmpeg archive is corrupted.")
    except Exception:
        return build(False, "Failed to read FFmpeg archive.")

    return build(True, None)


def verify_ffmpeg_binaries(return_reason: bool = False):
    """
    Verifies the presence of FFmpeg and FFprobe binaries.
    This function checks if the FFmpeg and FFprobe binaries are present in the
    plugin's root directory.
    Returns:
        bool | tuple[bool, str | None]: True when binaries are found (and reason when requested).
    """
    ffmpeg_path = os.path.join(PLUGIN_ROOT, "ffmpeg.exe")
    ffprobe_path = os.path.join(PLUGIN_ROOT, "ffprobe.exe")
    build = (
        (lambda ok, reason=None: (ok, reason))
        if return_reason
        else (lambda ok, _reason=None: ok)
    )
    ffmpeg_ok = _is_valid_executable(ffmpeg_path)
    ffprobe_ok = _is_valid_executable(ffprobe_path)
    issues = []

    if not ffmpeg_ok:
        if os.path.exists(ffmpeg_path):
            issues.append("ffmpeg.exe is empty or unreadable.")
        else:
            issues.append("ffmpeg.exe is missing.")

    if not ffprobe_ok:
        if os.path.exists(ffprobe_path):
            issues.append("ffprobe.exe is empty or unreadable.")
        else:
            issues.append("ffprobe.exe is missing.")

    if ffmpeg_ok and ffprobe_ok:
        return build(True, None)

    reason = (
        " ".join(issues)
        if issues
        else "FFmpeg/FFprobe executables are missing or empty."
    )
    return build(False, reason)


def get_binaries_paths():
    """
    Determines the path to the ffmpeg binaries.

    Returns:
        str: The directory path of the current file if ffmpeg binaries are verified,
             otherwise None.
    """
    if verify_ffmpeg_binaries():
        return os.path.dirname(__file__)
    return None


def verify_ffmpeg():
    """
    Verify the presence and integrity of FFmpeg.

    This function checks if the FFmpeg zip file and binaries are present and valid.
    It returns (True, None) if either the zip file or binaries are verified successfully,
    otherwise (False, <reason>) describing the failure.

    Returns:
        tuple[bool, str | None]: Validation status and reason when invalid.
    """
    if os.path.exists(FFMPEG_SETUP_LOCK):
        return False, "Please wait. FFmpeg setup in progress."

    binaries_ok, binaries_reason = verify_ffmpeg_binaries(return_reason=True)
    if binaries_ok:
        return True, None

    zip_ok, zip_reason = verify_ffmpeg_zip(return_reason=True)
    if zip_ok:
        return True, None

    return False, binaries_reason or zip_reason or "FFmpeg binaries not found."


def extract_ffmpeg():
    """
    Extracts the ffmpeg.zip file located in the plugin root directory.
    This function checks if the ffmpeg.zip file exists in the plugin root directory.
    If it exists, it extracts the contents of the zip file to the directory of the
    current script and then removes the zip file.
    Note:
        If the archive is missing or invalid, the function returns False with a reason.
    Raises:
        None
    """
    ffmpeg_zip = os.path.join(PLUGIN_ROOT, "ffmpeg.zip")

    if not os.path.exists(ffmpeg_zip):
        binaries_ok, binaries_reason = verify_ffmpeg_binaries(return_reason=True)
        if binaries_ok:
            return True, None
        return (
            False,
            binaries_reason or "FFmpeg archive missing and binaries not present.",
        )

    zip_ok, zip_reason = verify_ffmpeg_zip(return_reason=True)
    if not zip_ok:
        try:
            os.remove(ffmpeg_zip)
        except Exception:
            pass
        return False, zip_reason

    try:
        with zipfile.ZipFile(ffmpeg_zip, "r") as zip_ref:
            zip_ref.extractall(os.path.dirname(__file__))
        os.remove(ffmpeg_zip)
    except Exception:
        return False, "Failed to extract FFmpeg archive."

    binaries_ok, binaries_reason = verify_ffmpeg_binaries(return_reason=True)
    if not binaries_ok:
        return False, binaries_reason

    return True, None


def check_ytdlp_update_needed(check_interval_days=5):
    """
    Check if yt-dlp library update is needed based on the last update timestamp.

    Args:
        check_interval_days (int): Number of days between update checks.

    Returns:
        bool: True if update is needed, False otherwise.
    """

    # Path to yt-dlp package in lib folder
    lib_ytdlp_path = os.path.join(LIB_PATH, "yt_dlp")
    update_marker = os.path.join(LIB_PATH, ".ytdlp_last_update")

    # If yt-dlp doesn't exist in lib, update is needed
    if not os.path.exists(lib_ytdlp_path):
        return True

    # Check the update marker file
    if os.path.exists(update_marker):
        try:
            last_update = datetime.fromtimestamp(os.path.getmtime(update_marker))
            if datetime.now() - last_update < timedelta(days=check_interval_days):
                return False
        except Exception:
            # If we can't read the marker, assume update is needed
            return True

    return True


def update_ytdlp_library():
    """
    Launch the yt-dlp update script in a separate terminal window.
    The script runs independently so FL can close without interrupting the update.

    Returns:
        tuple: (success: bool, message: str)
    """

    update_script = os.path.join(PLUGIN_ROOT, "update_ytdlp.py")

    if not os.path.exists(update_script):
        return False, "Update script not found"

    try:
        # Launch script in a new console window, detached from parent process
        creationflags = (
            subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
        )

        subprocess.Popen(
            [sys.executable, update_script],
            creationflags=creationflags,
            close_fds=True,
            start_new_session=True,
        )

        return True, "Update started in separate window"
    except Exception as e:
        return False, f"Failed to launch updater: {str(e)}"


def skip_ytdlp_update():
    """
    Skip the yt-dlp update check by creating/updating the marker file.
    This allows users to postpone the update and use the existing bundled version.

    Returns:
        tuple: (success: bool, message: str)
    """
    update_marker = os.path.join(LIB_PATH, ".ytdlp_last_update")

    try:
        os.makedirs(LIB_PATH, exist_ok=True)
        with open(update_marker, "w") as f:
            f.write("skipped")
        return True, "Update skipped. Will check again in 5 days."
    except Exception as e:
        return False, f"Failed to skip update: {str(e)}"
