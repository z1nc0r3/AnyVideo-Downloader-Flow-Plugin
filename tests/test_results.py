"""Tests for plugin/results.py."""

from results import (
    DownloadContext,
    init_results,
    invalid_result,
    error_result,
    empty_result,
    cookie_file_error_result,
    ffmpeg_not_found_result,
    ffmpeg_setup_result,
    trim_disabled_result,
    plugin_setup_in_progress_result,
    ytdlp_update_in_progress_result,
    best_video_result,
    best_audio_result,
    query_result,
)


def _params(result):
    return result.json_rpc_action["Parameters"]


def _context(**overrides):
    values = {
        "url": "http://example.com",
        "download_path": "/downloads",
        "pref_video_path": "mp4",
        "pref_audio_path": "mp3",
    }
    values.update(overrides)
    return DownloadContext(**values)


class TestInitResults:
    def test_title_and_subtitle(self):
        r = init_results("/home/user/Downloads")
        assert r.title == "Please input the video URL"
        assert r.subtitle == "Download path: /home/user/Downloads"
        assert r.icon == "Images/app.png"


class TestInvalidResult:
    def test_fields(self):
        r = invalid_result()
        assert "URL" in r.title
        assert r.icon == "Images/error.png"


class TestErrorResult:
    def test_fields(self):
        r = error_result()
        assert "wrong" in r.title.lower()
        assert "video information" in r.subtitle.lower()


class TestEmptyResult:
    def test_fields(self):
        r = empty_result()
        assert "formats" in r.title.lower()


class TestCookieFileErrorResult:
    def test_fields(self):
        r = cookie_file_error_result("Cookie file not found")
        assert "cookie" in r.title.lower()
        assert "not found" in r.subtitle.lower()
        assert r.icon == "Images/error.png"


class TestFfmpegNotFoundResult:
    def test_fields(self):
        r = ffmpeg_not_found_result()
        assert "FFmpeg" in r.title
        assert r.subtitle is not None


class TestFfmpegSetupResult:
    def test_with_issue(self):
        r = ffmpeg_setup_result("Custom issue text")
        assert r.subtitle == "Custom issue text"

    def test_with_none(self):
        r = ffmpeg_setup_result(None)
        assert "wait" in r.subtitle.lower()


class TestTrimDisabledResult:
    def test_fields(self):
        r = trim_disabled_result()
        assert "disabled" in r.title.lower()
        assert "settings" in r.subtitle.lower()
        assert r.icon == "Images/error.png"


class TestPluginSetupInProgressResult:
    def test_fields(self):
        r = plugin_setup_in_progress_result()
        assert "setup in progress" in r.title.lower()
        assert "yt-dlp" in r.subtitle.lower()
        assert r.icon == "Images/app.png"


class TestYtdlpUpdateInProgressResult:
    def test_fields(self):
        r = ytdlp_update_in_progress_result()
        assert "yt-dlp" in r.title.lower()
        assert "updated" in r.title.lower() or "updating" in r.title.lower()
        assert "wait" in r.subtitle.lower()
        assert r.icon == "Images/app.png"


class TestBestVideoResult:
    def _make_format(self, resolution="1920x1080", format_id="137"):
        return {"resolution": resolution, "format_id": format_id}

    def test_with_resolution(self):
        fmt = self._make_format()
        r = best_video_result(_context(), None, fmt)
        assert "1920x1080" in r.title
        assert "BEST VIDEO" in r.title

    def test_without_resolution(self):
        fmt = {"format_id": "137"}
        r = best_video_result(_context(), None, fmt)
        assert r.title == "\u2605 BEST VIDEO QUALITY"

    def test_json_rpc_action_parameters(self):
        fmt = self._make_format()
        r = best_video_result(
            _context(auto_open_folder=True, cookie_file_path="/cookies.txt"),
            "thumb.jpg",
            fmt,
        )
        params = _params(r)
        assert r.json_rpc_action["Method"] == "download"
        assert params[0] == "http://example.com"
        assert params[1] == "137"
        assert params[2] == "/downloads"
        assert params[3] == "mp4"
        assert params[4] == "mp3"
        assert params[5] is False
        assert params[6] is True
        assert params[7] is True
        assert params[8] == "/cookies.txt"

    def test_thumbnail_fallback(self):
        fmt = self._make_format()
        r = best_video_result(_context(), None, fmt)
        assert r.icon == "Images/app.png"

    def test_thumbnail_used(self):
        fmt = self._make_format()
        r = best_video_result(_context(), "thumb.jpg", fmt)
        assert r.icon == "thumb.jpg"


class TestBestAudioResult:
    def test_with_tbr(self):
        fmt = {"format_id": "140", "tbr": 128.5}
        r = best_audio_result(_context(), None, fmt)
        assert "128.5 kbps" in r.title
        assert "AUDIO" in r.title

    def test_without_tbr(self):
        fmt = {"format_id": "140"}
        r = best_audio_result(_context(), None, fmt)
        assert r.title == "\u2605 BEST AUDIO ONLY"

    def test_is_audio_true_in_params(self):
        fmt = {"format_id": "140", "tbr": 128}
        r = best_audio_result(_context(), None, fmt)
        assert _params(r)[5] is True

    def test_overwrite_setting_in_params(self):
        fmt = {"format_id": "140", "tbr": 128}
        r = best_audio_result(_context(overwrite_existing_files=False), None, fmt)
        assert _params(r)[7] is False

    def test_cookie_file_setting_in_params(self):
        fmt = {"format_id": "140", "tbr": 128}
        r = best_audio_result(_context(cookie_file_path="/cookies.txt"), None, fmt)
        assert _params(r)[8] == "/cookies.txt"

    def test_download_section_setting_in_params(self):
        fmt = {"format_id": "140", "tbr": 128}
        r = best_audio_result(
            _context(
                download_section="*00:01-00:30",
                trim_start_time="00:01",
                trim_end_time="00:30",
                trim_mode="Download then trim",
                delete_original_after_trim=True,
            ),
            None,
            fmt,
        )
        assert _params(r)[9] == "*00:01-00:30"
        assert _params(r)[10] == "00:01"
        assert _params(r)[11] == "00:30"
        assert _params(r)[12] == "Download then trim"
        assert _params(r)[13] is True
        assert r.subtitle == "Trim: 00:01-00:30"


class TestQueryResult:
    def _make_format(self, **overrides):
        base = {
            "format_id": "137",
            "resolution": "1920x1080",
            "tbr": 4000.5,
            "filesize": 104857600,
            "fps": 30,
        }
        base.update(overrides)
        return base

    def test_full_subtitle(self):
        fmt = self._make_format()
        r = query_result(_context(), None, "Test Video", fmt)
        assert "Res: 1920x1080" in r.subtitle
        assert "4000.5 kbps" in r.subtitle
        assert "Size:" in r.subtitle
        assert "FPS: 30" in r.subtitle
        assert "\u2503" in r.subtitle

    def test_minimal_subtitle(self):
        fmt = self._make_format(tbr=None, filesize=None, fps=None)
        r = query_result(_context(), None, "Test Video", fmt)
        assert "Res: 1920x1080" in r.subtitle
        assert "kbps" not in r.subtitle
        assert "Size:" not in r.subtitle
        assert "FPS:" not in r.subtitle

    def test_audio_only_detection(self):
        fmt = self._make_format(resolution="audio only")
        r = query_result(
            _context(cookie_file_path="/cookies.txt"),
            None,
            "Test Video",
            fmt,
        )
        params = _params(r)
        assert params[5] is True
        assert params[8] == "/cookies.txt"

    def test_video_format_not_audio(self):
        fmt = self._make_format()
        r = query_result(_context(), None, "Test Video", fmt)
        assert _params(r)[5] is False

    def test_title_pass_through(self):
        fmt = self._make_format()
        r = query_result(_context(), None, "My Cool Video", fmt)
        assert r.title == "My Cool Video"

    def test_filesize_conversion_to_mb(self):
        fmt = self._make_format(filesize=5242880)
        r = query_result(_context(), None, "Test", fmt)
        assert "5.0MB" in r.subtitle

    def test_zero_filesize_omitted(self):
        fmt = self._make_format(filesize=0)
        r = query_result(_context(), None, "Test", fmt)
        assert "Size:" not in r.subtitle

    def test_zero_fps_omitted(self):
        fmt = self._make_format(fps=0)
        r = query_result(_context(), None, "Test", fmt)
        assert "FPS:" not in r.subtitle

    def test_download_section_added_to_subtitle(self):
        fmt = self._make_format()
        r = query_result(
            _context(download_section="*00:01-00:30"),
            None,
            "Test",
            fmt,
        )
        assert "Trim: 00:01-00:30" in r.subtitle
