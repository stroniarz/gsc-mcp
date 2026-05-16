"""Auth: OAuth2 user-flow (default) or Service Account (fallback)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
CONFIG_DIR = Path.home() / ".config" / "gsc-mcp"
SA_KEY_PATH = CONFIG_DIR / "sa-key.json"
OAUTH_CLIENT_PATH = CONFIG_DIR / "oauth-client.json"
OAUTH_TOKENS_PATH = CONFIG_DIR / "oauth-tokens.json"


def _resolve(path_env: str, default: Path) -> Path:
    v = os.environ.get(path_env)
    return Path(v).expanduser() if v else default


def _load_oauth_creds() -> Credentials:
    client_path = _resolve("GSC_MCP_OAUTH_CLIENT", OAUTH_CLIENT_PATH)
    tokens_path = _resolve("GSC_MCP_OAUTH_TOKENS", OAUTH_TOKENS_PATH)

    creds: Credentials | None = None
    if tokens_path.exists():
        creds = Credentials.from_authorized_user_info(
            json.loads(tokens_path.read_text()), SCOPES
        )

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        tokens_path.write_text(creds.to_json())
        tokens_path.chmod(0o600)
        return creds

    if not client_path.exists():
        raise RuntimeError(
            f"OAuth client not found at {client_path}. "
            "Download Desktop OAuth client JSON from Google Cloud Console "
            "(APIs & Services → Credentials → Create Credentials → OAuth client ID → Desktop app) "
            f"and place it at {client_path}, or set GSC_MCP_OAUTH_CLIENT env var. "
            "See README for the full setup."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
    creds = flow.run_local_server(
        port=0,
        prompt="consent",
        access_type="offline",
        open_browser=True,
    )
    tokens_path.parent.mkdir(parents=True, exist_ok=True)
    tokens_path.write_text(creds.to_json())
    tokens_path.chmod(0o600)
    return creds


def _load_sa_creds() -> service_account.Credentials:
    key_path = _resolve("GSC_MCP_SA_KEY", SA_KEY_PATH)
    if not key_path.exists():
        raise RuntimeError(
            f"Service Account key not found at {key_path}. "
            "Set GSC_MCP_SA_KEY env var or place the JSON at the default path."
        )
    return service_account.Credentials.from_service_account_file(
        str(key_path), scopes=SCOPES
    )


def get_service():
    mode = os.environ.get("GSC_MCP_AUTH", "oauth").lower()
    if mode == "sa":
        creds = _load_sa_creds()
    elif mode == "oauth":
        creds = _load_oauth_creds()
    else:
        raise RuntimeError(
            f"Unknown GSC_MCP_AUTH mode: {mode!r} (expected 'oauth' or 'sa')"
        )
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)
