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

### Monitors (`/monitors`)
**Headers:** `Authorization: Bearer <token>`

- **GET /monitors**
  - Get all uptime monitors for the user's projects.
  - Returns: `[ { "id": "...", "name": "...", "url": "...", "status": "operational|degraded|down", "latency": "...", "uptime": "...", "lastCheck": "...", "history": [...] } ]`

- **POST /monitors**
  - Create a new monitor.
  - Body: `{ "name": "...", "url": "...", "projectId": "...", "type": "http", "checkInterval": 60 }`
  - Returns: `{ "message": "...", "id": "...", ... }`

- **DELETE /monitors/<id>**
  - Delete a monitor.

### Alerts (`/alerts`)
**Headers:** `Authorization: Bearer <token>`

- **GET /alerts/**
  - Returns a list of alerts.
  - Query Params:
    - `status`: `active` (open) or `resolved`
    - `severity`: `critical`, `warning`, `low`
  - Returns: `{ "alerts": [ { "id": "...", "title": "...", "severity": "...", "status": "...", "time": "..." }, ... ] }`

### Events (`/events`)
**Headers:** `Authorization: Bearer <token>`

- **GET /events/**
  - Returns a stream of system events and logs.
  - Query Params:
    - `q`: Search query (searches message and source)
    - `type`: Filter by type (`info`, `success`, `error`, `warning`)
    - `limit`: Number of events (default 50)
  - Returns: `[ { "id": "...", "type": "...", "message": "...", "source": "...", "time": "..." }, ... ]`

- **POST /events/**
  - Create a new event log.
  - Body: `{ "projectId": "...", "type": "...", "message": "...", "source": "..." }`
  - Returns: `{ "message": "...", "id": "..." }`

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Run server: `python index.py`
