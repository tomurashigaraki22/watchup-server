from extensions.extensions import get_db_connection, mail, app
from extensions.dbschemas import setup_database_schemas
from functions.auth import auth_bp
from functions.projects import projects_bp
from functions.dashboard import dashboard_bp
from functions.alerts import alerts_bp
from functions.monitors import monitors_bp
from functions.events import events_bp
from functions.system import system_bp, v1_bp

app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(projects_bp, url_prefix="/projects")
app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
app.register_blueprint(alerts_bp, url_prefix="/alerts")
app.register_blueprint(monitors_bp, url_prefix="/") # Root or /monitors? Route defines /monitors, so prefix could be empty or /api
app.register_blueprint(events_bp, url_prefix="/events")
app.register_blueprint(system_bp, url_prefix="/system")
app.register_blueprint(v1_bp, url_prefix="/v1")




if __name__ == "__main__":
    setup_database_schemas()
    app.run(debug=True, host="0.0.0.0", port=2092, use_reloader=True)
