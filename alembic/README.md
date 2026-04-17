# Alembic Migrations — Odyssey RAG

Database migrations are managed with [Alembic](https://alembic.sqlalchemy.org/).

The async environment in `env.py` reads the database URL from `odyssey_rag.config.get_settings()` (i.e. the `DATABASE_URL` environment variable), so **no credentials are stored in `alembic.ini`**.

## Common Commands

```bash
# Apply all pending migrations
alembic upgrade head
# — or via Make:
make migrate

# Create a new auto-generated migration
alembic revision --autogenerate -m "describe your change"

# Apply one migration forward
alembic upgrade +1

# Downgrade one migration
alembic downgrade -1

# Show current revision
alembic current

# Show migration history
alembic history --verbose
```

## Baseline (existing databases)

The first migration (`001_baseline`) represents the current schema. For a database that already has the schema applied via `db/init/*.sql`, stamp it without running the DDL:

```bash
alembic stamp head
```

## Adding a New Migration

1. Make your changes in `src/odyssey_rag/db/models.py`
2. Generate a migration: `alembic revision --autogenerate -m "add foo column"`
3. Review the generated file in `alembic/versions/`
4. Apply: `alembic upgrade head`
5. Commit both the model change and the migration file
