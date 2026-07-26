"""Tests for plugin/main.py helper behavior."""

import main


class TestCookieFileSettings:
    def test_disabled_cookie_file_returns_empty_values(self):
        cookie_file_path, cookie_error = main._resolve_cookie_file_settings(
            {"use_cookie_file": False, "cookie_file_path": "missing.txt"}
        )

        assert cookie_file_path == ""
        assert cookie_error == ""

    def test_enabled_cookie_file_requires_path(self):
        cookie_file_path, cookie_error = main._resolve_cookie_file_settings(
            {"use_cookie_file": True, "cookie_file_path": ""}
        )

        assert cookie_file_path == ""
        assert "no cookies.txt path" in cookie_error

    def test_enabled_cookie_file_requires_existing_file(self, tmp_path):
        missing_cookie_file = tmp_path / "missing-cookies.txt"

        cookie_file_path, cookie_error = main._resolve_cookie_file_settings(
            {
                "use_cookie_file": True,
                "cookie_file_path": str(missing_cookie_file),
            }
        )

        assert cookie_file_path == ""
        assert str(missing_cookie_file) in cookie_error

    def test_enabled_cookie_file_returns_normalized_path(self, tmp_path):
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

        cookie_file_path, cookie_error = main._resolve_cookie_file_settings(
            {"use_cookie_file": True, "cookie_file_path": str(cookie_file)}
        )

        assert cookie_file_path == str(cookie_file)
        assert cookie_error == ""


class TestYdlOptions:
    def test_build_ydl_opts_without_cookie_file(self, monkeypatch):
        monkeypatch.setattr(main, "_node_js_runtime_available", lambda: False)
        ydl_opts = main._build_ydl_opts()

        assert ydl_opts["quiet"] is True
        assert ydl_opts["noplaylist"] is True
        assert ydl_opts["ignore_no_formats_error"] is True
        assert "cookiefile" not in ydl_opts
        assert "js_runtimes" not in ydl_opts

    def test_build_ydl_opts_with_cookie_file(self, monkeypatch):
        monkeypatch.setattr(main, "_node_js_runtime_available", lambda: False)
        ydl_opts = main._build_ydl_opts("C:\\cookies.txt")

        assert ydl_opts["cookiefile"] == "C:\\cookies.txt"

    def test_build_ydl_opts_uses_node_when_available(self, monkeypatch):
        monkeypatch.setattr(main, "_node_js_runtime_available", lambda: True)
        ydl_opts = main._build_ydl_opts()

        assert ydl_opts["js_runtimes"] == {"node": {}}


class TestDownloadCommand:
    def test_download_adds_cookie_file_argument(self, monkeypatch, tmp_path):
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
        captured = {}

        class CompletedProcess:
            returncode = 0

        def fake_run(command):
            captured["command"] = command
            return CompletedProcess()

        monkeypatch.setattr(main, "check_ytdlp_version", lambda interval: False)
        monkeypatch.setattr(main, "get_binaries_paths", lambda: "")
        monkeypatch.setattr(main, "_node_js_runtime_available", lambda: False)
        monkeypatch.setattr(main.subprocess, "run", fake_run)
        monkeypatch.setattr(main, "log_message", lambda message: None)

        main.download(
            "https://example.com/video",
            "18",
            str(tmp_path),
            "mp4",
            "mp3",
            False,
            False,
            True,
            str(cookie_file),
        )

        command = captured["command"]
        assert "--cookies" in command
        assert command[command.index("--cookies") + 1] == str(cookie_file)

    def test_download_omits_missing_cookie_file_argument(self, monkeypatch, tmp_path):
        missing_cookie_file = tmp_path / "missing-cookies.txt"
        captured = {}

        class CompletedProcess:
            returncode = 0

        def fake_run(command):
            captured["command"] = command
            return CompletedProcess()

        monkeypatch.setattr(main, "check_ytdlp_version", lambda interval: False)
        monkeypatch.setattr(main, "get_binaries_paths", lambda: "")
        monkeypatch.setattr(main, "_node_js_runtime_available", lambda: False)
        monkeypatch.setattr(main.subprocess, "run", fake_run)
        monkeypatch.setattr(main, "log_message", lambda message: None)

        main.download(
            "https://example.com/video",
            "18",
            str(tmp_path),
            "mp4",
            "mp3",
            False,
            False,
            True,
            str(missing_cookie_file),
        )

        assert "--cookies" not in captured["command"]

    def test_download_adds_node_js_runtime_argument(self, monkeypatch, tmp_path):
        captured = {}

        class CompletedProcess:
            returncode = 0

        def fake_run(command):
            captured["command"] = command
            return CompletedProcess()

        monkeypatch.setattr(main, "check_ytdlp_version", lambda interval: False)
        monkeypatch.setattr(main, "get_binaries_paths", lambda: "")
        monkeypatch.setattr(main, "_node_js_runtime_available", lambda: True)
        monkeypatch.setattr(main.subprocess, "run", fake_run)
        monkeypatch.setattr(main, "log_message", lambda message: None)

        main.download(
            "https://example.com/video",
            "18",
            str(tmp_path),
            "mp4",
            "mp3",
            False,
            False,
            True,
            "",
        )

        command = captured["command"]
        assert "--js-runtimes" in command
        assert command[command.index("--js-runtimes") + 1] == "node"


class TestQueryExtraction:
    def test_query_extracts_info_without_downloading(self, monkeypatch, tmp_path):
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
        captured = {}

        class FakeYoutubeDL:
            error_message = None

            def __init__(self, params):
                captured["params"] = params

            def extract_info(self, url, download=True):
                captured["url"] = url
                captured["download"] = download
                return {
                    "title": "Private Test Video",
                    "thumbnail": "",
                    "formats": [
                        {
                            "format_id": "18",
                            "resolution": "640x360",
                            "tbr": 400,
                            "ext": "mp4",
                        }
                    ],
                }

        monkeypatch.setattr(main, "send_results", lambda results: results)
        monkeypatch.setattr(main, "verify_ffmpeg", lambda: (True, None))
        monkeypatch.setattr(main, "extract_ffmpeg", lambda: (True, None))
        monkeypatch.setattr(main, "verify_ffmpeg_binaries", lambda: True)
        monkeypatch.setattr(main, "YTDLP_AVAILABLE", True)
        monkeypatch.setattr(main, "CustomYoutubeDL", FakeYoutubeDL)
        monkeypatch.setattr(main, "_node_js_runtime_available", lambda: True)
        monkeypatch.setattr(main, "log_message", lambda message: None)
        monkeypatch.setattr(
            main,
            "fetch_settings",
            lambda: main.PluginSettings(
                download_path=str(tmp_path),
                sorting_order="Resolution",
                preferred_video_format="mp4",
                preferred_audio_format="mp3",
                auto_open_folder=False,
                overwrite_existing_files=True,
                cookie_file_path=str(cookie_file),
            ),
        )

        results = main.query("https://www.youtube.com/watch?v=DxmcpD_g_Ys")

        assert captured["download"] is False
        assert captured["params"]["ignore_no_formats_error"] is True
        assert captured["params"]["cookiefile"] == str(cookie_file)
        assert captured["params"]["js_runtimes"] == {"node": {}}
        assert results

    def test_query_retries_without_cookies_when_only_non_media_formats_return(
        self, monkeypatch, tmp_path
    ):
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

        class FakeYoutubeDL:
            error_message = None

            def __init__(self, params):
                self.params = params

            def extract_info(self, url, download=True):
                if self.params.get("cookiefile"):
                    return {
                        "title": "Public Video",
                        "thumbnail": "",
                        "formats": [
                            {
                                "format_id": "sb0",
                                "url": "https://example.com/storyboard.mhtml",
                                "ext": "mhtml",
                                "protocol": "mhtml",
                                "format_note": "storyboard",
                                "resolution": "48x27",
                                "filesize_approx": 1000,
                                "vcodec": "none",
                                "acodec": "none",
                            }
                        ],
                    }
                return {
                    "title": "Public Video",
                    "thumbnail": "",
                    "formats": [
                        {
                            "format_id": "18",
                            "url": "https://example.com/video.mp4",
                            "resolution": "640x360",
                            "tbr": 400,
                            "ext": "mp4",
                        }
                    ],
                }

        monkeypatch.setattr(main, "send_results", lambda results: results)
        monkeypatch.setattr(main, "verify_ffmpeg", lambda: (True, None))
        monkeypatch.setattr(main, "extract_ffmpeg", lambda: (True, None))
        monkeypatch.setattr(main, "verify_ffmpeg_binaries", lambda: True)
        monkeypatch.setattr(main, "YTDLP_AVAILABLE", True)
        monkeypatch.setattr(main, "CustomYoutubeDL", FakeYoutubeDL)
        monkeypatch.setattr(main, "log_message", lambda message: None)
        monkeypatch.setattr(
            main,
            "fetch_settings",
            lambda: main.PluginSettings(
                download_path=str(tmp_path),
                sorting_order="Resolution",
                preferred_video_format="mp4",
                preferred_audio_format="mp3",
                auto_open_folder=False,
                overwrite_existing_files=True,
                cookie_file_path=str(cookie_file),
            ),
        )

        results = main.query("https://www.youtube.com/watch?v=public")

        assert results
        assert all(
            result.JsonRPCAction["parameters"][8] == ""
            for result in results
            if result.JsonRPCAction
        )

    def test_query_does_not_retry_without_cookies_when_no_raw_formats(
        self, monkeypatch, tmp_path
    ):
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
        calls = []

        class FakeYoutubeDL:
            error_message = None

            def __init__(self, params):
                self.params = params

            def extract_info(self, url, download=True):
                calls.append(self.params.get("cookiefile") or "")
                return {
                    "title": "Unavailable Video",
                    "thumbnail": "",
                    "formats": [],
                }

        monkeypatch.setattr(main, "send_results", lambda results: results)
        monkeypatch.setattr(main, "verify_ffmpeg", lambda: (True, None))
        monkeypatch.setattr(main, "extract_ffmpeg", lambda: (True, None))
        monkeypatch.setattr(main, "verify_ffmpeg_binaries", lambda: True)
        monkeypatch.setattr(main, "YTDLP_AVAILABLE", True)
        monkeypatch.setattr(main, "CustomYoutubeDL", FakeYoutubeDL)
        monkeypatch.setattr(main, "log_message", lambda message: None)
        monkeypatch.setattr(
            main,
            "fetch_settings",
            lambda: main.PluginSettings(
                download_path=str(tmp_path),
                sorting_order="Resolution",
                preferred_video_format="mp4",
                preferred_audio_format="mp3",
                auto_open_folder=False,
                overwrite_existing_files=True,
                cookie_file_path=str(cookie_file),
            ),
        )

        results = main.query("https://www.youtube.com/watch?v=empty")

        assert "formats" in results[0].Title.lower()
        assert calls == [str(cookie_file)]

class TestBuildFormats:
    def test_list_like_raw_formats_are_supported(self):
        class FormatCollection:
            def __iter__(self):
                return iter(
                    [
                        {
                            "format_id": "18",
                            "resolution": "640x360",
                            "tbr": 400,
                            "ext": "mp4",
                        }
                    ]
                )

        formats = main._build_formats({"formats": FormatCollection()})

        assert [format["format_id"] for format in formats] == ["18"]

    def test_storyboard_mhtml_format_is_filtered_out(self):
        info = {
            "formats": [
                {
                    "format_id": "sb0",
                    "url": "https://example.com/storyboard.mhtml",
                    "ext": "mhtml",
                    "protocol": "mhtml",
                    "format_note": "storyboard",
                    "resolution": "48x27",
                    "filesize_approx": 1000,
                    "vcodec": "none",
                    "acodec": "none",
                }
            ],
        }

        assert main._build_formats(info) == []

    def test_non_media_format_with_no_codecs_is_filtered_out(self):
        info = {
            "formats": [
                {
                    "format_id": "metadata",
                    "url": "https://example.com/metadata",
                    "ext": "json",
                    "resolution": "unknown",
                    "filesize_approx": 1000,
                    "vcodec": "none",
                    "acodec": "none",
                }
            ],
        }

        assert main._build_formats(info) == []

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
