# models/prediccion_afluencia.py
# ============================================================
#  Predicción de Afluencia con Random Forest
#  Usa historial de accesos de MySQL para entrenar el modelo
# ============================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
from database.db import get_conn

# ── Intentar importar sklearn ────────────────────────────────
try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, r2_score
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False


# ── Obtener datos históricos ─────────────────────────────────

def obtener_accesos_historicos(dias: int = 60) -> list:
    """Obtiene accesos de los últimos N días agrupados por hora y día."""
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT
            HOUR(accedido_at)        AS hora,
            DAYOFWEEK(accedido_at)   AS dia_semana,
            DAYNAME(accedido_at)     AS nombre_dia,
            DATE(accedido_at)        AS fecha,
            COUNT(*)                 AS total
        FROM accesos
        WHERE accedido_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
          AND resultado = 'concedido'
        GROUP BY fecha, hora, dia_semana, nombre_dia
        ORDER BY fecha, hora
    """, (dias,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows


# ── Preparar datos para el modelo ───────────────────────────

def preparar_datos(datos: list):
    """
    Convierte los registros en features para Random Forest.
    Features: [hora, dia_semana, es_manana, es_tarde, es_noche]
    Target: total de accesos
    """
    X, y = [], []
    for row in datos:
        hora       = row['hora']
        dia_semana = row['dia_semana']
        es_manana  = 1 if 6 <= hora < 12 else 0
        es_tarde   = 1 if 12 <= hora < 18 else 0
        es_noche   = 1 if 18 <= hora < 22 else 0
        es_semana  = 1 if dia_semana <= 5 else 0
        X.append([hora, dia_semana, es_manana, es_tarde, es_noche, es_semana])
        y.append(row['total'])
    return np.array(X), np.array(y)


# ── Entrenar modelo Random Forest ───────────────────────────

def entrenar_modelo(datos: list):
    """Entrena un Random Forest con los datos históricos."""
    if not SKLEARN_OK:
        return None, None

    X, y = preparar_datos(datos)
    if len(X) < 10:
        return None, None

    modelo = RandomForestRegressor(
        n_estimators=100,
        max_depth=8,
        random_state=42,
        n_jobs=-1
    )
    modelo.fit(X, y)

    # Métricas si hay suficientes datos
    metricas = {}
    if len(X) >= 20:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        m2 = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42, n_jobs=-1)
        m2.fit(X_train, y_train)
        pred = m2.predict(X_test)
        metricas['mae']  = round(float(mean_absolute_error(y_test, pred)), 2)
        metricas['r2']   = round(float(r2_score(y_test, pred)), 4)
        metricas['rmse'] = round(float(np.sqrt(np.mean((y_test - pred)**2))), 2)

    return modelo, metricas


# ── Predecir próximas horas ──────────────────────────────────

def predecir_proximas_horas(modelo, horas_adelante: int = 6) -> list:
    """Predice la afluencia para las próximas N horas usando el modelo RF."""
    ahora = datetime.now()
    predicciones = []

    for i in range(horas_adelante):
        dt         = ahora + timedelta(hours=i)
        hora       = dt.hour
        dia_semana = dt.isoweekday()  # 1=Lun, 7=Dom
        es_manana  = 1 if 6 <= hora < 12 else 0
        es_tarde   = 1 if 12 <= hora < 18 else 0
        es_noche   = 1 if 18 <= hora < 22 else 0
        es_semana  = 1 if dia_semana <= 5 else 0

        features = np.array([[hora, dia_semana, es_manana, es_tarde, es_noche, es_semana]])

        if modelo is not None:
            estimado = max(0, int(round(float(modelo.predict(features)[0]))))
        else:
            estimado = 0

        if estimado >= 15:   nivel = 'Alta'
        elif estimado >= 8:  nivel = 'Media'
        elif estimado >= 2:  nivel = 'Baja'
        else:                nivel = 'Mínima'

        predicciones.append({
            'hora':     f"{hora:02d}:00",
            'estimado': estimado,
            'nivel':    nivel,
        })

    return predicciones


# ── Horas pico por día ───────────────────────────────────────

def calcular_horas_pico(datos: list, top_n: int = 3) -> dict:
    """Calcula las N horas con más accesos por día de la semana."""
    por_dia = defaultdict(lambda: defaultdict(list))
    for row in datos:
        por_dia[row['nombre_dia']][row['hora']].append(row['total'])

    dias_orden = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    nombres_es = {
        'Monday':'Lunes','Tuesday':'Martes','Wednesday':'Miércoles',
        'Thursday':'Jueves','Friday':'Viernes','Saturday':'Sábado','Sunday':'Domingo'
    }

    resultado = {}
    for dia in dias_orden:
        if dia in por_dia:
            promedios = {h: sum(v)/len(v) for h, v in por_dia[dia].items()}
            top = sorted(promedios.items(), key=lambda x: x[1], reverse=True)[:top_n]
            resultado[nombres_es.get(dia, dia)] = [(h, round(v)) for h, v in top]

    return resultado


# ── Importancia de variables ─────────────────────────────────

def importancia_variables(modelo) -> list:
    """Devuelve la importancia de cada feature del modelo."""
    nombres = ['Hora del día', 'Día de semana', 'Es mañana', 'Es tarde', 'Es noche', 'Es día hábil']
    if modelo is None or not hasattr(modelo, 'feature_importances_'):
        return []
    importancias = modelo.feature_importances_
    resultado = sorted(
        [{'variable': n, 'importancia': round(float(i)*100, 1)} for n, i in zip(nombres, importancias)],
        key=lambda x: x['importancia'], reverse=True
    )
    return resultado


# ── Resumen completo ─────────────────────────────────────────

def resumen_prediccion(dias: int = 60) -> dict:
    """Genera el resumen completo con modelo Random Forest."""
    datos      = obtener_accesos_historicos(dias)
    modelo, metricas = entrenar_modelo(datos)
    horas_pico = calcular_horas_pico(datos)
    proximas   = predecir_proximas_horas(modelo, horas_adelante=6)
    importancia = importancia_variables(modelo)

    # Recomendaciones automáticas
    recomendaciones = []
    if metricas:
        r2 = metricas.get('r2', 0)
        if r2 >= 0.75:
            recomendaciones.append('El modelo tiene alta confiabilidad para predecir afluencia.')
        elif r2 >= 0.50:
            recomendaciones.append('El modelo es aceptable. Mejorará con más datos históricos.')
        else:
            recomendaciones.append('Se necesitan más datos históricos para mejorar la predicción.')

    hora_pico_hoy = None
    dia_actual = datetime.now().strftime('%A')
    nombres_es = {'Monday':'Lunes','Tuesday':'Martes','Wednesday':'Miércoles',
                  'Thursday':'Jueves','Friday':'Viernes','Saturday':'Sábado','Sunday':'Domingo'}
    dia_es = nombres_es.get(dia_actual, dia_actual)
    if dia_es in horas_pico and horas_pico[dia_es]:
        hora_pico_hoy = f"{horas_pico[dia_es][0][0]:02d}:00"
        recomendaciones.append(f'Hoy se espera mayor afluencia alrededor de las {hora_pico_hoy}.')

    return {
        'modelo':                      'Random Forest' if SKLEARN_OK else 'Promedio histórico',
        'sklearn_disponible':          SKLEARN_OK,
        'datos_analizados':            len(datos),
        'dias_analizados':             dias,
        'metricas_modelo':             metricas or {},
        'prediccion_proximas_horas':   proximas,
        'horas_pico_por_dia':          horas_pico,
        'importancia_variables':       importancia,
        'recomendaciones':             recomendaciones,
        'generado_en':                 datetime.now().isoformat(),
    }


if __name__ == '__main__':
    import json
    r = resumen_prediccion()
    print(json.dumps(r, ensure_ascii=False, indent=2))
