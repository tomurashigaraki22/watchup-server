from extensions.extensions import get_db_connection, mail, app
from extensions.dbschemas import setup_database_schemas
from functions.auth import auth_bp
from functions.projects import projects_bp
from functions.dashboard import dashboard_bp

app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(projects_bp, url_prefix="/projects")
app.register_blueprint(dashboard_bp, url_prefix="/dashboard")


if __name__ == "__main__":
    setup_database_schemas()
    app.run(debug=True, host="0.0.0.0", port=2092, use_reloader=True)