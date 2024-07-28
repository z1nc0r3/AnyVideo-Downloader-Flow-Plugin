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
from yt_dlp import YoutubeDL


class AnyVideo(FlowLauncher):

    def isValidURL(self, url):
        regex = (
            "((http|https)://)(www.)?"
            + "[a-zA-Z0-9@:%._\\+~#?&//=]"
            + "{1,256}\\.[a-z]"
            + "{2,6}\\b([-a-zA-Z0-9@:%"
            + "._\\+~#?&//=]*)"
        )

        p = re.compile(regex)

        if re.search(p, url):
            return True
        else:
            return False

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

        else:
            try:
                with YoutubeDL() as ydl:
                    info = ydl.extract_info(query, download=False)
            except Exception as e:
                output.append({"Title": f"Error: {e}", "IcoPath": "Images/app.png"})
                return output

            for format in reversed(info["formats"]):
                if format["resolution"] is not None and format["tbr"] is not None:
                    output.append(
                        {
                            "Title": info["title"],
                            "SubTitle": f"Resolution: {format['resolution']}    Bitrate: {format['tbr']}",
                            "IcoPath": "Images/app.png",
                            "JsonRPCAction": {
                                "method": "download",
                                "parameters": [query, f"{format['format_id']}"],
                            },
                        }
                    )

        return output

    def download(self, url, format_id):
        command = f"yt-dlp -f {format_id} {url} -P ~/Downloads --windows-filenames --quiet --progress"
        os.system(command)


if __name__ == "__main__":
    AnyVideo()
