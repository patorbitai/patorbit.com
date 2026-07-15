# PAT Orbit Backend API

A FastAPI backend to store visitor project requests in PostgreSQL.

## Setup Instructions

### 1. Install PostgreSQL

Install PostgreSQL locally, use Docker, or connect to a managed PostgreSQL database such as Supabase, Neon, Railway, or Azure Database for PostgreSQL.

### 2. Create Database

Open `psql`, pgAdmin, or your database console and run:

```sql
CREATE DATABASE data_with_arvind;
```

The API creates the `project_requests` table automatically on startup.

### 3. Install Python Dependencies

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4. Configure Environment

Copy `.env.example` to `.env` and update with your PostgreSQL credentials:

```text
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/data_with_arvind
```

### 5. Run the API

```powershell
uvicorn main:app --reload --port 8000
```

API will be available at `http://localhost:8000`.

### 6. View API Documentation

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/api/health`

## API Endpoints

### Save a Project Request

**POST** `/api/project-requests`

```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "project_type": "AI agent",
  "message": "Need a sales dashboard",
  "timeline": "2 weeks",
  "budget": "$5000"
}
```

### Get All Requests

**GET** `/api/project-requests`

### Get Single Request

**GET** `/api/project-requests/{id}`

### Delete Request

**DELETE** `/api/project-requests/{id}`

### Health Check

**GET** `/api/health`

Returns database connectivity status when PostgreSQL is reachable.

## Frontend Integration

The contact page posts JSON to:

```text
http://localhost:8000/api/project-requests
```

When the API is deployed, update the `data-api-url` attribute in `contact.html` to the production API URL.

## Troubleshooting

**Connection Error?**

- Ensure PostgreSQL is running
- Check `DATABASE_URL` in `.env`
- Verify the database exists
- Confirm `psycopg[binary]` installed from `requirements.txt`

**Port 8000 in use?**

```powershell
uvicorn main:app --reload --port 8001
```

## Next Steps

- Add admin authentication
- Add email notifications
- Deploy the API
- Connect an admin dashboard
