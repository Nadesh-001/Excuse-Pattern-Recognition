from repository.db import execute_query

def inspect():
    tables = execute_query("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'", fetch=True)
    for t in tables:
        name = t['table_name']
        print(f"\nTable: {name}")
        cols = execute_query(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{name}'", fetch=True)
        for c in cols:
            print(f"  - {c['column_name']} ({c['data_type']})")

if __name__ == "__main__":
    inspect()
