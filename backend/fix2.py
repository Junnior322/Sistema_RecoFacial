with open('api.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Buscar la línea con add_middleware
for i, line in enumerate(lines):
    if 'add_middleware' in line:
        print(f"Línea {i}: {line.strip()}")
        # Mostrar las 10 líneas siguientes
        for j in range(i, min(i+12, len(lines))):
            print(f"  {j}: {lines[j].rstrip()}")
        break