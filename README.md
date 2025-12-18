# WatchUp Server

This is the backend server for WatchUp.

## API Endpoints

### Auth (`/auth`)
- **POST /auth/login**
  - Body: `{ "email": "...", "password": "..." }`
  - Returns: `{ "user": {...}, "token": "..." }`
- **POST /auth/register**
  - Body: `{ "username": "...", "email": "...", "password": "..." }`
  - Returns: `{ "user": {...}, "token": "..." }`

### Projects (`/projects`)
**Headers:** `Authorization: Bearer <token>`

- **GET /projects/**
  - Get all projects the authenticated user is subscribed to.
  - Returns: `{ "projects": [...] }`

- **GET /projects/<project_id>**
  - Get details of a specific project.
  - Returns: `{ "project": {...} }`

- **POST /projects/**
  - Create a new project. The creator is automatically subscribed.
  - Body: `{ "name": "...", "description": "..." }`
  - Note: The Project ID will be automatically appended to the description.
  - Returns: `{ "project": {...}, "message": "..." }`

### Dashboard (`/dashboard`)
**Headers:** `Authorization: Bearer <token>`

- **GET /dashboard/stats**
  - Returns aggregated stats for cards (Uptime, Active Alerts, Avg Response).
  - Returns: `{ "uptime_24h": "...", "active_alerts": 0, "avg_response": "...", ... }`

- **GET /dashboard/charts**
  - Returns data for charts (Latency history, Uptime history).
  - Returns: `{ "latency": [...], "uptime": [...] }`

- **GET /dashboard/activity**
  - Returns recent activity feed.
  - Returns: `{ "activities": [...] }`

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Run server: `python index.py`
