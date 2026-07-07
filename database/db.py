# database/db.py
import os
import json
import mysql.connector
import mysql.connector.pooling
from dotenv import load_dotenv

load_dotenv()

_pool = None

def get_pool():
    global _pool
    if _pool is None:
        host     = os.getenv("DB_HOST", "localhost")
        port     = int(os.getenv("DB_PORT", 3306))
        user     = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASSWORD", "")
        database = os.getenv("DB_NAME", "facial_recognition_db")
        kwargs   = dict(
            pool_name="upsjb_pool", pool_size=5,
            host=host, port=port, user=user,
            password=password, database=database,
            connection_timeout=30,
            pool_reset_session=True,
        )
        if "aivencloud.com" in host:
            kwargs["ssl_disabled"] = False
        _pool = mysql.connector.pooling.MySQLConnectionPool(**kwargs)
    return _pool

def get_conn():
    return get_pool().get_connection()


def get_todos_estudiantes():
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT e.id, e.codigo,
               CONCAT(e.nombres,' ',e.apellidos) AS nombre_completo,
               e.email, c.nombre AS carrera, f.nombre AS facultad,
               CASE WHEN ef.id IS NOT NULL THEN 'Si' ELSE 'No' END AS tiene_embedding,
               e.activo, e.foto_path
        FROM estudiantes e
        JOIN carreras   c  ON c.id = e.carrera_id
        JOIN facultades f  ON f.id = c.facultad_id
        LEFT JOIN embeddings_faciales ef ON ef.estudiante_id = e.id
        WHERE e.activo = 1
        ORDER BY e.created_at DESC
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows


def get_estudiante_by_id(id: int):
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT e.id, e.codigo,
               CONCAT(e.nombres,' ',e.apellidos) AS nombre_completo,
               e.nombres, e.apellidos, e.email,
               c.nombre AS carrera, f.nombre AS facultad,
               CASE WHEN ef.id IS NOT NULL THEN 'Si' ELSE 'No' END AS tiene_embedding,
               e.activo, e.foto_path
        FROM estudiantes e
        JOIN carreras   c  ON c.id = e.carrera_id
        JOIN facultades f  ON f.id = c.facultad_id
        LEFT JOIN embeddings_faciales ef ON ef.estudiante_id = e.id
        WHERE e.id = %s
    """, (id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row


def insertar_estudiante(carrera_id, codigo, nombres, apellidos, email):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO estudiantes (carrera_id, codigo, nombres, apellidos, email)
        VALUES (%s, %s, %s, %s, %s)
    """, (carrera_id, codigo, nombres, apellidos, email))
    conn.commit()
    new_id = cur.lastrowid
    cur.close(); conn.close()
    return new_id


def actualizar_foto(id: int, foto_path: str):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("UPDATE estudiantes SET foto_path=%s WHERE id=%s", (foto_path, id))
    conn.commit()
    cur.close(); conn.close()


def guardar_embedding(estudiante_id: int, embedding: list):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM embeddings_faciales WHERE estudiante_id=%s", (estudiante_id,))
    cur.execute("""
        INSERT INTO embeddings_faciales (estudiante_id, embedding_json)
        VALUES (%s, %s)
    """, (estudiante_id, json.dumps(embedding)))
    conn.commit()
    cur.close(); conn.close()


def cargar_todos_embeddings():
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT ef.estudiante_id, ef.embedding_json,
               CONCAT(e.nombres,' ',e.apellidos) AS nombre_completo,
               e.codigo
        FROM embeddings_faciales ef
        JOIN estudiantes e ON e.id = ef.estudiante_id
        WHERE e.activo = 1
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    result = []
    for r in rows:
        r["embedding"] = json.loads(r["embedding_json"])
        result.append(r)
    return result


def registrar_acceso(resultado, confianza, estudiante_id=None, camara_id=0, captura_path=None):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO accesos (estudiante_id, resultado, confianza, camara_id, captura_path)
        VALUES (%s, %s, %s, %s, %s)
    """, (estudiante_id, resultado, confianza, camara_id, captura_path))
    conn.commit()
    acceso_id = cur.lastrowid
    cur.close(); conn.close()
    return acceso_id


def get_accesos_hoy():
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT a.id, a.resultado, a.confianza, a.camara_id, a.accedido_at,
               CONCAT(e.nombres,' ',e.apellidos) AS estudiante,
               e.codigo
        FROM accesos a
        LEFT JOIN estudiantes e ON e.id = a.estudiante_id
        WHERE DATE(a.accedido_at) = CURDATE()
        ORDER BY a.accedido_at DESC
        LIMIT 100
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows


def get_resumen_accesos(dias: int = 7):
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT DATE(accedido_at) AS fecha, resultado, COUNT(*) AS total
        FROM accesos
        WHERE accedido_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY fecha, resultado
        ORDER BY fecha
    """, (dias,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows


def get_alertas_pendientes():
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT id, tipo, descripcion, resuelta, created_at
        FROM alertas WHERE resuelta = 0
        ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows


def crear_alerta(acceso_id, tipo, descripcion):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO alertas (acceso_id, tipo, descripcion)
        VALUES (%s, %s, %s)
    """, (acceso_id, tipo, descripcion))
    conn.commit()
    cur.close(); conn.close()


def resolver_alerta(id: int):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("UPDATE alertas SET resuelta=1 WHERE id=%s", (id,))
    conn.commit()
    cur.close(); conn.close()


def desactivar_estudiante(id: int):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("UPDATE estudiantes SET activo=0 WHERE id=%s", (id,))
    conn.commit()
    cur.close(); conn.close()


def get_carreras():
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT c.id, c.nombre, f.nombre AS facultad
        FROM carreras c
        JOIN facultades f ON f.id = c.facultad_id
        ORDER BY f.nombre, c.nombre
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows
