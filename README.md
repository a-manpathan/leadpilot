# LeadPilot

LeadPilot is a local web app for business-development and go-to-market work. It helps you find public company websites, save prospects, read public contact details from those websites, score how complete each prospect is, and draft a cold email. It does not send email.

The app stores data in SQLite on your computer. The same code can later use Supabase PostgreSQL by changing one environment variable.

## What you can do

1. Discover businesses with DuckDuckGo, or load labeled sample businesses when search is unavailable.
2. Open a company website and collect public description, services, email, phone, contact page, and LinkedIn company URL.
3. Score each lead from 0 to 100 and adjust the score yourself.
4. Draft a professional, friendly, direct, or consultative email from the information you actually collected.
5. Search, filter, edit, annotate, and delete leads.
6. Export CSV files for all leads, high-priority leads, leads with emails, or leads with drafts.

A high score means the public profile matches the search you ran and that contact details were found. It does not mean the company intends to buy.

## Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the local address Streamlit prints, usually `http://localhost:8501`.

SQLite is created automatically at `data/leadpilot.db`. Copy `.env.example` to `.env` only if you want to change limits or the database URL. The checked-in `.env` already points at the local SQLite file.

## Tests

```bash
pytest
```

Tests use a temporary database under `tests/_tmp` and do not write into `data/leadpilot.db`.

## Search and email behavior

Live discovery uses the free `ddgs` library. Free search can be rate-limited or offline. When that happens, LeadPilot reports the failure and can show sample companies labeled `Sample/Demo Data (Search Fallback)`. You can also tick **Use offline sample data** on the Discover page. Sample companies are not real customers.

Email text is built from templates. If [Ollama](https://ollama.com) is installed and running, the Email Generator can optionally use it. No paid AI API is required.

Website research requests only public `http` and `https` pages, times out, waits between pages, and refuses local or private-network addresses. It does not log in, solve CAPTCHA checks, or pass paywalls.

## Move data from SQLite to PostgreSQL

Export the local database:

```bash
python -m database.migrations --export
```

This writes a JSON file in `data/backups/`.

Import that file into Supabase after you have a PostgreSQL URL:

```bash
python -m database.migrations --import-file data/backups/leadpilot_backup_YYYYMMDD_HHMMSS.json --target-url "postgresql://USER:PASSWORD@HOST:5432/postgres"
```

The import creates the tables if they do not exist and skips businesses that are already stored under the same domain. After import, set `DATABASE_URL` to the PostgreSQL URL and restart the app. Do this before you rely on the cloud database, and keep the JSON backup.

Step-by-step hosting instructions are in [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md). This project is not uploaded or deployed automatically.

## Project layout

- `app.py` starts the Streamlit interface.
- `config/settings.py` reads environment variables.
- `database/` contains SQLAlchemy models and the SQLite-to-PostgreSQL backup tool.
- `modules/` contains discovery, research, scoring, email drafts, lead edits, and CSV export.
- `pages/` contains one screen per navigation item.
- `tests/` checks the database, scoring, email drafts, and CSV export.

## Hosting note

Render can run this Streamlit app. Vercel is built for frontend sites and short serverless functions, so this long-running Streamlit process should stay on Render rather than being rewritten as a second application.
