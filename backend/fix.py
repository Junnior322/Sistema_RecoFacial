with open('api.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Buscar y reemplazar el bloque CORS
import re
content = re.sub(
    r'app\.add_middleware\s*\(\s*CORSMiddleware.*?\)',
    '''app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)''',
    content,
    flags=re.DOTALL
)

with open('api.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('OK - CORS corregido')