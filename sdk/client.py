from pathlib import Path
from typing import Any

import requests


class RegistryClient:
    def __init__(self, api_url: str, s3_public_endpoint: str | None = None) -> None:
        self._base_url = api_url.rstrip("/")
        self._session = requests.Session()
        self._s3_public_endpoint = s3_public_endpoint

    def _rewrite_s3_url(self, url: str) -> str:
        if not self._s3_public_endpoint:
            return url
        if "://s3:" in url or "://s3/" in url:
            return url.replace("http://s3:9000", self._s3_public_endpoint.rstrip("/")).replace(
                "https://s3:9000", self._s3_public_endpoint.rstrip("/").replace("http://", "https://")
            )
        return url

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def log_model(
        self,
        team_id: str,
        model_name: str,
        artifact_local_path: str,
        metrics: dict[str, Any] | None = None,
        parameters: dict[str, Any] | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        create_resp = self._session.post(
            self._url("/api/models"),
            json={
                "name": model_name,
                "team_id": team_id,
                "description": description,
            },
        )
        if create_resp.status_code not in (200, 201, 409):
            create_resp.raise_for_status()

        version_resp = self._session.post(
            self._url(f"/api/models/{model_name}/versions"),
            json={
                "metrics": metrics,
                "parameters": parameters,
            },
        )
        version_resp.raise_for_status()
        data = version_resp.json()
        upload_url = self._rewrite_s3_url(data["upload_url"])
        version_id = data["version_id"]
        version = data["version"]

        with open(artifact_local_path, "rb") as f:
            upload_resp = self._session.put(
                upload_url,
                data=f,
                headers={"Content-Type": "application/octet-stream"},
            )
        upload_resp.raise_for_status()

        return {
            "version_id": version_id,
            "version": version,
        }

    def transition_stage(
        self,
        model_name: str,
        version: int,
        stage: str,
    ) -> dict[str, Any]:
        resp = self._session.patch(
            self._url(f"/api/models/{model_name}/versions/{version}/stage"),
            json={"stage": stage},
        )
        resp.raise_for_status()
        return resp.json()

    def download_production_model(
        self,
        model_name: str,
        local_dir: str,
    ) -> str:
        resp = self._session.get(
            self._url(f"/api/models/{model_name}/production"),
        )
        resp.raise_for_status()
        data = resp.json()
        download_url = self._rewrite_s3_url(data["download_url"])
        artifact_uri = data["artifact_uri"]

        filename = Path(artifact_uri).name
        local_path = Path(local_dir) / filename
        local_path.parent.mkdir(parents=True, exist_ok=True)

        with self._session.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        return str(local_path)
