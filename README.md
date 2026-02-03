# School Accounting Backend

Multi-tenant SaaS platform for school financial management.

## Quick Start

```bash
# Start the database
docker-compose up -d db

# Install dependencies
uv sync

# Run migrations
docker-compose run --rm app uv run alembic upgrade head

# Run the server
uvicorn main:app --reload
```

## Database Migrations

```bash
# Create a new migration (after changing models)
docker-compose run --rm app uv run alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose run --rm app uv run alembic upgrade head

# Rollback one migration
docker-compose run --rm app uv run alembic downgrade -1

# View migration history
docker-compose run --rm app uv run alembic history

# View current revision
docker-compose run --rm app uv run alembic current
```

## API Docs

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
