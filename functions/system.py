from flask import Blueprint, request, jsonify
from extensions.extensions import get_db_connection
from functions.projects import login_required
import uuid
import datetime
import time
from functools import wraps

system_bp = Blueprint("system", __name__)
v1_bp = Blueprint("v1", __name__)

_rate_state = {}


def _rate_limit(project_id, limit, window_seconds):
    now = time.time()
    window = int(now // window_seconds)
    key = (project_id, window_seconds, window)
    current = _rate_state.get(key, 0) + 1
    _rate_state[key] = current
    if current > limit:
        return False
    return True


def sdk_auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        project_id = request.headers.get("x-project-id")
        api_key = request.headers.get("x-api-key")

        if not project_id or not api_key:
            return jsonify({"error": "Missing X-Watchup-Project or X-Watchup-Key"}), 401

        if not _rate_limit(project_id, limit=120, window_seconds=60):
            return jsonify({"error": "Rate limit exceeded"}), 429

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT ak.user_id
                    FROM api_keys ak
                    WHERE ak.api_key = %s
                    LIMIT 1
                    """,
                    (api_key,),
                )
                ak_row = cursor.fetchone()

                if not ak_row:
                    return jsonify({"error": "Invalid credentials"}), 401

                user_id = ak_row["user_id"]

                cursor.execute(
                    """
                    SELECT s.expires_at, s.is_active
                    FROM subscriptions s
                    WHERE s.user_id = %s AND s.project_id = %s
                    LIMIT 1
                    """,
                    (user_id, project_id),
                )
                sub_row = cursor.fetchone()

                if not sub_row or not bool(sub_row.get("is_active", True)):
                    return jsonify({"error": "Project access denied"}), 403

                expires_at = sub_row.get("expires_at")
                now_dt = datetime.datetime.now()
                is_paid = bool(expires_at and expires_at > now_dt)
                request.sdk_user_id = user_id
                request.sdk_project_id = project_id
                request.sdk_is_free = not is_paid
        finally:
            conn.close()

        return f(*args, **kwargs)

    return decorated


@system_bp.route("/api-key", methods=["GET"])
@login_required
def get_api_key():
    try:
        user_id = request.user_id
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT api_key, created_at, updated_at FROM api_keys WHERE user_id = %s",
                    (user_id,),
                )
                row = cursor.fetchone()
        finally:
            conn.close()

        if not row:
            return jsonify({"api_key": None}), 200

        return (
            jsonify(
                {
                    "api_key": row["api_key"],
                    "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                    "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
                }
            ),
            200,
        )
    except Exception as e:
        print("Get api key error:", e)
        return jsonify({"error": "Internal server error"}), 500


@system_bp.route("/api-key", methods=["POST"])
@login_required
def create_or_regenerate_api_key():
    try:
        user_id = request.user_id
        new_key = str(uuid.uuid4())

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT api_key FROM api_keys WHERE user_id = %s", (user_id,))
                existing = cursor.fetchone()

                if existing:
                    cursor.execute(
                        "UPDATE api_keys SET api_key = %s WHERE user_id = %s",
                        (new_key, user_id),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO api_keys (user_id, api_key) VALUES (%s, %s)",
                        (user_id, new_key),
                    )
            conn.commit()
        finally:
            conn.close()

        return jsonify({"api_key": new_key}), 200
    except Exception as e:
        print("Create/regenerate api key error:", e)
        return jsonify({"error": "Internal server error"}), 500


@system_bp.route("/sdk/auth", methods=["POST"])
def sdk_auth():
    try:
        data = request.get_json(silent=True) or {}
        project_id = data.get("projectId")
        api_key = data.get("apiKey")

        if not project_id or not api_key:
            return jsonify({"ok": False, "error": "Missing projectId or apiKey"}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"ok": False, "error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        ak.user_id,
                        s.expires_at,
                        s.is_active
                    FROM api_keys ak
                    JOIN subscriptions s ON s.user_id = ak.user_id
                    WHERE ak.api_key = %s AND s.project_id = %s
                    LIMIT 1
                    """,
                    (api_key, project_id),
                )
                row = cursor.fetchone()
        finally:
            conn.close()

        if not row:
            return jsonify({"ok": False, "error": "Invalid credentials"}), 401

        is_active = bool(row.get("is_active", True))
        expires_at = row.get("expires_at")
        now = datetime.datetime.now()

        is_paid = bool(expires_at and expires_at > now)
        is_free = not is_paid

        if not is_active:
            return jsonify({"ok": False, "error": "Subscription inactive"}), 403

        return (
            jsonify(
                {
                    "ok": True,
                    "userId": row["user_id"],
                    "projectId": project_id,
                    "isFree": is_free,
                    "plan": "free" if is_free else "paid",
                }
            ),
            200,
        )
    except Exception as e:
        print("SDK auth error:", e)
        return jsonify({"ok": False, "error": "Internal server error"}), 500


@v1_bp.route("/monitors", methods=["POST"])
@sdk_auth_required
def v1_create_monitor():
    try:
        data = request.get_json(silent=True) or {}
        url = (data.get("url") or "").strip()
        name = (data.get("name") or "").strip() or None
        interval_seconds = int(data.get("intervalSeconds", 60))
        timeout_ms = int(data.get("timeoutMs", 5000))

        if not url:
            return jsonify({"error": "Missing url"}), 400

        if interval_seconds < 30:
            interval_seconds = 30
        if interval_seconds > 3600:
            interval_seconds = 3600

        if timeout_ms < 1000:
            timeout_ms = 1000
        if timeout_ms > 30000:
            timeout_ms = 30000

        monitor_id = str(uuid.uuid4())
        project_id = request.sdk_project_id

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM uptime_monitors
                    WHERE project_id = %s AND url = %s AND deleted_at IS NULL
                    LIMIT 1
                    """,
                    (project_id, url),
                )
                existing = cursor.fetchone()
                if existing:
                    return jsonify({"id": existing["id"], "url": url, "projectId": project_id}), 200

                cursor.execute(
                    """
                    INSERT INTO uptime_monitors (
                        id, project_id, name, url, interval_seconds, timeout_ms, next_check_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (monitor_id, project_id, name, url, interval_seconds, timeout_ms),
                )
            conn.commit()
        finally:
            conn.close()

        return (
            jsonify(
                {
                    "id": monitor_id,
                    "projectId": project_id,
                    "url": url,
                    "name": name,
                    "intervalSeconds": interval_seconds,
                    "timeoutMs": timeout_ms,
                }
            ),
            201,
        )
    except Exception as e:
        print("Create monitor error:", e)
        return jsonify({"error": "Internal server error"}), 500


@v1_bp.route("/monitors", methods=["GET"])
@sdk_auth_required
def v1_list_monitors():
    try:
        project_id = request.sdk_project_id
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        project_id,
                        name,
                        url,
                        interval_seconds,
                        timeout_ms,
                        status,
                        consecutive_failures,
                        last_checked_at,
                        created_at,
                        updated_at
                    FROM uptime_monitors
                    WHERE project_id = %s AND deleted_at IS NULL
                    ORDER BY created_at DESC
                    """,
                    (project_id,),
                )
                rows = cursor.fetchall()
        finally:
            conn.close()

        for r in rows:
            if r.get("last_checked_at"):
                r["last_checked_at"] = r["last_checked_at"].isoformat()
            if r.get("created_at"):
                r["created_at"] = r["created_at"].isoformat()
            if r.get("updated_at"):
                r["updated_at"] = r["updated_at"].isoformat()

        return jsonify({"projectId": project_id, "monitors": rows}), 200
    except Exception as e:
        print("List monitors error:", e)
        return jsonify({"error": "Internal server error"}), 500


@v1_bp.route("/monitors/<monitor_id>", methods=["DELETE"])
@sdk_auth_required
def v1_delete_monitor(monitor_id):
    try:
        project_id = request.sdk_project_id
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE uptime_monitors
                    SET deleted_at = NOW(), is_active = FALSE
                    WHERE id = %s AND project_id = %s AND deleted_at IS NULL
                    """,
                    (monitor_id, project_id),
                )
                affected = cursor.rowcount
            conn.commit()
        finally:
            conn.close()

        if not affected:
            return jsonify({"error": "Monitor not found"}), 404

        return jsonify({"ok": True}), 200
    except Exception as e:
        print("Delete monitor error:", e)
        return jsonify({"error": "Internal server error"}), 500
