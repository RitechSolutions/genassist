"""Settings behaviour for Microsoft SSO redirect allowlist (no full app / DB)."""


def test_microsoft_sso_redirect_url_allowlist(monkeypatch):
    from app.core.config.settings import settings

    monkeypatch.setattr(settings, "SSO_MICROSOFT_POST_LOGIN_FRONTEND_URL", "https://app.example.com", raising=False)
    monkeypatch.setattr(settings, "CORS_ALLOWED_ORIGINS", "https://other.example.com", raising=False)
    monkeypatch.setattr(settings, "SSO_MICROSOFT_POST_LOGIN_ORIGINS_ALLOWLIST", None, raising=False)

    origins = settings.microsoft_sso_allowed_origins()
    assert "https://app.example.com" in origins
    assert "https://other.example.com" in origins

    assert settings.is_microsoft_sso_redirect_url_allowed(
        "https://app.example.com/login/sso-callback?sso_code=abc"
    )
    assert not settings.is_microsoft_sso_redirect_url_allowed("https://evil.example.com/login/sso-callback")
