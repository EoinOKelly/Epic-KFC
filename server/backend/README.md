# Secure Messaging Backend

FastAPI backend foundation for the university secure messaging project.

## Local Configuration

Create a local `.env` from `.env.example` and replace the placeholder database
credentials with local development-only values. Do not commit `.env`.

Required database settings:

```text
DATABASE_URL=postgresql+asyncpg://secure_app_user:change_me@localhost:5432/secure_messages
TEST_DATABASE_URL=postgresql+asyncpg://secure_app_test_user:change_me@localhost:5432/secure_messages_test
```

## Manual PostgreSQL Setup

Create local development databases manually before running the app:

```sql
CREATE DATABASE secure_messages;
CREATE DATABASE secure_messages_test;
CREATE USER secure_app_user WITH PASSWORD 'local_dev_password';
CREATE USER secure_app_test_user WITH PASSWORD 'local_test_password';
GRANT ALL PRIVILEGES ON DATABASE secure_messages TO secure_app_user;
GRANT ALL PRIVILEGES ON DATABASE secure_messages_test TO secure_app_test_user;
```

Use least-privilege database users where possible.

## Development Commands

Run these commands from the `backend/` directory.

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Run the API:

```bash
uvicorn app.main:app --reload
```

Check the database connection:

```bash
python3 -m scripts.check_db_connection
```

Expected successful output:

```text
Database connection successful
```

Check Alembic state:

```bash
alembic current
alembic history
```

No real app table migrations are expected yet because models have not been
created.
