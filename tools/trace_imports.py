
import builtins

old_import = builtins.__import__

stack = []

def new_import(name, globals=None, locals=None, fromlist=None, level=0):
    if name.startswith('routes') or name.startswith('services') or name.startswith('app'):
        stack.append(name)
        # print("  " * (len(stack)-1) + f"Importing: {name} (from {stack[-2] if len(stack)>1 else 'root'})")
        try:
            return old_import(name, globals, locals, fromlist, level)
        finally:
            stack.pop()
    return old_import(name, globals, locals, fromlist, level)

builtins.__import__ = new_import

try:
    from app import create_app
    app = create_app()
    print("App created successfully!")
except Exception:
    import traceback
    traceback.print_exc()
