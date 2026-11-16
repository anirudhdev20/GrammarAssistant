import os

import pytest

os.environ.setdefault("GA_LT_ENABLED", "false")

from app.config import Settings
from app.nlp.pipeline import Analyzer


@pytest.fixture(scope="session")
def analyzer() -> Analyzer:
    return Analyzer(Settings(lt_enabled=False), use_remote=False)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
