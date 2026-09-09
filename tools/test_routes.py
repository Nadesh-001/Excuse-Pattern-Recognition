import sys
import traceback
sys.path.insert(0, '.')

from app import create_app

app = create_app()
app.config['TESTING'] = True
app.config['PROPAGATE_EXCEPTIONS'] = True

with app.test_client() as client:
    # Set session directly to simulate logged-in user
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['user_name'] = 'Stark'
        sess['email'] = 'stark@gmail.com'
        sess['user_role'] = 'manager'

    # Test profile
    print("=== Testing /profile ===")
    try:
        r = client.get('/profile')
        print(f"Status: {r.status_code}")
        if r.status_code >= 500:
            print(r.data.decode('utf-8','replace')[:2000])
    except Exception:
        print(f"EXCEPTION:\n{traceback.format_exc()}")

    # Test tasks
    print("\n=== Testing /tasks ===")
    try:
        r = client.get('/tasks')
        print(f"Status: {r.status_code}")
        if r.status_code >= 500:
            print(r.data.decode('utf-8','replace')[:2000])
    except Exception:
        print(f"EXCEPTION:\n{traceback.format_exc()}")
