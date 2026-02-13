"""FMCClient - Thin synchronous HTTP client for Cisco FMC REST API."""

import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import requests
import urllib3

# Suppress SSL warnings for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class FMCClient:
    """Synchronous FMC REST API client.

    Handles authentication, token lifecycle (30-min expiry, 3 refresh max),
    domain UUID resolution, and self-signed cert support.

    Usage as context manager:
        with FMCClient(host, username, password) as fmc:
            networks = fmc.get("/object/networks")

    Usage as plain library:
        fmc = FMCClient(host, username, password)
        fmc.connect()
        networks = fmc.get("/object/networks")
        fmc.close()
    """

    def __init__(
        self,
        host: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        domain: Optional[str] = None,
        verify_ssl: Optional[bool] = None,
    ):
        self.host = (host or os.getenv("FMC_HOST", "192.168.45.45")).rstrip("/")
        self.username = username or os.getenv("FMC_USERNAME", "admin")
        self.password = password or os.getenv("FMC_PASSWORD", "Admin123")
        self.domain_name = domain or os.getenv("FMC_DOMAIN", "Global")
        if verify_ssl is not None:
            self.verify_ssl = verify_ssl
        else:
            self.verify_ssl = os.getenv("FMC_VERIFY_SSL", "false").lower() == "true"

        self.base_url = f"https://{self.host}/api"
        self.auth_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.domain_uuid: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self.refresh_count = 0
        self.session: Optional[requests.Session] = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def connect(self) -> None:
        """Create session and authenticate."""
        self.session = requests.Session()
        self.session.verify = self.verify_ssl
        try:
            self._authenticate()
        except Exception:
            self.session.close()
            self.session = None
            raise

    def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            self.session.close()
            self.session = None

    def _authenticate(self) -> None:
        """Authenticate with FMC and obtain tokens + domain UUID."""
        url = f"{self.base_url}/fmc_platform/v1/auth/generatetoken"
        resp = self.session.post(url, auth=(self.username, self.password))
        if resp.status_code != 204:
            raise Exception(f"Authentication failed: {resp.status_code} {resp.text}")

        self.auth_token = resp.headers.get("X-auth-access-token")
        self.refresh_token = resp.headers.get("X-auth-refresh-token")
        self._parse_domain_uuid(resp.headers.get("DOMAINS", ""))
        self.token_expiry = datetime.now() + timedelta(minutes=30)
        self.refresh_count = 0

    def _parse_domain_uuid(self, domains_header: str) -> None:
        """Extract domain UUID from the DOMAINS response header."""
        for entry in domains_header.split(";"):
            entry = entry.strip()
            if self.domain_name in entry:
                start = entry.find("(")
                end = entry.find(")")
                if start != -1 and end != -1:
                    self.domain_uuid = entry[start + 1 : end]
                    return
        raise Exception(f"Domain '{self.domain_name}' not found in: {domains_header}")

    def _refresh_auth_token(self) -> None:
        """Refresh the auth token, or re-authenticate if refreshes exhausted."""
        if self.refresh_count >= 3:
            self._authenticate()
            return
        url = f"{self.base_url}/fmc_platform/v1/auth/refreshtoken"
        headers = {
            "X-auth-access-token": self.auth_token,
            "X-auth-refresh-token": self.refresh_token,
        }
        resp = self.session.post(url, headers=headers)
        if resp.status_code != 204:
            self._authenticate()
            return
        self.auth_token = resp.headers.get("X-auth-access-token")
        self.refresh_token = resp.headers.get("X-auth-refresh-token")
        self.token_expiry = datetime.now() + timedelta(minutes=30)
        self.refresh_count += 1

    def _ensure_authenticated(self) -> None:
        """Refresh token if nearing expiry."""
        if not self.auth_token or not self.token_expiry:
            self._authenticate()
            return
        time_remaining = (self.token_expiry - datetime.now()).total_seconds()
        if time_remaining < 300:
            self._refresh_auth_token()

    def _headers(self) -> Dict[str, str]:
        return {
            "X-auth-access-token": self.auth_token,
            "Content-Type": "application/json",
        }

    def _build_url(self, path: str) -> str:
        """Build full URL from an API path.

        Paths starting with /api/ are used as-is (absolute).
        Otherwise, paths are relative to /api/fmc_config/v1/domain/{uuid}/.
        """
        path = path.lstrip("/")
        if path.startswith("api/"):
            return f"https://{self.host}/{path}"
        return f"{self.base_url}/fmc_config/v1/domain/{self.domain_uuid}/{path}"

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Generic HTTP request to FMC API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: API path, relative to domain config endpoint or absolute if starting with /api/.
            params: Optional query parameters.
            json: Optional JSON body.

        Returns:
            Parsed JSON response (or empty dict for 204 responses).
        """
        self._ensure_authenticated()
        url = self._build_url(path)
        resp = self.session.request(
            method, url, headers=self._headers(), params=params, json=json
        )
        if resp.status_code == 204:
            return {}
        if resp.status_code >= 400:
            raise Exception(
                f"{method} {path} failed ({resp.status_code}): {resp.text}"
            )
        return resp.json()

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET request."""
        return self.request("GET", path, params=params)

    def post(self, path: str, json: Optional[Any] = None) -> Dict[str, Any]:
        """POST request."""
        return self.request("POST", path, json=json)

    def put(self, path: str, json: Optional[Any] = None) -> Dict[str, Any]:
        """PUT request."""
        return self.request("PUT", path, json=json)

    def delete(self, path: str) -> Dict[str, Any]:
        """DELETE request."""
        return self.request("DELETE", path)

    def get_server_version(self) -> Dict[str, Any]:
        """Get FMC server version info."""
        return self.request("GET", "/api/fmc_platform/v1/info/serverversion")

    def get_api_spec(self) -> Dict[str, Any]:
        """Fetch the OpenAPI spec from FMC."""
        self._ensure_authenticated()
        url = f"{self.base_url}/api-explorer/openapi.json"
        resp = self.session.get(url, headers=self._headers())
        if resp.status_code != 200:
            raise Exception(f"Failed to fetch API spec: {resp.status_code}")
        return resp.json()

    def deploy(self, device_ids: Optional[list] = None, force: bool = False) -> Dict[str, Any]:
        """Trigger deployment to devices.

        Args:
            device_ids: List of device UUIDs to deploy to. If None, deploys to all
                       devices with pending changes.
            force: Force deployment even if no changes detected.

        Returns:
            Deployment task response.
        """
        # First get deployable devices
        deployable = self.get("/api/fmc_config/v1/domain/{domain_uuid}/deployment/deployabledevices".format(
            domain_uuid=self.domain_uuid
        ))
        items = deployable.get("items", [])
        if not items and not force:
            return {"message": "No devices with pending changes"}

        if device_ids is None:
            device_ids = [item["device"]["id"] for item in items if "device" in item]

        if not device_ids:
            return {"message": "No devices to deploy to"}

        deploy_payload = {
            "type": "DeploymentRequest",
            "version": str(int(datetime.now().timestamp() * 1000)),
            "forceDeploy": force,
            "ignoreWarning": True,
            "deviceList": device_ids,
        }
        return self.post(
            "/api/fmc_config/v1/domain/{domain_uuid}/deployment/deploymentrequests".format(
                domain_uuid=self.domain_uuid
            ),
            json=deploy_payload,
        )
