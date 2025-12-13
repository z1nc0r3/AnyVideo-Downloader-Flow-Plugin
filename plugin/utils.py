import re
import os
import zipfile

PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))
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
        bool | tuple[bool, str | None]: Validation status (and optional reason when
        return_reason=True).
    """
    ffmpeg_zip = os.path.join(PLUGIN_ROOT, "ffmpeg.zip")
    if not os.path.exists(ffmpeg_zip):
        result = (False, "FFmpeg zip is missing.")
        return result if return_reason else result[0]

    try:
        if os.path.getsize(ffmpeg_zip) == 0:
            result = (False, "Downloaded FFmpeg archive is empty.")
            return result if return_reason else result[0]
    except OSError:
        result = (False, "Failed to read FFmpeg archive.")
        return result if return_reason else result[0]

    try:
        with zipfile.ZipFile(ffmpeg_zip, "r") as zip_ref:
            members = zip_ref.namelist()
            if not members:
                result = (False, "Downloaded FFmpeg archive is empty.")
                return result if return_reason else result[0]

            required = ("ffmpeg.exe", "ffprobe.exe")
            missing = [
                exe for exe in required if not any(name.endswith(exe) for name in members)
            ]
            if missing:
                result = (
                    False,
                    f"FFmpeg archive is missing {', '.join(missing)}.",
                )
                return result if return_reason else result[0]

            empty_binaries = [
                info.filename
                for info in zip_ref.infolist()
                if info.filename.lower().endswith(".exe") and info.file_size == 0
            ]
            if empty_binaries:
                result = (
                    False,
                    f"FFmpeg archive contains empty binaries: {', '.join(empty_binaries)}.",
                )
                return result if return_reason else result[0]
    except zipfile.BadZipFile:
        result = (False, "Downloaded FFmpeg archive is corrupted.")
        return result if return_reason else result[0]
    except Exception:
        result = (False, "Failed to read FFmpeg archive.")
        return result if return_reason else result[0]

    result = (True, None)
    return result if return_reason else result[0]


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
    issues = []

    if not _is_valid_executable(ffmpeg_path):
        if os.path.exists(ffmpeg_path):
            issues.append("ffmpeg.exe is empty or unreadable.")
        else:
            issues.append("ffmpeg.exe is missing.")

    if not _is_valid_executable(ffprobe_path):
        if os.path.exists(ffprobe_path):
            issues.append("ffprobe.exe is empty or unreadable.")
        else:
            issues.append("ffprobe.exe is missing.")

    if _is_valid_executable(ffmpeg_path) and _is_valid_executable(ffprobe_path):
        result = (True, None)
        return result if return_reason else result[0]

    reason = " ".join(issues) if issues else "FFmpeg/FFprobe executables are missing or empty."
    result = (False, reason)
    return result if return_reason else result[0]


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
        return True, None

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
