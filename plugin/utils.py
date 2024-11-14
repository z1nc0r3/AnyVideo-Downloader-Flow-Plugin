import re
import os
import zipfile

PLUGIN_ROOT = os.path.dirname(__file__)
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
    ffmpeg_zip = os.path.join(PLUGIN_ROOT, "ffmpeg.zip")
    return not os.path.exists(ffmpeg_zip)


def verify_ffmpeg_binaries():
    ffmpeg_path = os.path.join(PLUGIN_ROOT, "ffmpeg.exe")
    ffprobe_path = os.path.join(PLUGIN_ROOT, "ffprobe.exe")

    return not os.path.exists(ffmpeg_path) or not os.path.exists(ffprobe_path)


def verify_ffmpeg():
    return verify_ffmpeg_zip() and verify_ffmpeg_binaries()


def extract_ffmpeg():
    ffmpeg_zip = os.path.join(PLUGIN_ROOT, "ffmpeg.zip")

    if os.path.exists(ffmpeg_zip):
        try:
            with zipfile.ZipFile(ffmpeg_zip, "r") as zip_ref:
                zip_ref.extractall(os.path.dirname(__file__))
            os.remove(ffmpeg_zip)
        except Exception as _:
            pass
