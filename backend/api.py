# backend/api.py
import os
import sys
import shutil
from datetime import datetime, timedelta

import bcrypt
import jwt
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import SECRET_KEY, JWT_EXPIRE_HOURS, PHOTOS_DIR
from database import db
from models.face_engine import generar_embedding, capturar_foto_webcam

os.makedirs(PHOTOS_DIR, exist_ok=True)

app = FastAPI(
    title="Sistema Reconocimiento Facial - API",
    version="1.0.0",
    description="API para gestion de acceso universitario por biometria facial",
)

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

bearer = HTTPBearer()

def crear_token(username: str, rol: str) -> str:
    payload = {
        "sub": username,
        "rol": rol,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        data = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return data
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token invalido")

class LoginRequest(BaseModel):
    username: str
    password: str

class EstudianteCreate(BaseModel):
    carrera_id: int
    codigo:     str
    nombres:    str
    apellidos:  str
    email:      str

@app.post("/auth/login", tags=["Auth"])
def login(body: LoginRequest):
    conn = db.get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM usuarios_admin WHERE username=%s AND activo=1", (body.username,))
    user = cur.fetchone()
    cur.close(); conn.close()
    if not user:
        raise HTTPException(401, "Credenciales incorrectas")
    if not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(401, "Credenciales incorrectas")
    conn = db.get_conn()
    cur  = conn.cursor()
    cur.execute("UPDATE usuarios_admin SET ultimo_login=NOW() WHERE id=%s", (user["id"],))
    conn.commit(); cur.close(); conn.close()
    token = crear_token(user["username"], user["rol"])
    return {"access_token": token, "token_type": "bearer", "nombre": user["nombre"], "rol": user["rol"]}

@app.get("/estudiantes", tags=["Estudiantes"])
def listar_estudiantes(token=Depends(verificar_token)):
    return db.get_todos_estudiantes()

@app.get("/estudiantes/{id}", tags=["Estudiantes"])
def obtener_estudiante(id: int, token=Depends(verificar_token)):
    est = db.get_estudiante_by_id(id)
    if not est:
        raise HTTPException(404, "Estudiante no encontrado")
    return est

@app.post("/estudiantes", tags=["Estudiantes"], status_code=201)
def crear_estudiante(body: EstudianteCreate):
    new_id = db.insertar_estudiante(body.carrera_id, body.codigo, body.nombres, body.apellidos, body.email)
    return {"id": new_id, "message": "Estudiante creado exitosamente"}

@app.delete("/estudiantes/{id}", tags=["Estudiantes"])
def desactivar_estudiante(id: int, token=Depends(verificar_token)):
    if token["rol"] not in ("superadmin", "admin"):
        raise HTTPException(403, "No autorizado")
    db.desactivar_estudiante(id)
    return {"message": "Estudiante desactivado"}

@app.post("/estudiantes/{id}/foto", tags=["Embeddings"])
async def subir_foto(id: int, foto: UploadFile = File(...)):
    est = db.get_estudiante_by_id(id)
    if not est:
        raise HTTPException(404, "Estudiante no encontrado")
    ext      = os.path.splitext(foto.filename)[1] or ".jpg"
    filename = f"est_{id}{ext}"
    filepath = os.path.join(PHOTOS_DIR, filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(foto.file, f)
    embedding = generar_embedding(filepath)
    if embedding is None:
        os.remove(filepath)
        raise HTTPException(400, "No se detecto un rostro claro en la foto.")
    db.actualizar_foto(id, filepath)
    db.guardar_embedding(id, embedding)
    return {"message": "Foto y embedding guardados correctamente"}

@app.get("/accesos/hoy", tags=["Accesos"])
def accesos_hoy(token=Depends(verificar_token)):
    return db.get_accesos_hoy()

@app.get("/accesos/resumen", tags=["Accesos"])
def resumen_accesos(dias: int = 7, token=Depends(verificar_token)):
    return db.get_resumen_accesos(dias)

@app.get("/alertas", tags=["Alertas"])
def alertas_pendientes(token=Depends(verificar_token)):
    return db.get_alertas_pendientes()

@app.patch("/alertas/{id}/resolver", tags=["Alertas"])
def resolver_alerta(id: int, token=Depends(verificar_token)):
    db.resolver_alerta(id)
    return {"message": "Alerta marcada como resuelta"}

@app.get("/dashboard", tags=["Dashboard"])
def dashboard(token=Depends(verificar_token)):
    conn = db.get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) AS total FROM estudiantes WHERE activo=1")
    total_est = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM embeddings_faciales")
    total_emb = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM accesos WHERE DATE(accedido_at) = CURDATE()")
    accesos_hoy_total = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM alertas WHERE resuelta=0")
    alertas_total = cur.fetchone()["total"]
    cur.execute("SELECT resultado, COUNT(*) AS total FROM accesos WHERE DATE(accedido_at) = CURDATE() GROUP BY resultado")
    accesos_breakdown = {r["resultado"]: r["total"] for r in cur.fetchall()}
    cur.close(); conn.close()
    return {
        "estudiantes_activos":   total_est,
        "con_embedding":         total_emb,
        "accesos_hoy":           accesos_hoy_total,
        "alertas_pendientes":    alertas_total,
        "accesos_breakdown_hoy": accesos_breakdown,
        "porcentaje_registrados": round(total_emb / total_est * 100, 1) if total_est else 0,
    }

@app.get("/carreras", tags=["Carreras"])
def listar_carreras():
    return db.get_carreras()

@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/verificar", tags=["Acceso"])
async def verificar_rostro(foto: UploadFile = File(...)):
    import numpy as np
    import face_recognition as fr
    import tempfile
    suffix = os.path.splitext(foto.filename)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await foto.read())
        tmp_path = tmp.name
    try:
        imagen    = fr.load_image_file(tmp_path)
        locs      = fr.face_locations(imagen, model="hog")
        encodings = fr.face_encodings(imagen, locs)
        if not encodings:
            return {"resultado": "sin_rostro"}
        enc       = encodings[0]
        registros = db.cargar_todos_embeddings()
        if not registros:
            return {"resultado": "sin_registros"}
        conocidos  = [np.array(r["embedding"]) for r in registros]
        distancias = fr.face_distance(conocidos, enc)
        mejor_idx  = int(np.argmin(distancias))
        dist_min   = float(distancias[mejor_idx])
        from config import FACE_TOLERANCE
        if dist_min <= FACE_TOLERANCE:
            dato = registros[mejor_idx]
            est  = db.get_estudiante_by_id(dato["estudiante_id"])
            db.registrar_acceso(resultado="concedido", confianza=round(dist_min, 4),
                                estudiante_id=dato["estudiante_id"], camara_id=0, captura_path=tmp_path)
            return {
                "resultado":     "concedido",
                "estudiante_id": dato["estudiante_id"],
                "nombre":        dato["nombre_completo"],
                "codigo":        dato["codigo"],
                "carrera":       est["carrera"] if est else "-",
                "confianza":     round(dist_min, 4),
                "foto_path":     est["foto_path"] if est else None,
            }
        else:
            acceso_id = db.registrar_acceso(resultado="desconocido", confianza=round(dist_min, 4), captura_path=tmp_path)
            db.crear_alerta(acceso_id, "cara_desconocida", f"Rostro no reconocido dist={round(dist_min,4)}")
            return {"resultado": "desconocido", "confianza": round(dist_min, 4)}
    finally:
        try: os.remove(tmp_path)
        except: pass

@app.get("/foto/{estudiante_id}", tags=["Estudiantes"])
def obtener_foto(estudiante_id: int):
    est = db.get_estudiante_by_id(estudiante_id)
    if not est or not est.get("foto_path"):
        raise HTTPException(404, "Foto no encontrada")
    if not os.path.exists(est["foto_path"]):
        raise HTTPException(404, "Archivo de foto no encontrado")
    return FileResponse(est["foto_path"], media_type="image/jpeg")

# -- Prediccion de afluencia con Random Forest --
from models.prediccion_afluencia import resumen_prediccion

@app.get("/prediccion/afluencia", tags=["Prediccion"])
def prediccion_afluencia(dias: int = 60, token=Depends(verificar_token)):
    """Predice afluencia con Random Forest basado en historial de accesos."""
    try:
        return resumen_prediccion(dias)
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")

# -- Servir frontend --
frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
