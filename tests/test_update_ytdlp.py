"""Tests for plugin/update_ytdlp.py"""

import json
from unittest.mock import MagicMock, mock_open, patch
from urllib.error import URLError

import pytest

import update_ytdlp


# ---------------------------------------------------------------------------
# download_ytdlp_from_pypi
# ---------------------------------------------------------------------------

class TestDownloadYtdlpFromPypi:
    def _make_pypi_response(self, version="2024.12.01"):
        """Helper: mock PyPI JSON response with a compatible wheel."""
        data = {
            "info": {"version": version},
            "urls": [
                {
                    "filename": f"yt_dlp-{version}-py3-none-any.whl",
                    "url": f"https://files.pythonhosted.org/yt_dlp-{version}-py3-none-any.whl",
                },
                {
                    "filename": f"yt_dlp-{version}.tar.gz",
                    "url": f"https://files.pythonhosted.org/yt_dlp-{version}.tar.gz",
                },
            ],
        }
        return json.dumps(data).encode("utf-8")

    def _mock_urlopen(self, *responses):
        """
        Create a side_effect for urlopen that returns successive mock responses.
        Each response is raw bytes.
        """
        mocks = []
        for resp_data in responses:
            mock_resp = MagicMock()
            mock_resp.read.return_value = resp_data
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mocks.append(mock_resp)
        return mocks

    @patch("update_ytdlp.os.remove")
    @patch("update_ytdlp.zipfile.ZipFile")
    @patch("update_ytdlp.glob.glob", return_value=[])
    @patch("update_ytdlp.shutil.rmtree")
    @patch("update_ytdlp.os.path.exists", return_value=False)
    @patch("update_ytdlp.os.makedirs")
    @patch("update_ytdlp.urlopen")
    def test_full_success(self, mock_urlopen, mock_makedirs, mock_exists,
                          mock_rmtree, mock_glob, mock_zipfile, mock_remove):
        pypi_data = self._make_pypi_response()
        wheel_data = b"fake-wheel-contents"
        responses = self._mock_urlopen(pypi_data, wheel_data)
        mock_urlopen.side_effect = responses

        mock_zip = MagicMock()
        mock_zip.__enter__ = MagicMock(return_value=mock_zip)
        mock_zip.__exit__ = MagicMock(return_value=False)
        mock_zipfile.return_value = mock_zip

        with patch("builtins.open", mock_open()):
            ok, result = update_ytdlp.download_ytdlp_from_pypi()

        assert ok is True
        assert result == "2024.12.01"
        mock_zip.extractall.assert_called_once()

    @patch("update_ytdlp.urlopen", side_effect=URLError("timeout"))
    def test_network_error(self, mock_urlopen):
        ok, msg = update_ytdlp.download_ytdlp_from_pypi()
        assert ok is False
        assert "Network error" in msg

    @patch("update_ytdlp.urlopen")
    def test_generic_fetch_error(self, mock_urlopen):
        mock_urlopen.side_effect = ValueError("bad data")
        ok, msg = update_ytdlp.download_ytdlp_from_pypi()
        assert ok is False
        assert "Failed to fetch" in msg

    @patch("update_ytdlp.urlopen")
    def test_no_compatible_wheel(self, mock_urlopen):
        # PyPI response with no wheel, only tarball
        data = {
            "info": {"version": "2024.12.01"},
            "urls": [
                {"filename": "yt_dlp-2024.12.01.tar.gz", "url": "https://example.com/tarball"},
            ],
        }
        responses = self._mock_urlopen(json.dumps(data).encode("utf-8"))
        mock_urlopen.side_effect = responses

        ok, msg = update_ytdlp.download_ytdlp_from_pypi()
        assert ok is False
        assert "No compatible wheel" in msg

    @patch("update_ytdlp.os.path.exists", return_value=True)
    @patch("update_ytdlp.os.remove")
    @patch("update_ytdlp.os.makedirs")
    @patch("update_ytdlp.urlopen")
    def test_wheel_download_fails(self, mock_urlopen, mock_makedirs,
                                   mock_remove, mock_exists):
        pypi_data = self._make_pypi_response()
        pypi_resp = self._mock_urlopen(pypi_data)[0]
        # First call returns PyPI data, second raises
        mock_urlopen.side_effect = [pypi_resp, Exception("download failed")]

        ok, msg = update_ytdlp.download_ytdlp_from_pypi()
        assert ok is False
        assert "Download failed" in msg
        # Cleanup: wheel file should be removed
        mock_remove.assert_called_once()

    @patch("update_ytdlp.zipfile.ZipFile", side_effect=Exception("extract failed"))
    @patch("update_ytdlp.glob.glob", return_value=[])
    @patch("update_ytdlp.shutil.rmtree")
    @patch("update_ytdlp.os.path.exists", return_value=False)
    @patch("update_ytdlp.os.makedirs")
    @patch("update_ytdlp.urlopen")
    def test_installation_fails(self, mock_urlopen, mock_makedirs,
                                 mock_exists, mock_rmtree, mock_glob,
                                 mock_zipfile):
        pypi_data = self._make_pypi_response()
        wheel_data = b"fake-wheel"
        responses = self._mock_urlopen(pypi_data, wheel_data)
        mock_urlopen.side_effect = responses

        with patch("builtins.open", mock_open()):
            ok, msg = update_ytdlp.download_ytdlp_from_pypi()

        assert ok is False
        assert "Installation failed" in msg

    @patch("update_ytdlp.os.remove")
    @patch("update_ytdlp.zipfile.ZipFile")
    @patch("update_ytdlp.glob.glob", return_value=["/lib/yt_dlp-2024.11.01.dist-info"])
    @patch("update_ytdlp.shutil.rmtree")
    @patch("update_ytdlp.os.path.exists", return_value=False)
    @patch("update_ytdlp.os.makedirs")
    @patch("update_ytdlp.urlopen")
    def test_old_dist_info_cleaned(self, mock_urlopen, mock_makedirs,
                                    mock_exists, mock_rmtree, mock_glob,
                                    mock_zipfile, mock_remove):
        pypi_data = self._make_pypi_response()
        wheel_data = b"fake-wheel"
        responses = self._mock_urlopen(pypi_data, wheel_data)
        mock_urlopen.side_effect = responses

        mock_zip = MagicMock()
        mock_zip.__enter__ = MagicMock(return_value=mock_zip)
        mock_zip.__exit__ = MagicMock(return_value=False)
        mock_zipfile.return_value = mock_zip

        with patch("builtins.open", mock_open()):
            ok, result = update_ytdlp.download_ytdlp_from_pypi()

        assert ok is True
        # rmtree called for old dist-info from glob
        rmtree_paths = [str(c) for c in mock_rmtree.call_args_list]
        assert any("dist-info" in p for p in rmtree_paths)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

class TestMain:
    @patch("update_ytdlp.time.sleep")
    @patch("update_ytdlp.sys.exit")
    @patch("update_ytdlp.os.makedirs", side_effect=OSError("no perms"))
    def test_lock_creation_fails(self, mock_makedirs, mock_exit, mock_sleep):
        mock_exit.side_effect = SystemExit(1)
        with pytest.raises(SystemExit):
            update_ytdlp.main()
        mock_exit.assert_called_once_with(1)

    @patch("update_ytdlp.time.sleep")
    @patch("update_ytdlp.os.remove")
    @patch("update_ytdlp.os.path.exists", return_value=True)
    @patch("update_ytdlp.os.makedirs")
    @patch("update_ytdlp.download_ytdlp_from_pypi", return_value=(True, "2024.12.01"))
    def test_success_writes_marker(self, mock_download, mock_makedirs,
                                    mock_exists, mock_remove, mock_sleep):
        m = mock_open()
        with patch("builtins.open", m):
            update_ytdlp.main()

        # Verify marker file was written
        written_data = [
            call_args
            for call_args in m().write.call_args_list
        ]
        assert any("updated" in str(c) for c in written_data)
        # Lock file removed
        mock_remove.assert_called_once()

    @patch("update_ytdlp.time.sleep")
    @patch("update_ytdlp.os.remove")
    @patch("update_ytdlp.os.path.exists", return_value=True)
    @patch("update_ytdlp.os.makedirs")
    @patch("update_ytdlp.download_ytdlp_from_pypi", return_value=(False, "error"))
    def test_failure_no_marker(self, mock_download, mock_makedirs,
                                mock_exists, mock_remove, mock_sleep):
        m = mock_open()
        with patch("builtins.open", m):
            update_ytdlp.main()

        # Only lock file write ("updating"), no marker write ("updated")
        written_data = [str(c) for c in m().write.call_args_list]
        assert not any("updated" in w for w in written_data)
        # Lock file still removed
        mock_remove.assert_called_once()

    @patch("update_ytdlp.time.sleep")
    @patch("update_ytdlp.os.remove", side_effect=OSError("locked"))
    @patch("update_ytdlp.os.path.exists", return_value=True)
    @patch("update_ytdlp.os.makedirs")
    @patch("update_ytdlp.download_ytdlp_from_pypi", return_value=(True, "2024.12.01"))
    def test_lock_removal_fails_silently(self, mock_download, mock_makedirs,
                                          mock_exists, mock_remove, mock_sleep):
        # Should not raise even if lock removal fails
        with patch("builtins.open", mock_open()):
            update_ytdlp.main()  # no exception
