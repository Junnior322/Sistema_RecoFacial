# models/face_engine.py
# ============================================================
#  Motor de reconocimiento facial
#  Librería: face_recognition (dlib) + OpenCV
# ============================================================

import os
import cv2
import numpy as np
import face_recognition
from datetime import datetime
from config import (FACE_TOLERANCE, CAMERA_INDEX,
                    FRAME_WIDTH, FRAME_HEIGHT, CAPTURES_DIR)

os.makedirs(CAPTURES_DIR, exist_ok=True)


# ── Captura de foto desde webcam ─────────────────────────────

def capturar_foto_webcam(save_path: str) -> bool:
    """
    Abre la webcam, muestra preview y captura un frame al presionar ESPACIO.
    Guarda la imagen en save_path. Retorna True si éxito.
    """
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    print("Presiona ESPACIO para capturar · ESC para cancelar")
    captured = False
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        # Mostrar recuadro guía
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        cv2.rectangle(frame, (cx-90, cy-110), (cx+90, cy+110), (0, 255, 100), 2)
        cv2.putText(frame, "Centra tu rostro",
                    (cx-80, cy+135), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,100), 1)
        cv2.imshow("Registro facial — ESPACIO: capturar  ESC: cancelar", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:   # ESC
            break
        if key == 32:   # ESPACIO
            cv2.imwrite(save_path, frame)
            captured = True
            break

    cap.release()
    cv2.destroyAllWindows()
    return captured


# ── Generación de embedding ──────────────────────────────────

def generar_embedding(image_path: str) -> list | None:
    """
    Recibe la ruta de una imagen, detecta el rostro y devuelve
    el embedding de 128 dimensiones como lista Python.
    Retorna None si no detecta exactamente un rostro.
    """
    imagen = face_recognition.load_image_file(image_path)
    # Detectar todas las caras en la imagen
    ubicaciones = face_recognition.face_locations(imagen, model="hog")

    if len(ubicaciones) == 0:
        print("[ERROR] No se detectó ningún rostro.")
        return None
    if len(ubicaciones) > 1:
        print(f"[AVISO] Se detectaron {len(ubicaciones)} rostros; usa una foto individual.")
        return None

    encodings = face_recognition.face_encodings(imagen, ubicaciones)
    return encodings[0].tolist()   # numpy array → lista Python (serializable JSON)


# ── Reconocimiento en tiempo real ────────────────────────────

class Reconocedor:
    """
    Mantiene en memoria los embeddings conocidos y compara
    en tiempo real contra la cámara.
    """

    def __init__(self):
        self.embeddings_conocidos: list[np.ndarray] = []
        self.datos_conocidos:      list[dict]       = []  # {estudiante_id, nombre_completo, codigo}

    def cargar_desde_db(self, registros: list[dict]):
        """
        Recibe la lista devuelta por db.cargar_todos_embeddings()
        y construye los arrays numpy en memoria.
        """
        self.embeddings_conocidos = []
        self.datos_conocidos      = []
        for r in registros:
            self.embeddings_conocidos.append(np.array(r["embedding"]))
            self.datos_conocidos.append({
                "estudiante_id":  r["estudiante_id"],
                "nombre_completo": r["nombre_completo"],
                "codigo":          r["codigo"],
            })
        print(f"[Reconocedor] {len(self.embeddings_conocidos)} embeddings cargados.")

    def identificar(self, frame_rgb: np.ndarray) -> list[dict]:
        """
        Recibe un frame en RGB.
        Retorna lista de detecciones:
          {top, right, bottom, left, estudiante_id, nombre, codigo, confianza, resultado}
        """
        # Escalar al 50% para procesar más rápido
        small = cv2.resize(frame_rgb, (0, 0), fx=0.5, fy=0.5)
        ubicaciones = face_recognition.face_locations(small)
        encodings   = face_recognition.face_encodings(small, ubicaciones)

        resultados = []
        for enc, loc in zip(encodings, ubicaciones):
            top, right, bottom, left = [v * 2 for v in loc]  # escalar de vuelta

            if len(self.embeddings_conocidos) == 0:
                resultados.append({
                    "top": top, "right": right, "bottom": bottom, "left": left,
                    "estudiante_id": None, "nombre": "Sin registros",
                    "codigo": "-", "confianza": None, "resultado": "desconocido"
                })
                continue

            distancias = face_recognition.face_distance(self.embeddings_conocidos, enc)
            mejor_idx  = int(np.argmin(distancias))
            dist_min   = float(distancias[mejor_idx])

            if dist_min <= FACE_TOLERANCE:
                dato = self.datos_conocidos[mejor_idx]
                resultados.append({
                    "top": top, "right": right, "bottom": bottom, "left": left,
                    "estudiante_id": dato["estudiante_id"],
                    "nombre":        dato["nombre_completo"],
                    "codigo":        dato["codigo"],
                    "confianza":     round(dist_min, 4),
                    "resultado":     "concedido",
                })
            else:
                resultados.append({
                    "top": top, "right": right, "bottom": bottom, "left": left,
                    "estudiante_id": None, "nombre": "Desconocido",
                    "codigo": "-", "confianza": round(dist_min, 4),
                    "resultado": "desconocido",
                })
        return resultados

    def dibujar_resultado(self, frame_bgr: np.ndarray, detecciones: list[dict]) -> np.ndarray:
        """Dibuja recuadros y etiquetas sobre el frame."""
        for d in detecciones:
            color = (40, 200, 80) if d["resultado"] == "concedido" else (30, 30, 220)
            cv2.rectangle(frame_bgr,
                          (d["left"], d["top"]),
                          (d["right"], d["bottom"]),
                          color, 2)
            label = f"{d['nombre']}  [{d['codigo']}]"
            cv2.rectangle(frame_bgr,
                          (d["left"], d["bottom"] - 28),
                          (d["right"], d["bottom"]),
                          color, cv2.FILLED)
            cv2.putText(frame_bgr, label,
                        (d["left"] + 6, d["bottom"] - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        return frame_bgr


# ── Loop principal de reconocimiento ────────────────────────

def iniciar_camara(reconocedor: Reconocedor, callback_acceso=None):
    """
    Abre la cámara y corre el loop de reconocimiento.
    callback_acceso(deteccion: dict) → llamado 1 vez por rostro identificado.
    Presiona Q para salir.
    """
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    print("Cámara activa · presiona Q para salir")
    frame_count   = 0
    PROCESS_EVERY = 5   # procesar 1 de cada 5 frames
    ultimas_detecciones = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        if frame_count % PROCESS_EVERY == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            ultimas_detecciones = reconocedor.identificar(rgb)

            if callback_acceso:
                for d in ultimas_detecciones:
                    callback_acceso(d, frame)

        frame = reconocedor.dibujar_resultado(frame, ultimas_detecciones)
        cv2.imshow("Sistema de Acceso Universitario", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


# ── Guardar frame de auditoría ───────────────────────────────

def guardar_captura(frame_bgr: np.ndarray) -> str:
    """Guarda el frame en la carpeta de capturas y retorna la ruta."""
    nombre = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".jpg"
    ruta   = os.path.join(CAPTURES_DIR, nombre)
    cv2.imwrite(ruta, frame_bgr)
    return ruta
