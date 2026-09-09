from repository.logs_repo import create_log

def log_activity(user_id, action, details):
    """
    Service to log user activity.
    """
    if user_id:
         try:
            create_log(user_id, action, details)
         except Exception as e:
            print(f"Logging failed: {e}")
