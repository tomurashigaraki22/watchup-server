from extensions.extensions import get_db_connection
from flask import Blueprint, request, jsonify
from functions.projects import login_required

alerts_bp = Blueprint("alerts", __name__)

@alerts_bp.route("/", methods=["GET"])
@login_required
def get_alerts():
    """
    Returns a list of alerts for the user's subscribed projects.
    Supports filtering by status (open/resolved) and severity (critical/warning/low).
    """
    try:
        user_id = request.user_id
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        # Query Parameters
        status_filter = request.args.get("status") # 'active' (open) or 'resolved'
        severity_filter = request.args.get("severity") # 'critical', 'warning', 'low'

        try:
            with conn.cursor() as cursor:
                # Base Query
                query = """
                    SELECT 
                        a.id,
                        a.type as severity,
                        a.message as title,
                        a.status,
                        a.created_at,
                        a.resolved_at,
                        m.name as service_name
                    FROM alerts a
                    JOIN monitors m ON a.monitor_id = m.id
                    JOIN subscriptions s ON m.project_id = s.project_id
                    WHERE s.user_id = %s
                """
                params = [user_id]

                # Apply Filters
                if status_filter:
                    # Map frontend 'open' to DB 'active' if needed, or stick to DB values
                    # DB uses 'active' for open alerts based on dbschemas.py
                    if status_filter == 'open':
                        query += " AND a.status = 'active'"
                    elif status_filter == 'resolved':
                         query += " AND a.status = 'resolved'"
                    else:
                         query += " AND a.status = %s"
                         params.append(status_filter)
                
                if severity_filter:
                    query += " AND a.type = %s"
                    params.append(severity_filter)

                query += " ORDER BY a.created_at DESC"

                cursor.execute(query, tuple(params))
                alerts = cursor.fetchall()

                # Format response to match frontend expectations
                formatted_alerts = []
                for alert in alerts:
                    # Calculate time ago string or just return ISO date for frontend to format
                    # Returning ISO date is cleaner for API
                    formatted_alerts.append({
                        "id": alert["id"],
                        "title": alert["title"],
                        "service": alert["service_name"],
                        "severity": alert["severity"], # type column in DB maps to severity
                        "status": "open" if alert["status"] == "active" else "resolved",
                        "time": alert["created_at"].strftime("%Y-%m-%d %H:%M:%S") if alert["created_at"] else None,
                        "created_at_iso": alert["created_at"].isoformat() if alert["created_at"] else None
                    })

        finally:
            conn.close()

        return jsonify({"alerts": formatted_alerts}), 200

    except Exception as e:
        print("Get alerts error:", e)
        return jsonify({"error": "Internal server error"}), 500
