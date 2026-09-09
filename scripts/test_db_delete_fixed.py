from repository.db import execute_query

def test_fixed_delete_behavior():
    print("Attempting to execute a DELETE-like statement with fetch=False...")
    try:
        # This is what wefixed in the repository code: using fetch=False
        row_count = execute_query("UPDATE system_config SET neural_sensitivity = 8.5 WHERE id = 99999", fetch=False)
        print(f"Success! Affected row count: {row_count}")
    except Exception as e:
        print(f"Failed again: {e}")

if __name__ == "__main__":
    test_fixed_delete_behavior()
