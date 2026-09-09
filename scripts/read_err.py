
import sys

def try_read(path):
    encodings = ['utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'latin-1']
    for enc in encodings:
        try:
            with open(path, 'rb') as f:
                content = f.read().decode(enc)
            if content.strip():
                print(f"--- Encoding: {enc} ---")
                # Print only first 1000 chars of last 5000 chars to find recent errors
                print(content[-5000:])
                return True
        except Exception:
            pass
    return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python read_err.py <path>")
    else:
        if not try_read(sys.argv[1]):
            print("Failed to read with common encodings.")
