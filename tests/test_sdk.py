import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from sdk.client import RegistryClient


@pytest.fixture
def mock_responses():
    with patch.object(requests.Session, "post") as mock_post, patch.object(
        requests.Session, "patch"
    ) as mock_patch, patch.object(requests.Session, "get") as mock_get, patch.object(
        requests.Session, "put"
    ) as mock_put:
        yield {
            "post": mock_post,
            "patch": mock_patch,
            "get": mock_get,
            "put": mock_put,
        }


def test_registry_client_init():
    client = RegistryClient(api_url="http://localhost:8000")
    assert client._base_url == "http://localhost:8000"


def test_registry_client_url_trailing_slash():
    client = RegistryClient(api_url="http://localhost:8000/")
    assert client._base_url == "http://localhost:8000"


def test_log_model_creates_model_and_version(mock_responses):
    post_returns = [
        {"id": "m1", "name": "m", "team_id": "t", "created_at": "2024-01-01"},
        {"version_id": "v1", "version": 1, "upload_url": "https://s3.example.com/upload"},
    ]
    call_idx = [0]

    def post_side_effect(*args, **kwargs):
        idx = call_idx[0]
        call_idx[0] += 1
        r = type("Resp", (), {})()
        r.status_code = 200
        r.json = lambda: post_returns[idx]
        r.raise_for_status = lambda: None
        return r

    mock_responses["post"].side_effect = post_side_effect
    put_r = type("PutResp", (), {})()
    put_r.status_code = 200
    put_r.raise_for_status = lambda: None
    mock_responses["put"].return_value = put_r

    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        f.write(b"model_data")
        path = f.name

    client = RegistryClient(api_url="http://api:8000")
    result = client.log_model(
        team_id="t1",
        model_name="m1",
        artifact_local_path=path,
        metrics={"f1": 0.9},
    )

    Path(path).unlink()

    assert result["version_id"] == "v1"
    assert result["version"] == 1
    assert mock_responses["post"].call_count == 2
    assert mock_responses["put"].call_count == 1


def test_log_model_ignores_409_on_model_create(mock_responses):
    create_resp = requests.Response()
    create_resp.status_code = 409
    version_resp = requests.Response()
    version_resp.status_code = 200
    version_resp.json = lambda: {"version_id": "v1", "version": 1, "upload_url": "https://u"}
    mock_responses["post"].side_effect = [create_resp, version_resp]
    mock_responses["put"].return_value.status_code = 200

    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        f.write(b"x")
        path = f.name

    client = RegistryClient(api_url="http://api:8000")
    result = client.log_model(
        team_id="t",
        model_name="m",
        artifact_local_path=path,
    )

    Path(path).unlink()
    assert result["version"] == 1


def test_transition_stage(mock_responses):
    mock_responses["patch"].return_value.status_code = 200
    mock_responses["patch"].return_value.json.return_value = {
        "id": "v1",
        "model_id": "m1",
        "version": 1,
        "stage": "Production",
        "artifact_uri": "t/m/v1/model.pkl",
        "metrics": {},
        "parameters": {},
        "created_at": "2024-01-01",
    }

    client = RegistryClient(api_url="http://api:8000")
    result = client.transition_stage(
        model_name="m",
        version=1,
        stage="Production",
    )

    assert result["stage"] == "Production"
    mock_responses["patch"].assert_called_once()
    call_args = mock_responses["patch"].call_args
    assert "stage" in str(call_args)
    assert call_args[1]["json"]["stage"] == "Production"


def test_download_production_model(mock_responses):
    api_resp = type("ApiResp", (), {})()
    api_resp.status_code = 200
    api_resp.json = lambda: {
        "id": "v1",
        "model_id": "m1",
        "version": 1,
        "stage": "Production",
        "artifact_uri": "t/m/v1/model.pkl",
        "metrics": {},
        "parameters": {},
        "created_at": "2024-01-01",
        "download_url": "https://s3.example.com/download",
    }
    api_resp.raise_for_status = lambda: None

    class MockStreamResponse:
        status_code = 200
        def raise_for_status(self): pass
        def iter_content(self, **kw): return iter([b"model_bytes"])
        def __enter__(self): return self
        def __exit__(self, *a): pass

    mock_responses["get"].side_effect = [api_resp, MockStreamResponse()]

    with tempfile.TemporaryDirectory() as tmpdir:
        client = RegistryClient(api_url="http://api:8000")
        path = client.download_production_model("m", tmpdir)
        assert path.endswith("model.pkl")
        assert Path(path).exists()
        assert Path(path).read_bytes() == b"model_bytes"


def test_rewrite_s3_url():
    client = RegistryClient(
        api_url="http://api:8000",
        s3_public_endpoint="http://localhost:9000",
    )
    url = "http://s3:9000/bucket/key?signature=xxx"
    rewritten = client._rewrite_s3_url(url)
    assert "localhost:9000" in rewritten
    assert "s3:9000" not in rewritten
