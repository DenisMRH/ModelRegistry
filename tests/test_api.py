import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_model(client: AsyncClient, unique_suffix: str):
    name = f"test_model_{unique_suffix}"
    response = await client.post(
        "/api/models",
        json={"name": name, "team_id": "team_1", "description": "Test"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == name
    assert data["team_id"] == "team_1"
    assert data["description"] == "Test"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_model_duplicate_returns_409(client: AsyncClient, unique_suffix: str):
    name = f"dup_model_{unique_suffix}"
    await client.post(
        "/api/models",
        json={"name": name, "team_id": "team_1"},
    )
    response = await client.post(
        "/api/models",
        json={"name": name, "team_id": "team_2"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_models_empty(client: AsyncClient, unique_suffix: str):
    response = await client.get("/api/models", params={"team_id": f"empty_team_{unique_suffix}"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_models_with_data(client: AsyncClient, unique_suffix: str):
    await client.post(
        "/api/models",
        json={"name": f"m1_{unique_suffix}", "team_id": "t1"},
    )
    await client.post(
        "/api/models",
        json={"name": f"m2_{unique_suffix}", "team_id": "t2"},
    )
    response = await client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    names = {m["name"] for m in data}
    assert f"m1_{unique_suffix}" in names
    assert f"m2_{unique_suffix}" in names


@pytest.mark.asyncio
async def test_list_models_filter_by_team_id(client: AsyncClient, unique_suffix: str):
    team_a = f"team_a_{unique_suffix}"
    team_b = f"team_b_{unique_suffix}"
    await client.post("/api/models", json={"name": f"ma_{unique_suffix}", "team_id": team_a})
    await client.post("/api/models", json={"name": f"mb_{unique_suffix}", "team_id": team_b})
    response = await client.get("/api/models", params={"team_id": team_a})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["team_id"] == team_a


@pytest.mark.asyncio
async def test_create_version_returns_upload_url(client: AsyncClient, unique_suffix: str):
    name = f"vmodel_{unique_suffix}"
    await client.post("/api/models", json={"name": name, "team_id": "vt"})
    response = await client.post(
        f"/api/models/{name}/versions",
        json={"metrics": {"f1": 0.9}, "parameters": {"lr": 0.01}},
    )
    assert response.status_code == 200
    data = response.json()
    assert "version_id" in data
    assert data["version"] == 1
    assert "upload_url" in data
    assert isinstance(data["upload_url"], str) and len(data["upload_url"]) > 0


@pytest.mark.asyncio
async def test_create_version_increments(client: AsyncClient, unique_suffix: str):
    name = f"inc_model_{unique_suffix}"
    await client.post("/api/models", json={"name": name, "team_id": "inc"})
    r1 = await client.post(
        f"/api/models/{name}/versions",
        json={"metrics": {}},
    )
    r2 = await client.post(
        f"/api/models/{name}/versions",
        json={"metrics": {}},
    )
    assert r1.json()["version"] == 1
    assert r2.json()["version"] == 2


@pytest.mark.asyncio
async def test_create_version_model_not_found(client: AsyncClient):
    response = await client.post(
        "/api/models/nonexistent/versions",
        json={"metrics": {}},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_transition_stage(client: AsyncClient, unique_suffix: str):
    name = f"stage_model_{unique_suffix}"
    await client.post("/api/models", json={"name": name, "team_id": "st"})
    await client.post(f"/api/models/{name}/versions", json={})
    response = await client.patch(
        f"/api/models/{name}/versions/1/stage",
        json={"stage": "Production"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == "Production"
    assert data["version"] == 1


@pytest.mark.asyncio
async def test_transition_to_production_archives_others(client: AsyncClient, unique_suffix: str):
    name = f"prod_model_{unique_suffix}"
    await client.post("/api/models", json={"name": name, "team_id": "p"})
    await client.post(f"/api/models/{name}/versions", json={})
    await client.post(f"/api/models/{name}/versions", json={})
    await client.patch(
        f"/api/models/{name}/versions/1/stage",
        json={"stage": "Production"},
    )
    await client.patch(
        f"/api/models/{name}/versions/2/stage",
        json={"stage": "Production"},
    )
    response = await client.get(f"/api/models/{name}/production")
    assert response.status_code == 200
    assert response.json()["version"] == 2


@pytest.mark.asyncio
async def test_get_production(client: AsyncClient, unique_suffix: str):
    name = f"getprod_{unique_suffix}"
    await client.post("/api/models", json={"name": name, "team_id": "gp"})
    await client.post(f"/api/models/{name}/versions", json={"metrics": {"auc": 0.95}})
    await client.patch(
        f"/api/models/{name}/versions/1/stage",
        json={"stage": "Production"},
    )
    response = await client.get(f"/api/models/{name}/production")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == 1
    assert data["stage"] == "Production"
    assert "download_url" in data
    assert data["metrics"] == {"auc": 0.95}


@pytest.mark.asyncio
async def test_get_production_not_found(client: AsyncClient):
    response = await client.get("/api/models/nonexistent/production")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_production_no_production_version(client: AsyncClient, unique_suffix: str):
    name = f"noprod_{unique_suffix}"
    await client.post("/api/models", json={"name": name, "team_id": "np"})
    await client.post(f"/api/models/{name}/versions", json={})
    response = await client.get(f"/api/models/{name}/production")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_models_filter_invalid_stage(client: AsyncClient):
    response = await client.get("/api/models", params={"stage": "InvalidStage"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_models_filter_by_metrics(client: AsyncClient, unique_suffix: str):
    await client.post("/api/models", json={"name": f"high_f1_{unique_suffix}", "team_id": "tf"})
    await client.post(f"/api/models/high_f1_{unique_suffix}/versions", json={"metrics": {"f1": 0.95}})
    await client.post("/api/models", json={"name": f"low_f1_{unique_suffix}", "team_id": "tf"})
    await client.post(f"/api/models/low_f1_{unique_suffix}/versions", json={"metrics": {"f1": 0.5}})
    response = await client.get(
        "/api/models",
        params={"metric_key": "f1", "metric_min": 0.9},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    names = [m["name"] for m in data]
    assert f"high_f1_{unique_suffix}" in names


@pytest.mark.asyncio
async def test_list_models_filter_by_stage(client: AsyncClient, unique_suffix: str):
    name = f"smodel_{unique_suffix}"
    await client.post("/api/models", json={"name": name, "team_id": "ts"})
    await client.post(f"/api/models/{name}/versions", json={})
    await client.patch(
        f"/api/models/{name}/versions/1/stage",
        json={"stage": "Staging"},
    )
    response = await client.get("/api/models", params={"stage": "Staging"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    names = [m["name"] for m in data]
    assert name in names
