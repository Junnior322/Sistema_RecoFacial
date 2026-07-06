# main_camara.py
# ============================================================
#  Punto de entrada: reconocimiento en tiempo real
#  Ejecutar: python main_camara.py
# ============================================================

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from database import db
from models.face_engine import Reconocedor, iniciar_camara, guardar_captura
from collections import defaultdict
from datetime import datetime, timedelta

# ── Anti-spam: evitar registrar el mismo estudiante cada frame ─
_ultima_deteccion: dict[int, datetime] = defaultdict(lambda: datetime.min)
COOLDOWN_SEGUNDOS = 8   # mínimo tiempo entre registros del mismo estudiante


def callback_acceso(deteccion: dict, frame):
    """
    Llamado por el loop de cámara cada vez que se detecta un rostro.
    Registra el acceso en MySQL y genera alertas si corresponde.
    """
    resultado     = deteccion["resultado"]
    estudiante_id = deteccion.get("estudiante_id")
    confianza     = deteccion.get("confianza")

    # Anti-spam por estudiante identificado
    if estudiante_id is not None:
        ahora   = datetime.now()
        ultima  = _ultima_deteccion[estudiante_id]
        if ahora - ultima < timedelta(seconds=COOLDOWN_SEGUNDOS):
            return
        _ultima_deteccion[estudiante_id] = ahora

    # Guardar frame de auditoría
    captura_path = guardar_captura(frame)

    # Registrar en BD
    acceso_id = db.registrar_acceso(
        resultado=resultado,
        confianza=confianza,
        estudiante_id=estudiante_id,
        camara_id=0,
        captura_path=captura_path,
    )

    if resultado == "concedido":
        print(f"✅  ACCESO CONCEDIDO — {deteccion['nombre']}  ({deteccion['codigo']})"
              f"  confianza={confianza:.4f}")

    elif resultado == "desconocido":
        print(f"❌  Rostro no identificado  confianza={confianza}")
        db.crear_alerta(acceso_id, "cara_desconocida",
                        f"Rostro no reconocido · distancia={confianza}")

    elif resultado == "denegado":
        print(f"⛔  ACCESO DENEGADO — {deteccion['nombre']}")
        db.crear_alerta(acceso_id, "multiples_intentos",
                        f"Intento denegado para {deteccion['nombre']}")


def main():
    print("=" * 50)
    print("  SISTEMA DE RECONOCIMIENTO FACIAL UNIVERSITARIO")
    print("=" * 50)

    # Cargar embeddings desde MySQL
    print("Cargando embeddings desde la base de datos...")
    registros = db.cargar_todos_embeddings()

    if not registros:
        print("[AVISO] No hay embeddings registrados. "
              "Registra estudiantes primero desde el panel admin.")

    reconocedor = Reconocedor()
    reconocedor.cargar_desde_db(registros)

    # Iniciar loop de cámara
    iniciar_camara(reconocedor, callback_acceso=callback_acceso)

    print("Sistema detenido.")


if __name__ == "__main__":
    main()
