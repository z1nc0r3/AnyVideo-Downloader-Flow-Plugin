"""Tests for plugin/main.py helper behavior."""

import main


class TestBuildFormats:
    def test_direct_unknown_format_fallback(self):
        info = {
            "direct": True,
            "formats": [
                {
                    "format_id": "mp4",
                    "url": "https://example.com/video.mp4",
                    "ext": "mp4",
                    "resolution": None,
                    "tbr": None,
                    "filesize_approx": None,
                    "vcodec": None,
                    "format": "mp4 - unknown",
                }
            ],
        }

        formats = main._build_formats(info)

        assert formats == [
            {
                "format_id": "mp4",
                "resolution": "unknown",
                "filesize": None,
                "tbr": None,
                "fps": None,
                "width": None,
                "height": None,
                "vcodec": None,
                "acodec": None,
                "ext": "mp4",
            }
        ]

    def test_direct_unknown_fallback_only_when_strict_formats_missing(self):
        info = {
            "formats": [
                {
                    "format_id": "low-info",
                    "url": "https://example.com/low.mp4",
                    "ext": "mp4",
                },
                {
                    "format_id": "720p",
                    "resolution": "1280x720",
                    "tbr": 1200,
                    "ext": "mp4",
                },
            ],
        }

        formats = main._build_formats(info)

        assert [format["format_id"] for format in formats] == ["720p"]
