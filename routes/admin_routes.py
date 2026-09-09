from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from utils.flask_auth import admin_required, main_admin_required
from utils.permissions import can_manage_user
from services.user_service import get_users_list, manage_create_user, manage_update_user
from repository.users_repo import soft_delete_user, get_active_user_list, get_user_by_id, count_admins, count_main_admins
from repository.logs_repo import get_recent_logs
from repository.tasks_repo import get_all_tasks
from repository.db import test_connection
from services.activity_service import log_activity
from services.audit_service import log_action, AuditActions

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
@admin_required
def admin_panel():
    user_id = session.get('user_id')
    users = get_users_list(user_id)
    
    # Filter for active only for the primary display
    active_users = [u for u in users if u.get('active_status', True)]

    # Real Audit Logs
    logs = get_recent_logs(limit=50)

    # Real Active Users (Active in last 15 mins)
    currently_active = get_active_user_list(minutes=15)

    # Dynamic Diagnostics from real DB connection test
    import sys
    import platform
    try:
        db_result = test_connection()
    except Exception:
        db_result = {'database': {'status': False, 'message': 'Connection test failed'}, 'system': {}}

    diagnostics = {
        "database": db_result.get('database', {}),
        "system": db_result.get('system', {}) or {
            'Python Version': sys.version,
            'OS': f"{platform.system()} {platform.release()}"
        },
        "config": session.get('system_config', {
            "ai_confidence": 10,
            "detection_window": 14,
            "risk_threshold": 3,
            "max_load_time": 200,
            "neural_sensitivity": 8.5,
            "backup_freq": "EVERY 6H"
        })
    }

    tasks = get_all_tasks()
    actor_role = session.get('user_role', '')

    return render_template(
        'admin.html',
        users=active_users,
        logs=logs,
        diagnostics=diagnostics,
        tasks=tasks,
        currently_active=currently_active,
        actor_role=actor_role,
    )

@admin_bp.route('/admin/system/config', methods=['POST'])
@admin_required
def admin_system_config():
    try:
        # Save to session to simulate persistence
        new_config = {
            "ai_confidence": int(request.form.get('ai_confidence', 10)),
            "detection_window": int(request.form.get('detection_window', 14)),
            "risk_threshold": int(request.form.get('risk_threshold', 3)),
            "max_load_time": int(request.form.get('max_load_time', 200)),
            "neural_sensitivity": float(request.form.get('neural_sensitivity', 8.5)),
            "backup_freq": request.form.get('backup_freq', "EVERY 6H")
        }
        session['system_config'] = new_config
        # Persist to DB
        from repository.db import execute_query
        try:
            execute_query("""
                UPDATE system_config
                SET neural_sensitivity = %s,
                    ai_confidence = %s,
                    detection_window = %s,
                    risk_threshold = %s,
                    max_load_time = %s,
                    backup_freq = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (
                new_config['neural_sensitivity'],
                new_config['ai_confidence'],
                new_config['detection_window'],
                new_config['risk_threshold'],
                new_config['max_load_time'],
                new_config['backup_freq'],
            ), fetch=False)
        except Exception as db_err:
            current_app.logger.warning("Failed to persist system config to DB: %s", db_err)
        
        log_activity(session.get('user_id'), "SYSTEM_CONFIG", "Updated system configuration")
        return jsonify({"status": "success", "message": "Configuration saved successfully"}), 200
    except Exception as e:
        current_app.logger.error(f"Config save error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route('/admin/users/add', methods=['POST'])
@admin_required
def admin_add_user():
    try:
        actor_id    = session.get('user_id')
        full_name   = request.form.get('name')
        email       = request.form.get('email')
        password    = request.form.get('password')
        role        = request.form.get('role', 'employee')
        
        success, message = manage_create_user(actor_id, full_name, email, password, role)
        
        if success:
            log_activity(actor_id, "USER_CREATE", f"Created user: {email}")
            flash(message, "success")
        else:
            flash(message, "error")
            
    except Exception as e:
        flash("Error creating user. Please check logs.", "error")
        current_app.logger.error(f"Admin add user error: {e}")
    
    return redirect(url_for('admin.admin_panel'))


@admin_bp.route('/admin/users/<int:user_id>/delete', methods=['POST', 'DELETE'])
@admin_bp.route('/api/users/<int:user_id>', methods=['DELETE', 'POST'])
@admin_required
def admin_delete_user(user_id):
    is_json = request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    try:
        actor_id   = session.get('user_id')
        actor_role = session.get('user_role', 'employee')

        # Block self-deactivation
        if actor_id == user_id:
            msg = "You cannot deactivate your own account from the Admin Panel."
            if is_json:
                return jsonify({"status": "error", "error": msg}), 400
            flash(msg, "error")
            return redirect(url_for('admin.admin_panel'))

        target = get_user_by_id(user_id)
        if not target:
            msg = "User not found."
            if is_json:
                return jsonify({"status": "error", "error": msg}), 404
            flash(msg, "error")
            return redirect(url_for('admin.admin_panel'))

        target_role = target.get('role', 'employee')

        # Use centralised can_manage_user (self-guard + role hierarchy)
        if not can_manage_user(actor_role, target_role, actor_id, user_id):
            msg = "You do not have permission to deactivate this user."
            if is_json:
                return jsonify({"status": "error", "error": msg}), 403
            flash(msg, "error")
            return redirect(url_for('admin.admin_panel'))

        # Last-main-admin guard
        if target_role == 'main_admin' and count_main_admins() <= 1:
            msg = "Cannot deactivate the last Main Admin account."
            if is_json:
                return jsonify({"status": "error", "error": msg}), 400
            flash(msg, "error")
            return redirect(url_for('admin.admin_panel'))

        soft_delete_user(user_id)
        log_activity(actor_id, "USER_DEACTIVATE", f"Deactivated user ID: {user_id} (role: {target_role})")
        log_action("USER_DEACTIVATED", f"Actor {actor_id} deactivated user {user_id} ({target_role})", target_user_id=user_id)

        if is_json:
            return jsonify({"status": "success", "message": "User deactivated successfully!"}), 200

        flash("User deactivated successfully!", "success")
    except Exception as e:
        current_app.logger.error(f"Admin delete user error: {e}", exc_info=True)
        if is_json:
            return jsonify({"status": "error", "error": str(e)}), 500
        flash(f"Error deactivating user: {str(e)}", "error")

    return redirect(url_for('admin.admin_panel'))


@admin_bp.route('/admin/users/edit', methods=['POST'])
@admin_required
def admin_edit_user():
    try:
        actor_id       = session.get('user_id')
        actor_role     = session.get('user_role', 'employee')
        target_user_id_raw = request.form.get('user_id')
        if not target_user_id_raw:
            flash("Missing user ID.", "error")
            return redirect(url_for('admin.admin_panel'))
        target_user_id = int(target_user_id_raw)
        full_name      = request.form.get('name', '').strip()
        email          = request.form.get('email', '').strip()
        role           = request.form.get('role')
        active_status  = request.form.get('active_status', 'true').lower() == 'true'

        target = get_user_by_id(target_user_id)
        target_role = target.get('role', 'employee') if target else 'employee'

        # Use centralised can_manage_user
        if not can_manage_user(actor_role, target_role, actor_id, target_user_id):
            flash("You do not have permission to edit this user.", "error")
            return redirect(url_for('admin.admin_panel'))

        success, message = manage_update_user(
            actor_id, target_user_id, full_name, email, role, active_status
        )

        if success:
            log_activity(actor_id, "USER_UPDATE", f"Updated user ID: {target_user_id}")
            log_action("USER_UPDATED", f"Actor {actor_id} updated user {target_user_id} → role={role}", target_user_id=target_user_id)
            flash(message, "success")
        else:
            flash(message, "error")

    except (ValueError, TypeError):
        flash("Invalid request data.", "error")
    except Exception as e:
        flash("Error updating user. Please check logs.", "error")
        current_app.logger.error(f"Admin edit user error: {e}")

    return redirect(url_for('admin.admin_panel'))


@admin_bp.route('/admin/users/<int:user_id>/role', methods=['PATCH', 'POST'])
@admin_required
def admin_change_role(user_id):
    """Change a user's role. Only main_admin may promote/demote to secondary_admin."""
    is_json = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    try:
        actor_id   = session.get('user_id')
        actor_role = session.get('user_role', 'employee')
        new_role   = (request.json or request.form).get('role', '').strip().lower()

        target = get_user_by_id(user_id)
        if not target:
            msg = "User not found."
            return (jsonify({"status": "error", "error": msg}), 404) if is_json else (flash(msg, "error"), redirect(url_for('admin.admin_panel')))[1]

        target_role = target.get('role', 'employee')

        if not can_manage_user(actor_role, target_role, actor_id, user_id):
            msg = "You do not have permission to change this user's role."
            if is_json:
                return jsonify({"status": "error", "error": msg}), 403
            flash(msg, "error")
            return redirect(url_for('admin.admin_panel'))

        old_role = target_role
        success, message = manage_update_user(
            actor_id, user_id,
            target.get('full_name', ''),
            target.get('email', ''),
            new_role,
            target.get('active_status', True)
        )

        if success:
            log_action(
                AuditActions.ROLE_CHANGED,
                f"Actor {actor_id} changed user {user_id} role: {old_role} → {new_role}",
                target_user_id=user_id
            )
            if is_json:
                return jsonify({"status": "success", "message": message}), 200
            flash(message, "success")
        else:
            if is_json:
                return jsonify({"status": "error", "error": message}), 400
            flash(message, "error")

    except Exception as e:
        current_app.logger.error(f"Admin change role error: {e}", exc_info=True)
        if is_json:
            return jsonify({"status": "error", "error": str(e)}), 500
        flash("Error changing role.", "error")

    return redirect(url_for('admin.admin_panel'))
