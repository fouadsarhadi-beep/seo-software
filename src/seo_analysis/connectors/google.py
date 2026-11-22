"""Read-only Google connections for the local CLI."""
from hashlib import sha256
import json
import logging
from pathlib import Path
import re

from filelock import FileLock
import requests

from seo_analysis.connectors.gsc import SCOPE as GSC_SCOPE
from seo_analysis.storage.history import History

SCOPES = {"gsc": GSC_SCOPE, "ga4": "https://www.googleapis.com/auth/analytics.readonly"}
APP_NAME = "SEO Analysis Software Google OAuth"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
SITES_URL = "https://www.googleapis.com/webmasters/v3/sites"
SUMMARIES_URL = "https://analyticsadmin.googleapis.com/v1beta/accountSummaries"
NATIVE_KEYRINGS = {
    "keyring.backends.Windows.WinVaultKeyring",
    "keyring.backends.macOS.Keyring",
    "keyring.backends.SecretService.Keyring",
    "keyring.backends.libsecret.Keyring",
    "keyring.backends.kwallet.DBusKeyring",
}


def native_keyring():
    try:
        import keyring
    except ImportError:
        raise RuntimeError("Install the optional Google dependencies with pip install 'seo-analysis[google]'.") from None
    try:
        backend = keyring.get_keyring()
        backends = backend.backends if type(backend).__module__ == "keyring.backends.chainer" else [backend]
        for candidate in backends:
            kind = type(candidate)
            if f"{kind.__module__}.{kind.__name__}" in NATIVE_KEYRINGS:
                return candidate
    except Exception:
        raise RuntimeError("Unable to open the OS credential store.") from None
    raise RuntimeError("Google connections require an available OS credential store, such as Windows Credential Manager.")


def authorize(client_file, scope):
    from google_auth_oauthlib.flow import InstalledAppFlow

    try:
        installed = json.loads(Path(client_file).read_text(encoding="utf-8"))["installed"]
        client_id, secret = installed["client_id"], installed["client_secret"]
    except (OSError, KeyError, TypeError, ValueError):
        raise ValueError("Select a Google OAuth client JSON file for a Desktop app.") from None
    if (not isinstance(client_id, str) or not client_id.endswith(".apps.googleusercontent.com")
            or not isinstance(secret, str) or not secret):
        raise ValueError("The Desktop app JSON must contain a Google OAuth client ID and secret.")
    flow = InstalledAppFlow.from_client_config({
        "installed": {
            "client_id": client_id, "client_secret": secret, "auth_uri": AUTH_URL, "token_uri": TOKEN_URL,
        }
    }, scopes=[scope], autogenerate_code_verifier=True)
    # The SDK's HTTP access log can include the authorization code in the callback URL.
    logger = logging.getLogger("google_auth_oauthlib.flow")
    previous = logger.disabled
    logger.disabled = True
    try:
        creds = flow.run_local_server(
            host="127.0.0.1", port=0, timeout_seconds=180, prompt="consent",
            authorization_prompt_message="Open this URL on this computer to authorize the connection: {url}",
            success_message="Google consent returned to SEO Analysis Software. Check the terminal for the result.",
        )
    except Exception:
        raise RuntimeError("Google authorization failed or timed out. Check the Desktop app and consent settings.") from None
    finally:
        logger.disabled = previous
    if not creds.refresh_token or (creds.granted_scopes is not None and set(creds.granted_scopes) != {scope}):
        raise RuntimeError("Google did not issue a refresh token with the requested read-only permission.")
    return creds


def google_json(session, method, url, **kwargs):
    from google.auth.exceptions import GoogleAuthError

    try:
        with session.request(method, url, timeout=(5, 30), allow_redirects=False, **kwargs) as response:
            if not response.ok or response.is_redirect:
                raise RuntimeError(f"Google API returned HTTP {response.status_code}.")
            payload = response.json()
    except (requests.RequestException, GoogleAuthError, ValueError):
        raise RuntimeError("Unable to read the Google API response. Check connectivity and Google consent.") from None
    if not isinstance(payload, dict):
        raise RuntimeError("Google returned an unexpected response.")
    return payload


def properties(service, session):
    if service == "gsc":
        sites = google_json(session, "GET", SITES_URL).get("siteEntry", [])
        return {site["siteUrl"]: site["siteUrl"] for site in sites
                if isinstance(site.get("siteUrl"), str) and site.get("permissionLevel") in {"siteOwner", "siteFullUser", "siteRestrictedUser"}}

    found = {}
    token = None
    for _ in range(100):
        params = {"pageSize": 200}
        if token:
            params["pageToken"] = token
        response = google_json(session, "GET", SUMMARIES_URL, params=params)
        for account in response.get("accountSummaries", []):
            for prop in account.get("propertySummaries", []):
                name = prop.get("property")
                if isinstance(name, str) and re.fullmatch(r"properties/[0-9]+", name):
                    found[name] = prop.get("displayName") or name
        token = response.get("nextPageToken")
        if not token:
            return found
    raise RuntimeError("Google Analytics property listing exceeded 100 pages.")


class GoogleConnection:
    def __init__(self, workspace, project, service):
        self.history = History(workspace)
        self.history.selection(project, None)
        self.project = project
        self.service = service
        self.scope = SCOPES[service]
        identity = json.dumps([str(workspace.data_dir.resolve()), project, service])
        self.key = sha256(identity.encode()).hexdigest()
        self.lock = FileLock(str(workspace.data_dir / f".google-{self.key}.lock"), timeout=10)

    def selected(self):
        return self.history.google_connection(self.project, self.service)

    def _credential_call(self, backend, method, *args):
        try:
            return getattr(backend, method)(APP_NAME, self.key, *args)
        except Exception:
            raise RuntimeError("Unable to access the OS credential store.") from None

    def connect(self, client_file, choose):
        from google.auth.transport.requests import AuthorizedSession

        backend = native_keyring()
        self._credential_call(backend, "get_password")
        credentials = authorize(client_file, self.scope)
        with AuthorizedSession(credentials, refresh_timeout=30) as session:
            available = properties(self.service, session)
        property_id = choose(available)
        if property_id not in available:
            raise ValueError("Select the ID of a property listed for this account.")
        record = json.dumps({"refresh_token": credentials.refresh_token, "client_id": credentials.client_id,
                             "client_secret": credentials.client_secret})
        self.history.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            previous = self._credential_call(backend, "get_password")
            self._credential_call(backend, "set_password", record)
            try:
                self.history.set_google_connection(self.project, self.service, property_id, available[property_id])
            except Exception:
                if previous is None:
                    self._credential_call(backend, "delete_password")
                else:
                    self._credential_call(backend, "set_password", previous)
                raise
        return {"property_id": property_id, "property_name": available[property_id]}

    def disconnect(self, *, revoke=False):
        backend = native_keyring()
        self.history.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            record = self._credential_call(backend, "get_password")
            if record is not None:
                if revoke:
                    with requests.Session() as session:
                        try:
                            with session.post(REVOKE_URL, data={"token": json.loads(record)["refresh_token"]},
                                              timeout=(5, 15), allow_redirects=False) as response:
                                # An already-invalid token needs only local cleanup.
                                invalid = response.status_code == 400 and response.json().get("error") == "invalid_token"
                                if response.status_code != 200 and not invalid:
                                    raise RuntimeError("Google did not revoke the grant. Retry or run disconnect without --revoke.")
                        except (requests.RequestException, ValueError):
                            raise RuntimeError("Unable to revoke the Google grant. Retry or run disconnect without --revoke.") from None
                self._credential_call(backend, "delete_password")
            self.history.remove_google_connection(self.project, self.service)
