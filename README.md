# Sistema de Reconocimiento Facial Universitario

Sistema de control de acceso biométrico desarrollado en Python,
con base de datos MySQL y panel web de administración.

---

## Estructura del proyecto

```
facial_system/
├── config.py                  # Configuración central
├── main_camara.py             # Loop principal de reconocimiento
├── requirements.txt
├── .env.example               # Plantilla de variables de entorno
│
├── database/
│   ├── schema.sql             # ← Ejecutar en MySQL Workbench primero
│   └── db.py                  # CRUD y conexión al pool MySQL
│
├── models/
│   └── face_engine.py         # Motor de reconocimiento (dlib + OpenCV)
│
├── backend/
│   └── api.py                 # API REST con FastAPI
│
└── frontend/
    └── panel_admin.html       # Panel web (abrir en navegador)
```

---

## Instalación paso a paso

### 1. Requisitos previos

- Python 3.10 o superior
- MySQL 8.0 (con MySQL Workbench instalado)
- Webcam conectada
- CMake instalado (necesario para compilar dlib)

**En Windows**, instalar CMake desde https://cmake.org/download/
**En Linux/Mac**: `sudo apt install cmake` o `brew install cmake`

---

### 2. Base de datos en MySQL Workbench

1. Abre MySQL Workbench y conéctate a tu servidor local.
2. Ve a **File → Open SQL Script** y abre `database/schema.sql`.
3. Ejecuta el script completo (Ctrl+Shift+Enter).
4. Verifica que se creó la base de datos `facial_recognition_db` con todas sus tablas.

---

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` y coloca tu contraseña de MySQL y una clave secreta aleatoria.

---

### 4. Instalar dependencias Python

```bash
# Crear entorno virtual (recomendado)
python -m venv venv

# Activar (Windows)
venv\Scripts\activate

# Activar (Linux/Mac)
source venv/bin/activate

# Instalar librerías
pip install -r requirements.txt
```

> **Nota**: La instalación de `face_recognition` puede tardar varios minutos
> porque compila dlib desde código fuente.

---

### 5. Levantar la API REST

```bash
cd backend
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Documentación interactiva disponible en: http://localhost:8000/docs

---

### 6. Abrir el panel de administración

Abre `frontend/panel_admin.html` directamente en tu navegador.
En producción, servir con un servidor web estático (Nginx, etc.)

---

### 7. Registrar estudiantes

Desde el panel admin → **Estudiantes → Nuevo estudiante**:
1. Completa los datos del estudiante.
2. Sube una foto clara del rostro (o usa la opción webcam desde la API).
3. El sistema genera el embedding automáticamente y lo guarda en MySQL.

---

### 8. Iniciar el reconocimiento en tiempo real

```bash
python main_camara.py
```

El sistema cargará todos los embeddings de MySQL y abrirá la cámara.
Presiona **Q** para detener.

---

## Parámetros de configuración

| Parámetro          | Default | Descripción                                      |
|--------------------|---------|--------------------------------------------------|
| `FACE_TOLERANCE`   | 0.45    | Umbral de distancia coseno (menor = más estricto)|
| `PROCESS_EVERY`    | 5       | Procesar 1 de cada N frames (rendimiento)        |
| `COOLDOWN_SEGUNDOS`| 8       | Segundos entre registros del mismo estudiante    |
| `CAMERA_INDEX`     | 0       | Índice de la cámara (0 = primera webcam)         |

---

## Endpoints de la API

| Método | Ruta                              | Descripción                         |
|--------|-----------------------------------|-------------------------------------|
| POST   | /auth/login                       | Autenticación → JWT                 |
| GET    | /estudiantes                      | Listar todos los estudiantes        |
| POST   | /estudiantes                      | Crear nuevo estudiante              |
| POST   | /estudiantes/{id}/foto            | Subir foto y generar embedding      |
| POST   | /estudiantes/{id}/embedding-webcam| Capturar embedding desde webcam     |
| GET    | /accesos/hoy                      | Accesos del día actual              |
| GET    | /accesos/resumen?dias=7           | Resumen por días                    |
| GET    | /alertas                          | Alertas pendientes                  |
| PATCH  | /alertas/{id}/resolver            | Marcar alerta como resuelta         |
| GET    | /dashboard                        | Métricas generales                  |

---

## Tecnologías utilizadas

- **Python 3.10+** — lenguaje principal
- **face_recognition** — detección y embeddings faciales (dlib/ResNet)
- **OpenCV** — captura de cámara y procesamiento de video
- **MySQL 8** — base de datos relacional
- **FastAPI** — API REST asíncrona
- **JWT + bcrypt** — autenticación segura
- **HTML/CSS/JS** — panel de administración web
