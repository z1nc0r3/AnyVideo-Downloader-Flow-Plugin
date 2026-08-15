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


class TestTrimModeSettings:
    def test_normalize_trim_mode(self):
        assert main._normalize_trim_mode("Off") == main.TRIM_MODE_OFF
        assert (
            main._normalize_trim_mode("Native section download")
            == main.TRIM_MODE_NATIVE_SECTION
        )
        assert (
            main._normalize_trim_mode(" Download then trim ")
            == main.TRIM_MODE_DOWNLOAD_THEN_TRIM
        )
        assert main._normalize_trim_mode("unknown") == main.TRIM_MODE_OFF


class TestFormatChoices:
    def test_video_format_choices_keep_requested_format_first(self):
        assert main._build_format_choices("137", False) == [
            "137",
            "137+bestaudio",
            "bestvideo+bestaudio",
            "best",
        ]

    def test_audio_format_choices_use_audio_fallback(self):
        assert main._build_format_choices("140", True) == ["bestaudio/best"]

    def test_empty_video_format_choices_fall_back_to_best_video(self):
        assert main._build_format_choices("", False) == [
            "bestvideo+bestaudio",
            "best",
        ]


class TestQueryRequestParsing:
    def test_url_only(self):
        request = main._parse_query_request(
            "https://www.youtube.com/watch?v=DxmcpD_g_Ys"
        )

        assert request.url == "https://www.youtube.com/watch?v=DxmcpD_g_Ys"
        assert request.download_section == ""

    def test_url_with_time_range(self):
        request = main._parse_query_request(
            "https://www.youtube.com/watch?v=DxmcpD_g_Ys 00:01:20 00:03:45"
        )

        assert request.url == "https://www.youtube.com/watch?v=DxmcpD_g_Ys"
        assert request.download_section == "*00:01:20-00:03:45"

    def test_url_with_open_ended_time_range(self):
        request = main._parse_query_request(
            "https://www.youtube.com/watch?v=DxmcpD_g_Ys 10:15 inf"
        )

        assert request.url == "https://www.youtube.com/watch?v=DxmcpD_g_Ys"
        assert request.download_section == "*10:15-inf"

    def test_invalid_time_range_is_left_as_query_text(self):
        request = main._parse_query_request(
            "https://www.youtube.com/watch?v=DxmcpD_g_Ys 00:03:45 00:01:20"
        )

        assert request.url.endswith("00:03:45 00:01:20")
        assert request.download_section == ""


class TestPostTrimHelpers:
    def test_read_final_path_marker_returns_last_non_empty_line(self, tmp_path):
        marker = tmp_path / "marker.txt"
        marker.write_text("\nC:\\first.webm\nC:\\final.webm\n", encoding="utf-8")

        assert main._read_final_path_marker(str(marker)) == "C:\\final.webm"

    def test_trimmed_output_path_overwrites_simple_name(self, tmp_path):
        source = tmp_path / "Video.webm"
        source.write_text("source", encoding="utf-8")

        assert main._trimmed_output_path(str(source), True) == str(
            tmp_path / "Video - trimmed.webm"
        )

    def test_trimmed_output_path_uses_unique_name_when_needed(self, tmp_path):
        source = tmp_path / "Video.webm"
        source.write_text("source", encoding="utf-8")
        (tmp_path / "Video - trimmed.webm").write_text("existing", encoding="utf-8")

        assert main._trimmed_output_path(str(source), False) == str(
            tmp_path / "Video - trimmed (1).webm"
        )

    def test_run_post_trim_builds_ffmpeg_command_and_deletes_original(
        self, monkeypatch, tmp_path
    ):
        source = tmp_path / "Video.webm"
        source.write_bytes(b"source")
        captured = {}

        class CompletedProcess:
            returncode = 0

        def fake_run(command):
            captured["command"] = command
            output_path = command[-1]
            with open(output_path, "wb") as output_file:
                output_file.write(b"trimmed")
            return CompletedProcess()

        monkeypatch.setattr(main.subprocess, "run", fake_run)
        monkeypatch.setattr(main, "log_message", lambda message: None)

        ok = main._run_post_trim(
            str(source),
            "1:00",
            "2:30",
            str(tmp_path),
            True,
            True,
        )

        assert ok is True
        assert captured["command"][:6] == [
            str(tmp_path / "ffmpeg.exe"),
            "-y",
            "-ss",
            "1:00",
            "-i",
            str(source),
        ]
        assert "-t" in captured["command"]
        assert captured["command"][captured["command"].index("-t") + 1] == "90"
        assert "-c" in captured["command"]
        assert not source.exists()

    def test_run_post_trim_inf_end_omits_duration(self, monkeypatch, tmp_path):
        source = tmp_path / "Video.webm"
        source.write_bytes(b"source")
        captured = {}

        class CompletedProcess:
            returncode = 0

        def fake_run(command):
            captured["command"] = command
            with open(command[-1], "wb") as output_file:
                output_file.write(b"trimmed")
            return CompletedProcess()

        monkeypatch.setattr(main.subprocess, "run", fake_run)
        monkeypatch.setattr(main, "log_message", lambda message: None)

        ok = main._run_post_trim(
            str(source),
            "1:00",
            "inf",
            str(tmp_path),
            True,
            False,
        )

        assert ok is True
        assert "-t" not in captured["command"]
        assert source.exists()

    def test_run_post_trim_rejects_invalid_range(self, monkeypatch, tmp_path):
        source = tmp_path / "Video.webm"
        source.write_bytes(b"source")

        def fake_run(command):
            raise AssertionError("ffmpeg should not run for an invalid range")

        monkeypatch.setattr(main.subprocess, "run", fake_run)
        monkeypatch.setattr(main, "log_message", lambda message: None)

        ok = main._run_post_trim(
            str(source),
            "2:00",
            "1:00",
            str(tmp_path),
            True,
            False,
        )

        assert ok is False
        assert source.exists()


class TestDownloadCommand:
    def test_download_adds_resilient_http_retry_arguments(self, monkeypatch, tmp_path):
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
            "",
        )

        command = captured["command"]
        assert command[command.index("-f") + 1] == "18"
        assert "--retries" in command
        assert command[command.index("--retries") + 1] == "10"
        assert "--fragment-retries" in command
        assert command[command.index("--fragment-retries") + 1] == "10"
        assert "--file-access-retries" in command
        assert "--extractor-retries" in command
        assert "--http-chunk-size" in command
        assert command[command.index("--http-chunk-size") + 1] == "10M"
        assert "--no-part" not in command

    def test_download_retries_next_format_choice_after_failure(
        self, monkeypatch, tmp_path
    ):
        commands = []

        class FailedProcess:
            returncode = 1

        class CompletedProcess:
            returncode = 0

        def fake_run(command):
            commands.append(command)
            return FailedProcess() if len(commands) == 1 else CompletedProcess()

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
            "",
        )

        assert len(commands) == 2
        assert commands[0][commands[0].index("-f") + 1] == "18"
        assert commands[1][commands[1].index("-f") + 1] == "18+bestaudio"

    def test_download_logs_concise_summary_when_all_format_choices_fail(
        self, monkeypatch, tmp_path
    ):
        messages = []

        class FailedProcess:
            returncode = 1

        def fake_run(command):
            return FailedProcess()

        monkeypatch.setattr(main, "check_ytdlp_version", lambda interval: False)
        monkeypatch.setattr(main, "get_binaries_paths", lambda: "")
        monkeypatch.setattr(main, "_node_js_runtime_available", lambda: False)
        monkeypatch.setattr(main.subprocess, "run", fake_run)
        monkeypatch.setattr(main, "log_message", messages.append)

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

        assert messages == [
            (
                "All download attempts failed. Last exit code 1. "
                "Formats tried: 18, 18+bestaudio, bestvideo+bestaudio, best"
            )
        ]

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
        assert "--quiet" in command
        assert "--progress" in command

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
        assert "--quiet" in command

    def test_download_adds_section_argument(self, monkeypatch, tmp_path):
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
            "",
            "*00:01:20-00:03:45",
            "00:01:20",
            "00:03:45",
            main.TRIM_MODE_NATIVE_SECTION,
        )

        command = captured["command"]
        assert "--download-sections" in command
        assert command[command.index("--download-sections") + 1] == (
            "*00:01:20-00:03:45"
        )
        assert "--quiet" not in command
        assert "--progress" in command
        assert "--newline" in command
        assert "--downloader-args" in command
        assert command[command.index("--downloader-args") + 1] == (
            "ffmpeg:-stats -stats_period 1 -progress pipe:2"
        )

    def test_download_post_trim_uses_marker_and_cleans_it(self, monkeypatch, tmp_path):
        marker = tmp_path / "trim-final-path.txt"
        final_path = tmp_path / "Video.webm"
        captured = {}

        class CompletedProcess:
            returncode = 0

        def fake_run(command):
            captured["command"] = command
            final_path.write_bytes(b"downloaded")
            marker.write_text(str(final_path), encoding="utf-8")
            return CompletedProcess()

        def fake_trim(path, start, end, ffmpeg_path, overwrite, delete_original):
            captured["trim"] = (path, start, end, ffmpeg_path, overwrite, delete_original)
            return True

        monkeypatch.setattr(main, "check_ytdlp_version", lambda interval: False)
        monkeypatch.setattr(main, "get_binaries_paths", lambda: str(tmp_path))
        monkeypatch.setattr(main, "_node_js_runtime_available", lambda: False)
        monkeypatch.setattr(main, "_create_trim_marker_path", lambda: str(marker))
        monkeypatch.setattr(main, "_run_post_trim", fake_trim)
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
            "*00:01:00-00:02:30",
            "00:01:00",
            "00:02:30",
            main.TRIM_MODE_DOWNLOAD_THEN_TRIM,
            True,
        )

        command = captured["command"]
        assert "--download-sections" not in command
        assert "--print-to-file" in command
        assert command[command.index("--print-to-file") + 1] == "after_move:filepath"
        assert command[command.index("--print-to-file") + 2] == str(marker)
        assert captured["trim"] == (
            str(final_path),
            "00:01:00",
            "00:02:30",
            str(tmp_path),
            True,
            True,
        )
        assert not marker.exists()

    def test_download_post_trim_cleans_marker_when_download_fails(
        self, monkeypatch, tmp_path
    ):
        marker = tmp_path / "trim-final-path.txt"
        marker.write_text("stale", encoding="utf-8")
        captured = {}

        class CompletedProcess:
            returncode = 1

        def fake_run(command):
            captured["command"] = command
            return CompletedProcess()

        def fake_trim(*args):
            raise AssertionError("trim should not run after failed download")

        monkeypatch.setattr(main, "check_ytdlp_version", lambda interval: False)
        monkeypatch.setattr(main, "get_binaries_paths", lambda: str(tmp_path))
        monkeypatch.setattr(main, "_node_js_runtime_available", lambda: False)
        monkeypatch.setattr(main, "_create_trim_marker_path", lambda: str(marker))
        monkeypatch.setattr(main, "_run_post_trim", fake_trim)
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
            "*00:01:00-00:02:30",
            "00:01:00",
            "00:02:30",
            main.TRIM_MODE_DOWNLOAD_THEN_TRIM,
            False,
        )

        assert "--print-to-file" in captured["command"]
        assert not marker.exists()


class TestQueryExtraction:
    def test_query_returns_disabled_result_when_video_trimming_is_off(
        self, monkeypatch, tmp_path
    ):
        class FakeYoutubeDL:
            def __init__(self, params):
                raise AssertionError("format extraction should not run")

        monkeypatch.setattr(main, "send_results", lambda results: results)
        monkeypatch.setattr(main, "verify_ffmpeg", lambda: (True, None))
        monkeypatch.setattr(main, "extract_ffmpeg", lambda: (True, None))
        monkeypatch.setattr(main, "YTDLP_AVAILABLE", True)
        monkeypatch.setattr(main, "CustomYoutubeDL", FakeYoutubeDL)
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
                trim_mode=main.TRIM_MODE_OFF,
            ),
        )

        results = main.query(
            "https://www.youtube.com/watch?v=DxmcpD_g_Ys 00:01:00 00:02:00"
        )

        assert results[0].title == "Video trimming is disabled"

    def test_query_validates_url_before_trim_mode(self, monkeypatch, tmp_path):
        class FakeYoutubeDL:
            def __init__(self, params):
                raise AssertionError("format extraction should not run")

        monkeypatch.setattr(main, "send_results", lambda results: results)
        monkeypatch.setattr(main, "verify_ffmpeg", lambda: (True, None))
        monkeypatch.setattr(main, "extract_ffmpeg", lambda: (True, None))
        monkeypatch.setattr(main, "YTDLP_AVAILABLE", True)
        monkeypatch.setattr(main, "CustomYoutubeDL", FakeYoutubeDL)
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
                trim_mode=main.TRIM_MODE_OFF,
            ),
        )

        results = main.query("not-a-url 00:01:00 00:02:00")

        assert results[0].title == "Please check the URL for errors."

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

    def test_query_extracts_bare_url_and_passes_download_section(
        self, monkeypatch, tmp_path
    ):
        captured = {}

        class FakeYoutubeDL:
            error_message = None

            def __init__(self, params):
                captured["params"] = params

            def extract_info(self, url, download=True):
                captured["url"] = url
                captured["download"] = download
                return {
                    "title": "Partial Test Video",
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
        monkeypatch.setattr(main, "_node_js_runtime_available", lambda: False)
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
                trim_mode=main.TRIM_MODE_NATIVE_SECTION,
            ),
        )

        results = main.query(
            "https://www.youtube.com/watch?v=DxmcpD_g_Ys 00:01:20 00:03:45"
        )

        assert captured["url"] == "https://www.youtube.com/watch?v=DxmcpD_g_Ys"
        assert captured["download"] is False
        assert results
        assert all(
            result.json_rpc_action["Parameters"][0]
            == "https://www.youtube.com/watch?v=DxmcpD_g_Ys"
            for result in results
            if result.json_rpc_action
        )
        assert all(
            result.json_rpc_action["Parameters"][9] == "*00:01:20-00:03:45"
            for result in results
            if result.json_rpc_action
        )

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
            result.json_rpc_action["Parameters"][8] == ""
            for result in results
            if result.json_rpc_action
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

        assert "formats" in results[0].title.lower()
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
