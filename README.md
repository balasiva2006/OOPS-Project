# HMC - Hall Management Centre

A Python OOP assignment using Flask, PostgreSQL, HTML and CSS. The main package is `hmc_system`. PostgreSQL stores accounts, room records, bills, payments, complaints, and uploaded documents.

## Run on Windows

Open this directory in VS Code and use its PowerShell terminal.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Skip the copy command if `.env` already exists. Open `.env` and fill in:

```dotenv
DATABASE_URL=your_postgresql_connection_string
HMC_SECRET_KEY=your_private_random_key
```

Get the PostgreSQL connection string from your Neon project's Connect panel. Use its pooled connection string with SSL enabled. Generate a session key with:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Keep `.env` private. It is excluded from Git and Vercel uploads. Never put credentials in Python source or README.md.

For an assignment demonstration, create tables and sample accounts:

```powershell
.\.venv\Scripts\python.exe seed.py
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000. Stop with Ctrl+C. After setup you can also use START_WINDOWS.bat to start the app.

For Linux/macOS, use `python3 -m venv .venv` and `.venv/bin/python` instead of the Windows Python path.

## Accounts

These fictitious demo accounts are created only when you run seed.py:

| Role | Username | Password |
|---|---|---|
| Administrator | OOPS | OOPS@123 |

Seeding again preserves existing records and passwords. Change every demo password before exposing demo accounts publicly.

For a fresh public deployment, create your own administrator instead of seeding demo accounts:

```powershell
.\.venv\Scripts\python.exe -m flask --app app create-admin
```

This command creates missing tables and prompts for your username and password. Staff accounts and student accounts can then be created through the admin interface. To create tables only:

```powershell
.\.venv\Scripts\python.exe -m flask --app app init-db
```

## Deploy on Vercel

1. Set up a Neon PostgreSQL database. Reset any database password previously shared publicly.
2. Set `DATABASE_URL` and `HMC_SECRET_KEY` in your local `.env`, then run `create-admin` above against the database you intend to deploy. The same database is used from local Python and Vercel.
3. Push the project to your Git repository, then import it in Vercel. Select Flask if asked for a framework. The root `app.py` exports the Flask application.
4. Add `DATABASE_URL` and `HMC_SECRET_KEY` in Vercel's project environment variables. Keep the session key stable across deployments. Use a separate database or Neon branch for preview deployments if previews should not modify production records.
5. Deploy, then test login, registration, document downloads, bills and complaints.

Dependencies come from requirements.txt. vercel.json sets the function timeout. CSS is served from `public/static/css/style.css`. Database setup is an explicit command; application imports and builds do not create tables or demo users.

The app needs no writable server filesystem. Uploaded PNG/JPEG photos and PDF/PNG/JPEG admission notes are kept in PostgreSQL and served only after role/student/hall permission checks. The complete registration request is limited to 4 MB, including both files and form fields. This simple storage approach suits a small assignment; large document collections should move to private object storage.

## Package structure

```text
hmc_system/
    __init__.py                 Application factory
    __main__.py                 Package launcher
    seed.py                     Optional sample data
    accounts/user.py            User model and password checks
    accommodation/room.py       Room model
    accommodation/allocation.py Room capacity and allocation rules
    transactions/bill.py        Bill totals and balance
    transactions/billing.py     Bills and payments
    transactions/settlement.py  Monthly mess handovers
    utilities/database.py       PostgreSQL schema, connections and transactions
    utilities/documents.py      Private document storage
    utilities/validation.py     Money, month and timestamp validation
    utilities/audit.py          Audit events
    web/application.py          Routes, forms and permission checks
templates/                      Formatted HTML/Jinja pages
public/static/css/style.css     Formatted stylesheet
tests/                          Configuration and PostgreSQL workflow tests
```

Each package/subpackage includes `__init__.py`. All application code is Python, following the requested language despite Java appearing in the original question.

## Implemented workflows

- Student registration with contact details, photo, admission note and login.
- Hall/room inventory, room allocation with capacity checks, printable allotment letters.
- Monthly mess charges, rent and amenities; bills and partial/full payments; printed receipts.
- Repair/staff complaints and warden Action Taken Reports.
- Hall-specific and overall occupancy; annual consolidated accounts with signature lines.
- Mess settlement sheets, cheque preparation details and manager acknowledgement.
- Password hashing, CSRF tokens, parameterised SQL, role/hall checks and audit records.

Rent and amenity fees are monthly per student. Mess charges must be entered before billing, including an explicit zero if applicable. Posted bills preserve their amounts. Payments allocate to mess, then rent, then amenities. Settlements close a hall's collection month, using UTC payment dates; later mess collections for that closed month are rejected. A database transaction and advisory lock serialise application writes across server instances.

Cheques are recorded and printed for demonstration; the app does not move money. Annual billing totals use bill months, while cash totals use receipt/handover dates. Net cash flow excludes opening balances and other expenses. Room transfers, refunds, corrections/reversals, online payments and account recovery are outside this assignment's scope.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Set `TEST_DATABASE_URL` in your terminal to run database workflow tests against a dedicated PostgreSQL test database. Each test creates and removes its own uniquely named schema; the test user needs permission to create schemas. Tests do not use `DATABASE_URL` as a fallback. Without a test connection, database tests are reported as skipped and configuration checks still run.

## Existing local data

The old `instance/` folder is no longer used. It has been preserved because it may contain your previous records and documents. They are not automatically copied into PostgreSQL. The app has no local database fallback. Keep the folder privately if you need those records later; it is excluded from deployment.

This is an educational project. Before storing real student/financial data, review access controls, backups, logging, login rate limiting and operational security. Local debug mode is only used by the direct development launch command.
