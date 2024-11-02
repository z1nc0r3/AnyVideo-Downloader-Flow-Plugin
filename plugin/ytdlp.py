from yt_dlp import YoutubeDL


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
