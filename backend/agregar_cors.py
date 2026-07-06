# Ejecutar este script desde la carpeta backend:
# python agregar_cors.py

with open('api.py', 'r', encoding='utf-8') as f:
    content = f.read()

cors_import = "from fastapi.middleware.cors import CORSMiddleware\n"
cors_middleware = """
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "null",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
"""

# Agregar import si no existe
if "CORSMiddleware" not in content:
    content = content.replace(
        "from fastapi import",
        cors_import + "from fastapi import"
    )

# Agregar middleware si no existe
if "add_middleware" not in content:
    content = content.replace(
        "app = FastAPI(",
        "app = FastAPI("
    )
    # Insertar después de la definición de app
    idx = content.find("\n\n", content.find("app = FastAPI("))
    content = content[:idx] + "\n" + cors_middleware + content[idx:]

with open('api.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("CORS agregado correctamente")
print("Ahora reinicia uvicorn")
