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
    def test_build_ydl_opts_without_cookie_file(self):
        ydl_opts = main._build_ydl_opts()

        assert ydl_opts["quiet"] is True
        assert ydl_opts["noplaylist"] is True
        assert "cookiefile" not in ydl_opts

    def test_build_ydl_opts_with_cookie_file(self):
        ydl_opts = main._build_ydl_opts("C:\\cookies.txt")

        assert ydl_opts["cookiefile"] == "C:\\cookies.txt"


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
        monkeypatch.setattr(main.subprocess, "run", fake_run)

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
        monkeypatch.setattr(main.subprocess, "run", fake_run)

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
