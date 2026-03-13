"""Tests for PlaudClient."""

from unittest.mock import patch, MagicMock, call
import pytest

from plaud_downloader.client import PlaudClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_auth_response(token="test-token-123"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"access_token": token}
    resp.raise_for_status = MagicMock()
    return resp


def _mock_json_response(data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TestAuth:
    @patch("plaud_downloader.client.requests.Session")
    def test_auth_sends_correct_request(self, MockSession):
        session = MockSession.return_value
        session.post.return_value = _mock_auth_response("my-token")

        client = PlaudClient("user@example.com", "s3cret")

        # Should have called POST to the auth endpoint
        session.post.assert_called_once()
        args, kwargs = session.post.call_args
        assert args[0] == "https://api.plaud.ai/auth/access-token"
        assert kwargs["data"]["username"] == "user@example.com"
        assert kwargs["data"]["password"] == "s3cret"
        assert kwargs["data"]["client_id"] == "web"

        # Token stored
        assert client._token == "my-token"

    @patch("plaud_downloader.client.requests.Session")
    def test_auth_uses_eu_base(self, MockSession):
        session = MockSession.return_value
        session.post.return_value = _mock_auth_response()

        PlaudClient("u@e.com", "pw", base_url="https://api-euc1.plaud.ai")

        args, _ = session.post.call_args
        assert args[0] == "https://api-euc1.plaud.ai/auth/access-token"

    @patch("plaud_downloader.client.requests.Session")
    def test_auth_raises_on_failure(self, MockSession):
        session = MockSession.return_value
        resp = MagicMock()
        resp.raise_for_status.side_effect = Exception("401 Unauthorized")
        session.post.return_value = resp

        with pytest.raises(Exception, match="401"):
            PlaudClient("u@e.com", "bad")

    @patch("plaud_downloader.client.requests.Session")
    def test_auth_sets_browser_headers(self, MockSession):
        session = MockSession.return_value
        session.post.return_value = _mock_auth_response("tok")

        PlaudClient("u@e.com", "pw")

        # First call sets browser headers, second sets Authorization
        headers = session.headers.update.call_args_list[0][0][0]
        assert headers["Origin"] == "https://app.plaud.ai"
        assert headers["Referer"] == "https://app.plaud.ai/"
        assert "Safari" in headers["User-Agent"]
        assert headers["app-platform"] == "web"


# ---------------------------------------------------------------------------
# list_recordings
# ---------------------------------------------------------------------------

class TestListRecordings:
    @patch("plaud_downloader.client.requests.Session")
    def test_list_recordings_single_page(self, MockSession):
        session = MockSession.return_value
        session.post.return_value = _mock_auth_response()

        files = [{"id": "f1"}, {"id": "f2"}]
        session.get.return_value = _mock_json_response({
            "status": 0,
            "data_file_list": files,
        })

        client = PlaudClient("u@e.com", "pw")
        result = client.list_recordings(limit=200)

        assert result == files
        session.get.assert_called_once()
        url = session.get.call_args[0][0]
        assert "/file/simple/web" in url

    @patch("plaud_downloader.client.requests.Session")
    def test_list_recordings_paginates(self, MockSession):
        session = MockSession.return_value
        session.post.return_value = _mock_auth_response()

        page1 = [{"id": f"f{i}"} for i in range(3)]
        page2 = [{"id": "extra"}]

        session.get.side_effect = [
            _mock_json_response({"status": 0, "data_file_list": page1}),
            _mock_json_response({"status": 0, "data_file_list": page2}),
        ]

        client = PlaudClient("u@e.com", "pw")
        result = client.list_recordings(limit=3)

        assert len(result) == 4
        assert session.get.call_count == 2

    @patch("plaud_downloader.client.requests.Session")
    def test_list_recordings_has_cache_buster(self, MockSession):
        session = MockSession.return_value
        session.post.return_value = _mock_auth_response()
        session.get.return_value = _mock_json_response({
            "status": 0, "data_file_list": [],
        })

        client = PlaudClient("u@e.com", "pw")
        client.list_recordings()

        url = session.get.call_args[0][0]
        assert "r=" in url


# ---------------------------------------------------------------------------
# get_tags
# ---------------------------------------------------------------------------

class TestGetTags:
    @patch("plaud_downloader.client.requests.Session")
    def test_get_tags(self, MockSession):
        session = MockSession.return_value
        session.post.return_value = _mock_auth_response()

        tags = [{"id": "t1", "name": "Work"}, {"id": "t2", "name": "Personal"}]
        session.get.return_value = _mock_json_response({
            "status": 0,
            "data_filetag_list": tags,
        })

        client = PlaudClient("u@e.com", "pw")
        result = client.get_tags()

        assert result == tags
        url = session.get.call_args[0][0]
        assert "/filetag/" in url
        assert "r=" in url


# ---------------------------------------------------------------------------
# get_recording_details
# ---------------------------------------------------------------------------

class TestGetRecordingDetails:
    @patch("plaud_downloader.client.requests.Session")
    def test_get_recording_details(self, MockSession):
        session = MockSession.return_value
        # First post is auth, second is the details call
        auth_resp = _mock_auth_response()
        details = [
            {"id": "f1", "trans_result": "hello", "ai_content": "summary"},
        ]
        details_resp = _mock_json_response({
            "status": 0,
            "data_file_list": details,
        })
        session.post.side_effect = [auth_resp, details_resp]

        client = PlaudClient("u@e.com", "pw")
        result = client.get_recording_details(["f1"])

        assert result == details
        # Second post call is for details
        _, kwargs = session.post.call_args
        assert kwargs["json"] == ["f1"]

    @patch("plaud_downloader.client.requests.Session")
    def test_get_recording_details_url(self, MockSession):
        session = MockSession.return_value
        session.post.side_effect = [
            _mock_auth_response(),
            _mock_json_response({"status": 0, "data_file_list": []}),
        ]

        client = PlaudClient("u@e.com", "pw")
        client.get_recording_details(["a", "b"])

        url = session.post.call_args[0][0]
        assert "/file/list" in url
        assert "support_mul_summ=true" in url
