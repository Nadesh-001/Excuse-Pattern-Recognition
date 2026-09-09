from flask import Blueprint, request, jsonify
from repository.db import execute_query
from utils.flask_auth import admin_required

config_bp = Blueprint("config", __name__)

@config_bp.route("/api/system-config", methods=["GET"])
@admin_required
def get_config():
    try:
        query = "SELECT * FROM system_config WHERE id = 1"
        result = execute_query(query, fetch=True)
        if result:
            return jsonify(result[0])
        else:
            return jsonify({"error": "Configuration not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@config_bp.route("/api/system-config", methods=["POST"])
@admin_required
def update_config():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validation
        try:
            ns = float(data.get("neural_sensitivity", 8.5))
            if not (0 <= ns <= 10):
                return jsonify({"error": "Neural sensitivity must be between 0-10"}), 400

            ct = int(data.get("ai_confidence", 10))
            if not (0 <= ct <= 100):
                return jsonify({"error": "AI confidence must be 0-100"}), 400
        except ValueError:
            return jsonify({"error": "Invalid numeric values"}), 400

        update_query = """
        UPDATE system_config
        SET neural_sensitivity = %s,
            ai_confidence = %s,
            detection_window = %s,
            risk_threshold = %s,
            max_load_time = %s,
            backup_freq = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
        """

        execute_query(update_query, (
            ns,
            ct,
            int(data.get("detection_window", 14)),
            int(data.get("risk_threshold", 3)),
            int(data.get("max_load_time", 200)),
            data.get("backup_freq", "EVERY 6H")
        ), fetch=False)

        return jsonify({"message": "Configuration updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
