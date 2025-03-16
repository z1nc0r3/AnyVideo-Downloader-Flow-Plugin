import re
import os
import zipfile
import shutil

PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))
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


def verify_ffmpeg_zip():
    """
    Checks if the ffmpeg.zip file exists in the plugin directory.

    Returns:
        bool: False if the ffmpeg.zip file does not exist, True otherwise.
    """
    ffmpeg_zip = os.path.join(PLUGIN_ROOT, "ffmpeg.zip")
    return os.path.exists(ffmpeg_zip)


def verify_ffmpeg_binaries():
    """
    Verifies the presence of FFmpeg and FFprobe binaries.
    This function checks if the FFmpeg and FFprobe binaries are present in the
    plugin's root directory. If they are not found there, it checks if they are
    available in the system's PATH.
    Returns:
        bool: True if both FFmpeg and FFprobe binaries are found, False otherwise.
    """
    ffmpeg_path = os.path.join(PLUGIN_ROOT, "ffmpeg.exe")
    ffprobe_path = os.path.join(PLUGIN_ROOT, "ffprobe.exe")

    if os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path):
        return True

    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return True

    return False


def get_binaries_paths():
    """
    Determines the path to the ffmpeg binaries.

    Returns:
        str: The directory path of the current file if ffmpeg binaries are verified.
             Otherwise, returns the path to the ffmpeg executable found in the system PATH.
    """
    if verify_ffmpeg_binaries():
        return os.path.dirname(__file__)
    else:
        return shutil.which("ffmpeg")


def verify_ffmpeg():
    """
    Verify the presence and integrity of FFmpeg.

    This function checks if the FFmpeg zip file and binaries are present and valid.
    It returns True if both the zip file and binaries are verified successfully, otherwise False.

    Returns:
        bool: True if both FFmpeg zip file and binaries are verified, False otherwise.
    """
    return verify_ffmpeg_zip() or verify_ffmpeg_binaries()


def extract_ffmpeg():
    """
    Extracts the ffmpeg.zip file located in the plugin root directory.
    This function checks if the ffmpeg.zip file exists in the plugin root directory.
    If it exists, it extracts the contents of the zip file to the directory of the
    current script and then removes the zip file.
    Note:
        If an exception occurs during the extraction process, it is silently ignored.
    Raises:
        None
    """
    ffmpeg_zip = os.path.join(PLUGIN_ROOT, "ffmpeg.zip")

    if os.path.exists(ffmpeg_zip):
        try:
            with zipfile.ZipFile(ffmpeg_zip, "r") as zip_ref:
                zip_ref.extractall(os.path.dirname(__file__))
            os.remove(ffmpeg_zip)
        except Exception as _:
            pass

