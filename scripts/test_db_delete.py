from repository.db import execute_query

def test_delete_behavior():
    print("Attempting to execute a DELETE-like statement with fetch=True (default)...")
    try:
        # We'll use a harmless UPDATE or DELETE that affects 0 rows if possible, 
        # or just a statement that doesn't return anything.
        # Actually, any non-SELECT with fetch=True should trigger it.
        # Let's try to update a non-existent system config entry.
        res = execute_query("UPDATE system_config SET neural_sensitivity = 8.5 WHERE id = 99999", fetch=True)
        print(f"Result: {res}")
    except Exception as e:
        print(f"Caught expected error: {e}")

if __name__ == "__main__":
    test_delete_behavior()
