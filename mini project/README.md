# DegreePath

DegreePath is a Flask and SQLite academic planning workspace for a BTech CSE mini-project demonstration. Students can create their own semester structure, track subjects and deadlines, explore a career skill path, and simulate future terms. The application does not provide an official graduation audit or institution-approved academic advice.

## Features

- Flask app factory, blueprints, SQLite/SQLAlchemy models, Flask-Login, Flask-WTF CSRF, Flask-Migrate, and pytest.
- Registration, password hashing, login/logout, server-side role checks, disabled-account support, secure cookie options, and interactive admin creation.
- Personal onboarding, semester timelines, editable subjects, prerequisite links and cycle checks, status/grade/credit records, progress summaries, and roadmap views.
- Study tasks with Upcoming, Today, Overdue, and Completed filters; what-if schedule previews saved separately from real academic records.
- Editable career skill recommendations and portfolio items; user administration, curriculum template versions, CSV import/export, and audit events.
- Responsive layouts for landing, dashboard, roadmap, progress, planner, career, account, and admin experiences.

## Requirements

Python 3.10 or newer is recommended. Python 3.14 was used to scaffold this project; use the host's supported Python version in production. Dependencies are listed in `requirements.txt`.

## Local setup

In PowerShell from the project directory:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set a unique `SECRET_KEY`; use `APP_ENV=production` in production. Apply the checked-in migration to create or upgrade the database:

```powershell
flask --app run.py db upgrade
```

The initial schema migration is included under `migrations/versions/`. For later model changes, run `flask --app run.py db migrate -m "describe change"`, review the generated revision, and commit it before applying `flask --app run.py db upgrade`. `db init` is only needed if deliberately creating a new migration repository. The app never deletes or overwrites an existing database at startup.

Create the first administrator securely. The command prompts for an email, display name, and hidden password; no default admin credentials are shipped:

```powershell
flask --app run.py create-admin
```

Optional: load the fictional demonstration structure:

```powershell
python scripts/load_demo_data.py
```

Then start the app:

```powershell
flask --app run.py run --debug --port 5002
```

Open `http://127.0.0.1:5002`. Registration is available from the landing page.

## Demo curriculum and verified data

`load-demo-data` creates `DegreePath DEMO DATA: BTech CSE`, explicitly marked as fictional and unverified. It contains 12 sample subjects across four semesters, with illustrative credits and prerequisite links. It is not a real institution's official curriculum. The loader is idempotent and will not replace existing data.

For an actual course structure, obtain current requirements directly from the relevant institution. An administrator can create a separate curriculum template and import a UTF-8 CSV with required columns `semester,code,name,credits`; `category` is optional. Each row is validated and duplicate subject codes are rejected. Review exported data and institution requirements before marking any version verified. Student records remain separate from templates.

## Tests

Tests use isolated in-memory SQLite and never open the configured student database:

```powershell
python -m pytest -q
```

The tests cover authentication and hashing, role enforcement, onboarding, personal subject CRUD/status and prerequisite checks, progress credits, deadline/task ownership, what-if isolation, career skills/portfolio, and CSV validation/import. Run tests after applying code changes.

## Deployment

The production WSGI entry point is `wsgi:app`. On a Linux-compatible Python host:

1. Install `requirements.txt` and set `SECRET_KEY` to a strong random value.
2. Set `DATABASE_URL` to a persistent SQLite location for a small single-instance demo, or a PostgreSQL SQLAlchemy URL for a multi-instance deployment.
3. Set `SESSION_COOKIE_SECURE=true` behind HTTPS; keep `SESSION_COOKIE_HTTPONLY` and `SESSION_COOKIE_SAMESITE` enabled.
4. Run `flask --app run.py db upgrade` as a release step, not on every worker start.
5. Create an administrator interactively through a secure deployment shell using `flask --app run.py create-admin`.
6. Start a WSGI server, for example `gunicorn wsgi:app` where Gunicorn is available.
7. Confirm persistent database storage, backups and restore procedure, HTTPS, environment secrets, logs, and a verified curriculum source.

Ephemeral filesystems can erase SQLite data on restart or redeploy. Do not store real student records on ephemeral storage. Use mounted persistent storage with tested backups for a small single-instance deployment; use managed PostgreSQL and access-controlled backups when scaling or requiring multiple app instances. Configure `DATABASE_URL` with the provider's supported SQLAlchemy URI.

## Security and privacy notes

- The app uses password hashes, CSRF protection for forms, owner-scoped lookups, role checks, and server-side validation. User-provided text is rendered with Jinja autoescaping.
- Set a production secret and HTTPS cookie flag. Rate limiting, email verification, account recovery, and formal privacy/retention workflows are not included.
- Browser notifications are not claimed; deadlines are shown inside the app. The Chart.js dashboard visualization is loaded from a CDN and is nonessential to record calculations.
- Degree progress and suggested career skills are planning estimates. Neither placement outcomes nor official graduation eligibility are guaranteed.
- Curriculum CSV import creates shared template records only; it does not bulk alter student records.

## Known limitations

- The app provides a single current-semester date range, not per-semester academic calendar editing in the onboarding form.
- Saved what-if scenarios can be created, but there is no saved-scenario management/deletion screen or automatic timetable optimization.
- Curriculum prerequisites are selected and validated within a student's personal subject structure; imported CSV currently carries no prerequisite column.
- No email notifications, external calendar sync, file attachments, GPA conversion policy, official degree audit, browser push service, or production rate limiting is implemented.
- A curriculum marked verified is an administrator assertion; the software does not independently verify institutional rules.
