from flask import Blueprint, request, jsonify
from extensions.extensions import get_db_connection
import bcrypt
import jwt
import datetime
from datetime import timedelta
import uuid
import secrets

auth_bp = Blueprint("auth", __name__)

JWT_SECRET="watchupisthebest"

pending_otps = []

def _generate_otp(length=6):
    return ''.join(str(secrets.randbelow(10)) for _ in range(length))

def _find_otp_record(email=None, user_id=None):
    for rec in pending_otps:
        if (email and rec.get("email") == email) or (user_id and rec.get("user_id") == user_id):
            return rec
    return None

def _cleanup_expired_otps():
    now = datetime.datetime.utcnow()
    # remove expired
    pending_otps[:] = [rec for rec in pending_otps if rec.get("expires_at") and rec["expires_at"] > now]


@auth_bp.route("/", methods=["GET", "OPTIONS"])
def auth_root():
    return jsonify({"status": "Auth service running", "endpoints": ["/login", "/register"]}), 200

# -------------------- LOGIN -----------------------
@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")

        # ✅ Validate input
        if not email or not password:
            return jsonify({"error": "Missing required fields"}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()
        finally:
            conn.close()

        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        # ✅ Verify password
        # Database stores password_hash
        stored_hash = user.get("password_hash")
        if not stored_hash:
             # If for some reason password_hash is missing but user exists (should not happen with constraints)
             return jsonify({"error": "Invalid credentials"}), 401

        if not bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
            return jsonify({"error": "Invalid credentials"}), 401

        # ✅ Generate JWT token with new payload structure
        payload = {
            "id": user["id"],
            "email": user["email"],
            "username": user["name"], # map name to username in token
            "iat": datetime.datetime.utcnow(),
            "exp": datetime.datetime.utcnow() + timedelta(days=7)  # 7 day expiry
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

        # ✅ Remove sensitive info before sending user back
        user.pop("password_hash", None)
        # Ensure we return 'username' if frontend expects it, mapping from 'name'
        if "name" in user:
            user["username"] = user["name"]

        return jsonify({
            "user": user,
            "token": token
        }), 200

    except Exception as e:
        print("Login error:", e)
        return jsonify({"error": "Internal server error"}), 500


# -------------------- REGISTER --------------------
@auth_bp.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")

        # Validate input
        if not username or not email or not password:
            return jsonify({"error": "Missing required fields"}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                # Check if user exists. Check against 'name' or 'email'
                # Note: 'username' from input maps to 'name' in DB.
                cursor.execute(
                    "SELECT * FROM users WHERE email = %s OR name = %s",
                    (email, username)
                )
                existing = cursor.fetchone()

                if existing:
                    return jsonify({"error": "User already exists"}), 400

                # Hash password
                hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                user_id = str(uuid.uuid4())

                # Insert user (role_id = 3 for normal user, adjust as needed)
                # DB Columns: id, name, email, password_hash
                cursor.execute(
                    "INSERT INTO users (id, name, email, password_hash) VALUES (%s, %s, %s, %s)",
                    (user_id, username, email, hashed_password)
                )
                conn.commit()

                # Fetch created user (without password)
                cursor.execute(
                    "SELECT id, name, email, created_at FROM users WHERE id = %s",
                    (user_id,)
                )
                new_user = cursor.fetchone()

                # ✅ Generate JWT token for new user
                payload = {
                    "id": new_user["id"],
                    "email": new_user["email"],
                    "username": new_user["name"],
                    "iat": datetime.datetime.utcnow(),
                    "exp": datetime.datetime.utcnow() + timedelta(days=365)  # 1 year expiry
                }
                token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
                
                # Map name to username for frontend consistency
                if "name" in new_user:
                    new_user["username"] = new_user["name"]

        finally:
            conn.close()

        return jsonify({
            "user": new_user,
            "token": token
        }), 200

    except Exception as e:
        print("Registration error:", e)
        return jsonify({"error": "Internal server error"}), 500
