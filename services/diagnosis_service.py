import os
import sys

def check_database():
    try:
        from repository.db import get_db_connection
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return True, "Connected successfully" if result else "Query failed"
    except Exception as e:
        return False, f"Connection error: {str(e)}"

def check_api_keys():
    status = {}
    
    # Check Groq
    groq_key = os.getenv("GROQ_API_KEY")
    status["Groq API"] = (True, "Key Found") if groq_key else (False, "Key Missing")
    
    # Check Gemini
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY_SECONDARY") or groq_key
    status["Gemini/Secondary API"] = (True, "Key Found") if gemini_key else (False, "Key Missing")
    
    return status

def check_filesystem():
    status = {}
    
    # Check uploads dir
    uploads_path = "uploads"
    if not os.path.exists(uploads_path):
        try:
            os.makedirs(uploads_path)
            status["Uploads Dir"] = (True, "Created missing directory")
        except Exception as e:
            status["Uploads Dir"] = (False, f"Missing and cannot create: {e}")
    else:
        # Check permissions by writing a temp file
        try:
            test_file = os.path.join(uploads_path, "test_write.tmp")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            status["Uploads Dir"] = (True, "Writable")
        except Exception as e:
            status["Uploads Dir"] = (False, f"Not writable: {e}")
            
    return status

def get_system_info():
    return {
        "Python Version": sys.version.split()[0],
        "OS": sys.platform
    }

def run_all_diagnostics():
    """
    Runs all system checks and returns a structured result.
    """
    db_status, db_msg = check_database()
    api_status = check_api_keys()
    fs_status = check_filesystem()
    sys_info = get_system_info()
    
    return {
        "database": {"status": db_status, "message": db_msg},
        "api": api_status,
        "filesystem": fs_status,
        "system": sys_info
    }
