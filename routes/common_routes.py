from flask import Blueprint, request, jsonify, current_app, render_template, session, redirect, url_for
from app.extensions import csrf
from repository.db import get_db_connection
from repository.users_repo import get_user_by_id
from services.upload_service import upload_file
from utils.flask_auth import auth_required
from repository.tasks_repo import get_all_tasks
from repository.delays_repo import get_delays_all
from services.analytics_service import get_ai_intelligence

common_bp = Blueprint('common', __name__)

@common_bp.route('/health')
def health():
    """Health check endpoint for production monitoring"""
    db_status = "disconnected"
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                 cursor.execute("SELECT 1")
                 db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return jsonify({
        "status": "ok",
        "db": db_status,
        "ai": "configured"
    }), 200

@common_bp.route("/upload", methods=["POST"])
@auth_required
@csrf.exempt
def upload():
    """Generic file upload endpoint."""
    file = request.files.get("file") or request.files.get("avatar")
    if not file:
        return jsonify({'error': 'No file part'}), 400
        
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    try:
        result = upload_file(file, folder="avatars")
        if result.get('success'):
            user_id = session.get('user_id')
            if user_id:
                try:
                    from repository.users_repo import update_user_profile
                    update_user_profile(user_id, profile_pic=result['path'])
                    session['profile_pic'] = result['path']
                except Exception as avatar_err:
                    current_app.logger.warning(f"Failed to update profile pic DB record: {avatar_err}")
            return jsonify({
                "success": True,
                "url": result.get('url') or result.get('path'),
                "path": result.get('path'),
                "message": "Profile photo updated successfully!"
            })
        else:
            return jsonify({"error": result.get('error', 'Upload failed')}), 400
    except Exception as e:
        current_app.logger.error(f"Upload error: {e}", exc_info=True)
        return jsonify({"error": "Unable to upload photo. Please select an image under 5 MB."}), 500

@common_bp.route('/search')
@auth_required
def universal_search():
    """Universal search across tasks, delays, and users with logging and semantic expansion"""
    query = request.args.get('q', '').strip()
    request.args.get('date_from')
    request.args.get('date_to')
    user_id = session.get('user_id')
    
    # --- 1. Log the Search ---
    if query:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO search_logs (user_id, query) VALUES (%s, %s)",
                        (user_id, query)
                    )
                conn.commit()
        except Exception as e:
            current_app.logger.error(f"Failed to log search: {e}")

    expanded_terms = [query.lower()]
    # Removed Semantic Expansion (Mock AI) to comply with No-Mock policy.
            
    # --- 3. Execute Search ---
    try:
        # Search Tasks
        all_tasks = get_all_tasks()
        matched_tasks = []
        for t in all_tasks:
            # Check string overlap with any expanded term
            text_corpus = f"{t.get('title')} {t.get('description')} {t.get('priority')} {t.get('status')}".lower()
            if any(term in text_corpus for term in expanded_terms):
                matched_tasks.append(t)

        # Search Delays
        all_delays = get_delays_all()
        matched_delays = []
        for d in all_delays:
            text_corpus = f"{d.get('reason_text')} {d.get('task_title')} {d.get('risk_level')}".lower()
            if any(term in text_corpus for term in expanded_terms):
                matched_delays.append(d)
                
        # Search Users (Admin/Manager only typically, but open for global search demo)
        from repository.users_repo import get_all_users
        all_users = get_all_users()
        matched_users = [
            u for u in all_users
            if query.lower() in (u.get('full_name') or '').lower() or 
               query.lower() in (u.get('email') or '').lower()
        ]

        # --- 4. Get Trending & Recent Searches (for Empty State) ---
        trending = []
        recent_searches = []
        if not query:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Get most common recent queries (Global)
                    cur.execute("""
                        SELECT query, COUNT(*) as count 
                        FROM search_logs 
                        WHERE timestamp > NOW() - INTERVAL '7 days' 
                        GROUP BY query 
                        ORDER BY count DESC 
                        LIMIT 5
                    """)
                    trending = [row['query'] for row in cur.fetchall()]

                    # Get user's recent searches (Personal)
                    if user_id:
                        cur.execute("""
                            SELECT query, MAX(timestamp) as last_used
                            FROM search_logs 
                            WHERE user_id = %s 
                            GROUP BY query
                            ORDER BY last_used DESC 
                            LIMIT 5
                        """, (user_id,))
                        recent_searches = [row['query'] for row in cur.fetchall()]

        return render_template('search.html', 
                             query=query, 
                             tasks=matched_tasks, 
                             delays=matched_delays,
                             users=matched_users,
                             trending=trending,
                             recent_searches=recent_searches)
                             
    except Exception as e:
        current_app.logger.error(f"Search error: {e}")
        return render_template('search.html', query=query, tasks=[], delays=[], users=[], error=str(e))

@common_bp.route('/')
def index():
    """Landing page"""
    if 'user_id' in session:
        return redirect(url_for('dashboard.dashboard'))
    return render_template('landing.html')

@common_bp.route('/profile')
@auth_required
def profile():
    """User profile page"""
    user_name = session.get('user_name', 'Unknown User')
    email = session.get('email', 'Not available')
    role = session.get('user_role', 'employee')
    user_id = session.get('user_id')

    task_count = 0
    baseline = {'avg_auth': 0, 'std_auth': 0, 'avg_avoid': 0, 'std_avoid': 0, 'count': 0}
    momentum = {'risk_drift': None, 'escalation_velocity': 'unknown',
                'recent_scores': [], 'burst_count_14d': 0, 'momentum_dir': 'neutral'}
    integrity = {}
    st_baseline = {}
    behavioral_state = {}

    if user_id:
        try:
            from repository.tasks_repo import count_user_tasks
            task_count = count_user_tasks(user_id)
        except Exception as e:
            current_app.logger.error(f"Error fetching task count for profile: {e}")
        try:
            from services.user_service import (
                get_user_baseline, 
                get_user_momentum, 
                get_user_integrity_stats,
                get_user_short_term_baseline,
                compute_behavioral_state
            )
            from services.risk_service import check_risk_escalation
            baseline = get_user_baseline(user_id)
            momentum = get_user_momentum(user_id)
            integrity = get_user_integrity_stats(user_id)
            escalation_level, escalation_msg = check_risk_escalation(user_id)
            momentum['escalation_level'] = escalation_level
            momentum['escalation_msg'] = escalation_msg
            
            # Tier 4: Predictive Intelligence
            st_baseline = get_user_short_term_baseline(user_id)
            behavioral_state = compute_behavioral_state(user_id)
        except Exception as e:
            current_app.logger.warning(f"Could not load baseline/momentum/integrity for profile: {e}")
            integrity = {}
            st_baseline = {}
            behavioral_state = {}



    user = get_user_by_id(user_id) if user_id else None
    ai_data = get_ai_intelligence(user_id, role) if user_id else {}

    return render_template('profile.html',
                         user_name=user_name,
                         email=email,
                         role=role,
                         user=user,
                         ai_data=ai_data,
                         task_count=task_count,
                         baseline=baseline,
                         momentum=momentum,
                         integrity=integrity,
                         st_baseline=st_baseline,
                         behavioral_state=behavioral_state)







@common_bp.route('/settings')
@auth_required
def settings():
    """Application settings page"""
    from repository.users_repo import get_user_by_id
    user_id = session.get('user_id')
    user = get_user_by_id(user_id)
    
    # Defaults handled by DB schema but ensured here for template
    neural_config = {
        'notifications': user.get('neural_notifications', True) if user else True,
        'auto_analysis': user.get('neural_auto_analysis', True) if user else True,
        'temperature': user.get('neural_temperature', 0.7) if user else 0.7
    }
    
    return render_template('settings.html', neural_config=neural_config)

@common_bp.route('/settings/neural', methods=['POST'])
@auth_required
def update_neural_settings():
    """Handle neural interface settings via AJAX"""
    user_id = session.get('user_id')
    data = request.get_json()

    if not data:
        return jsonify(success=False, error="No data provided"), 400

    try:
        # Write to the physical table (admins / managers / employees) directly.
        # The unified `users` VIEW is UNION ALL and cannot be updated directly.
        from repository.users_repo import update_user_profile
        update_user_profile(
            user_id,
            neural_notifications=data.get('notifications', True),
            neural_auto_analysis=data.get('auto_analysis', True),
            neural_temperature=data.get('temperature', 0.7),
        )
        return jsonify(success=True)
    except Exception as e:
        current_app.logger.error("Error updating neural settings user_id=%s: %s", user_id, e)
        return jsonify(success=False, error=str(e)), 500


@common_bp.route('/settings/update', methods=['POST'])
@auth_required
def update_settings():
    """Handle settings form submission"""
    from repository.users_repo import update_user_profile
    from flask import flash, redirect, url_for

    full_name = request.form.get('full_name')
    email = request.form.get('email')
    user_id = session.get('user_id')

    try:
        update_user_profile(user_id, full_name, email)
        
        # Update session
        session['user_name'] = full_name
        session['email'] = email
        
        flash('Profile updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating profile: {str(e)}', 'error')

    return redirect(url_for('common.settings'))

@common_bp.route('/settings/change-password', methods=['POST'])
@auth_required
def settings_change_password():
    """Handle password change from settings page"""
    from repository.users_repo import get_user_by_id, update_password_hash
    from flask import flash, redirect, url_for
    from utils.hashing import verify_password, hash_password

    user_id = session.get('user_id')
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not current_password or not new_password or not confirm_password:
        flash('All password fields are required.', 'error')
        return redirect(url_for('common.settings'))

    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('common.settings'))

    if len(new_password) < 8:
        flash('New password must be at least 8 characters.', 'error')
        return redirect(url_for('common.settings'))

    try:
        user = get_user_by_id(user_id)
        if not user or not verify_password(current_password, user['password_hash']):
            flash('Incorrect current password.', 'error')
            return redirect(url_for('common.settings'))

        update_password_hash(user_id, hash_password(new_password))
        flash('Password changed successfully!', 'success')
    except Exception as e:
        current_app.logger.error("Settings password change error user_id=%s: %s", user_id, e)
        flash('An error occurred while changing your password.', 'error')

    return redirect(url_for('common.settings'))

@common_bp.route('/settings/delete-account', methods=['POST'])
@auth_required
def settings_delete_account():
    """Handle account deletion (soft delete)"""
    from repository.users_repo import soft_delete_user

    user_id = session.get('user_id')

    try:
        soft_delete_user(user_id)
        session.clear()
        flash('Your account has been deactivated.', 'info')
        return redirect(url_for('auth.login'))
    except Exception as e:
        current_app.logger.error("Settings delete account error user_id=%s: %s", user_id, e)
        flash('Error deleting account. Please try again.', 'error')
        return redirect(url_for('common.settings'))


@common_bp.route('/api/user/estimation-bias')
@auth_required
def get_user_bias():
    """Return the user's historical estimation bias."""
    user_id = session.get('user_id')
    try:
        from services.risk_service import calculate_estimation_bias
        bias = calculate_estimation_bias(user_id)
        return jsonify(bias=bias)
    except Exception as e:
        current_app.logger.error(f"Error fetching estimation bias: {e}")
        return jsonify(bias=1.0)

@common_bp.route('/settings/logs')
@auth_required
def settings_logs():
    """Return the last 50 activity log entries for the current user as JSON."""
    user_id = session.get('user_id')
    logs = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT action, details, created_at
                    FROM activity_logs
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 50
                """, (user_id,))
                rows = cur.fetchall()
                for row in rows:
                    ts = row['created_at']
                    logs.append({
                        'ts': ts.strftime('%Y-%m-%d %H:%M:%S') if ts else '',
                        'action': row.get('action', ''),
                        'details': row.get('details', ''),
                    })
    except Exception as e:
        current_app.logger.error("settings_logs error user_id=%s: %s", user_id, e)
        return jsonify(error=str(e)), 500

    return jsonify(logs=logs)
