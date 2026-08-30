#!/usr/bin/env python3
"""Fetch PSI or CrUX JSON while keeping Google API keys out of CLI arguments."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


API_KEY_ENV = "CRUX_API_KEY"
MAX_RESPONSE_BYTES = 64 * 1024 * 1024
ERROR_BODY_BYTES = 64 * 1024
USER_AGENT = "web-performance-audit-agent-skill/1.0"
PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
CRUX_ENDPOINTS = {
    "crux": "https://chromeuxreport.googleapis.com/v1/records:queryRecord",
    "crux-history": "https://chromeuxreport.googleapis.com/v1/records:queryHistoryRecord",
}


class FetchError(Exception):
    """Expected configuration, API, network, or output failure."""


def redact(text: str, secrets: tuple[str, ...] = ()) -> str:
    sanitized = text
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    return re.sub(r"([?&]key=)[^&\s\"']+", r"\1[REDACTED]", sanitized, flags=re.IGNORECASE)


def redact_payload(value: Any, secret: str) -> Any:
    if isinstance(value, str):
        return redact(value, (secret,))
    if isinstance(value, list):
        return [redact_payload(item, secret) for item in value]
    if isinstance(value, dict):
        return {
            redact(str(key), (secret,)): redact_payload(item, secret)
            for key, item in value.items()
        }
    return value


def require_api_key(environ: Mapping[str, str]) -> str:
    key = environ.get(API_KEY_ENV, "").strip()
    if not key:
        raise FetchError(
            f"{API_KEY_ENV} is not available in this process. Direct CrUX queries require "
            "a Google Cloud API key enabled for the Chrome UX Report API. Configure it in "
            "the environment or secret manager that launches the agent; do not paste it into chat."
        )
    return key


def validate_target(value: str, *, origin_only: bool = False) -> str:
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise FetchError("Target must be an absolute HTTP or HTTPS URL.")
    if parsed.username is not None or parsed.password is not None:
        raise FetchError("Target URLs containing credentials are not accepted.")
    if origin_only:
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise FetchError("An origin must contain only scheme and host, without a path, query, or fragment.")
        return urlunsplit((parsed.scheme.lower(), parsed.netloc, "", "", ""))
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, parsed.fragment))


def build_psi_request(args: argparse.Namespace, key: str) -> Request:
    params: list[tuple[str, str]] = [
        ("url", validate_target(args.url)),
        ("strategy", args.strategy),
    ]
    if key:
        params.append(("key", key))
    for category in args.category or ["PERFORMANCE"]:
        params.append(("category", category))
    if args.locale:
        params.append(("locale", args.locale))
    return Request(
        f"{PSI_ENDPOINT}?{urlencode(params)}",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        method="GET",
    )


def build_crux_request(args: argparse.Namespace, key: str) -> Request:
    body: dict[str, Any] = {}
    if args.origin:
        body["origin"] = validate_target(args.origin, origin_only=True)
    else:
        body["url"] = validate_target(args.url)
    if args.form_factor:
        body["formFactor"] = args.form_factor
    if args.metric:
        body["metrics"] = args.metric
    endpoint = CRUX_ENDPOINTS[args.command]
    return Request(
        f"{endpoint}?{urlencode({'key': key})}",
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )


def extract_api_message(raw: bytes) -> str:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "Google returned an error response without a readable JSON message."
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
    return "Google returned an error response without a recognized message."


def fetch_json(
    request: Request,
    *,
    timeout: float,
    key: str,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    try:
        with opener(request, timeout=timeout) as response:
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > MAX_RESPONSE_BYTES:
                        raise FetchError("Google response exceeds the 64 MiB safety limit.")
                except ValueError:
                    pass
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except FetchError:
        raise
    except HTTPError as exc:
        raw_error = exc.read(ERROR_BODY_BYTES + 1)[:ERROR_BODY_BYTES]
        message = redact(extract_api_message(raw_error), (key,))
        raise FetchError(f"Google API returned HTTP {exc.code}: {message}") from None
    except URLError as exc:
        reason = redact(str(exc.reason), (key,))
        raise FetchError(f"Google API request failed: {reason}") from None
    except TimeoutError:
        raise FetchError(f"Google API request exceeded the {timeout:g}-second timeout.") from None
    except Exception as exc:
        message = redact(str(exc), (key,))
        raise FetchError(f"Google API request failed unexpectedly: {message}") from None

    if len(raw) > MAX_RESPONSE_BYTES:
        raise FetchError("Google response exceeds the 64 MiB safety limit.")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise FetchError("Google returned a successful response that was not valid JSON.") from None
    if not isinstance(payload, dict):
        raise FetchError("Google returned a JSON value that was not an object.")
    if "error" in payload:
        message = redact(extract_api_message(raw), (key,))
        raise FetchError(f"Google API returned an error: {message}")
    return redact_payload(payload, key)


def validate_output_path(path: Path, *, force: bool) -> Path:
    output = Path(os.path.abspath(path.expanduser()))
    if not output.parent.is_dir():
        raise FetchError(f"Output directory does not exist: {output.parent}")
    if output.is_symlink():
        raise FetchError(f"Output path must not be a symbolic link: {output}")
    if output.is_dir():
        raise FetchError(f"Output path is a directory: {output}")
    if output.exists() and not force:
        raise FetchError(f"Output file already exists: {output}. Pass --force to replace it.")
    return output


def write_json_atomic(path: Path, payload: dict[str, Any], *, force: bool) -> int:
    serialized = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            try:
                os.chmod(temporary_path, 0o600)
            except OSError:
                pass
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() and not force:
            raise FetchError(f"Output file appeared during the request: {path}. Pass --force to replace it.")
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
    return len(serialized)


def timeout_value(value: str) -> float:
    try:
        timeout = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeout must be a number") from exc
    if not 1 <= timeout <= 300:
        raise argparse.ArgumentTypeError("timeout must be between 1 and 300 seconds")
    return timeout


def add_output_arguments(parser: argparse.ArgumentParser, default_timeout: float) -> None:
    parser.add_argument("--output", required=True, type=Path, help="JSON file to create")
    parser.add_argument("--force", action="store_true", help="replace an existing output file")
    parser.add_argument("--timeout", type=timeout_value, default=default_timeout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "check-key",
        help=f"check whether {API_KEY_ENV} is available without printing its value",
    )

    psi = subparsers.add_parser("psi", help="run PageSpeed Insights")
    psi.add_argument("--url", required=True)
    psi.add_argument("--strategy", choices=("MOBILE", "DESKTOP"), default="MOBILE")
    psi.add_argument(
        "--category",
        action="append",
        choices=("ACCESSIBILITY", "BEST_PRACTICES", "PERFORMANCE", "SEO"),
        help="repeat to request multiple Lighthouse categories; default: PERFORMANCE",
    )
    psi.add_argument("--locale")
    add_output_arguments(psi, 180)

    for command, help_text in (
        ("crux", "query the current CrUX record"),
        ("crux-history", "query CrUX history"),
    ):
        crux = subparsers.add_parser(command, help=help_text)
        target = crux.add_mutually_exclusive_group(required=True)
        target.add_argument("--origin")
        target.add_argument("--url")
        crux.add_argument("--form-factor", choices=("PHONE", "DESKTOP", "TABLET"))
        crux.add_argument("--metric", action="append", help="repeat to limit returned metrics")
        add_output_arguments(crux, 60)
    return parser


def run(
    args: argparse.Namespace,
    *,
    environ: Mapping[str, str] = os.environ,
    opener: Callable[..., Any] = urlopen,
) -> tuple[Path, int]:
    output = validate_output_path(args.output, force=args.force)
    key = environ.get(API_KEY_ENV, "").strip()
    if args.command != "psi":
        key = require_api_key(environ)
    request = build_psi_request(args, key) if args.command == "psi" else build_crux_request(args, key)
    payload = fetch_json(request, timeout=args.timeout, key=key, opener=opener)
    size = write_json_atomic(output, payload, force=args.force)
    return output, size


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "check-key":
            require_api_key(os.environ)
            print(f"{API_KEY_ENV} is available to this process.")
            return 0
        output, size = run(args)
    except FetchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception:
        print("ERROR: Unexpected helper failure; request details were suppressed to protect secrets.", file=sys.stderr)
        return 3
    print(f"Wrote sanitized Google API JSON to {output} ({size} bytes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
