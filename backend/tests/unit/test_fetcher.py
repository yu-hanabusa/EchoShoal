"""GitHub README取得のユニットテスト."""

from app.core.documents.fetcher import is_github_url


class TestIsGithubUrl:
    def test_valid_github_url(self):
        assert is_github_url("https://github.com/owner/repo") is True

    def test_valid_github_url_with_trailing_slash(self):
        assert is_github_url("https://github.com/owner/repo/") is True

    def test_valid_github_url_with_git_extension(self):
        assert is_github_url("https://github.com/owner/repo.git") is True

    def test_http_github_url(self):
        assert is_github_url("http://github.com/owner/repo") is True

    def test_invalid_url(self):
        assert is_github_url("https://gitlab.com/owner/repo") is False

    def test_github_subpath(self):
        assert is_github_url("https://github.com/owner/repo/tree/main") is False

    def test_none_url(self):
        assert is_github_url(None) is False

    def test_empty_url(self):
        assert is_github_url("") is False
