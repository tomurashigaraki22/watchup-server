from extensions.extensions import get_db_connection
from flask import Blueprint, request, jsonify
from functions.projects import login_required
import datetime

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/stats", methods=["GET"])
@login_required
def get_dashboard_stats():
    """
    Returns aggregated stats for the user's projects/monitors.
    - Uptime (24h)
    - Active Alerts
    - Avg Response
    - Last Incident
    """
    try:
        user_id = request.user_id
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        stats = {
            "uptime_24h": "100%", # Default
            "uptime_trend": "+0.00%",
            "active_alerts": 0,
            "critical_alerts": 0,
            "avg_response": "0ms",
            "avg_response_trend": "0ms",
            "last_incident": "None"
        }

        try:
            with conn.cursor() as cursor:
                # 1. Active Alerts
                # Get alerts for monitors belonging to projects the user is subscribed to
                query_alerts = """
                    SELECT COUNT(*) as count, 
                           SUM(CASE WHEN i.started_reason = 'down' THEN 1 ELSE 0 END) as critical_count
                    FROM uptime_incidents i
                    LEFT JOIN uptime_monitors m ON i.monitor_id = m.id
                    JOIN subscriptions s ON i.project_id = s.project_id
                    WHERE s.user_id = %s AND i.status = 'open'
                """
                cursor.execute(query_alerts, (user_id,))
                alerts_data = cursor.fetchone()
                if alerts_data:
                    stats["active_alerts"] = alerts_data["count"]
                    stats["critical_alerts"] = alerts_data["critical_count"] or 0

                # 2. Avg Response (last 24h)
                query_avg_resp = """
                    SELECT AVG(mc.response_time_ms) as avg_resp
                    FROM uptime_heartbeats mc
                    JOIN uptime_monitors m ON mc.monitor_id = m.id
                    JOIN subscriptions s ON m.project_id = s.project_id
                    WHERE s.user_id = %s AND mc.checked_at > NOW() - INTERVAL 1 DAY
                """
                cursor.execute(query_avg_resp, (user_id,))
                resp_data = cursor.fetchone()
                if resp_data and resp_data["avg_resp"]:
                    stats["avg_response"] = f"{int(resp_data['avg_resp'])}ms"

                # 3. Uptime (last 24h)
                # (Active Checks / Total Checks) * 100
                query_uptime = """
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN mc.status = 'up' THEN 1 ELSE 0 END) as up_count
                    FROM uptime_heartbeats mc
                    JOIN uptime_monitors m ON mc.monitor_id = m.id
                    JOIN subscriptions s ON m.project_id = s.project_id
                    WHERE s.user_id = %s AND mc.checked_at > NOW() - INTERVAL 1 DAY
                """
                cursor.execute(query_uptime, (user_id,))
                uptime_data = cursor.fetchone()
                if uptime_data and uptime_data["total"] > 0:
                    uptime_pct = (uptime_data["up_count"] / uptime_data["total"]) * 100
                    stats["uptime_24h"] = f"{uptime_pct:.2f}%"

        finally:
            conn.close()

        return jsonify(stats), 200

    except Exception as e:
        print("Dashboard stats error:", e)
        return jsonify({"error": "Internal server error"}), 500

@dashboard_bp.route("/charts", methods=["GET"])
@login_required
def get_dashboard_charts():
    """
    Returns data for:
    - Response Latency (History)
    - Uptime History
    """
    try:
        user_id = request.user_id
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        charts = {
            "latency": [],
            "uptime": []
        }

        try:
            with conn.cursor() as cursor:
                # Latency History (Last 50 checks aggregated or raw?)
                # Let's get the last 50 checks across all monitors (average per time bucket would be better but keeping it simple)
                query_latency = """
                    SELECT mc.checked_at, AVG(mc.response_time_ms) as avg_resp
                    FROM uptime_heartbeats mc
                    JOIN uptime_monitors m ON mc.monitor_id = m.id
                    JOIN subscriptions s ON m.project_id = s.project_id
                    WHERE s.user_id = %s
                    GROUP BY mc.checked_at
                    ORDER BY mc.checked_at DESC
                    LIMIT 50
                """
                cursor.execute(query_latency, (user_id,))
                charts["latency"] = cursor.fetchall()

                # Uptime History (simplified: status codes or up/down boolean)
                # ... similar logic
        finally:
            conn.close()

        return jsonify(charts), 200
    except Exception as e:
        print("Dashboard charts error:", e)
        return jsonify({"error": "Internal server error"}), 500


@dashboard_bp.route("/activity", methods=["GET"])
@login_required
def get_dashboard_activity():
    """
    Returns recent activity feed.
    """
    try:
        user_id = request.user_id
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        activities = []
        try:
            with conn.cursor() as cursor:
                query = """
                    SELECT * FROM activities 
                    WHERE user_id = %s OR project_id IN (
                        SELECT project_id FROM subscriptions WHERE user_id = %s
                    )
                    ORDER BY created_at DESC
                    LIMIT 10
                """
                cursor.execute(query, (user_id, user_id))
                activities = cursor.fetchall()
        finally:
            conn.close()
            
        return jsonify({"activities": activities}), 200

    except Exception as e:
        print("Dashboard activity error:", e)
        return jsonify({"error": "Internal server error"}), 500
