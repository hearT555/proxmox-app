"""Small read-only NetBox VM dashboard API."""
from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
LOGGER = logging.getLogger("proxmox-app")
PORT = int(os.getenv("PORT", "8000"))
NETBOX_URL = os.getenv("NETBOX_URL", "").strip()
NETBOX_TOKEN = os.getenv("NETBOX_TOKEN", "").strip()
NETBOX_AUTH_SCHEME = os.getenv("NETBOX_AUTH_SCHEME", "Bearer").strip()
JENKINS_JOB_URL = os.getenv(
    "JENKINS_JOB_URL", ""
).strip()
_jenkins_parts = urlsplit(JENKINS_JOB_URL)
if _jenkins_parts.scheme not in {"http", "https"} or not _jenkins_parts.hostname:
    JENKINS_JOB_URL = ""
STATIC_PAGE = os.path.join(os.path.dirname(__file__), "index.html")


def _origin(url: str) -> tuple[str, str, int | None]:
    parts = urlsplit(url)
    return parts.scheme, parts.hostname or "", parts.port


def _fetch_json(url: str) -> dict:
    headers = {"Accept": "application/json"}
    if NETBOX_TOKEN:
        headers["Authorization"] = f"{NETBOX_AUTH_SCHEME} {NETBOX_TOKEN}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=8) as response:
        return json.load(response)


def _display(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("label") or value.get("name") or value.get("value") or "")
    if value is None:
        return ""
    return str(value)


def _load_virtual_machines() -> list[dict[str, str]]:
    if not NETBOX_URL or not NETBOX_TOKEN:
        raise RuntimeError("NetBox is not configured")

    base = NETBOX_URL.rstrip("/") + "/"
    current_url = urljoin(base, "api/virtualization/virtual-machines/?limit=100")
    expected_origin = _origin(current_url)
    machines: list[dict[str, str]] = []

    # Follow NetBox pagination, while refusing any URL outside the configured origin.
    while current_url and len(machines) < 1000:
        if _origin(current_url) != expected_origin:
            raise RuntimeError("NetBox returned a pagination URL outside its origin")
        page = _fetch_json(current_url)
        for vm in page.get("results", []):
            primary_ip = vm.get("primary_ip4") or vm.get("primary_ip")
            machines.append(
                {
                    "name": _display(vm.get("name")) or "—",
                    "role": _display(vm.get("role")) or "ไม่ระบุ",
                    "status": _display(vm.get("status")) or "ไม่ระบุ",
                    "ip": (
                        _display(primary_ip.get("address")) or "—"
                        if isinstance(primary_ip, dict)
                        else _display(primary_ip) or "—"
                    ),
                    "cluster": _display(vm.get("cluster")) or "—",
                }
            )
            if len(machines) >= 1000:
                break
        next_page = page.get("next")
        current_url = urljoin(current_url, next_page) if next_page else ""

    return sorted(machines, key=lambda item: item["name"].casefold())


class Handler(BaseHTTPRequestHandler):
    server_version = "ProxmoxApp"

    def _send(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, status: int, payload: dict | list) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            try:
                with open(STATIC_PAGE, "rb") as page:
                    self._send(200, page.read(), "text/html; charset=utf-8")
            except OSError:
                self._send_json(500, {"error": "ไม่พบหน้า dashboard"})
            return

        if self.path == "/api/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "netbox_configured": bool(NETBOX_URL and NETBOX_TOKEN),
                },
            )
            return

        if self.path == "/api/config":
            self._send_json(200, {"jenkins_job_url": JENKINS_JOB_URL})
            return

        if self.path == "/api/vms":
            try:
                machines = _load_virtual_machines()
                self._send_json(200, {"count": len(machines), "results": machines})
            except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError) as exc:
                # Keep upstream response bodies and credentials out of browser responses.
                LOGGER.warning("NetBox inventory request failed: %s", type(exc).__name__)
                if isinstance(exc, RuntimeError) and str(exc) == "NetBox is not configured":
                    self._send_json(
                        503,
                        {"error": "ยังไม่ได้ตั้งค่า NetBox URL หรือ read-only token"},
                    )
                else:
                    self._send_json(
                        502,
                        {"error": "อ่านรายการ VM จาก NetBox ไม่สำเร็จ"},
                    )
            return

        self._send_json(404, {"error": "ไม่พบ endpoint"})

    def log_message(self, fmt: str, *args: object) -> None:
        LOGGER.info("%s - %s", self.address_string(), fmt % args)


if __name__ == "__main__":
    LOGGER.info("Starting Proxmox App on port %s", PORT)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

