import os
import logging
from datetime import timedelta
from flask import Flask, render_template

from .extensions import csrf, login_manager
from database.connection import DatabaseConnection
from dotenv import load_dotenv
from .config import Config

load_dotenv()

def create_app() -> Flask:
    """
    Neural_Protocol Application Factory.
    Follows strict one-direction dependency: app -> routes -> services -> database.
    """
    app = Flask(__name__, 
                template_folder='../templates', 
                static_folder='../static')
    
    # --- Configuration ---
    app.config.from_object(Config)
    


    # --- Initialize Extensions ---
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # Initialize Database Connection Pool (safe for multi-worker)
    try:
        DatabaseConnection.initialize_pool(min_conn=2, max_conn=10)
    except Exception as e:
        app.logger.error(f"Failed to initialize database pool: {e}")

    # --- Register Blueprints (Internal Imports to Kill Circularity) ---
    from routes.auth_routes import auth_bp
    from routes.dashboard_routes import dashboard_bp
    from routes.task_routes import tasks_bp
    from routes.admin_routes import admin_bp
    from routes.analytics_routes import analytics_bp
    from routes.chatbot_routes import chatbot_bp
    from routes.common_routes import common_bp
    from routes.team_routes import team_bp
    from routes.export_routes import export_bp
    from routes.ai_routes import ai_bp
    from routes.feedback_routes import feedback_bp
    from routes.report_routes import report_bp
    from routes.config_routes import config_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tasks_bp, url_prefix='/tasks')
    app.register_blueprint(admin_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(common_bp)
    app.register_blueprint(team_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(config_bp)

    # --- Global Context & Handlers ---
    @app.route('/favicon.ico')
    def favicon():
        from flask import make_response, send_from_directory
        response = make_response(send_from_directory(os.path.join(app.root_path, '../static'), 'favicon.ico'))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response

    @login_manager.user_loader
    def load_user(user_id):
        from repository.users_repo import get_user_by_id
        from .models import User # Use models to avoid circularity
        user_data = get_user_by_id(user_id)
        if user_data:
            return User(user_data)
        return None

    @app.errorhandler(500)
    def internal_server_error(e):
        app.logger.error(f"Server Error: {e}", exc_info=True)
        return render_template('error.html', code=500), 500

    return app

