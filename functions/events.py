from flask import Blueprint, request, jsonify, g
from extensions.extensions import get_db_connection
from functions.dashboard import login_required
import uuid
import pymysql
from datetime import datetime

events_bp = Blueprint('events', __name__)

def format_time_ago(dt):
    if not dt:
        return "Never"
    now = datetime.now()
    diff = now - dt
    if diff.total_seconds() < 60:
        return f"{int(diff.total_seconds())}s ago"
    if diff.total_seconds() < 3600:
        return f"{int(diff.total_seconds() // 60)}m ago"
    if diff.total_seconds() < 86400:
        return f"{int(diff.total_seconds() // 3600)}h ago"
    return f"{diff.days}d ago"

@events_bp.route('/', methods=['GET'])
@login_required
def get_events():
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # Get query parameters
        search_query = request.args.get('q', '').lower()
        filter_type = request.args.get('type')
        limit = int(request.args.get('limit', 50))
        
        # Base query joining subscriptions to ensure user access
        sql = """
            SELECT e.id, e.type, e.message, e.source, e.created_at, e.project_id
            FROM events e
            JOIN subscriptions s ON e.project_id = s.project_id
            WHERE s.user_id = %s
        """
        params = [request.user_id]
        
        # Apply filters
        if search_query:
            sql += " AND (LOWER(e.message) LIKE %s OR LOWER(e.source) LIKE %s)"
            params.extend([f"%{search_query}%", f"%{search_query}%"])
            
        if filter_type:
            sql += " AND e.type = %s"
            params.append(filter_type)
            
        # Sorting and Limit
        sql += " ORDER BY e.created_at DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(sql, tuple(params))
        events_data = cursor.fetchall()
        
        # Format response
        result = []
        for event in events_data:
            result.append({
                "id": event['id'],
                "type": event['type'],
                "message": event['message'],
                "source": event['source'],
                "time": format_time_ago(event['created_at']),
                "projectId": event['project_id']
            })
            
        return jsonify(result), 200
        
    except Exception as e:
        print(f"Error fetching events: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        conn.close()

@events_bp.route('/', methods=['POST'])
@login_required
def create_event():
    # This endpoint is primarily for system usage or testing, 
    # normally events are created by internal services.
    data = request.get_json()
    project_id = data.get('projectId')
    event_type = data.get('type') # info, success, error, warning
    message = data.get('message')
    source = data.get('source')
    
    if not all([project_id, event_type, message, source]):
        return jsonify({"error": "Missing required fields"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check authorization
        cursor.execute("""
            SELECT 1 FROM subscriptions WHERE user_id = %s AND project_id = %s
        """, (request.user_id, project_id))
        
        if not cursor.fetchone():
            return jsonify({"error": "Unauthorized"}), 403
            
        event_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO events (id, project_id, type, message, source)
            VALUES (%s, %s, %s, %s, %s)
        """, (event_id, project_id, event_type, message, source))
        
        conn.commit()
        return jsonify({"message": "Event created", "id": event_id}), 201
        
    except Exception as e:
        print(f"Error creating event: {e}")
        conn.rollback()
        return jsonify({"error": "Internal server error"}), 500
    finally:
        conn.close()
