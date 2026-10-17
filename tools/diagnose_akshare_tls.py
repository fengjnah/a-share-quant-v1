"""Read-only runtime report; opt-in, bounded TLS handshakes without market GETs.

Only push2his.eastmoney.com and the PyPI control host are permitted. Direct
sockets are used only as a diagnostic comparison, never as an SDK fallback.
No proxy/CA/environment settings are changed and certificate verification stays on.
"""

import argparse
import hashlib
import importlib.metadata
import ipaddress
import json
import os
from pathlib import Path
import socket
import ssl
import sys
import time
from urllib.parse import urlsplit

import requests

from ai_trade.storage.db import DatabaseConfig

HOSTS = ("push2his.eastmoney.com", "pypi.org")


def proxy_info(value):
    """Never include raw proxy URLs, user names, passwords or query strings."""
    if not value:
        return None
    try:
        parsed = urlsplit(value if "://" in value else "http://" + value)
        return {"scheme": parsed.scheme, "host": parsed.hostname,
                "port": parsed.port or (443 if parsed.scheme == "https" else 80),
                "credentials_present": parsed.username is not None or parsed.password is not None}
    except ValueError:
        return {"unparseable": True}


def runtime_report():
    config = DatabaseConfig.from_env()  # Resolves paths; never opens SQLite.
    versions = {}
    for name in ("akshare", "requests", "urllib3", "certifi"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {
        "python": sys.executable, "python_version": sys.version,
        "virtual_environment": sys.prefix, "openssl": ssl.OPENSSL_VERSION,
        "packages": versions, "ca_bundle": requests.certs.where(),
        "ca_bundle_exists": Path(requests.certs.where()).is_file(),
        "certificate_environment_names": [key for key in (
            "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE") if os.environ.get(key)],
        "proxy_environment_names": [key for key in os.environ if key.upper() in (
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")],
        "effective_proxy": {host: proxy_info(requests.utils.select_proxy(
            "https://" + host, requests.utils.get_environ_proxies("https://" + host))) for host in HOSTS},
        "database": {"environment": config.environment, "resolved_path": str(config.path),
                     "file_exists": config.path.is_file(), "connection_opened": False},
    }


def tls_probe(host, route, proxy, addresses, deadline):
    """One TCP connection and verified TLS handshake, no application GET."""
    if host not in HOSTS or route not in ("direct", "proxy"):
        raise ValueError("only the fixed host/route matrix is permitted")
    result = {"host": host, "route": route, "market_http_get_sent": False,
              "certificate_verification": True, "hostname_verification": True}
    if route == "proxy" and (not proxy or proxy.get("scheme") != "http"
                              or proxy.get("host") not in ("127.0.0.1", "localhost")
                              or proxy.get("credentials_present") or proxy.get("unparseable")):
        return result | {"status": "skipped", "reason": "no supported unauthenticated loopback HTTP proxy"}
    stream = None
    started = time.monotonic()
    stage = "tcp_connect"

    def timeout():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("overall diagnostic deadline reached")
        return min(4.0, remaining)

    try:
        if route == "proxy":
            stream = socket.create_connection((proxy["host"], proxy["port"]), timeout=timeout())
            stage = "proxy_connect"
            stream.sendall(f"CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n".encode("ascii"))
            header = bytearray()
            while not header.endswith(b"\r\n\r\n"):
                if len(header) >= 8192:
                    raise ValueError("proxy response header exceeded diagnostic limit")
                stream.settimeout(timeout())
                piece = stream.recv(1)
                if not piece:
                    raise ConnectionError("proxy closed before CONNECT headers completed")
                header.extend(piece)
            # Preserve only the numeric status, not proxy headers/authentication fields.
            code = int(header.split(b"\r\n", 1)[0].split()[1])
            result["proxy_connect_status"] = code
            if code != 200:
                return result | {"status": "failed", "stage": stage, "error_type": "ProxyConnectRejected"}
        else:
            if not addresses:
                return result | {"status": "skipped", "reason": "DNS supplied no address"}
            selected = next((address for address in addresses if address[0] == socket.AF_INET), addresses[0])
            family, socktype, protocol, _, address = selected
            stream = socket.socket(family, socktype, protocol)
            stream.settimeout(timeout())
            stream.connect(address)
            result["selected_ip"] = address[0]
        stage = "tls_handshake"
        stream.settimeout(timeout())
        context = ssl.create_default_context(cafile=requests.certs.where())
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        stream = context.wrap_socket(stream, server_hostname=host)
        certificate = stream.getpeercert()
        result.update(status="success", stage=stage, tls_version=stream.version(),
                      cipher=stream.cipher()[0], peer_sha256=hashlib.sha256(stream.getpeercert(binary_form=True)).hexdigest(),
                      issuer_common_names=[value for group in certificate.get("issuer", ())
                                           for key, value in group if key == "commonName"])
    except Exception as exc:
        # These socket/SSL operations never construct a URL with credentials or market parameters.
        result.update(status="failed", stage=stage, error_type=type(exc).__name__,
                      error=str(exc)[:600])
        if isinstance(exc, ssl.SSLCertVerificationError):
            result["classification"] = "certificate_verification_failure"
        elif isinstance(exc, ssl.SSLError):
            result["classification"] = "tls_handshake_failure"
        elif isinstance(exc, (TimeoutError, socket.timeout)):
            result["classification"] = "timeout"
        else:
            result["classification"] = "connection_or_proxy_failure"
    finally:
        if stream is not None:
            stream.close()
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-tls", action="store_true", help="permit at most four TLS handshakes; no market GET")
    parser.add_argument("--output", type=Path, required=True, help="local diagnostic JSON, not a database")
    args = parser.parse_args()
    if args.output.suffix.lower() != ".json":
        parser.error("diagnostic output must use a .json extension")
    if args.output.exists():
        parser.error("output already exists; choose a new diagnostic file")
    report = runtime_report() | {"network_opt_in": args.probe_tls, "dns": [], "probes": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    save()
    if args.probe_tls:
        deadline = time.monotonic() + 45
        for host in HOSTS:
            if time.monotonic() >= deadline:
                report["deadline_reached"] = True
                break
            try:
                addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
                ips = sorted({address[4][0] for address in addresses})
                report["dns"].append({"host": host, "addresses": ips,
                                      "benchmark_range_detected": any(ipaddress.ip_address(ip) in ipaddress.ip_network(
                                          "198.18.0.0/15") for ip in ips if ":" not in ip)})
            except OSError as exc:
                addresses = []
                report["dns"].append({"host": host, "error_type": type(exc).__name__})
            for route in ("proxy", "direct"):
                if time.monotonic() >= deadline:
                    report["deadline_reached"] = True
                    break
                report["probes"].append(tls_probe(host, route, report["effective_proxy"][host], addresses, deadline))
                save()
    save()
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
