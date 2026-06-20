# Pattern Pipeline

Pattern Pipeline is a trust-first data transformation workspace built for the
Rhombus AI engineering exercise. It turns natural-language matching requests
into inspectable regular expressions, previews their effects, and applies only
approved changes to CSV and Excel files.

The application is under active development. Setup and deployment instructions
will be expanded as each vertical slice becomes runnable.

## Project layout

- `backend/`: Django REST API and deterministic transformation engine.
- `frontend/`: React and TypeScript user interface.
