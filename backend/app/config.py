"""Runtime settings, read from the environment (or ../.env)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    db_path: Path = ROOT / "data" / "elnino.db"
    host: str = "127.0.0.1"
    port: int = 8911
    # Set to 0 to disable the background scheduler (tests, one-shot runs).
    scheduler: bool = True
    # Identify politely to the data providers. Set CONTACT (an email or URL) so they can reach you.
    contact: str = ""
    user_agent: str = "ElNinoWatch/0.1 (open-source ENSO tracker; +https://github.com/SoCloseSociety/elnino-watch)"

    # The watched place. Default = the centre of Koh Samui, Thailand; set HOME_NAME / HOME_LAT /
    # HOME_LON (a village, a pier, ...) in .env to move the watch point without touching the code.
    home_name: str = "Koh Samui"
    home_lat: float = 9.512
    home_lon: float = 100.013
    home_radius_km: float = 800.0

    # Optional credentials. Every collector that needs one reports
    # "needs_config" on the sources page instead of failing silently.
    x_bearer_token: str = ""
    x_auth_token: str = ""          # optional X cookie session (auth_token)
    x_ct0: str = ""                 # optional X cookie session (ct0)
    bluesky_handle: str = ""
    bluesky_app_password: str = ""
    telegram_api_id: str = ""       # Telethon user session, for reading channels
    telegram_api_hash: str = ""
    firms_map_key: str = ""         # NASA FIRMS active fires
    neo_api_url: str = ""           # optional webhook base URL: POST {url}/device_alert (see docs/BOT_CONNECTOR.md)
    neo_api_token: str = ""         # its Bearer token
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    computeforge_url: str = "https://computeforge.soclose.co"
    computeforge_key: str = ""
    briefing_model: str = "claude-fable-5-1"

    # Public deployment (app/security.py). public_mode=true: every write on /api and
    # the heavy upstream-triggering GETs need the X-Admin-Token header == admin_token
    # (empty admin_token = nobody is admin, fail closed); /docs, /redoc, /openapi.json
    # are off; a strict Content-Security-Policy is sent.
    public_mode: bool = False
    admin_token: str = ""

    # SEO (app/seo.py). public_origin is the ONE canonical origin: canonical links,
    # sitemap, Open Graph URLs, robots.txt and JSON-LD all derive from it. Set PUBLIC_ORIGIN
    # (no trailing slash, e.g. https://elnino.example.com) on a public deployment.
    public_origin: str = "http://127.0.0.1:8911"
    site_name: str = "El Nino Watch"
    org_name: str = "SoClose"
    org_url: str = "https://soclose.co"
    # Search engine ownership proofs, rendered as <meta> tags when set
    # (Google Search Console "HTML tag" method, Bing Webmaster "meta tag" method).
    google_site_verification: str = ""
    bing_site_verification: str = ""
    # IndexNow (Bing / Yandex / Seznam / Naver instant indexing). Key = 8-128 hex/alnum
    # chars, served at /<key>.txt. Pings only run when the key is set AND public_origin
    # is not the throw-away sslip.io name (indexnow_enabled property in app/seo.py).
    indexnow_key: str = ""


settings = Settings()
if settings.contact and settings.contact not in settings.user_agent:
    # "ElNinoWatch/0.1 (...; contact you@example.com)": providers can reach the operator.
    settings.user_agent = settings.user_agent.rstrip(")") + f"; contact {settings.contact})"
