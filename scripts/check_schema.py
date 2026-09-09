from repository.db import execute_query

def check_schema():
    print("Checking 'delays' table schema...")
    cols = execute_query("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'delays';")
    for col in cols:
        print(f"- {col['column_name']} ({col['data_type']})")

    print("\nChecking 'tasks' table schema...")
    cols = execute_query("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'tasks';")
    for col in cols:
        print(f"- {col['column_name']} ({col['data_type']})")

if __name__ == "__main__":
    try:
        check_schema()
    except Exception as e:
        print(f"Error checking schema: {e}")
