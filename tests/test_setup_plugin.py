"""Tests for plugin/setup_plugin.py"""

import zipfile
from unittest.mock import MagicMock, call, mock_open, patch

import pytest

import setup_plugin


# ---------------------------------------------------------------------------
# is_ffmpeg_needed
# ---------------------------------------------------------------------------

class TestIsFfmpegNeeded:
    @patch("setup_plugin.os.path.getsize", return_value=1024)
    @patch("setup_plugin.os.path.isfile", return_value=True)
    def test_both_present_and_nonempty(self, mock_isfile, mock_getsize):
        assert setup_plugin.is_ffmpeg_needed() is False

    @patch("setup_plugin.os.path.isfile", return_value=False)
    def test_both_missing(self, mock_isfile):
        assert setup_plugin.is_ffmpeg_needed() is True

    @patch("setup_plugin.os.path.getsize", return_value=1024)
    @patch("setup_plugin.os.path.isfile")
    def test_one_missing(self, mock_isfile, mock_getsize):
        # First file exists, second doesn't
        mock_isfile.side_effect = [True, False]
        assert setup_plugin.is_ffmpeg_needed() is True

    @patch("setup_plugin.os.path.getsize")
    @patch("setup_plugin.os.path.isfile", return_value=True)
    def test_one_zero_size(self, mock_isfile, mock_getsize):
        # First non-empty, second empty
        mock_getsize.side_effect = [1024, 0]
        assert setup_plugin.is_ffmpeg_needed() is True


# ---------------------------------------------------------------------------
# is_ytdlp_update_needed
# ---------------------------------------------------------------------------

class TestIsYtdlpUpdateNeeded:
    @patch("setup_plugin.os.path.exists", return_value=True)
    def test_both_exist(self, mock_exists):
        assert setup_plugin.is_ytdlp_update_needed() is False

    @patch("setup_plugin.os.path.exists")
    def test_dir_missing(self, mock_exists):
        # yt_dlp dir doesn't exist
        mock_exists.return_value = False
        assert setup_plugin.is_ytdlp_update_needed() is True

    @patch("setup_plugin.os.path.exists")
    def test_marker_missing(self, mock_exists):
        # yt_dlp dir exists, marker doesn't
        mock_exists.side_effect = [True, False]
        assert setup_plugin.is_ytdlp_update_needed() is True


# ---------------------------------------------------------------------------
# download_ffmpeg
# ---------------------------------------------------------------------------

class TestDownloadFfmpeg:
    def _mock_zip(self):
        """Create a mock ZipFile that passes all validations."""
        mock_info1 = MagicMock()
        mock_info1.filename = "ffmpeg.exe"
        mock_info1.file_size = 1024
        mock_info2 = MagicMock()
        mock_info2.filename = "ffprobe.exe"
        mock_info2.file_size = 1024

        mock_zip = MagicMock()
        mock_zip.namelist.return_value = ["ffmpeg.exe", "ffprobe.exe"]
        mock_zip.infolist.return_value = [mock_info1, mock_info2]
        mock_zip.__enter__ = MagicMock(return_value=mock_zip)
        mock_zip.__exit__ = MagicMock(return_value=False)
        return mock_zip

    @patch("setup_plugin.os.remove")
    @patch("setup_plugin.zipfile.ZipFile")
    @patch("setup_plugin.os.path.getsize", return_value=1024)
    @patch("setup_plugin.os.path.exists", return_value=True)
    @patch("setup_plugin.subprocess.run")
    def test_full_success(self, mock_run, mock_exists, mock_getsize,
                          mock_zipfile, mock_remove):
        mock_zipfile.return_value = self._mock_zip()
        assert setup_plugin.download_ffmpeg() is True
        mock_run.assert_called_once()

    @patch("setup_plugin.os.remove")
    @patch("setup_plugin.zipfile.ZipFile")
    @patch("setup_plugin.os.path.getsize", return_value=1024)
    @patch("setup_plugin.os.path.exists", return_value=True)
    @patch("setup_plugin.subprocess.run")
    def test_first_curl_fails_shell_succeeds(self, mock_run, mock_exists,
                                              mock_getsize, mock_zipfile, mock_remove):
        # First call raises, second succeeds
        mock_run.side_effect = [Exception("command not found"), None]
        mock_zipfile.return_value = self._mock_zip()
        assert setup_plugin.download_ffmpeg() is True
        assert mock_run.call_count == 2

    @patch("setup_plugin.subprocess.run", side_effect=Exception("curl failed"))
    def test_both_curl_fail(self, mock_run):
        assert setup_plugin.download_ffmpeg() is False

    @patch("setup_plugin.os.path.exists", return_value=False)
    @patch("setup_plugin.subprocess.run")
    def test_zip_not_created(self, mock_run, mock_exists):
        assert setup_plugin.download_ffmpeg() is False

    @patch("setup_plugin.os.remove")
    @patch("setup_plugin.os.path.getsize", return_value=0)
    @patch("setup_plugin.os.path.exists", return_value=True)
    @patch("setup_plugin.subprocess.run")
    def test_empty_zip(self, mock_run, mock_exists, mock_getsize, mock_remove):
        assert setup_plugin.download_ffmpeg() is False
        mock_remove.assert_called_once()

    @patch("setup_plugin.os.remove")
    @patch("setup_plugin.zipfile.ZipFile")
    @patch("setup_plugin.os.path.getsize", return_value=1024)
    @patch("setup_plugin.os.path.exists", return_value=True)
    @patch("setup_plugin.subprocess.run")
    def test_missing_required_files_in_zip(self, mock_run, mock_exists,
                                            mock_getsize, mock_zipfile, mock_remove):
        mock_zip = MagicMock()
        mock_zip.namelist.return_value = ["readme.txt"]
        mock_zip.__enter__ = MagicMock(return_value=mock_zip)
        mock_zip.__exit__ = MagicMock(return_value=False)
        mock_zipfile.return_value = mock_zip
        assert setup_plugin.download_ffmpeg() is False

    @patch("setup_plugin.os.remove")
    @patch("setup_plugin.zipfile.ZipFile")
    @patch("setup_plugin.os.path.getsize", return_value=1024)
    @patch("setup_plugin.os.path.exists", return_value=True)
    @patch("setup_plugin.subprocess.run")
    def test_empty_exe_in_zip(self, mock_run, mock_exists, mock_getsize,
                               mock_zipfile, mock_remove):
        mock_info = MagicMock()
        mock_info.filename = "ffmpeg.exe"
        mock_info.file_size = 0

        mock_zip = MagicMock()
        mock_zip.namelist.return_value = ["ffmpeg.exe", "ffprobe.exe"]
        mock_zip.infolist.return_value = [mock_info]
        mock_zip.__enter__ = MagicMock(return_value=mock_zip)
        mock_zip.__exit__ = MagicMock(return_value=False)
        mock_zipfile.return_value = mock_zip
        assert setup_plugin.download_ffmpeg() is False

    @patch("setup_plugin.os.remove")
    @patch("setup_plugin.zipfile.ZipFile", side_effect=zipfile.BadZipFile("bad"))
    @patch("setup_plugin.os.path.getsize", return_value=1024)
    @patch("setup_plugin.os.path.exists", return_value=True)
    @patch("setup_plugin.subprocess.run")
    def test_bad_zip_file(self, mock_run, mock_exists, mock_getsize,
                           mock_zipfile, mock_remove):
        assert setup_plugin.download_ffmpeg() is False


# ---------------------------------------------------------------------------
# update_ytdlp
# ---------------------------------------------------------------------------

class TestUpdateYtdlp:
    def _run_update_ytdlp(self, download_return):
        """
        Run setup_plugin.update_ytdlp() with download_ytdlp_from_pypi mocked.
        The function does `from update_ytdlp import download_ytdlp_from_pypi`
        at call time, so we mock via a fake module in sys.modules.
        """
        mock_module = MagicMock()
        mock_module.download_ytdlp_from_pypi.return_value = download_return
        with patch.dict("sys.modules", {"update_ytdlp": mock_module}), \
             patch("setup_plugin.os.makedirs"), \
             patch("builtins.open", mock_open()):
            # Force re-import inside update_ytdlp()
            return setup_plugin.update_ytdlp()

    def test_success(self):
        assert self._run_update_ytdlp((True, "2024.12.01")) is True

    def test_failure(self):
        assert self._run_update_ytdlp((False, "error")) is False


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

class TestMain:
    @patch("setup_plugin.time.sleep")
    @patch("setup_plugin.sys.exit")
    def test_lock_creation_fails(self, mock_exit, mock_sleep):
        mock_exit.side_effect = SystemExit(1)
        with patch("builtins.open", side_effect=OSError("permission denied")):
            with pytest.raises(SystemExit):
                setup_plugin.main()
        mock_exit.assert_called_once_with(1)

    @patch("setup_plugin.time.sleep")
    @patch("setup_plugin.os.remove")
    @patch("setup_plugin.os.path.exists", return_value=True)
    @patch("setup_plugin.update_ytdlp", return_value=True)
    @patch("setup_plugin.download_ffmpeg", return_value=True)
    @patch("setup_plugin.is_ytdlp_update_needed", return_value=True)
    @patch("setup_plugin.is_ffmpeg_needed", return_value=True)
    def test_both_needed_both_succeed(self, mock_ffmpeg_needed, mock_ytdlp_needed,
                                      mock_dl_ffmpeg, mock_update_ytdlp,
                                      mock_exists, mock_remove, mock_sleep):
        with patch("builtins.open", mock_open()):
            setup_plugin.main()
        mock_dl_ffmpeg.assert_called_once()
        mock_update_ytdlp.assert_called_once()
        mock_remove.assert_called_once()  # lock cleaned up

    @patch("setup_plugin.time.sleep")
    @patch("setup_plugin.os.remove")
    @patch("setup_plugin.os.path.exists", return_value=True)
    @patch("setup_plugin.update_ytdlp")
    @patch("setup_plugin.download_ffmpeg")
    @patch("setup_plugin.is_ytdlp_update_needed", return_value=False)
    @patch("setup_plugin.is_ffmpeg_needed", return_value=False)
    def test_neither_needed(self, mock_ffmpeg_needed, mock_ytdlp_needed,
                             mock_dl_ffmpeg, mock_update_ytdlp,
                             mock_exists, mock_remove, mock_sleep):
        with patch("builtins.open", mock_open()):
            setup_plugin.main()
        mock_dl_ffmpeg.assert_not_called()
        mock_update_ytdlp.assert_not_called()

    @patch("setup_plugin.time.sleep")
    @patch("setup_plugin.os.remove")
    @patch("setup_plugin.os.path.exists", return_value=True)
    @patch("setup_plugin.is_ytdlp_update_needed", return_value=False)
    @patch("setup_plugin.is_ffmpeg_needed", side_effect=Exception("unexpected"))
    def test_exception_still_cleans_lock(self, mock_ffmpeg_needed,
                                         mock_ytdlp_needed, mock_exists,
                                         mock_remove, mock_sleep):
        with patch("builtins.open", mock_open()):
            with pytest.raises(Exception, match="unexpected"):
                setup_plugin.main()
        # Lock still cleaned up via finally
        mock_remove.assert_called_once()
