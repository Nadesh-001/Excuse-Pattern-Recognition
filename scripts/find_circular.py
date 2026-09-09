
import os
import re
import sys

def get_imports(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Simple regex to find imports
    # matching: from x.y import z OR import x.y
    imports = []
    
    # from routes.auth_routes import auth_bp
    from_matches = re.findall(r'^from\s+([a-zA-Z0-9_\.]+)\s+import', content, re.MULTILINE)
    imports.extend(from_matches)
    
    # import services.auth_service
    import_matches = re.findall(r'^import\s+([a-zA-Z0-9_\.]+)', content, re.MULTILINE)
    imports.extend(import_matches)
    
    return imports

def build_graph(root_dir):
    graph = {}
    for root, _, files in os.walk(root_dir):
        if '.venv' in root or '.git' in root or '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                # Convert path to module name
                rel_path = os.path.relpath(file_path, root_dir)
                module_name = rel_path.replace(os.path.sep, '.').replace('.__init__.py', '').replace('.py', '')
                if module_name == '__init__': module_name = os.path.basename(root_dir)
                
                deps = get_imports(file_path)
                graph[module_name] = deps
    return graph

def find_cycles(graph):
    cycles = []
    
    def visit(node, stack):
        if node in stack:
            # Found a cycle
            cycle = stack[stack.index(node):] + [node]
            cycles.append(cycle)
            return
        
        if node not in graph:
            return
            
        stack.append(node)
        for neighbor in graph[node]:
            # Simplify neighbor to top level or match graph keys
            # e.g. services.auth_service.register_user -> services.auth_service
            neighbor_base = neighbor
            if neighbor_base not in graph:
                # Try parts
                parts = neighbor_base.split('.')
                for i in range(len(parts), 0, -1):
                    cand = '.'.join(parts[:i])
                    if cand in graph:
                        neighbor_base = cand
                        break
            
            if neighbor_base in graph:
                visit(neighbor_base, stack[:])
    
    for node in graph:
        visit(node, [])
        
    return cycles

if __name__ == "__main__":
    root = "."
    if len(sys.argv) > 1:
        root = sys.argv[1]
    
    g = build_graph(root)
    cycles = find_cycles(g)
    
    unique_cycles = []
    seen = set()
    for c in cycles:
        # Normalize cycle to avoid duplicates (a-b-a and b-a-b)
        # But for import cycles, order matters for the "first" import
        # Let's just use a sorted tuple of the cycle members
        c_tuple = tuple(sorted(set(c)))
        if c_tuple not in seen:
            unique_cycles.append(c)
            seen.add(c_tuple)
            
    if unique_cycles:
        print(f"Detected {len(unique_cycles)} unique circular dependency chains:")
        for c in unique_cycles:
            print(" -> ".join(c))
    else:
        print("No circular dependencies detected (at top-level imports).")
