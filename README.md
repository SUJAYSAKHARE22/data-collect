# Project Data Collector

A production-quality Python service whose **only** responsibility is to
**fetch, extract, organize, and store project data** from multiple input
sources, in a standard structured format that a separate downstream auditing
system can consume.

This service does **not** perform code analysis, auditing, documentation
generation, or LLM processing — it is purely a data collection layer.

## Supported Input Sources

| Source                    | Endpoint       | Notes                                   |
|----------------------------|----------------|------------------------------------------|
| Public GitHub repository   | `POST /github` | Clone via HTTPS                          |
| Private GitHub repository  | `POST /github` | Requires a Personal Access Token (PAT)   |
| Website URL                 | `POST /website`| Same-domain crawl of public pages only   |
| ZIP file upload              | `POST /zip`    | Zip-Slip safe extraction                 |
| Local project directory    | `POST /local`  | Server-side path (e.g. for CLI/CI use)   |

## Architecture

Clean, layered architecture:

```
app/
  routers/       # FastAPI route handlers (HTTP layer only)
  services/       # Orchestration: job lifecycle, collector coordination
  loaders/        # One loader per input source (github, website, zip, local)
  storage/         # Standard output directory layout on disk
  utils/           # Tree building, hashing, file metadata, logging
  models/          # In-memory job record
  schemas/         # Pydantic request/response/metadata models
  config/          # Environment-driven settings
```

Each loader implements a single `collect(...)` method that returns
`(metadata, tree, files)` — the routers and services never know the
internal details of how a GitHub clone differs from a website crawl or a
ZIP extraction.

## Output Format

Every job produces a folder under `output/{job_id}/`:

```
output/{job_id}/
  project/            # The collected project content itself
  metadata.json       # Standard metadata (see below)
  tree.json           # Nested directory tree
  files.json           # Flat list of file records (size, hash, language, ...)
  logs/
  downloads/           # Generated zip archive for /download
```

`metadata.json` follows this common schema regardless of input source:

```json
{
  "input_type": "github_public",
  "project_name": "example-repo",
  "source": "https://github.com/owner/example-repo",
  "language": "Python",
  "framework": null,
  "created_at": "2026-07-02T00:00:00+00:00",
  "files": ["app/main.py", "README.md"],
  "folders": ["app"],
  "entry_files": ["app/main.py"],
  "dependencies": ["requirements.txt"],
  "extra": {
    "owner": "owner",
    "branch": "main",
    "commit_hash": "abc123...",
    "license": "MIT",
    "languages": {"Python": 12345}
  }
}
```

## API Endpoints

| Method | Path                 | Description                                  |
|--------|----------------------|-----------------------------------------------|
| POST   | `/github`            | Start a GitHub repo collection job            |
| POST   | `/website`           | Start a website crawl job                     |
| POST   | `/zip`                | Upload and process a ZIP file                 |
| POST   | `/local`             | Collect a local server-side directory         |
| GET    | `/status/{job_id}`   | Poll job status                               |
| GET    | `/metadata/{job_id}`  | Fetch `metadata.json`                          |
| GET    | `/tree/{job_id}`      | Fetch `tree.json`                              |
| GET    | `/files/{job_id}`     | Fetch `files.json`                             |
| GET    | `/download/{job_id}`  | Download the collected project as a ZIP        |

All collection jobs run as FastAPI background tasks; endpoints return
`202 Accepted` immediately with a `job_id` to poll.

Interactive API docs are available at `/docs` (Swagger UI) once running.

## Installation & Setup

### 1. Backend Setup

First, navigate to the `backend` directory, create a virtual environment, install the dependencies, and set up your environment variables:

```bash
# Navigate to the backend directory
cd backend

# Create a virtual environment
python -m venv venv

# Activate virtual environment
# On Windows (Command Prompt):
venv\Scripts\activate.bat
# On Windows (PowerShell):
.\venv\Scripts\activate.ps1
# On macOS/Linux:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Create .env file from template
cp .env.example .env
# Edit the .env file if you wish to override GITHUB_TOKEN or change directories
```

### 2. Frontend Setup

In a separate terminal, navigate to the `frontend` directory and install the Node.js packages:

```bash
# Navigate to the frontend directory
cd frontend

# Install packages
npm install
```

---

## Running the Application

To run the full stack, you need to start both the FastAPI backend and the Vite frontend:

### 1. Start the Backend Server

From the `backend` directory (ensure your virtual environment is activated):

```bash
# Run using the run script
python run.py

# Alternatively, run using uvicorn directly:
uvicorn run:app --reload
```

The backend API will start at **`http://localhost:8000`** with the interactive documentation available at **`http://localhost:8000/docs`**.

### 2. Start the Frontend Dev Server

From the `frontend` directory:

```bash
npm run dev
```

The Vite dev server will start at **`http://localhost:3000`**. Open this URL in your web browser to access the dashboard.

## Running with Docker

```bash
docker compose up --build
```

## Usage Examples

### Collect a public GitHub repository

```bash
curl -X POST http://localhost:8000/github \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/octocat/Hello-World"}'
```

### Collect a private GitHub repository

```bash
curl -X POST http://localhost:8000/github \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/your-org/private-repo", "access_token": "ghp_xxx"}'
```

### Crawl a website

```bash
curl -X POST http://localhost:8000/website \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "max_pages": 20, "max_depth": 2}'
```

### Upload a ZIP file

```bash
curl -X POST http://localhost:8000/zip -F "file=@project.zip"
```

### Collect a local directory

```bash
curl -X POST http://localhost:8000/local \
  -H "Content-Type: application/json" \
  -d '{"path": "/absolute/path/to/project"}'
```

### Poll status and fetch results

```bash
curl http://localhost:8000/status/<job_id>
curl http://localhost:8000/metadata/<job_id>
curl http://localhost:8000/tree/<job_id>
curl -OJ http://localhost:8000/download/<job_id>
```

## Configuration

All configuration is via environment variables (see `.env.example`):

- `GITHUB_TOKEN` — default PAT for private repos (can be overridden per-request)
- `OUTPUT_DIR` / `LOGS_DIR` — base storage locations
- `MAX_UPLOAD_SIZE_MB` — ZIP upload size limit
- `CRAWLER_TIMEOUT_SECONDS`, `CRAWLER_MAX_PAGES`, `CRAWLER_MAX_DEPTH` — website crawler limits
- `HTTP_MAX_RETRIES`, `HTTP_RETRY_BACKOFF_SECONDS` — network retry behavior

## Security Notes

- **Zip Slip protection**: every ZIP entry path is resolved and validated to
  stay within the target extraction directory before extraction.
- **Website crawling** only follows same-domain links and only collects
  publicly served content (HTML, robots.txt, sitemap.xml, public assets) —
  it never attempts to access backend/private resources.
- **Private GitHub repos** use a PAT injected into the HTTPS clone URL; the
  token itself is never persisted to disk or included in `metadata.json`.

## Testing

```bash
pytest -q
```

Tests cover: tree building, hashing, ignore-pattern logic, the ZIP loader
(including Zip Slip rejection), the local directory loader, and GitHub URL
parsing helpers.

## Folder Explanation

- `app/routers/` — thin HTTP layer; one file per endpoint group.
- `app/services/` — `CollectorService` orchestrates loaders + storage;
  `JobRepository` tracks job state in memory.
- `app/loaders/` — one self-contained loader per input source.
- `app/storage/` — `StorageManager` owns the on-disk output layout.
- `app/utils/` — reusable helpers (tree building, hashing, logging, ignore
  patterns, file metadata).
- `app/schemas/` — Pydantic models for requests, responses, and the common
  metadata format.
- `app/models/` — the `Job` dataclass used for in-memory job tracking.
- `app/config/` — environment-driven `Settings`.
