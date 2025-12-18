from extensions.extensions import get_db_connection
from flask import Blueprint, request, jsonify
import jwt
import uuid
from functools import wraps

projects_bp = Blueprint("projects", __name__)

JWT_SECRET = "watchupisthebest"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
        
        if not token:
            return jsonify({"error": "Token is missing"}), 401
        
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            request.user_id = payload["id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
            
        return f(*args, **kwargs)
    return decorated_function

# Get all projects related to a user (subscribed projects)
@projects_bp.route("/", methods=["GET"])
@login_required
def get_user_projects():
    try:
        user_id = request.user_id
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                # Select projects where user has a subscription
                query = """
                    SELECT p.* 
                    FROM projects p
                    JOIN subscriptions s ON p.id = s.project_id
                    WHERE s.user_id = %s
                """
                cursor.execute(query, (user_id,))
                projects = cursor.fetchall()
        finally:
            conn.close()

        return jsonify({"projects": projects}), 200

    except Exception as e:
        print("Get projects error:", e)
        return jsonify({"error": "Internal server error"}), 500

# Get details about a specific project
@projects_bp.route("/<project_id>", methods=["GET"])
@login_required
def get_project_details(project_id):
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
                project = cursor.fetchone()
                
                if not project:
                    return jsonify({"error": "Project not found"}), 404
                    
        finally:
            conn.close()

        return jsonify({"project": project}), 200

    except Exception as e:
        print("Get project details error:", e)
        return jsonify({"error": "Internal server error"}), 500

# Create a project
@projects_bp.route("/", methods=["POST"])
@login_required
def create_project():
    try:
        data = request.get_json()
        name = data.get("name")
        description = data.get("description", "")
        
        if not name:
            return jsonify({"error": "Project name is required"}), 400
            
        user_id = request.user_id
        project_id = str(uuid.uuid4())
        
        # Include project id in description as requested
        description = f"{description} [Project ID: {project_id}]"
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                # 1. Create Project
                cursor.execute(
                    "INSERT INTO projects (id, name, description) VALUES (%s, %s, %s)",
                    (project_id, name, description)
                )
                
                # 2. Subscribe User to Project
                subscription_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO subscriptions (id, user_id, project_id) 
                    VALUES (%s, %s, %s)
                    """,
                    (subscription_id, user_id, project_id)
                )
                
                conn.commit()
                
                # Fetch created project
                cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
                new_project = cursor.fetchone()
                
        finally:
            conn.close()

        return jsonify({"project": new_project, "message": "Project created and subscribed successfully"}), 201

    except Exception as e:
        print("Create project error:", e)
        return jsonify({"error": "Internal server error"}), 500
