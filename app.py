"""
Campus Resource Intelligence & Sharing System (CRISS)
Main Application Entry Point.
"""

import os
from datetime import datetime
from flask import Flask, render_template, session
from config import Config
from routes.auth_routes import auth_bp, generate_csrf_token
from routes.catalog_routes import catalog_bp
from routes.student_routes import student_bp
from routes.admin_routes import admin_bp
from routes.api_routes import api_bp
from services.notification_service import NotificationService

class CSRFTokenHelper:
    def __call__(self):
        return generate_csrf_token()
    def __str__(self):
        return generate_csrf_token()

csrf_helper = CSRFTokenHelper()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Register Blueprints
    app.register_blueprint(catalog_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    # Template Context Processors
    @app.context_processor
    def inject_globals():
        user_id = session.get('user_id')
        unread_count = 0
        if user_id:
            try:
                unread_count = NotificationService.get_unread_count(user_id)
            except Exception:
                unread_count = 0

        return {
            "current_user": {
                "id": session.get('user_id'),
                "email": session.get('email'),
                "name": session.get('full_name'),
                "role": session.get('role'),
                "department": session.get('department_name')
            } if user_id else None,
            "csrf_token": generate_csrf_token(),
            "unread_notifications_count": unread_count,
            "now": datetime.now(),
            "year": datetime.now().year
        }

    # Custom Jinja Filters
    @app.template_filter('dt_format')
    def dt_format(value, format_str="%b %d, %Y %I:%M %p"):
        if not value:
            return "N/A"
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        return value.strftime(format_str)

    @app.template_filter('date_only')
    def date_only(value):
        if not value:
            return "N/A"
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        return value.strftime("%b %d, %Y")

    # Error Handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n========================================================")
    print(f"CRISS Platform Starting on http://127.0.0.1:{port}")
    print(f"Connected to MySQL on port {Config.MYSQL_PORT}")
    print(f"========================================================\n")
    app.run(host='127.0.0.1', port=port, debug=True)
