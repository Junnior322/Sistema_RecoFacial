# config.py
# ============================================================
#  Configuración central del sistema
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()

# --- Base de datos MySQL ---
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", 3306)),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "facial_recognition_db"),
    "charset":  "utf8mb4",
}

# --- Reconocimiento facial ---
FACE_TOLERANCE      = 0.45   # distancia coseno; < = más estricto
LIVENESS_THRESHOLD  = 0.60   # umbral anti-spoofing
CAMERA_INDEX = 0    # índice de webcam (0 = primera)
FRAME_WIDTH         = 640
FRAME_HEIGHT        = 480
CAPTURES_DIR        = "captures"   # carpeta de frames de auditoría
PHOTOS_DIR          = "photos"     # fotos de registro de estudiantes

# --- API / servidor ---
API_HOST    = "0.0.0.0"
API_PORT    = 8000
SECRET_KEY  = os.getenv("SECRET_KEY", "cambia_esto_en_produccion")
JWT_EXPIRE_HOURS = 8
