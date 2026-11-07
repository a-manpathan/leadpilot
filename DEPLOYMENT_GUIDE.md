# LeadPilot deployment guide

This guide assumes you have the project folder on your computer and you want to run it yourself. You create the GitHub repository, the Render account, and the Supabase database. Nothing in this guide uploads code or creates accounts for you.

Words used below:

- **Folder** means the project directory that contains `app.py`.
- **Terminal** means the black or blue text window where you type commands. On Windows, open PowerShell.
- **Repository** means a project stored on GitHub.
- **Environment variable** means a named setting, such as `DATABASE_URL`, that the app reads when it starts. It is not written into the Python files.

## Part A: Run LeadPilot on your computer

### 1. Install Python

1. Go to [https://www.python.org/downloads/](https://www.python.org/downloads/).
2. Download Python 3.11 or newer for Windows.
3. Run the installer.
4. On the first screen, tick **Add python.exe to PATH**, then choose **Install Now**.

Check the installation. Open PowerShell and run:

```powershell
python --version
```

You should see a version such as `Python 3.11.9` or `Python 3.13.x`. If PowerShell says Python is not recognized, close PowerShell, open it again, and retry. If it still fails, reinstall Python and tick **Add python.exe to PATH**.

### 2. Open the project folder

If the project is in Downloads:

```powershell
cd "$env:USERPROFILE\Downloads\b2b"
```

Confirm you are in the right folder:

```powershell
dir app.py
```

You should see `app.py` listed. If PowerShell says it cannot find the file, you are in the wrong folder.

### 3. Install the libraries

Create a virtual environment so these libraries stay inside the project:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If activation is blocked by a script policy, run this once, then activate again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

The install can take a few minutes. It is finished when you see a new prompt and no red error at the end.

### 4. Start the application

```powershell
streamlit run app.py
```

Expected output includes a line similar to:

```text
You can now view your Streamlit app in your browser.
Local URL: http://localhost:8501
```

Open that address in your browser. The sidebar should list Dashboard, Discover Leads, Research & Enrichment, Lead Qualification, Email Generator, Lead Management, Export Data, and Settings.

The first start creates `data/leadpilot.db`. That file is your local database. Leave it in place if you want to keep your leads.

Stop the app with `Ctrl+C` in PowerShell.

### 5. Try the workflow without live search

1. Open **Discover Leads**.
2. Tick **Use offline sample data**.
3. Click **Discover Prospects**, then **Save New Leads**.
4. Open **Research & Enrichment**. Sample domains such as `example.com` often do not provide a real company site, so research may finish as blocked or without an email. That is expected for sample data.
5. Open **Lead Qualification** and click **Recalculate Score**.
6. Open **Email Generator**, fill in your company details, and click **Generate Email**, then **Save Draft**.
7. Open **Export Data**, choose a preset, click **Prepare CSV**, then **Download CSV**.
8. Stop the app with `Ctrl+C` and start it again. The saved leads should still be there.

For a real website check, save a business whose website you know is public, then run research on that one lead. The app stores the page URL next to any email or phone it finds and marks the contact as needing verification unless the email domain matches the company domain.

### 6. Common local problems

| What you see | What to do |
|---|---|
| `python` is not recognized | Reinstall Python and tick **Add python.exe to PATH**. Close and reopen PowerShell. |
| `streamlit` is not recognized | Activate `.venv`, then run `pip install -r requirements.txt` again. |
| Port 8501 already in use | Another copy is running. Close that PowerShell window, or run `streamlit run app.py --server.port 8502`. |
| Database connection failed | Open `.env`. For local use it should contain `DATABASE_URL=sqlite:///./data/leadpilot.db`. |
| Search returns nothing or a warning | Free DuckDuckGo search is busy or blocked. Tick **Use offline sample data**, or try again later. |
| A website says blocked or failed | The site refused the request, timed out, or is not public HTML. The lead is still saved. Enter a contact by hand in Lead Management if you found it yourself. |

Run the automated checks from the project folder:

```powershell
pytest
```

You should see passed tests. A failure here is a code or setup problem, not a deployment problem.

## Part B: Put the code on GitHub yourself

GitHub is a website that stores project files. Render can later read those files and start the app. You will create the repository in the browser and upload the files yourself.

### 1. Create a GitHub account

1. Open [https://github.com/signup](https://github.com/signup).
2. Enter your email, a password, and a username.
3. Confirm the email GitHub sends you.

### 2. Create an empty repository

1. Sign in and click the **+** icon at the top right.
2. Click **New repository**.
3. Name it `leadpilot`.
4. Leave it **Private** if you do not want other people to see the code.
5. Do not add a README, `.gitignore`, or license. The project already has those files.
6. Click **Create repository**.

### 3. Upload the project in the browser

1. On the empty repository page, click **uploading an existing file**.
2. Open the project folder on your computer.
3. Select the files and folders listed below and drag them into GitHub.
4. Do not upload the items in the "leave these out" list.
5. Scroll down, type a short message such as `Add LeadPilot`, and click **Commit changes**.

Upload these:

- `app.py`
- `requirements.txt`
- `README.md`
- `DEPLOYMENT_GUIDE.md`
- `render.yaml`
- `.env.example`
- `.gitignore`
- `config`
- `database`
- `modules`
- `utils`
- `pages`
- `tests`
- `.streamlit`
- `data/.gitkeep`

Leave these out:

- `.env`, because it is your local settings file.
- `.venv` or `venv`, because it is a large local copy of the libraries. Render installs them from `requirements.txt`.
- `data/leadpilot.db` and any file ending in `.db`. Your leads stay on your computer unless you migrate them on purpose.
- `__pycache__` folders.
- `data/backups`, unless you intentionally want a backup file online. Backup files contain your lead data.
- `.streamlit/secrets.toml`, if you create one later. It can contain a database password.

GitHub's website upload sometimes skips folders that look empty. `data` should contain `.gitkeep`. If a folder is missing after upload, open it on GitHub with **Add file** and upload its files.

### 4. Environment variables, in plain language

The app reads `DATABASE_URL` when it starts.

- On your computer, `.env` can contain `DATABASE_URL=sqlite:///./data/leadpilot.db`.
- On Render, you will type the Supabase PostgreSQL address into the Render dashboard. Do not paste that password into a Python file and do not commit `.env`.

`.env.example` lists the setting names without real passwords. That file is safe to upload.

## Part C: Deploy on Render

Render is the hosting service recommended for this app. It runs the `streamlit run app.py` command on a small computer that stays available on the internet.

Vercel is a different host aimed at JavaScript websites and short functions. This LeadPilot app is one Python process that stays running. Putting it on Vercel would mean building a second application. Use Render for this version.

### 1. Create a Render account

1. Open [https://render.com](https://render.com).
2. Sign up with your email or with GitHub.
3. If Render asks to connect GitHub, approve access to the `leadpilot` repository you created.

### 2. Create a web service

1. In the Render dashboard, click **New +**.
2. Click **Web Service**.
3. Choose the `leadpilot` repository.
4. Use these settings:

| Setting | Value |
|---|---|
| Name | `leadpilot` |
| Region | The region closest to you |
| Branch | `main` |
| Runtime | Python 3 |
| Build command | `pip install -r requirements.txt` |
| Start command | `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true` |
| Instance type | Free, if it is offered |

The `render.yaml` file in the project records the same build and start commands. You can still type them in the form. `$PORT` is a value Render provides. You do not replace it with a number.

### 3. Add environment variables

On the same page, open **Environment** or **Environment Variables** and add:

| Key | Value |
|---|---|
| `APP_ENV` | `production` |
| `DATABASE_URL` | The Supabase address from Part D |
| `MAX_CRAWL_PAGES_PER_SITE` | `3` |
| `HTTP_TIMEOUT_SECONDS` | `8` |
| `REQUEST_DELAY_SECONDS` | `1.0` |

Create the Supabase database in Part D before the first successful production start if you want cloud data. You can deploy once with a temporary SQLite URL, but the free Render disk is wiped when the service sleeps or redeploys, so business records would disappear. For anything you need to keep, use Supabase.

### 4. Deploy and open the site

1. Click **Create Web Service** or **Deploy**.
2. Wait until the log says the service is live. The first build often takes several minutes.
3. Copy the URL at the top of the service page. It looks like `https://leadpilot.onrender.com`.
4. Open it. You should see the LeadPilot sidebar.
5. Open **Settings** inside the app. It should say the database connected, and the engine should be PostgreSQL after you set the Supabase URL.

If the page loads slowly the first time, the free service may be waking up. Give it about a minute and refresh.

## Part D: Create the Supabase database

Supabase provides the PostgreSQL database. The app creates its tables the first time it starts with that `DATABASE_URL`.

### 1. Create a project

1. Open [https://supabase.com](https://supabase.com) and create a free account.
2. Click **New project**.
3. Choose an organization, a project name such as `leadpilot`, a database password, and a region.
4. Save the database password in a password manager. Supabase shows it once.

### 2. Copy the connection string

1. Open your project.
2. Click **Connect** or go to **Project Settings**, then **Database**.
3. Find the URI connection string. It looks like:

```text
postgresql://postgres.PROJECT:YOUR_PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres
```

4. Replace the password placeholder with the database password.
5. If the address starts with `postgres://`, change the first word to `postgresql://`. The app also accepts `postgres://` and rewrites it, but the `postgresql://` form is clearer.

Use the **Session pooler** or direct connection on port `5432` if the pooler URL fails during table creation. Some pooler modes block the statements SQLAlchemy uses to create tables. If startup says the database connection failed, switch to the direct connection string from the same Supabase page and redeploy.

### 3. Give the address to Render

1. In Render, open your web service.
2. Click **Environment**.
3. Set `DATABASE_URL` to the full Supabase address.
4. Save changes. Render starts a new deploy.

### 4. Let the app create the tables

You do not run a separate SQL file for a new empty database. On startup, LeadPilot creates:

- `businesses`
- `lead_research`
- `lead_qualifications`
- `email_drafts`
- `activity_logs`
- `company_settings`

In Supabase, open **Table Editor** after the Render deploy is live. Those tables should be listed. Add one sample lead in the live app, refresh Supabase, and confirm a row exists in `businesses`.

### 5. Bring your local leads across

Do this on your computer, in PowerShell, from the project folder.

Export SQLite:

```powershell
.\.venv\Scripts\Activate.ps1
python -m database.migrations --export
```

Expected output:

```text
[OK] Database exported successfully to: ...\data\backups\leadpilot_backup_YYYYMMDD_HHMMSS.json
Total businesses exported: N
```

Import into Supabase. Put your real address in quotes:

```powershell
python -m database.migrations --import-file "data\backups\leadpilot_backup_YYYYMMDD_HHMMSS.json" --target-url "postgresql://USER:PASSWORD@HOST:5432/postgres"
```

Expected output includes `[OK] Successfully imported backup`.

The import skips a company that is already stored with the same website domain, so running it twice does not create duplicate companies. Keep the JSON file. It is your copy of the data. Do not upload it to GitHub if it contains customer information.

Restart is not required for the import itself. The next time you open the Render site, the imported rows are already in Supabase. Local SQLite and Supabase are separate after this point. New local leads are not copied until you export and import again.

## Part E: Update the website later

### 1. Change the code

Edit the files on your computer. Test them with:

```powershell
streamlit run app.py
```

### 2. Upload the changed files

1. Open your repository on GitHub.
2. Click the file you changed, then the pencil icon, and paste the new contents. Or use **Add file** > **Upload files** and let GitHub replace the old file.
3. Click **Commit changes**.

There is no automatic link from your computer to GitHub. A change is online only after you commit it on GitHub.

### 3. Watch Render deploy

1. Open the Render service.
2. Render usually starts a deploy when the `main` branch changes. If it does not, click **Manual Deploy** > **Deploy latest commit**.
3. Open the **Logs** tab.
4. A healthy deploy ends with Streamlit saying it is running, and the service status becomes **Live**.
5. Open the public URL and test the page you changed.

### 4. When a deploy fails

Read the last red lines in the Render log.

| Log message | What it usually means |
|---|---|
| `Could not open requirements.txt` or file not found | The GitHub repository is missing a file. Upload it. |
| `No matching distribution` | A library version could not be installed. Run `pip install -r requirements.txt` locally and confirm it succeeds. |
| Database connection failed | `DATABASE_URL` is missing, the password is wrong, or the Supabase host blocked the connection. Paste the connection string again. |
| Port scan or "no open ports" | The start command must include `--server.port $PORT` and `--server.address 0.0.0.0`. |
| Application error after sleep | Free services spin down. Refresh after a minute. |

The running site keeps using the last successful deploy until a new one succeeds.

## Part F: Free-plan limits

### Render

The free web service can go to sleep after a period with no visitors. The next visit may take up to a minute to wake it. Render may also limit free hours per month. When the hours are used up, the site stays offline until the next month or until you choose a paid instance.

Sleep does not delete a Supabase database. It would delete files saved only on Render's disk, which is why leads belong in Supabase.

### Supabase

The free database has a size limit, a limit on monthly active users of Supabase's own features, and the project can pause after a week without activity. A paused project does not accept connections until you restore it from the Supabase dashboard. If you exceed the free database size, new writes fail until you remove data or upgrade.

LeadPilot does not upload large files. Text leads stay small, but a backup JSON file should still be kept on your computer.

### Search

DuckDuckGo through the `ddgs` library is free and unofficial. It can slow down, return no results, or block an address that sends too many searches. The app searches a few queries per click and waits briefly between them. There is no paid search account in this project. If search is unavailable, use **Use offline sample data** or paste websites you already know into Lead Management by discovering one reachable company and editing it.

### What can start costing money

- Render, if you need the site to stay awake all the time.
- Supabase, if the database grows past the free size or you need backups and uptime beyond the free plan.
- A paid AI API, only if you later choose to add one. The current email drafts do not need one.
- A paid lead database, only if you later choose to add one. This app does not include one.

Ollama runs on your own computer and is optional. It is not available to the Render website unless you set up a separate machine, which this guide does not require.

## What this guide does not do

It does not create a GitHub repository, push code, deploy the site, or open a Supabase account. Those steps are yours to click through when you are ready.
