"""Tests for plugin/results.py"""

import pytest

from results import (
    init_results,
    invalid_result,
    error_result,
    empty_result,
    ffmpeg_not_found_result,
    ffmpeg_setup_result,
    plugin_setup_in_progress_result,
    ytdlp_update_in_progress_result,
    best_video_result,
    best_audio_result,
    query_result,
)


# ---------------------------------------------------------------------------
# Simple result builders
# ---------------------------------------------------------------------------

class TestInitResults:
    def test_title_and_subtitle(self):
        r = init_results("/home/user/Downloads")
        assert r.Title == "Please input the video URL"
        assert r.SubTitle == "Download path: /home/user/Downloads"
        assert r.IcoPath == "Images/app.png"


class TestInvalidResult:
    def test_fields(self):
        r = invalid_result()
        assert "URL" in r.Title
        assert r.IcoPath == "Images/error.png"


class TestErrorResult:
    def test_fields(self):
        r = error_result()
        assert "wrong" in r.Title.lower()
        assert "video information" in r.SubTitle.lower()


class TestEmptyResult:
    def test_fields(self):
        r = empty_result()
        assert "formats" in r.Title.lower()


class TestFfmpegNotFoundResult:
    def test_fields(self):
        r = ffmpeg_not_found_result()
        assert "FFmpeg" in r.Title
        assert r.SubTitle is not None


class TestFfmpegSetupResult:
    def test_with_issue(self):
        r = ffmpeg_setup_result("Custom issue text")
        assert r.SubTitle == "Custom issue text"

    def test_with_none(self):
        r = ffmpeg_setup_result(None)
        assert "wait" in r.SubTitle.lower()


class TestPluginSetupInProgressResult:
    def test_fields(self):
        r = plugin_setup_in_progress_result()
        assert "setup in progress" in r.Title.lower()
        assert "yt-dlp" in r.SubTitle.lower()
        assert r.IcoPath == "Images/app.png"


class TestYtdlpUpdateInProgressResult:
    def test_fields(self):
        r = ytdlp_update_in_progress_result()
        assert "yt-dlp" in r.Title.lower()
        assert "updated" in r.Title.lower() or "updating" in r.Title.lower()
        assert "wait" in r.SubTitle.lower()
        assert r.IcoPath == "Images/app.png"


# ---------------------------------------------------------------------------
# Download result builders
# ---------------------------------------------------------------------------

class TestBestVideoResult:
    def _make_format(self, resolution="1920x1080", format_id="137"):
        return {"resolution": resolution, "format_id": format_id}

    def test_with_resolution(self):
        fmt = self._make_format()
        r = best_video_result("http://example.com", None, fmt,
                              "/downloads", "mp4", "mp3")
        assert "1920x1080" in r.Title
        assert "BEST VIDEO" in r.Title

    def test_without_resolution(self):
        fmt = {"format_id": "137"}
        r = best_video_result("http://example.com", None, fmt,
                              "/downloads", "mp4", "mp3")
        assert r.Title == "★ BEST VIDEO QUALITY"

    def test_json_rpc_action_parameters(self):
        fmt = self._make_format()
        r = best_video_result("http://example.com", "thumb.jpg", fmt,
                              "/downloads", "mp4", "mp3", auto_open_folder=True,
                              needs_update=True)
        params = r.JsonRPCAction["parameters"]
        assert params[0] == "http://example.com"
        assert params[1] == "137"
        assert params[2] == "/downloads"
        assert params[3] == "mp4"
        assert params[4] == "mp3"
        assert params[5] is False  # is_audio
        assert params[6] is True   # auto_open_folder
        assert params[7] is True   # needs_update

    def test_needs_update_false_by_default(self):
        fmt = self._make_format()
        r = best_video_result("http://example.com", None, fmt,
                              "/downloads", "mp4", "mp3")
        params = r.JsonRPCAction["parameters"]
        assert params[7] is False

    def test_thumbnail_fallback(self):
        fmt = self._make_format()
        r = best_video_result("http://example.com", None, fmt,
                              "/downloads", "mp4", "mp3")
        assert r.IcoPath == "Images/app.png"

    def test_thumbnail_used(self):
        fmt = self._make_format()
        r = best_video_result("http://example.com", "thumb.jpg", fmt,
                              "/downloads", "mp4", "mp3")
        assert r.IcoPath == "thumb.jpg"


class TestBestAudioResult:
    def test_with_tbr(self):
        fmt = {"format_id": "140", "tbr": 128.5}
        r = best_audio_result("http://example.com", None, fmt,
                              "/downloads", "mp4", "mp3")
        assert "128.5 kbps" in r.Title
        assert "AUDIO" in r.Title

    def test_without_tbr(self):
        fmt = {"format_id": "140"}
        r = best_audio_result("http://example.com", None, fmt,
                              "/downloads", "mp4", "mp3")
        assert r.Title == "★ BEST AUDIO ONLY"

    def test_is_audio_true_in_params(self):
        fmt = {"format_id": "140", "tbr": 128}
        r = best_audio_result("http://example.com", None, fmt,
                              "/downloads", "mp4", "mp3")
        params = r.JsonRPCAction["parameters"]
        assert params[5] is True  # is_audio

    def test_needs_update_propagation(self):
        fmt = {"format_id": "140", "tbr": 128}
        r = best_audio_result("http://example.com", None, fmt,
                              "/downloads", "mp4", "mp3", needs_update=True)
        params = r.JsonRPCAction["parameters"]
        assert params[7] is True


class TestQueryResult:
    def _make_format(self, **overrides):
        base = {
            "format_id": "137",
            "resolution": "1920x1080",
            "tbr": 4000.5,
            "filesize": 104857600,  # 100 MB
            "fps": 30,
        }
        base.update(overrides)
        return base

    def test_full_subtitle(self):
        fmt = self._make_format()
        r = query_result("http://example.com", None, "Test Video", fmt,
                         "/downloads", "mp4", "mp3")
        assert "Res: 1920x1080" in r.SubTitle
        assert "4000.5 kbps" in r.SubTitle
        assert "Size:" in r.SubTitle
        assert "FPS: 30" in r.SubTitle
        assert "┃" in r.SubTitle

    def test_minimal_subtitle(self):
        fmt = self._make_format(tbr=None, filesize=None, fps=None)
        r = query_result("http://example.com", None, "Test Video", fmt,
                         "/downloads", "mp4", "mp3")
        assert "Res: 1920x1080" in r.SubTitle
        assert "kbps" not in r.SubTitle
        assert "Size:" not in r.SubTitle
        assert "FPS:" not in r.SubTitle

    def test_audio_only_detection(self):
        fmt = self._make_format(resolution="audio only")
        r = query_result("http://example.com", None, "Test Video", fmt,
                         "/downloads", "mp4", "mp3")
        params = r.JsonRPCAction["parameters"]
        assert params[5] is True  # is_audio

    def test_video_format_not_audio(self):
        fmt = self._make_format()
        r = query_result("http://example.com", None, "Test Video", fmt,
                         "/downloads", "mp4", "mp3")
        params = r.JsonRPCAction["parameters"]
        assert params[5] is False  # is_audio

    def test_needs_update_in_params(self):
        fmt = self._make_format()
        r = query_result("http://example.com", None, "Test Video", fmt,
                         "/downloads", "mp4", "mp3", needs_update=True)
        params = r.JsonRPCAction["parameters"]
        assert params[7] is True

    def test_title_pass_through(self):
        fmt = self._make_format()
        r = query_result("http://example.com", None, "My Cool Video", fmt,
                         "/downloads", "mp4", "mp3")
        assert r.Title == "My Cool Video"

    def test_filesize_conversion_to_mb(self):
        fmt = self._make_format(filesize=5242880)  # 5 MB
        r = query_result("http://example.com", None, "Test", fmt,
                         "/downloads", "mp4", "mp3")
        assert "5.0MB" in r.SubTitle

    def test_zero_filesize_omitted(self):
        # filesize=0 is falsy, should be omitted
        fmt = self._make_format(filesize=0)
        r = query_result("http://example.com", None, "Test", fmt,
                         "/downloads", "mp4", "mp3")
        assert "Size:" not in r.SubTitle

    def test_zero_fps_omitted(self):
        # fps=0 is falsy, should be omitted
        fmt = self._make_format(fps=0)
        r = query_result("http://example.com", None, "Test", fmt,
                         "/downloads", "mp4", "mp3")
        assert "FPS:" not in r.SubTitle
