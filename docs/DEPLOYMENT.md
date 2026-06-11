# Deployment

## Production Compose

Create a private `.env` containing `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `JWT_SECRET`, `CORS_ORIGINS`, `PUBLIC_API_BASE_URL`, and optionally `OPENAI_API_KEY`.

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

The API runs Alembic migrations before startup. Demo seeding is disabled. The frontend is built once and served by Nginx.

## Render Blueprint

`render.yaml` declares a PostgreSQL database, Docker backend, and static frontend. After creating the Blueprint:

1. Install the `vector` extension on the managed PostgreSQL instance if the plan does not enable it automatically.
2. Set `OPENAI_API_KEY` and update `VITE_API_BASE_URL`.
3. The public portfolio blueprint runs idempotent demo seeding on startup. Set `DEMO_SEED_ENABLED=false` and remove `python seed_demo.py` from `dockerCommand` for an operational deployment.
4. Replace demo users before exposing operational data.

## Release Checklist

- CI backend, frontend, migration, and container jobs pass.
- Golden evaluation results meet all gates.
- Migrations are reviewed and backed up.
- Production secrets differ from `.env.example`.
- CORS is restricted to the deployed frontend.
- Health endpoint and authenticated smoke test pass.
