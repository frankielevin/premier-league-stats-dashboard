import importlib
import os
import sys

CHAMPIONSHIP_DIR = os.path.join(os.path.dirname(__file__), "championship")
if CHAMPIONSHIP_DIR not in sys.path:
    sys.path.insert(0, CHAMPIONSHIP_DIR)


class StripChampionshipPrefix:
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "") or ""
        if path == "/championship":
            environ["PATH_INFO"] = "/"
        elif path.startswith("/championship/"):
            environ["PATH_INFO"] = path[len("/championship"):]
        return self.wrapped(environ, start_response)


def load_app(module_name):
    module = importlib.import_module(module_name)
    flask_app = module.app
    if not isinstance(flask_app.wsgi_app, StripChampionshipPrefix):
        flask_app.wsgi_app = StripChampionshipPrefix(flask_app.wsgi_app)
    return flask_app
