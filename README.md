# Pattern Pipeline

Pattern Pipeline is a trust-first data transformation workspace built for the
Rhombus AI engineering exercise. It converts natural-language requests into
inspectable plans, previews every affected value, and writes approved changes
to a separate CSV or XLSX artifact.

> Live URL: add after deployment
>
> Demo video: add after recording

## What to try

1. Upload [`samples/messy_customers.csv`](samples/messy_customers.csv).
2. Select `email` and `notes`, then enter `Find email addresses`.
3. Generate the regex, inspect its explanation and examples, and preview the
   highlighted cell-level diff.
4. Approve the run and download the processed CSV.
5. Try `Standardize categories` on `state`, or `Extract fields` on `name`.

The deployed application remains usable without an API key for common email,
phone, URL, IP address, Australian-state, boolean, name, and email-extraction
requests. When `OPENAI_API_KEY` is configured it uses schema-constrained OpenAI
Responses for arbitrary requests.

## Product decisions

- **AI proposes; deterministic code executes.** Model output is schema-validated,
  compiled, safety checked, previewed, and explicitly approved.
- **Uploaded rows never enter the regex planner.** The provider receives only the
  instruction and selected column names. Optional plans follow the same boundary.
- **The original is immutable.** Every approved operation creates a new artifact
  and an append-only `TransformRun` recipe.
- **Manual mode is first class.** Generated regexes, flags, mappings, and named
  extraction groups remain visible and editable.
- **Safety is part of the UI.** Nested repetition, empty matches, unsupported
  columns, excessive cell length, broad match rates, and regex timeouts are
  handled before application.

## Architecture

```text
React + TypeScript
  | multipart upload / JSON plans
Django REST Framework
  |-- local CSV/XLSX parsing and profiling
  |-- structured LLM provider boundary
  |-- timeout-protected deterministic executors
  |-- immutable datasets and transformation runs
PostgreSQL/SQLite + filesystem artifacts
```

Core workflow:

```text
Upload -> Profile -> Describe -> Generate -> Trust Gate -> Approve -> Export
```

The LLM never performs the replacement itself. It produces either:

- a regex proposal with flags, explanation, assumptions, and examples;
- a canonical category mapping; or
- a named-capture extraction plan.

All three are executed locally by deterministic Python services.

## Local setup

Requirements:

- Python 3.12
- Node.js 24
- pnpm 11

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt

cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

In a second terminal:

```bash
python backend/manage.py migrate
python backend/manage.py runserver
```

Open `http://localhost:5173`. Vite proxies `/api` to Django on port 8000.

Copy `.env.example` to `.env` to configure an OpenAI key or production settings.
No uploaded cell values are included in model requests.

## Verification

```bash
python backend/manage.py test datasets
python backend/manage.py makemigrations --check --dry-run

cd frontend
pnpm lint
pnpm test
pnpm build
```

The backend suite covers CSV and XLSX ingestion, schema profiling, privacy at the
provider boundary, unsafe regex rejection, cell-level previews, immutable apply,
formula-injection-safe export, both optional transforms, and downloads in the
original format.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

The multi-stage image builds React, collects hashed static assets through
WhiteNoise, migrates the database at startup, and serves Django with Gunicorn.

The included [`render.yaml`](render.yaml) provisions a Docker web service and
PostgreSQL database. Configure `OPENAI_API_KEY` in the Render dashboard; the
built-in plans remain available if it is omitted.

## API summary

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/datasets/` | Upload and profile CSV/XLSX |
| `POST` | `/api/datasets/:id/transforms/generate/` | Generate regex proposal |
| `POST` | `/api/datasets/:id/transforms/preview/` | Safety-check and diff regex |
| `POST` | `/api/datasets/:id/transforms/apply/` | Persist run and output artifact |
| `POST` | `/api/datasets/:id/ai-transforms/*/` | Generate, preview, or apply optional plans |
| `GET` | `/api/transforms/:id/download/` | Download processed artifact |

## Security and limitations

- Uploads are limited to CSV/XLSX and 20 MB; XLSX signatures are checked.
- Regex length, cell length, supported flags, nested repetition, empty matches,
  and per-cell execution time are bounded.
- Spreadsheet values beginning with `=`, `+`, `-`, or `@` are escaped on export.
- Files expire logically after one hour. A production cleanup worker should remove
  expired database rows and artifacts on a schedule.
- XLSX processing currently operates on the first sheet and exports processed
  tabular data rather than preserving workbook formatting or formulas.
- Authentication and multi-user project isolation are intentionally outside this
  exercise; opaque UUIDs are not a substitute for authorization in production.

## Repository layout

- `backend/`: Django models, APIs, provider adapters, deterministic services, tests.
- `frontend/`: React workflow, Zod API contracts, trust-gate and diff UI.
- `samples/`: synthetic datasets for the reviewer path.
- `.github/workflows/ci.yml`: backend and frontend verification.
