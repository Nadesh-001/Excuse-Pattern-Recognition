import sys
import os
sys.path.append(os.getcwd())
from database.connection import execute_query

def check_indexes():
    query = """
    SELECT tablename, indexname, indexdef 
    FROM pg_indexes 
    WHERE tablename IN ('tasks', 'delays') 
    ORDER BY tablename, indexname;
    """
    try:
        res = execute_query(query)
        with open('index_status.txt', 'w') as f:
            for row in res:
                f.write(f"Table: {row['tablename']} | Index: {row['indexname']}\n")
                f.write(f"  Definition: {row['indexdef']}\n")
                f.write("-" * 20 + "\n")
        print("Index status written to index_status.txt")
    except Exception as e:
        print(f"Error checking indexes: {e}")

if __name__ == "__main__":
    check_indexes()
