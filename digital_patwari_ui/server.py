"""Local development server for the Digital Patwari beta UI.

Binds to 127.0.0.1 by default. Live document reading is OFF unless
``--enable-live-reading`` is passed AND ``GEMINI_API_KEY`` is present in the
environment; without it the UI runs on synthetic sample records and says so.

    python -m digital_patwari_ui
"""
from __future__ import annotations

import argparse
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from digital_patwari_ui.api import Api
from digital_patwari_ui.sessions import SessionStore

MAX_REQUEST_BYTES = 32 * 1024 * 1024


def build_handler(api: Api) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "DigitalPatwariUI"
        sys_version = ""

        def _dispatch(self, method: str) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_REQUEST_BYTES:
                self.send_error(413, "Request too large")
                return
            body = self.rfile.read(length) if length else b""
            try:
                response = api.handle(method, self.path, body)
            except Exception as exc:  # noqa: BLE001 - never leak a traceback to the browser
                self.log_error("unhandled error: %s", type(exc).__name__)
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(b'{"error":"Something went wrong on this computer. Please try again."}')
                return
            self.send_response(response.status)
            for key, value in response.headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(response.body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                # style-src allows 'unsafe-inline' because the UI's own view
                # code sets element.style attributes directly (layout, not
                # user content) -- audited to carry only numeric/computed
                # values (percentages, region floats), never raw citizen or
                # extracted-document text. script-src stays locked to 'self'
                # with no unsafe-inline/unsafe-eval, which is what actually
                # prevents script injection.
                "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                "script-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'",
            )
            self.end_headers()
            if method != "HEAD":
                self.wfile.write(response.body)

        def do_GET(self) -> None:  # noqa: N802
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch("POST")

        def do_DELETE(self) -> None:  # noqa: N802
            self._dispatch("DELETE")

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Digital Patwari beta UI locally.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--enable-live-reading", action="store_true",
        help="Allow uploaded documents to be sent to the configured reading provider. "
             "Requires GEMINI_API_KEY. Off by default.",
    )
    parser.add_argument(
        "--model", default=os.environ.get("DIGITAL_PATWARI_MODEL", "gemini-3.5-flash"),
        help="Reading model to use when live reading is enabled (default: %(default)s).",
    )
    args = parser.parse_args(argv)

    live_enabled = args.enable_live_reading
    if live_enabled and not os.environ.get("GEMINI_API_KEY"):
        print("Refusing to enable live reading: GEMINI_API_KEY is not set.", file=sys.stderr)
        return 2

    store = SessionStore(live_enabled=live_enabled, live_model=args.model)
    api = Api(store)
    server = ThreadingHTTPServer((args.host, args.port), build_handler(api))
    print(f"Digital Patwari beta UI: http://{args.host}:{args.port}")
    print(
        "Live document reading is ENABLED." if live_enabled
        else "Live document reading is OFF. Sample records only — no document leaves this computer."
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.server_close()
        store.close_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
