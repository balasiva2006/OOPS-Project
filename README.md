# HMC — Hall Management Centre

A runnable Python OOP package named `hmc_system`, organised into subpackages and modules following the package example in the assignment. This implements the HMC problem in Python.

A Python mini project with Flask, SQLite, HTML, and CSS. It includes the application code, 19 HTML templates, a shared stylesheet, sample data setup, and automated workflow checks.

## Start here — Windows / VS Code

Requires Python 3.10 or newer. An internet connection is needed for the first package installation.

1. Open **this directory** in VS Code (the folder containing app.py and hmc_system/).
2. Open Terminal → New Terminal.
3. Run these commands one by one:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe seed.py
.\.venv\Scripts\python.exe app.py
```

4. Open http://127.0.0.1:5000 in your browser.
5. Leave the terminal running. Press Ctrl+C to stop the server.

Alternatively, double-click START_WINDOWS.bat. It creates the environment, installs Flask, adds sample data, and starts the app. If Windows uses `python` instead of `py`, use `python -m venv .venv` for the first command.

The environment does not need to be activated. Calling its Python executable directly avoids PowerShell execution-policy issues.

## Linux / macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python seed.py
.venv/bin/python app.py
```

## Demonstration accounts

These accounts are created by seed.py. They are fictitious local-demo accounts, not real users.

| Role | Username | Password | Scope |
|---|---|---|---|
| Administrator | admin | Admin@123 | All halls and financial entry |
| Student | student1 | Student@123 | Own records; Old Hall room 101 |
| Hall warden | warden1 | Warden@123 | Old Hall |
| Hall warden | warden2 | Warden@123 | New Hall |
| Mess manager | mess1 | Mess@123 | Old Hall |
| Mess manager | mess2 | Mess@123 | New Hall |
| Controlling warden | chief | Chief@123 | Read reports across halls |

Use Password in the navigation bar to change a password. Student accounts are created during registration. The administrator can create additional staff accounts from Staff accounts. Running seed.py again keeps existing records and passwords.

## Features

- Register a student with permanent address, contact numbers, photograph, and admission note; create the student's account.
- Add halls with amenities and fixed amenity charges.
- Add single or sharing rooms with capacity and monthly rent per student. Sample new-hall rent is higher and sharing-room rent is lower.
- Allocate an available bed; reject overbooking and duplicate student allocations.
- Print an allotment letter from the student profile.
- Enter monthly mess charges, including an explicit zero.
- Generate one bill per student and billing month. Bill snapshots preserve the original charges.
- Record full or partial payments, reject overpayment, and print numbered receipts.
- Students submit repair or staff complaints; hall wardens add Action Taken Reports and statuses.
- Hall wardens see only their hall. The controlling warden sees occupancy and reports across halls.
- Record mess handovers based on mess cash collected; print the settlement/signature sheet and cheque preparation details. Mess managers can acknowledge receipt.
- View/print annual consolidated billing and cash statements with a warden signature line.
- Hashed passwords, session login, server-side role checks, CSRF form tokens, escaped template text, parameterized SQL, protected document downloads, and application audit events.

## Important project assumptions

1. Rent and amenity fees are **monthly amounts per student**. Sharing rent is entered per person, not divided again by capacity.
2. Mess charges are entered before generating the bill. They can be revised until a bill is posted. Posted bill/payment records have no editing or deletion interface.
3. Payment allocation order is **mess → room rent → amenities**. A partial payment therefore has an explicit mess component for settlement purposes.
4. Mess settlement uses the **collection month**, determined by payment timestamp, rather than the bill month. Timestamps and reporting boundaries use UTC consistently.
5. One settlement closes a hall's mess collections for that month. Enter all payments before closing. Any later payment that would allocate more mess to that closed month is rejected. Rent-only/amenity-only payments remain possible.
6. Settlement records represent a manually recorded cheque handover. Printing does not send money. The cheque section is a demonstration layout; actual bank cheques require bank-issued stationery. Online acknowledgement supplements the signature line on the printed sheet.
7. Billing-year totals use bill months; paid-against-bill totals include all payment dates. Cash-year totals use receipt/handover dates. Net recorded cash flow is not a complete bank balance: no opening balance or other expense ledger is included.
8. This version has no room transfers, checkout, proration, refunds, financial reversal workflow, online payment gateway, or email/SMS service. These are possible extensions.

## Suggested demonstration (15–20 minutes)

1. Run seed.py and start the app.
2. Log in as admin. Open Halls and Rooms to inspect the sample inventory.
3. Register a new student with a real PNG/JPEG photo and a PDF/PNG/JPEG admission note. Use fictitious contact details for demonstrations.
4. Allocate an available room, open the profile, and print the allotment letter.
5. Open Mess charges. For the sample student, enter Rs. 2,500 for the current month.
6. Generate the sample student's bill. Old Hall room 101 gives rent Rs. 1,500 + mess Rs. 2,500 + amenities Rs. 300 = Rs. 4,300.
7. Record a payment of Rs. 3,000. It allocates Rs. 2,500 to mess and Rs. 500 to rent. Outstanding becomes Rs. 1,300. Print the receipt.
8. Pay the remaining Rs. 1,300 and open Receipts.
9. Log out. Log in as student1 and submit an Electrical complaint.
10. Log in as warden1. Open that complaint, record an ATR, and set it to Resolved.
11. Log in as student1 and verify the response.
12. Log in as admin. After completing all mess payments, record the Old Hall settlement for the current collection month with manager name and a unique fictitious cheque reference.
13. Print the settlement sheet. Log in as mess1 and confirm receipt.
14. Log in as chief to view overall occupancy and accounts. Print the annual statement.
15. Log in as warden2 and verify that Old Hall records are not visible.

## Code structure

```text
assignment - 3/
|-- hmc_system/                  Main Python package
|   |-- __init__.py              Public create_app() factory
|   |-- __main__.py              python -m hmc_system launcher
|   |-- seed.py                  Sample-data setup function
|   |-- accounts/
|   |   |-- __init__.py
|   |   `-- user.py              User class and password verification
|   |-- accommodation/
|   |   |-- __init__.py
|   |   |-- room.py              Room class and capacity check
|   |   `-- allocation.py        AllocationService class
|   |-- transactions/
|   |   |-- __init__.py
|   |   |-- bill.py              Bill class, total and balance
|   |   |-- billing.py           BillingService: generate and pay
|   |   `-- settlement.py        SettlementService: mess handover
|   |-- utilities/
|   |   |-- __init__.py
|   |   |-- database.py          SQLite schema and connection helpers
|   |   |-- validation.py        Money, month and timestamp functions
|   |   `-- audit.py             Audit recording function
|   `-- web/
|       |-- __init__.py
|       `-- application.py       Flask routes, forms and role checks
|-- app.py                       Existing application launcher
|-- seed.py                      Existing sample-data launcher
|-- templates/                   HTML pages and print layouts
|-- static/css/style.css         Shared screen and print styles
|-- tests/test_workflows.py      Workflow checks using package imports
|-- README.md                    Setup and demonstration
|-- requirements.txt            Flask dependency
`-- START_WINDOWS.bat           Windows launcher
```

Each subpackage contains an `__init__.py` file. The classes and functions live in the modules above. Import them directly from their hmc_system subpackages. Flask and SQLite are used directly.

You can also seed and run the package directly:

```powershell
.\.venv\Scripts\python.exe -m hmc_system.seed
.\.venv\Scripts\python.exe -m hmc_system
```

`instance/`, the database, uploaded documents, and the session secret are created automatically. The ZIP intentionally contains no database, private uploads, secret key, or virtual environment.

## Checking the project

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Ten automated tests cover money validation, room capacity and duplicate allocation, missing/duplicate bills, partial payments and overpayments, document/record permissions, complaint ATR permissions, settlement totals and closed collections, login/CSRF, registration/uploads/HTML escaping, and role-specific pages/print reports. Tests use temporary databases and do not change your project records.

## Troubleshooting

- **No module named flask:** Install requirements with the same .venv Python used to start app.py.
- **TemplateNotFound:** Keep templates/ and static/ in the project directory beside hmc_system/ and app.py.
- **No sample accounts:** Run seed.py before logging in.
- **Port 5000 already in use:** Stop the previous Flask terminal with Ctrl+C, or temporarily use `run(port=5001, debug=True)` in app.py.
- **409 duplicate record:** Check the roll number, login name, hall/room number, bill month, or settlement month.
- **400 CSRF token:** Refresh the page and submit again. A login/logout in another tab may invalidate an old form.
- **413 upload error:** The complete request may not exceed 6 MB. Use smaller files.
- **Print layout:** Choose Print / Save as PDF and disable browser headers/footers if desired.

## Scope

This is an educational local mini project, not a production financial system. It has no payment gateway, bank integration, tamper-proof external audit storage, account recovery, login rate limiting, or production hosting configuration. File checks validate signatures, not full malware scanning. Debug mode is for local development. Before using real personal or financial data, extend and review the implementation appropriately.

The original image names Java. This submission implements the HMC requirements in Python, as requested. The banking example supplies the package organisation pattern; the application domain remains HMC.
