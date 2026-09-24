import os
from pathlib import Path
import sys
import tempfile
import types

os.environ.setdefault(
    "KANZI_ANNOTATION_DB", str(Path(tempfile.gettempdir()) / "kanzi-test-import.db")
)

try:
    import fastapi  # noqa: F401
except ModuleNotFoundError:
    class _FastAPI:
        def __init__(self, **_kwargs):
            pass

        def get(self, *_args, **_kwargs):
            return lambda function: function

        post = get

    class _HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    fake_fastapi = types.ModuleType("fastapi")
    fake_fastapi.FastAPI = _FastAPI
    fake_fastapi.HTTPException = _HTTPException
    fake_fastapi.Request = object
    fake_responses = types.ModuleType("fastapi.responses")
    fake_responses.HTMLResponse = str
    sys.modules["fastapi"] = fake_fastapi
    sys.modules["fastapi.responses"] = fake_responses

from collector import app as collector
from fastapi import HTTPException


class _Request:
    def __init__(self, token: str | None = None):
        self.headers = {"authorization": f"Bearer {token}"} if token else {}


def test_collector_issues_and_verifies_installation_credentials():
    original_db = collector.DB
    with tempfile.TemporaryDirectory() as temporary:
        collector.DB = Path(temporary) / "annotations.db"
        collector.init_db()
        credentials = collector.register()

        assert collector._authenticated_anon_id(
            _Request(credentials["token"])
        ) == credentials["anonId"]
        try:
            collector._authenticated_anon_id(_Request("wrong"))
        except HTTPException as error:
            assert error.status_code == 401
        else:
            raise AssertionError("Invalid collector token was accepted")
    collector.DB = original_db
