# database/db.py
# ============================================================
#  Conexión y operaciones CRUD con MySQL (mysql-connector-python)
# ============================================================

import json
import mysql.connector
from mysql.connector import pooling
from config import DB_CONFIG

# Pool de conexiones (reutiliza hasta 5 conexiones simultáneas)
_pool = pooling.MySQLConnectionPool(
    pool_name="facial_pool",
    pool_size=5,
    **DB_CONFIG,
)


def get_conn():
    """Retorna una conexión del pool."""
    return _pool.get_connection()


# ── Estudiantes ─────────────────────────────────────────────

def get_todos_estudiantes():
    """Devuelve lista de dicts con datos de estudiantes y si tienen embedding."""
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM v_estudiantes_completo ORDER BY nombre_completo")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows


def get_estudiante_by_id(estudiante_id: int):
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM v_estudiantes_completo WHERE id = %s", (estudiante_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row


def insertar_estudiante(carrera_id, codigo, nombres, apellidos, email, foto_path=None):
    conn = get_conn()
    cur  = conn.cursor()
    sql  = """INSERT INTO estudiantes
              (carrera_id, codigo, nombres, apellidos, email, foto_path)
              VALUES (%s, %s, %s, %s, %s, %s)"""
    cur.execute(sql, (carrera_id, codigo, nombres, apellidos, email, foto_path))
    conn.commit()
    new_id = cur.lastrowid
    cur.close(); conn.close()
    return new_id


def actualizar_foto(estudiante_id: int, foto_path: str):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("UPDATE estudiantes SET foto_path=%s WHERE id=%s",
                (foto_path, estudiante_id))
    conn.commit()
    cur.close(); conn.close()


def desactivar_estudiante(estudiante_id: int):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("UPDATE estudiantes SET activo=0 WHERE id=%s", (estudiante_id,))
    conn.commit()
    cur.close(); conn.close()


# ── Embeddings ───────────────────────────────────────────────

def guardar_embedding(estudiante_id: int, embedding: list, modelo="face_recognition_v1"):
    """Inserta o actualiza el embedding de un estudiante."""
    conn = get_conn()
    cur  = conn.cursor()
    sql  = """INSERT INTO embeddings_faciales (estudiante_id, embedding, modelo)
              VALUES (%s, %s, %s)
              ON DUPLICATE KEY UPDATE
                  embedding = VALUES(embedding),
                  modelo    = VALUES(modelo),
                  actualizado_at = CURRENT_TIMESTAMP"""
    cur.execute(sql, (estudiante_id, json.dumps(embedding), modelo))
    conn.commit()
    cur.close(); conn.close()


def cargar_todos_embeddings():
    """
    Carga todos los embeddings activos para el reconocedor en memoria.
    Retorna lista de dicts: {estudiante_id, nombre_completo, codigo, embedding}
    """
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    sql  = """
        SELECT e.id AS estudiante_id,
               CONCAT(e.nombres,' ',e.apellidos) AS nombre_completo,
               e.codigo,
               ef.embedding
        FROM   embeddings_faciales ef
        JOIN   estudiantes e ON e.id = ef.estudiante_id
        WHERE  e.activo = 1
    """
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close(); conn.close()
    # Parsear JSON → lista Python
    for r in rows:
        r["embedding"] = json.loads(r["embedding"])
    return rows


# ── Accesos ──────────────────────────────────────────────────

def registrar_acceso(resultado: str, confianza: float = None,
                     estudiante_id: int = None,
                     camara_id: int = 0, captura_path: str = None):
    conn = get_conn()
    cur  = conn.cursor()
    sql  = """INSERT INTO accesos
              (estudiante_id, resultado, confianza, camara_id, captura_path)
              VALUES (%s, %s, %s, %s, %s)"""
    cur.execute(sql, (estudiante_id, resultado, confianza, camara_id, captura_path))
    conn.commit()
    acceso_id = cur.lastrowid
    cur.close(); conn.close()
    return acceso_id


def get_accesos_hoy():
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM v_accesos_hoy")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows


def get_resumen_accesos(dias: int = 7):
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT * FROM v_resumen_accesos
        WHERE fecha >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
    """, (dias,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows


# ── Alertas ──────────────────────────────────────────────────

def crear_alerta(acceso_id: int, tipo: str, descripcion: str = None):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""INSERT INTO alertas (acceso_id, tipo, descripcion)
                   VALUES (%s, %s, %s)""",
                (acceso_id, tipo, descripcion))
    conn.commit()
    cur.close(); conn.close()


def get_alertas_pendientes():
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT al.*, a.accedido_at, a.camara_id
        FROM alertas al
        JOIN accesos a ON a.id = al.acceso_id
        WHERE al.resuelta = 0
        ORDER BY al.created_at DESC
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows


def resolver_alerta(alerta_id: int):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("UPDATE alertas SET resuelta=1 WHERE id=%s", (alerta_id,))
    conn.commit()
    cur.close(); conn.close()


# ── Carreras / Facultades ────────────────────────────────────

def get_carreras():
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT c.id, c.codigo, c.nombre,
               f.nombre AS facultad
        FROM carreras c
        JOIN facultades f ON f.id = c.facultad_id
        ORDER BY f.nombre, c.nombre
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows
