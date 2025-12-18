from flask import Blueprint, request, jsonify, g
from extensions.extensions import get_db_connection
from functions.dashboard import login_required
import uuid
import pymysql
from datetime import datetime, timedelta

monitors_bp = Blueprint('monitors', __name__)

def format_time_ago(dt):
    if not dt:
        return "Never"
    now = datetime.now()
    diff = now - dt
    if diff.total_seconds() < 60:
        return "Just now"
    if diff.total_seconds() < 3600:
        return f"{int(diff.total_seconds() // 60)}m ago"
    if diff.total_seconds() < 86400:
        return f"{int(diff.total_seconds() // 3600)}h ago"
    return f"{diff.days}d ago"

@monitors_bp.route('/monitors', methods=['GET'])
@login_required
def get_monitors():
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # Get all monitors for projects the user is subscribed to
        cursor.execute("""
            SELECT m.id, m.name, m.url, m.project_id, m.type, m.check_interval
            FROM monitors m
            JOIN subscriptions s ON m.project_id = s.project_id
            WHERE s.user_id = %s AND m.is_active = TRUE
        """, (request.user_id,))
        monitors = cursor.fetchall()
        
        result = []
        for monitor in monitors:
            monitor_id = monitor['id']
            
            # Get latest check for status and last_check
            cursor.execute("""
                SELECT status, response_time_ms, checked_at
                FROM monitor_checks
                WHERE monitor_id = %s
                ORDER BY checked_at DESC
                LIMIT 1
            """, (monitor_id,))
            latest_check = cursor.fetchone()
            
            # Calculate uptime and average latency for last 24h
            yesterday = datetime.now() - timedelta(hours=24)
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_checks,
                    SUM(CASE WHEN status = 'up' OR status = '200' OR status_code >= 200 AND status_code < 300 THEN 1 ELSE 0 END) as up_checks,
                    AVG(response_time_ms) as avg_latency
                FROM monitor_checks
                WHERE monitor_id = %s AND checked_at >= %s
            """, (monitor_id, yesterday))
            stats = cursor.fetchone()
            
            # Determine status
            status = "down"
            last_check_time = "Never"
            latency_display = "-"
            
            if latest_check:
                last_check_time = format_time_ago(latest_check['checked_at'])
                
                # Logic for status:
                # If latest check failed (status != 'up' or code not 2xx) -> down
                # If latest check slow (> 500ms) -> degraded
                # Else -> operational
                
                # Note: 'status' column in monitor_checks might be 'up'/'down' or HTTP code. 
                # Assuming 'up' or '200' means good.
                check_status = str(latest_check.get('status', '')).lower()
                response_time = latest_check.get('response_time_ms', 0) or 0
                
                if check_status == 'up' or check_status == '200' or check_status == 'ok':
                    if response_time > 500:
                        status = "degraded"
                    else:
                        status = "operational"
                else:
                    status = "down"
            else:
                status = "operational" # Default for new monitors with no checks yet
            
            # Calculate uptime percentage
            uptime = "100%"
            if stats and stats['total_checks'] > 0:
                up_pct = (stats['up_checks'] / stats['total_checks']) * 100
                uptime = f"{up_pct:.1f}%"
            
            # Format latency
            if stats and stats['avg_latency'] is not None:
                latency_display = f"{int(stats['avg_latency'])}ms"
            elif latest_check and latest_check.get('response_time_ms'):
                 latency_display = f"{int(latest_check['response_time_ms'])}ms"

            # Get history for sparkline (last 12 checks)
            cursor.execute("""
                SELECT response_time_ms, status
                FROM monitor_checks
                WHERE monitor_id = %s
                ORDER BY checked_at DESC
                LIMIT 12
            """, (monitor_id,))
            history_rows = cursor.fetchall()
            history = []
            for h in history_rows:
                history.append({
                    'latency': h['response_time_ms'],
                    'status': h['status']
                })
            # Reverse to have oldest first for charts if needed, but usually newest first is fine for processing
            
            result.append({
                "id": monitor['id'],
                "name": monitor['name'],
                "url": monitor['url'],
                "status": status,
                "latency": latency_display,
                "lastCheck": last_check_time,
                "uptime": uptime,
                "history": history
            })
            
        return jsonify(result), 200
        
    except Exception as e:
        print(f"Error fetching monitors: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        conn.close()

@monitors_bp.route('/monitors', methods=['POST'])
@login_required
def create_monitor():
    data = request.get_json()
    name = data.get('name')
    url = data.get('url')
    project_id = data.get('projectId')
    monitor_type = data.get('type', 'http')
    check_interval = data.get('checkInterval', 60)
    
    if not name or not url or not project_id:
        return jsonify({"error": "Missing required fields"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify user is subscribed to project
        cursor.execute("""
            SELECT 1 FROM subscriptions 
            WHERE user_id = %s AND project_id = %s
        """, (request.user_id, project_id))
        if not cursor.fetchone():
            return jsonify({"error": "Unauthorized access to project"}), 403
            
        monitor_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO monitors (id, project_id, name, url, type, check_interval)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (monitor_id, project_id, name, url, monitor_type, check_interval))
        
        conn.commit()
        
        return jsonify({
            "message": "Monitor created successfully",
            "id": monitor_id,
            "name": name,
            "url": url,
            "status": "operational", # Default
            "latency": "-",
            "lastCheck": "Just now",
            "uptime": "100%"
        }), 201
        
    except Exception as e:
        print(f"Error creating monitor: {e}")
        conn.rollback()
        return jsonify({"error": "Internal server error"}), 500
    finally:
        conn.close()

@monitors_bp.route('/monitors/<monitor_id>', methods=['DELETE'])
@login_required
def delete_monitor(monitor_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify ownership (via project subscription)
        cursor.execute("""
            SELECT m.id 
            FROM monitors m
            JOIN subscriptions s ON m.project_id = s.project_id
            WHERE m.id = %s AND s.user_id = %s
        """, (monitor_id, request.user_id))
        
        if not cursor.fetchone():
            return jsonify({"error": "Monitor not found or unauthorized"}), 404
            
        # Delete related data first (FK constraints)
        cursor.execute("DELETE FROM alerts WHERE monitor_id = %s", (monitor_id,))
        cursor.execute("DELETE FROM monitor_checks WHERE monitor_id = %s", (monitor_id,))
        cursor.execute("DELETE FROM monitors WHERE id = %s", (monitor_id,))
        
        conn.commit()
        return jsonify({"message": "Monitor deleted successfully"}), 200
        
    except Exception as e:
        print(f"Error deleting monitor: {e}")
        conn.rollback()
        return jsonify({"error": "Internal server error"}), 500
    finally:
        conn.close()
