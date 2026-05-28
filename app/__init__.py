from flask import Flask
import json
from config.settings import FLASK_SECRET_KEY

def create_app():
    app = Flask(__name__, template_folder="templates")
    app.secret_key = FLASK_SECRET_KEY or "clinical-ai-secret-key-12345"
    
    # Custom Jinja filters
    app.jinja_env.filters["fromjson"] = json.loads

    # Register Route Blueprints
    from app.routes.summarizer import summarizer_bp
    from app.routes.patients import patients_bp
    from app.routes.search import search_bp
    from app.routes.csv_ingest import csv_ingest_bp
    from app.routes.copilot import copilot_bp

    app.register_blueprint(summarizer_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(csv_ingest_bp)
    app.register_blueprint(copilot_bp)

    return app
