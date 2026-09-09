from flask import Blueprint, request, jsonify
from utils.flask_auth import auth_required

ai_bp = Blueprint("ai", __name__)

@ai_bp.route("/api/simulate-sensitivity", methods=["POST"])
@auth_required
def simulate_sensitivity():
    try:
        data = request.json
        sensitivity = float(data.get("sensitivity", 8.5))

        # Simulated base AI output (this should come from real model logic)
        base_score = 65.0

        def apply_sensitivity_local(score, s):
            if s <= 3:
                multiplier = 0.7
            elif s <= 6:
                multiplier = 0.9
            elif s <= 8.5:
                multiplier = 1.0
            else:
                multiplier = 1.2
            return min(round(score * multiplier, 2), 100)

        low_mode = apply_sensitivity_local(base_score, 3)
        current_mode = apply_sensitivity_local(base_score, sensitivity)

        if sensitivity <= 3:
            mode_label = "Lenient Mode"
        elif sensitivity <= 6:
            mode_label = "Balanced Mode"
        elif sensitivity <= 8.5:
            mode_label = "Standard Mode"
        else:
            mode_label = "Aggressive Mode"

        return jsonify({
            "status": "success",
            "base_score": base_score,
            "low_mode": low_mode,
            "current_mode": current_mode,
            "mode_label": mode_label
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
