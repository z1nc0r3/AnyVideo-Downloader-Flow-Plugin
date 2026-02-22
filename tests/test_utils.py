"""Tests for plugin/utils.py"""

import json
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import MagicMock, mock_open, patch

import utils


# ---------------------------------------------------------------------------
# is_valid_url
# ---------------------------------------------------------------------------

class TestIsValidUrl:
    def test_http_url(self):
        assert utils.is_valid_url("http://example.com") is True

    def test_https_url(self):
        assert utils.is_valid_url("https://www.youtube.com/watch?v=abc123") is True

    def test_url_with_path_and_params(self):
        assert utils.is_valid_url("https://example.com/path?q=1&b=2") is True

    def test_plain_text(self):
        assert utils.is_valid_url("not a url") is False

    def test_empty_string(self):
        assert utils.is_valid_url("") is False

    def test_missing_scheme(self):
        assert utils.is_valid_url("example.com") is False


# ---------------------------------------------------------------------------
# sort_by_resolution
# ---------------------------------------------------------------------------

class TestSortByResolution:
    def test_descending_order(self):
        formats = [
            {"resolution": "640x480"},
            {"resolution": "1920x1080"},
            {"resolution": "1280x720"},
        ]
        result = utils.sort_by_resolution(formats)
        assert [f["resolution"] for f in result] == [
            "1920x1080", "1280x720", "640x480"
        ]

    def test_audio_only_at_bottom(self):
        formats = [
            {"resolution": "audio only"},
            {"resolution": "1280x720"},
        ]
        result = utils.sort_by_resolution(formats)
        assert result[0]["resolution"] == "1280x720"
        assert result[1]["resolution"] == "audio only"

    def test_mixed_formats(self):
        formats = [
            {"resolution": "audio only"},
            {"resolution": "640x480"},
            {"resolution": "1920x1080"},
            {"resolution": "audio only"},
        ]
        result = utils.sort_by_resolution(formats)
        assert result[0]["resolution"] == "1920x1080"
        assert result[1]["resolution"] == "640x480"


# ---------------------------------------------------------------------------
# sort_by_tbr
# ---------------------------------------------------------------------------

class TestSortByTbr:
    def test_descending_order(self):
        formats = [
            {"tbr": 100},
            {"tbr": 500},
            {"tbr": 250},
        ]
        result = utils.sort_by_tbr(formats)
        assert [f["tbr"] for f in result] == [500, 250, 100]


# ---------------------------------------------------------------------------
# sort_by_fps
# ---------------------------------------------------------------------------

class TestSortByFps:
    def test_descending_order(self):
        formats = [
            {"fps": 24},
            {"fps": 60},
            {"fps": 30},
        ]
        result = utils.sort_by_fps(formats)
        assert [f["fps"] for f in result] == [60, 30, 24]

    def test_none_at_end(self):
        formats = [
            {"fps": None},
            {"fps": 30},
            {"fps": 60},
        ]
        result = utils.sort_by_fps(formats)
        assert result[0]["fps"] == 60
        assert result[1]["fps"] == 30
        assert result[2]["fps"] is None


# ---------------------------------------------------------------------------
# sort_by_size
# ---------------------------------------------------------------------------

class TestSortBySize:
    def test_descending_order(self):
        formats = [
            {"filesize": 1000},
            {"filesize": 5000},
            {"filesize": 2500},
        ]
        result = utils.sort_by_size(formats)
        assert [f["filesize"] for f in result] == [5000, 2500, 1000]

    def test_none_at_end(self):
        formats = [
            {"filesize": None},
            {"filesize": 1000},
            {"filesize": 5000},
        ]
        result = utils.sort_by_size(formats)
        assert result[0]["filesize"] == 5000
        assert result[1]["filesize"] == 1000
        assert result[2]["filesize"] is None


# ---------------------------------------------------------------------------
# _is_valid_executable
# ---------------------------------------------------------------------------

class TestIsValidExecutable:
    @patch("utils.os.path.getsize", return_value=1024)
    @patch("utils.os.path.isfile", return_value=True)
    def test_valid_file(self, mock_isfile, mock_getsize):
        assert utils._is_valid_executable("ffmpeg.exe") is True

    @patch("utils.os.path.isfile", return_value=False)
    def test_missing_file(self, mock_isfile):
        assert utils._is_valid_executable("ffmpeg.exe") is False

    @patch("utils.os.path.getsize", return_value=0)
    @patch("utils.os.path.isfile", return_value=True)
    def test_zero_size_file(self, mock_isfile, mock_getsize):
        assert utils._is_valid_executable("ffmpeg.exe") is False

    @patch("utils.os.path.isfile", side_effect=OSError("permission denied"))
    def test_os_error(self, mock_isfile):
        assert utils._is_valid_executable("ffmpeg.exe") is False


# ---------------------------------------------------------------------------
# verify_ffmpeg_binaries
# ---------------------------------------------------------------------------

class TestVerifyFfmpegBinaries:
    @patch("utils._is_valid_executable", return_value=True)
    def test_both_valid_returns_bool(self, mock_exec):
        assert utils.verify_ffmpeg_binaries() is True

    @patch("utils._is_valid_executable", return_value=True)
    def test_both_valid_returns_tuple(self, mock_exec):
        ok, reason = utils.verify_ffmpeg_binaries(return_reason=True)
        assert ok is True
        assert reason is None

    @patch("utils.os.path.exists", return_value=False)
    @patch("utils._is_valid_executable", return_value=False)
    def test_both_missing(self, mock_exec, mock_exists):
        ok, reason = utils.verify_ffmpeg_binaries(return_reason=True)
        assert ok is False
        assert "ffmpeg.exe is missing" in reason
        assert "ffprobe.exe is missing" in reason

    @patch("utils.os.path.exists", side_effect=lambda p: "ffmpeg" in p)
    @patch("utils._is_valid_executable", return_value=False)
    def test_ffmpeg_empty_ffprobe_missing(self, mock_exec, mock_exists):
        ok, reason = utils.verify_ffmpeg_binaries(return_reason=True)
        assert ok is False
        assert "ffmpeg.exe is empty or unreadable" in reason
        assert "ffprobe.exe is missing" in reason


# ---------------------------------------------------------------------------
# verify_ffmpeg
# ---------------------------------------------------------------------------

class TestVerifyFfmpeg:
    @patch("utils.os.path.exists", return_value=True)
    def test_lock_file_exists(self, mock_exists):
        ok, reason = utils.verify_ffmpeg()
        assert ok is False
        assert "setup in progress" in reason.lower()

    @patch("utils.verify_ffmpeg_zip")
    @patch("utils.verify_ffmpeg_binaries", return_value=(True, None))
    @patch("utils.os.path.exists", return_value=False)
    def test_binaries_ok(self, mock_exists, mock_binaries, mock_zip):
        ok, reason = utils.verify_ffmpeg()
        assert ok is True
        assert reason is None
        mock_zip.assert_not_called()

    @patch("utils.verify_ffmpeg_zip", return_value=(True, None))
    @patch("utils.verify_ffmpeg_binaries", return_value=(False, "ffmpeg.exe is missing."))
    @patch("utils.os.path.exists", return_value=False)
    def test_binaries_bad_zip_ok(self, mock_exists, mock_binaries, mock_zip):
        ok, reason = utils.verify_ffmpeg()
        assert ok is True
        assert reason is None

    @patch("utils.verify_ffmpeg_zip", return_value=(False, "FFmpeg zip is missing."))
    @patch("utils.verify_ffmpeg_binaries", return_value=(False, "ffmpeg.exe is missing."))
    @patch("utils.os.path.exists", return_value=False)
    def test_both_bad(self, mock_exists, mock_binaries, mock_zip):
        ok, reason = utils.verify_ffmpeg()
        assert ok is False
        assert reason is not None


# ---------------------------------------------------------------------------
# extract_ffmpeg
# ---------------------------------------------------------------------------

class TestExtractFfmpeg:
    @patch("utils.verify_ffmpeg_binaries", return_value=(True, None))
    @patch("utils.os.path.exists", return_value=False)
    def test_no_zip_binaries_ok(self, mock_exists, mock_binaries):
        ok, reason = utils.extract_ffmpeg()
        assert ok is True
        assert reason is None

    @patch("utils.verify_ffmpeg_binaries", return_value=(False, "ffmpeg.exe is missing."))
    @patch("utils.os.path.exists", return_value=False)
    def test_no_zip_binaries_missing(self, mock_exists, mock_binaries):
        ok, reason = utils.extract_ffmpeg()
        assert ok is False
        assert "missing" in reason.lower()

    @patch("utils.os.remove")
    @patch("utils.verify_ffmpeg_zip", return_value=(False, "FFmpeg archive is corrupted."))
    @patch("utils.os.path.exists", return_value=True)
    def test_invalid_zip_removed(self, mock_exists, mock_zip, mock_remove):
        ok, reason = utils.extract_ffmpeg()
        assert ok is False
        assert "corrupted" in reason.lower()

    @patch("utils.verify_ffmpeg_binaries", return_value=(True, None))
    @patch("utils.os.remove")
    @patch("utils.zipfile.ZipFile")
    @patch("utils.verify_ffmpeg_zip", return_value=(True, None))
    @patch("utils.os.path.exists", return_value=True)
    def test_extraction_success(self, mock_exists, mock_zip_verify, mock_zipfile,
                                 mock_remove, mock_binaries):
        mock_zipfile.return_value.__enter__ = MagicMock()
        mock_zipfile.return_value.__exit__ = MagicMock(return_value=False)
        ok, reason = utils.extract_ffmpeg()
        assert ok is True
        assert reason is None

    @patch("utils.zipfile.ZipFile", side_effect=Exception("disk error"))
    @patch("utils.verify_ffmpeg_zip", return_value=(True, None))
    @patch("utils.os.path.exists", return_value=True)
    def test_extraction_failure(self, mock_exists, mock_zip_verify, mock_zipfile):
        ok, reason = utils.extract_ffmpeg()
        assert ok is False
        assert "extract" in reason.lower()


# ---------------------------------------------------------------------------
# check_ytdlp_version
# ---------------------------------------------------------------------------

class TestCheckYtdlpVersion:
    def _make_pypi_response(self, version):
        """Helper to create a mock urlopen response with a given version."""
        data = json.dumps({"info": {"version": version}}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = data
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    @patch("utils.os.path.exists", return_value=True)
    @patch("utils.os.path.getmtime")
    def test_fresh_marker_returns_false(self, mock_mtime, mock_exists):
        # Marker modified 1 day ago
        mock_mtime.return_value = (datetime.now() - timedelta(days=1)).timestamp()
        assert utils.check_ytdlp_version(7) is False

    @patch("utils.os.path.exists")
    @patch("utils.os.path.getmtime")
    def test_stale_marker_lock_exists_returns_false(self, mock_mtime, mock_exists):
        # marker exists and is stale, lock also exists
        def exists_side_effect(path):
            return True  # both marker and lock exist
        mock_exists.side_effect = exists_side_effect
        mock_mtime.return_value = (datetime.now() - timedelta(days=10)).timestamp()
        assert utils.check_ytdlp_version(7) is False

    @patch("utils.open", mock_open(), create=True)
    @patch("utils.os.makedirs")
    @patch("utils.urlopen")
    @patch("utils.os.path.exists")
    @patch("utils.os.path.getmtime")
    def test_versions_match_returns_false_touches_marker(self, mock_mtime, mock_exists,
                                                          mock_urlopen, mock_makedirs):
        mock_mtime.return_value = (datetime.now() - timedelta(days=10)).timestamp()

        def exists_side_effect(path):
            if "last_update" in path:
                return True
            return False  # lock doesn't exist
        mock_exists.side_effect = exists_side_effect

        # Mock yt_dlp version
        mock_ytdlp = MagicMock()
        mock_ytdlp.version.__version__ = "2024.12.01"

        mock_urlopen.return_value = self._make_pypi_response("2024.12.01")

        with patch.dict("sys.modules", {"yt_dlp": mock_ytdlp}):
            result = utils.check_ytdlp_version(7)

        assert result is False

    @patch("utils.urlopen")
    @patch("utils.os.path.exists")
    @patch("utils.os.path.getmtime")
    def test_versions_differ_returns_true(self, mock_mtime, mock_exists, mock_urlopen):
        mock_mtime.return_value = (datetime.now() - timedelta(days=10)).timestamp()

        def exists_side_effect(path):
            if "last_update" in path:
                return True
            return False
        mock_exists.side_effect = exists_side_effect

        mock_ytdlp = MagicMock()
        mock_ytdlp.version.__version__ = "2024.11.01"

        mock_urlopen.return_value = self._make_pypi_response("2024.12.01")

        with patch.dict("sys.modules", {"yt_dlp": mock_ytdlp}):
            result = utils.check_ytdlp_version(7)

        assert result is True

    @patch("utils.urlopen", side_effect=Exception("network error"))
    @patch("utils.os.path.exists", return_value=False)
    def test_network_error_returns_false(self, mock_exists, mock_urlopen):
        mock_ytdlp = MagicMock()
        mock_ytdlp.version.__version__ = "2024.11.01"

        with patch.dict("sys.modules", {"yt_dlp": mock_ytdlp}):
            result = utils.check_ytdlp_version(7)

        assert result is False

    @patch("utils.urlopen")
    @patch("utils.os.path.exists", return_value=False)
    def test_missing_pypi_version_returns_false(self, mock_exists, mock_urlopen):
        # PyPI response with no version
        data = json.dumps({"info": {}}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = data
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        mock_ytdlp = MagicMock()
        mock_ytdlp.version.__version__ = "2024.11.01"

        with patch.dict("sys.modules", {"yt_dlp": mock_ytdlp}):
            result = utils.check_ytdlp_version(7)

        assert result is False

    @patch("utils.os.path.exists", return_value=False)
    def test_no_marker_no_lock_versions_differ(self, mock_exists):
        mock_ytdlp = MagicMock()
        mock_ytdlp.version.__version__ = "2024.11.01"

        mock_resp = MagicMock()
        data = json.dumps({"info": {"version": "2024.12.01"}}).encode("utf-8")
        mock_resp.read.return_value = data
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {"yt_dlp": mock_ytdlp}), \
             patch("utils.urlopen", return_value=mock_resp):
            result = utils.check_ytdlp_version(7)

        assert result is True


# ---------------------------------------------------------------------------
# update_ytdlp_library
# ---------------------------------------------------------------------------

class TestUpdateYtdlpLibrary:
    @patch("utils.os.path.exists", return_value=False)
    def test_script_missing(self, mock_exists):
        ok, msg = utils.update_ytdlp_library()
        assert ok is False
        assert "not found" in msg.lower()

    @patch("utils.subprocess.Popen")
    @patch("utils.os.path.exists", return_value=True)
    def test_spawn_success(self, mock_exists, mock_popen):
        ok, msg = utils.update_ytdlp_library()
        assert ok is True
        assert "started" in msg.lower()
        mock_popen.assert_called_once()

    @patch("utils.subprocess.Popen", side_effect=OSError("spawn failed"))
    @patch("utils.os.path.exists", return_value=True)
    def test_spawn_failure(self, mock_exists, mock_popen):
        ok, msg = utils.update_ytdlp_library()
        assert ok is False
        assert "failed" in msg.lower()


# ---------------------------------------------------------------------------
# launch_plugin_setup
# ---------------------------------------------------------------------------

class TestLaunchPluginSetup:
    @patch("utils.os.path.exists", return_value=False)
    def test_script_missing(self, mock_exists):
        ok, msg = utils.launch_plugin_setup()
        assert ok is False
        assert "not found" in msg.lower()

    @patch("utils.subprocess.Popen")
    @patch("utils.os.path.exists", return_value=True)
    def test_spawn_success(self, mock_exists, mock_popen):
        with patch("builtins.open", mock_open()):
            ok, msg = utils.launch_plugin_setup()
        assert ok is True
        assert "started" in msg.lower()

    @patch("utils.os.remove")
    @patch("utils.os.path.exists", return_value=True)
    @patch("utils.subprocess.Popen", side_effect=OSError("spawn failed"))
    def test_spawn_failure_cleans_lock(self, mock_popen, mock_exists, mock_remove):
        with patch("builtins.open", mock_open()):
            ok, msg = utils.launch_plugin_setup()
        assert ok is False
        assert "failed" in msg.lower()
        # Lock file should be cleaned up on failure
        mock_remove.assert_called_once()
