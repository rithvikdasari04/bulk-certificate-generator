# Bulk Certificate Generator

A small API for submitting a group of certificate recipients, generating one PDF
per recipient, and checking each result. It is intended as a beginner-friendly
internship assignment project.

## Features

- Accepts a non-empty list of recipients with a name and valid email address.
- Stores jobs and recipient results in SQLite.
- Generates an individual PDF for each recipient using one built-in landscape
  certificate template.
- Uses random UUID filenames; recipient input is never used as a filesystem path.
- Records each recipient as `succeeded` or `failed`, including a failure message
  when generation fails.
- Continues to the remaining recipients if one PDF fails.
- Provides job progress, recipient results, and individual PDF downloads.

## Technology

- Python 3.10 or newer
- FastAPI and Uvicorn for the HTTP API
- Pydantic for request validation and response schemas
- SQLAlchemy and SQLite for persistence
- ReportLab for PDF creation
- Pytest and FastAPI's `TestClient` for automated tests

## Prerequisites

- Windows 10/11
- Python 3.10 or newer installed and available as `py` or `python`
- PowerShell

## Windows setup and installation

Open PowerShell in the project directory and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks virtual environment activation, use its Python directly
instead of activating it:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run the application

From the project directory, activate `.venv` as above, then run:

```powershell
python -m uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. FastAPI's interactive API
documentation is at `http://127.0.0.1:8000/docs`.

At startup, the application creates or updates the SQLite tables. The database
URL is `sqlite:///./certificates.db`, so `certificates.db` is stored relative to
the process's current working directory. Generated PDFs go in the project-level
`generated_certificates/` directory.

## API endpoints

### Health check

`GET /` returns:

```json
{"status": "ok"}
```

### Create a job and generate certificates

`POST /api/jobs` accepts a JSON object with a non-empty `recipients` array.
Each entry must have a non-blank `full_name` (up to 200 characters) and a valid
`email` address.

Example request:

```json
{
  "recipients": [
    {"full_name": "Ada Lovelace", "email": "ada@example.com"},
    {"full_name": "Grace Hopper", "email": "grace@example.com"}
  ]
}
```

The endpoint returns HTTP 201 after it has attempted generation for every
recipient. Its response has the existing `id` and `status` fields:

```json
{"id": 1, "status": "completed"}
```

The final job status is `completed` when all recipients succeeded, `partial`
when some succeeded and some failed, or `failed` when all failed. Invalid input
returns HTTP 422.

### Get job status and progress

`GET /api/jobs/{job_id}` returns the job ID, current status, recipient counts,
and percentage complete. For a completed two-recipient job, the response is:

```json
{
  "id": 1,
  "status": "completed",
  "total_recipients": 2,
  "succeeded": 2,
  "failed": 0,
  "progress_percent": 100
}
```

An unknown job ID returns HTTP 404.

### List recipient results

`GET /api/jobs/{job_id}/recipients` returns an array. Each item contains
`id`, `full_name`, `email`, `generation_status`, `pdf_path`, and
`failure_message`. For a successful item, `pdf_path` is the generated filename
and `failure_message` is `null`. Failed results include their failure message
and have a `null` PDF path.

### Download a certificate

`GET /api/jobs/{job_id}/recipients/{recipient_id}/pdf` downloads an individual
PDF for a successful recipient. The response is a PDF file. A missing recipient,
failed certificate, or missing file returns HTTP 404.

## Example API requests in PowerShell

With the server running in another PowerShell window:

```powershell
$body = @{
    recipients = @(
        @{ full_name = "Ada Lovelace"; email = "ada@example.com" },
        @{ full_name = "Grace Hopper"; email = "grace@example.com" }
    )
} | ConvertTo-Json -Depth 3

$job = Invoke-RestMethod -Method Post `
    -Uri "http://127.0.0.1:8000/api/jobs" `
    -ContentType "application/json" `
    -Body $body

$job
Invoke-RestMethod "http://127.0.0.1:8000/api/jobs/$($job.id)"
$recipients = Invoke-RestMethod `
    "http://127.0.0.1:8000/api/jobs/$($job.id)/recipients"
$recipients

Invoke-WebRequest `
    "http://127.0.0.1:8000/api/jobs/$($job.id)/recipients/$($recipients[0].id)/pdf" `
    -OutFile ".\certificate.pdf"
```

The job-creation request waits until the generation attempts finish, then returns
the final status. Use the returned job ID to inspect its recorded counts and
recipient results.

## Architecture and design decisions

- `app/main.py` creates the FastAPI application and initializes the database
  tables at startup.
- `app/database.py` configures the SQLite engine and SQLAlchemy sessions. It
  adds the recipient result columns when an existing database is started with
  this version of the application.
- `app/models.py` defines the job and recipient database records.
- `app/schemas.py` defines validated request bodies and API responses.
- `app/routers/jobs.py` contains job submission, progress, results, and download
  routes.
- `app/certificate_generator.py` contains the single ReportLab template and
  writes PDFs with random UUID filenames.
- `tests/test_jobs.py` exercises the API using temporary SQLite files and
  temporary PDF output directories under the test directory.

Generation is synchronous inside `POST /api/jobs`. This keeps the assignment
simple and avoids background-worker infrastructure, but the request stays open
until all recipients have been processed. Each recipient is handled separately:
success or failure is saved before moving to the next recipient, and a failure
does not cancel the rest of the job.

## Run tests

Install dependencies first, then run from the project directory:

```powershell
python -m pytest -q
```

The tests create isolated temporary database and output paths and clean them up;
they do not use the project database or `generated_certificates/` directory.

## Limitations and possible next steps

- Jobs run in the API request process; long lists keep that request open and
  progress is not delivered asynchronously.
- There is one predefined template and no endpoint to edit certificate content
  or choose a template.
- SQLite and the local output directory are suitable for a small assignment, not
  a multi-server deployment.
- There is no authentication, job deletion, or automatic cleanup of generated
  PDFs.
- Future improvements could add configurable templates, asynchronous processing,
  deployment-oriented storage, and pagination for large recipient lists.

Generated databases and certificate PDFs are excluded from Git by `.gitignore`;
source code, requirements, documentation, and tests remain available to commit.
