from flask import Blueprint, request, jsonify, session
from utils.flask_auth import auth_required
from repository.db import execute_query
import logging

feedback_bp = Blueprint('feedback', __name__)
logger = logging.getLogger(__name__)

@feedback_bp.route('/submit-app-rating', methods=['POST'])
@auth_required
def submit_app_rating():
    """Submit a 1-5 star rating for the application."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "No JSON payload provided."}), 400

    rating = data.get('rating')
    comment = data.get('comment', '')
    user_id = session.get('user_id')

    if rating is None or not isinstance(rating, int) or not (1 <= rating <= 5):
        return jsonify({"success": False, "message": "Invalid rating. Must be an integer between 1 and 5."}), 400

    try:
        query = "INSERT INTO feedback (user_id, rating, comment) VALUES (%s, %s, %s)"
        execute_query(query, (user_id, rating, comment))
        return jsonify({"success": True, "message": "Thank you for your feedback!"})
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        return jsonify({"success": False, "message": "Could not save feedback. Please try again."}), 500
