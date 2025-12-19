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
                # Maps uptime_incidents to alert structure
                query = """
                    SELECT 
                        i.id,
                        i.project_id,
                        i.started_reason,
                        i.last_error,
                        i.status,
                        i.started_at,
                        i.resolved_at,
                        m.name as service_name,
                        m.url as service_url
                    FROM uptime_incidents i
                    JOIN uptime_monitors m ON i.monitor_id = m.id
                    JOIN subscriptions s ON m.project_id = s.project_id
                    WHERE s.user_id = %s
                """
                params = [user_id]

                # Apply Filters
                if status_filter:
                    if status_filter == 'open' or status_filter == 'active':
                        query += " AND i.status = 'open'"
                    elif status_filter == 'resolved':
                         query += " AND i.status = 'resolved'"
                    else:
                         query += " AND i.status = %s"
                         params.append(status_filter)
                
                # Map severity filter to started_reason
                # 'critical' -> 'down'
                # 'warning' -> 'degraded' (if supported)
                if severity_filter:
                    if severity_filter == 'critical':
                        query += " AND i.started_reason = 'down'"
                    elif severity_filter == 'warning':
                         query += " AND i.started_reason != 'down'" # Assuming anything else is warning
                    else:
                         pass # low severity not strictly mapped yet

                query += " ORDER BY i.started_at DESC"

                cursor.execute(query, tuple(params))
                alerts = cursor.fetchall()

                # Format response to match frontend expectations
                formatted_alerts = []
                for alert in alerts:
                    # Map started_reason to severity
                    severity = "critical" if alert["started_reason"] == "down" else "warning"
                    
                    # Construct title
                    title = f"Monitor {alert['started_reason']}: {alert['last_error'] or 'Unknown error'}"
                    
                    formatted_alerts.append({
                        "id": alert["id"],
                        "projectId": alert["project_id"],
                        "title": title,
                        "service": alert["service_name"] or alert["service_url"],
                        "severity": severity,
                        "status": "open" if alert["status"] == "open" else "resolved",
                        "time": alert["started_at"].strftime("%Y-%m-%d %H:%M:%S") if alert["started_at"] else None,
                        "created_at_iso": alert["started_at"].isoformat() if alert["started_at"] else None
                    })

        finally:
            conn.close()

        return jsonify({"alerts": formatted_alerts}), 200

    except Exception as e:
        print("Get alerts error:", e)
        return jsonify({"error": "Internal server error"}), 500
