from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from flask_login import login_user, logout_user
from urllib.parse import urlparse
from services.auth_service import register_user, authenticate_user, change_user_password
from services.user_service import service_delete_own_account
from services.permission_service import load_user_permissions
from services.activity_service import log_activity
from utils.flask_auth import auth_required

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    limiter = current_app.extensions.get('limiter')
    if limiter:
        # Use a dynamic limit if needed, or we just rely on the decorator if possible
        # Since decorators need the object at import time, we can use a wrapper or the app-level config
        pass
    
    if request.method == 'POST':
        # Sanitize inputs
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', '').strip().lower()
        try:
            user = authenticate_user(email, password, role=role)
            if user:
                # Prevent session fixation
                session.clear()
                
                session.permanent = False
                session['user_id'] = user['id']
                session['user_role'] = user['role'].lower()
                session['user_name'] = user['full_name']
                session['email'] = user.get('email', email)
                
                # Load permissions AFTER session is set
                load_user_permissions()
                
                # Tell Flask-Login about the logged-in user so that
                # current_user.is_authenticated is True in templates.
                from app.models import User as FlaskLoginUser
                flask_login_user = FlaskLoginUser(user)
                login_user(flask_login_user, remember=False)
                
                # Log Activity
                log_activity(user['id'], "LOGIN", "User logged in successfully")
                
                flash("Login successful!", "success")
                
                # Redirect to original requested page or dashboard
                next_url = request.args.get('next') or request.form.get('next')
                if next_url:
                    parsed = urlparse(next_url)
                    # Only allow relative redirects (no scheme, no netloc) to prevent open redirects
                    if not parsed.scheme and not parsed.netloc and next_url.startswith('/'):
                        return redirect(next_url)
                return redirect(url_for('dashboard.dashboard'))
            else:
                flash("Invalid credentials. Please try again.", "error")
        except Exception as e:
            current_app.logger.error(f"Login error: {e}")
            flash("An error occurred. Please try again.", "error")
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        # Sanitize email
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'employee').lower()
        job_role = request.form.get('job_role', '').strip() or None
        
        bio         = request.form.get('bio', '').strip()
        phone       = request.form.get('phone', '').strip()
        city        = request.form.get('city', '').strip()
        country     = request.form.get('country', '').strip()
        postal_code = request.form.get('postal_code', '').strip()
        
        # Handle avatar upload
        avatar_url = None
        avatar_file = request.files.get('avatar')
        if avatar_file and avatar_file.filename:
            try:
                from services.upload_service import upload_file
                upload_res = upload_file(avatar_file, folder="avatars")
                if upload_res.get('success'):
                    avatar_url = upload_res['path']
            except Exception as e:
                current_app.logger.error(f"Avatar upload failed during registration: {e}")

        try:
            success, message = register_user(
                full_name, 
                email, 
                password, 
                role, 
                job_role=job_role,
                avatar_url=avatar_url,
                bio=bio,
                phone=phone,
                city=city,
                country=country,
                postal_code=postal_code
            )
            if success:
                flash(message, "success")
                return redirect(url_for('auth.login'))
            else:
                flash(message, "error")
        except Exception as e:
            current_app.logger.error(f"Registration error: {e}")
            flash("Registration failed. Please try again.", "error")
    
    return render_template('register.html')


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@auth_required
def change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password')
        new_pw = request.form.get('new_password')
        confirm_pw = request.form.get('confirm_password')
        
        try:
            success, message = change_user_password(
                session['user_id'], 
                current_pw, 
                new_pw, 
                confirm_pw
            )
            
            if success:
                log_activity(session['user_id'], "PASSWORD_CHANGE", "User changed password")
                flash(message, "success")
                return redirect(url_for('dashboard.dashboard'))
            else:
                flash(message, "error")
        except Exception as e:
            current_app.logger.error(f"Error changing password: {e}")
            flash("An error occurred. Please try again.", "error")
            
    return render_template('change_password.html')


@auth_bp.route('/logout')
def logout():
    if 'user_id' in session:
        log_activity(session['user_id'], "LOGOUT", "User logged out")
    logout_user()
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for('common.index'))


@auth_bp.route('/delete-account', methods=['POST'])
@auth_required
def delete_account():
    try:
        success, message = service_delete_own_account(session['user_id'])
        if success:
            session.clear()
            flash("Your account has been successfully deleted.", "success")
            return redirect(url_for('common.index'))
        else:
            flash(f"Error deleting account: {message}", "error")
            return redirect(url_for('common.profile'))
    except Exception as e:
        current_app.logger.error(f"Error in delete_account route: {e}")
        flash("An unexpected error occurred.", "error")
        return redirect(url_for('dashboard.dashboard'))
