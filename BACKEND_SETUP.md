# Backend API Setup Guide

## Quick Start

Your project has a Python/FastAPI backend that stores visitor project requests in PostgreSQL.

### Step 1: Install PostgreSQL

Install PostgreSQL locally, use Docker, or connect to a managed PostgreSQL database such as Supabase, Neon, Railway, or Azure Database for PostgreSQL.

### Step 2: Create Database

Open `psql`, pgAdmin, or your database console and run:

```sql
CREATE DATABASE data_with_arvind;
```

The API creates the `project_requests` table automatically when it starts.

### Step 3: Setup Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Step 4: Configure `.env`

Copy `backend/.env.example` to `backend/.env` and update your PostgreSQL credentials:

```text
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/data_with_arvind
```

### Step 5: Run API

```powershell
uvicorn main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for interactive API documentation.

### Step 6: Connect Frontend

`contact.html` posts enquiry data to:

```text
http://localhost:8000/api/project-requests
```

When you deploy the backend, update the `data-api-url` value on the contact form to your live API URL.

## API Endpoints

- **POST** `/api/project-requests` - Save a project request
- **GET** `/api/project-requests` - Get all requests
- **GET** `/api/health` - Check API and database connectivity

## Database Schema

The `project_requests` table stores:

- `id` - Primary key
- `name` - Visitor name
- `email` - Visitor email
- `project_type` - Type of project
- `message` - Project description
- `timeline` - Project timeline
- `budget` - Budget estimate
- `submitted_at` - Submission timestamp

## Troubleshooting

**PostgreSQL Connection Error?**

- Check PostgreSQL is running
- Verify the `data_with_arvind` database exists
- Verify `DATABASE_URL` in `.env`
- Confirm `psycopg[binary]` installed from `requirements.txt`

**Port 8000 in use?**

```powershell
uvicorn main:app --reload --port 8001
```

**ModuleNotFoundError?**

- Ensure the virtual environment is activated
- Run `pip install -r requirements.txt` again

## Next Steps

1. Add JWT authentication for admin-only enquiry access
2. Create an admin dashboard
3. Deploy the API
4. Add email notifications after database save
