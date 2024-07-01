from unittest.mock import Mock

from llm_github.core import get_rate_limit, return_verbatim


def test_return_verbatim():
    assert return_verbatim("foo") == "foo"


def test_get_rate_limit():
    mock_session = Mock()
    mock_session.get.return_value.status_code = 200
    mock_session.get.return_value.json.return_value = {"rate": {"limit": 5000, "remaining": 4999}}

    token = "fake_token"  # noqa: S105
    result = get_rate_limit(token, mock_session)
    assert result == {"limit": 5000, "remaining": 4999}
