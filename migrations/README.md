# Database Migrations

Alembic mengelola application tables pada schema PostgreSQL `public`.

Extension dan graph Apache AGE tetap di-bootstrap melalui `schemas/init/001_initialize_age.sql` karena keduanya merupakan database infrastructure, bukan application tables.

```bash
alembic upgrade head
alembic current
alembic history
alembic downgrade -1
```
