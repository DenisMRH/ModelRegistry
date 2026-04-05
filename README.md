## Как запустить

```bash
docker compose up -d
```

Сервисы:
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- MinIO Console: http://localhost:9001 (логин: `minioadmin` / `minioadminpassword`)

Остановка:

```bash
docker compose down
```

## Пример использования SDK

```python
from sdk import RegistryClient

# Подключаемся к API (если SDK запущен на хосте, укажите s3_public_endpoint для загрузки в MinIO)
client = RegistryClient(
    api_url="http://localhost:8000",
    s3_public_endpoint="http://localhost:9000",  # для работы с хоста
)

# 1. Обучили модель и сохранили
# model = train_model(X, y)
# model.save("train_model.pkl")

# 2. Логируем модель в Registry
result = client.log_model(
    team_id="mlds_180",
    model_name="recsys_main",
    artifact_local_path="train_model.pkl",
    metrics={"roc_auc": 0.89, "f1": 0.82},
    parameters={"learning_rate": 0.01, "epochs": 50, "dataset": "v1_with_rank"},
)

print(f"Загружена версия {result['version']} (id: {result['version_id']})")

# 3. После успешного тестирования — переводим в Production
client.transition_stage(
    model_name="recsys_main",
    version=result["version"],
    stage="Production",
)

# 4. Скачивание Production-модели (например, для инференса)
path = client.download_production_model("recsys_main", "./models")
print(f"Модель сохранена в {path}")
```


## REST API

| Метод | Путь | Описание |
|-------|------|----------|
| POST | /api/models | Создать модель |
| GET | /api/models?team_id=&stage=&metric_key=&metric_min=&metric_max= | Список моделей (фильтры: команда, стадия, метрики) |
| POST | /api/models/{name}/versions | Создать версию, получить presigned URL для загрузки |
| PATCH | /api/models/{name}/versions/{v}/stage | Сменить стадию (Development, Staging, Production, Archived) |
| GET | /api/models/{name}/production | Получить Production-версию и ссылку на скачивание |

Поиск по метрикам (GET /api/models):
- metric_key — имя метрики (например, f1, roc_auc)
- metric_min / metric_max — границы значения (число)
- stage — фильтр по стадии версий

Пример: GET /api/models?team_id=mlds_180&metric_key=f1&metric_min=0.85 — модели команды с F1 ≥ 0.85.
