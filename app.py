import pandas as pd
import xgboost as xgb
from datetime import datetime

# --- CONFIGURACIÓN DE PESOS [cite: 95-99, 162-166] ---
PESOS_BLOQUES = [0.10, 0.40, 0.15, 0.25, 0.10]

def motor_prediccion_pro(jornada, bloques_l, bloques_v, datos_ml, df_historico):
    """
    Cerebro integral que combina Rama Métrica y ML.
    """
    
    # 1. CÁLCULO RAMA 1: MÉTRICA PURA [cite: 9, 73]
    def calcular_bloque(datos, j):
        if not datos: return 0
        # Limpiador de Ruido desde J14: elimina 2 celdas (Max y Min) [cite: 105-106]
        if j >= 14 and len(datos) >= 3:
            datos = sorted(datos)[1:-1]
        return sum(datos) / len(datos)

    goles_m_l = sum(calcular_bloque(bloques_l[i], jornada) * PESOS_BLOQUES[i] for i in range(5))
    goles_m_v = sum(calcular_bloque(bloques_v[i], jornada) * PESOS_BLOQUES[i] for i in range(5))

    # 2. CÁLCULO RAMA 2: ML (XGBOOST) [cite: 10, 110]
    # Se asume que el modelo ya está cargado y entrenado
    # pred_ml = modelo_xgb.predict(datos_ml) 
    goles_ml_l, goles_ml_v = 1.5, 1.2  # REEMPLAZAR con la salida real de tu modelo XGBoost

    # 3. COMBINACIÓN DINÁMICA POR JORNADAS [cite: 162-166]
    if 1 <= jornada <= 5: m_p, ml_p = 0.20, 0.80
    elif 6 <= jornada <= 10: m_p, ml_p = 0.30, 0.70
    elif 11 <= jornada <= 14: m_p, ml_p = 0.40, 0.60
    elif 15 <= jornada <= 20: m_p, ml_p = 0.50, 0.50
    elif 21 <= jornada <= 30: m_p, ml_p = 0.60, 0.40
    else: m_p, ml_p = 0.65, 0.35

    goles_f_l = (goles_m_l * m_p) + (goles_ml_l * ml_p)
    goles_f_v = (goles_m_v * m_p) + (goles_ml_v * ml_p)

    # 4. GESTIÓN DEL LIBRO HISTÓRICO Y CONTADOR [cite: 116, 125-127]
    fecha_hoy = datetime.now().strftime('%d/%m/%Y')
    
    # Check de existencia para el contador [cite: 126-127]
    existe = df_historico[
        (df_historico['JORNADA'] == jornada) & 
        (df_historico['FECHA'] == fecha_hoy)
    ]

    if not existe.empty:
        # Aumenta el contador [cite: 127]
        df_historico.loc[existe.index[0], 'CONTADOR PREDICCION'] += 1
    else:
        # Registra nueva predicción [cite: 127, 131-158]
        nueva_fila = {
            'COMPETICCIÓN': 'LALIGA 25/26',
            'FECHA': fecha_hoy,
            'JORNADA': jornada,
            'GOLES LOCAL': round(goles_f_l, 2),
            'GOLES VISITANTE': round(goles_f_v, 2),
            'CONTADOR PREDICCION': 1
        }
        df_historico = pd.concat([df_historico, pd.DataFrame([nueva_fila])], ignore_index=True)

    return round(goles_f_l, 2), round(goles_f_v, 2), df_historico
