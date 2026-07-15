# PAT Orbit Portfolio Website

A static PAT Orbit website for AI agents, intelligent automation, AI-powered software products, and practical product concepts. The repository also includes a browser data preview page, a dedicated Python EDA tool, and an optional FastAPI backend for saving contact/project requests.

## Project Structure

```text
.
|-- index.html                  # Home page
|-- about.html                  # Profile and skills
|-- services.html               # Service offerings
|-- portfolio.html              # Featured work
|-- contact.html                # Contact form and email delivery details
|-- blog.html                   # Blog overview
|-- data-analyzer.html          # Browser preview for uploaded datasets
|-- azure-etl-pipeline.html     # Legacy redirect page
|-- css/
|   `-- style.css               # Shared site styles
|-- js/
|   `-- live-analytics.js       # Static browser data preview logic
|-- tools/
|   |-- eda_report.py           # Python EDA report generator
|   |-- requirements.txt        # EDA tool dependencies
|   `-- README.md               # EDA tool usage
|-- projects/                   # Detailed project pages and ETL sample
`-- backend/                    # Optional FastAPI API
```

## Run The Website

Open `index.html` directly in a browser. The site is static and does not require a build step.

The contact form posts to the FastAPI backend at `/api/project-requests`, where visitor enquiries can be saved in PostgreSQL. For local testing, run the backend on `http://localhost:8000`.

## Publish On patorbit.com

This site is ready for GitHub Pages. The root `CNAME` file contains `patorbit.com`, and SEO files already point to `https://patorbit.com`.

In GitHub, publish the `main` branch from the repository root using Pages. At your domain registrar, point DNS to GitHub Pages:

```text
A     @    185.199.108.153
A     @    185.199.109.153
A     @    185.199.110.153
A     @    185.199.111.153
CNAME www  patorbitai.github.io
```

After DNS updates, set the custom domain to `patorbit.com` in GitHub Pages and enable HTTPS once GitHub finishes checking the domain.

## Run The Python EDA Tool

Use this when you need proper dataset cleaning, column identity checks, KPI summaries, correlations, and chart files.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r tools\requirements.txt
python tools\eda_report.py
```

The EDA tool reads the newest local dataset from `datasets/` by default. It supports CSV, TSV, JSON, XLS, and XLSX files. It creates a cleaned CSV, a JSON summary, a Markdown report, and chart images inside the output folder.

## Run The Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Create a `.env` file from `backend/.env.example` and update `DATABASE_URL` before running the API.

## Code Style

- Use 2 spaces for HTML, CSS, JavaScript, and Markdown.
- Use 4 spaces for Python.
- Keep shared styles in `css/style.css`.
- Keep browser data preview logic in `js/live-analytics.js`.
- Keep deeper EDA/report generation logic in `tools/`.
- Keep project case studies inside `projects/`.
