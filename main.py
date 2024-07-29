# Author: Lasith Manujitha
# Github: @z1nc0r3
# Description: A plugin to download videos from lots of websites
# Date: 2024-07-28

import sys, os, re

parent_folder_path = os.path.abspath(os.path.dirname(__file__))
sys.path.append(parent_folder_path)
sys.path.append(os.path.join(parent_folder_path, "lib"))
sys.path.append(os.path.join(parent_folder_path, "plugin"))

from flowlauncher import FlowLauncher
from yt_dlp import YoutubeDL, DownloadError


# Custom YoutubeDL class to exception handling
class CustomYoutubeDL(YoutubeDL):
    def __init__(self, params=None, auto_init=True):
        super().__init__(params, auto_init)
        self.error_message = None

    def report_error(self, message, *args, **kwargs):
        self.error_message = message

    def extract_info(
        self,
        url,
        download=False,
        ie_key=None,
        extra_info=None,
        process=True,
        force_generic_extractor=False,
    ):
        try:
            result = super().extract_info(
                url, download, ie_key, extra_info, process, force_generic_extractor
            )
            return result
        except Exception as e:
            self.error_message = f"Unexpected error: {str(e)}"
            return None


class AnyVideo(FlowLauncher):

    # Check if the input is a valid URL
    def isValidURL(self, url):
        regex = (
            "((http|https)://)(www.)?"
            + "[a-zA-Z0-9@:%._\\+~#?&//=]"
            + "{1,256}\\.[a-z]"
            + "{2,6}\\b([-a-zA-Z0-9@:%"
            + "._\\+~#?&//=]*)"
        )

        p = re.compile(regex)

        return re.match(p, url)

    def query(self, query):
        output = []
        if len(query.strip()) == 0:
            output.append({"Title": "Enter a video URL", "IcoPath": "Images/app.png"})
            return output

        if not self.isValidURL(query):
            output.append(
                {"Title": "Please enter a valid URL", "IcoPath": "Images/app.png"}
            )
            return output

        # Temporary fix for "This request has been blocked due to its TLS fingerprint" when using https for some sites.
        if query.startswith("https://"):
            query = query.replace("https://", "http://")

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format-sort": "res,tbr",
        }

        ydl = CustomYoutubeDL(params=ydl_opts)

        info = ydl.extract_info(query)
        if ydl.error_message:
            output.append(
                {
                    "Title": "Something went wrong!",
                    "SubTitle": ydl.error_message,
                    "IcoPath": "Images/app.png",
                }
            )
            
            return output
        else:
            thumbnail = info.get("thumbnail")

        for format in reversed(info["formats"]):
            if format["resolution"] is not None and format["tbr"] is not None:
                output.append(
                    {
                        "Title": info["title"],
                        "SubTitle": f"Resolution: {format['resolution']}    Bitrate: {format['tbr']}",
                        "IcoPath": thumbnail if thumbnail else "Images/app.png",
                        "JsonRPCAction": {
                            "method": "download",
                            "parameters": [query, f"{format['format_id']}"],
                        },
                    }
                )

        return output

    def download(self, url, format_id):
        command = f"yt-dlp -f {format_id} {url} -P ~/Downloads/AnyDownloader --windows-filenames --quiet --progress --no-mtime --force-overwrites --no-part"
        os.system(command)


if __name__ == "__main__":
    AnyVideo()
