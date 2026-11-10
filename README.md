# Euphoria X — Backend foundation

This starter adds a Flask API and SQLAlchemy database to the existing Euphoria X HTML prototype.

## Database tables
- `project`: current draft, format, status and display settings.
- `revision`: durable submitted snapshots with finding counts and submitter role.
- `activity`: comments, submissions, decisions and restore events.

## Run locally (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```

Open http://127.0.0.1:5000 and test http://127.0.0.1:5000/api/health.

The SQLite database is created automatically as `instance/euphoria_x.db` inside the project folder.

## API routes
- `GET /api/health`
- `GET /api/project`
- `PUT /api/project`
- `POST /api/project/revisions`
- `POST /api/project/activities`
- `POST /api/project/decision`
- `POST /api/project/restore/<revision_id>`

## Important current boundary
This is the persistence foundation, not the finished secure multi-user system. The current prototype's role selector is not authentication. Before public multi-user use, add sign-in, server-verified permissions, CSRF protection and production database configuration. The `DATABASE_URL` setting is already supported so SQLite can later be switched to PostgreSQL without rewriting the models.
