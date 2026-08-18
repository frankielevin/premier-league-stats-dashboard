import importlib
import os
import sys

CHAMPIONSHIP_DIR = os.path.join(os.path.dirname(__file__), "championship")
if CHAMPIONSHIP_DIR not in sys.path:
    sys.path.insert(0, CHAMPIONSHIP_DIR)


class StripChampionshipPrefix:
    def __init__(self, wrapped):
        self.wrapped = wrapped

    @staticmethod
    def _rewrite_championship_paths(body):
        # Keep the Championship app fully namespaced when it is mounted under
        # /championship alongside the legacy Premier League application.
        # Protect already-prefixed paths first so repeated rewriting is safe.
        replacements = (
            (b"/championship/api/", b"__CHAMPIONSHIP_API__"),
            (b"/championship/static/", b"__CHAMPIONSHIP_STATIC__"),
        )
        for old, marker in replacements:
            body = body.replace(old, marker)

        body = body.replace(b"/api/", b"/championship/api/")
        body = body.replace(b"/static/", b"/championship/static/")

        body = body.replace(b"__CHAMPIONSHIP_API__", b"/championship/api/")
        body = body.replace(b"__CHAMPIONSHIP_STATIC__", b"/championship/static/")
        return body

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "") or ""
        is_championship = path == "/championship" or path.startswith("/championship/")

        if path == "/championship":
            environ["PATH_INFO"] = "/"
        elif path.startswith("/championship/"):
            environ["PATH_INFO"] = path[len("/championship"):]

        if not is_championship:
            return self.wrapped(environ, start_response)

        captured = {}
        written = []

        def capture_start_response(status, headers, exc_info=None):
            captured["status"] = status
            captured["headers"] = list(headers)
            captured["exc_info"] = exc_info

            def write(data):
                written.append(data)

            return write

        response = self.wrapped(environ, capture_start_response)
        try:
            chunks = written + list(response)
        finally:
            close = getattr(response, "close", None)
            if close:
                close()

        body = b"".join(chunks)
        headers = captured.get("headers", [])
        content_type = next(
            (value.lower() for key, value in headers if key.lower() == "content-type"),
            "",
        )

        if (
            "text/html" in content_type
            or "javascript" in content_type
            or "text/css" in content_type
        ):
            body = self._rewrite_championship_paths(body)
            headers = [
                (key, value)
                for key, value in headers
                if key.lower() != "content-length"
            ]
            headers.append(("Content-Length", str(len(body))))

        start_response(
            captured.get("status", "200 OK"),
            headers,
            captured.get("exc_info"),
        )
        return [body]


def load_app(module_name):
    module = importlib.import_module(module_name)
    flask_app = module.app
    if not isinstance(flask_app.wsgi_app, StripChampionshipPrefix):
        flask_app.wsgi_app = StripChampionshipPrefix(flask_app.wsgi_app)
    return flask_app
