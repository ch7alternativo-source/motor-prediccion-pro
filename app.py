import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
from math import exp, factorial
import re
import os
import joblib

st.set_page_config(page_title="Analizador de Partidos PRO", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)
ID_CONTROL = "1E0oz34jM0-kAyh_XUVwRrI_wy2VK3Rmr9ExgxbkLXSA"

# =========================================================
# AUTENTICACIÓN (original de tu app)
# =========================================================
def check_user(user_in, pass_in):
    try:
        sh = client.open_by_key(ID_CONTROL).worksheet("Sheet1")
        data = sh.get_all_values()
        for fila in data:
            u_excel = str(fila[0]).strip()
            p_excel = str(fila[1]).strip().replace(".0", "")
            if u_excel == str(user_in).strip() and p_excel == str(pass_in).strip():
                return True
        return False
    except:
        return False

if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.markdown("<h2 style='text-align: center;'>🔐 Acceso al Sistema</h2>", unsafe_allow_html=True)
    with st.form("login"):
        u = st.text_input("Usuario:")
        p = st.text_input("Contraseña:", type="password")
        if st.form_submit_button("Entrar"):
            if check_user(u, p):
                st.session_state['autenticado'] = True
                st.rerun()
            else:
                st.error("Datos incorrectos")
    st.stop()

# =========================================================
# CARGA DE MODELOS ML
# =========================================================
PREFIJOS_METRICAS = {
    "GOLES_FAVOR": "goles_local",
    "GOLES_CONTRA": "goles_visitante",
    "REMATES_TOTALES": "remates_totales",
    "REMATES_PUERTA": "remates_puerta",
    "PARADAS": "paradas",
    "CORNERS": "corners",
    "TARJETAS": "tarjetas"
}

FEATURES_MODELO = [
    "ES_LOCAL", "JORNADA", "POSICION_RIVAL",
    "GOLES_FAVOR_MA3", "GOLES_CONTRA_MA3", "REMATES_TOTALES_MA3",
    "REMATES_PUERTA_MA3", "PARADAS_MA3", "CORNERS_MA3", "TARJETAS_MA3",
    "GOLES_FAVOR_MA5", "GOLES_CONTRA_MA5", "REMATES_TOTALES_MA5",
    "REMATES_PUERTA_MA5", "PARADAS_MA5", "CORNERS_MA5", "TARJETAS_MA5",
    "GOLES_FAVOR_MA10", "GOLES_CONTRA_MA10", "REMATES_TOTALES_MA10",
    "REMATES_PUERTA_MA10", "PARADAS_MA10", "CORNERS_MA10", "TARJETAS_MA10",
]

@st.cache_resource
def cargar_modelos_ml():
    modelos = {}
    carpeta = "models"
    if not os.path.exists(carpeta):
        return modelos
    archivos = [f for f in os.listdir(carpeta) if f.endswith(".pkl")]
    for archivo in archivos:
        ruta = os.path.join(carpeta, archivo)
        nombre = archivo.replace(".pkl", "")
        try:
            obj = joblib.load(ruta)
            if isinstance(obj, dict):
                for clave, valor in obj.items():
                    metrica_interna = PREFIJOS_METRICAS.get(clave.upper())
                    if not metrica_interna:
                        continue
                    if isinstance(valor, list):
                        for item in valor:
                            if isinstance(item, dict) and "modelo" in item:
                                modelos.setdefault(metrica_interna, []).append(item["modelo"])
                            elif hasattr(item, 'predict'):
                                modelos.setdefault(metrica_interna, []).append(item)
                    elif hasattr(valor, 'predict'):
                        modelos.setdefault(metrica_interna, []).append(valor)
            elif hasattr(obj, 'predict'):
                nombre_upper = nombre.upper()
                for prefijo, metrica_interna in PREFIJOS_METRICAS.items():
                    if nombre_upper.startswith(prefijo):
                        modelos.setdefault(metrica_interna, []).append(obj)
                        break
        except Exception:
            pass
    return modelos

def calcular_ma(df, col, ventana):
    if col not in df.columns or df.empty:
        return 0.0
    valores = df[col].dropna().tolist()
    if not valores:
        return 0.0
    return float(np.mean(valores[-ventana:]))

def construir_features_ml(df_local, df_visit, es_local, jornada, pos_rival):
    col_map = {
        "GOLES_FAVOR": "GOL FAVOR",
        "GOLES_CONTRA": "GOL CONTRA",
        "REMATES_TOTALES": "REMATES TOTALES FAVOR",
        "REMATES_PUERTA": "REMATES PUERTA FAVOR",
        "PARADAS": "PARADAS FAVOR",
        "CORNERS": "CORNERES FAVOR",
        "TARJETAS": "TARJETAS AMARILLAS FAVOR",
    }
    if not df_local.empty and not df_visit.empty:
        df_hist = pd.concat([df_local, df_visit]).sort_values("FECHA") if "FECHA" in df_local.columns else pd.concat([df_local, df_visit])
    elif not df_local.empty:
        df_hist = df_local
    elif not df_visit.empty:
        df_hist = df_visit
    else:
        df_hist = pd.DataFrame()
    feats = {
        "ES_LOCAL": 1 if es_local else 0,
        "JORNADA": jornada,
        "POSICION_RIVAL": pos_rival if pos_rival else 10,
    }
    for nombre_feat, col_sheet in col_map.items():
        for ventana in [3, 5, 10]:
            feats[f"{nombre_feat}_MA{ventana}"] = calcular_ma(df_hist, col_sheet, ventana)
    return feats

def predecir_ml(modelos_ml, feats_local, feats_visit):
    if not modelos_ml:
        return None
    resultados = {}
    todas = {
        "goles_local": feats_local,
        "remates_totales": feats_local,
        "remates_puerta": feats_local,
        "paradas": feats_local,
        "corners": feats_local,
        "tarjetas": feats_local,
        "goles_visitante": feats_visit
    }
    for metrica, feats in todas.items():
        lista_modelos = modelos_ml.get(metrica, [])
        if not lista_modelos:
            continue
        predicciones = []
        for modelo in lista_modelos:
            try:
                X = pd.DataFrame([feats])[FEATURES_MODELO].fillna(0)
                pred = modelo.predict(X)[0]
                predicciones.append(float(pred))
            except Exception:
                continue
        if predicciones:
            resultados[metrica] = float(np.mean(predicciones))
    pares = [
        ("goles_local", "goles_visitante", "goles_partido"),
        ("remates_totales", "remates_totales", "remates_totales_partido"),
        ("remates_puerta", "remates_puerta", "remates_puerta_partido"),
        ("paradas", "paradas", "paradas_partido"),
        ("corners", "corners", "corners_partido"),
        ("tarjetas", "tarjetas", "tarjetas_partido"),
    ]
    for k_loc, k_vis, k_partido in pares:
        v_loc = resultados.get(k_loc)
        v_vis = resultados.get(k_vis) if k_loc != k_vis else resultados.get("goles_visitante")
        if v_loc is not None and v_vis is not None:
            resultados[k_partido] = v_loc + v_vis
    return resultados if resultados else None

# =========================================================
# LÓGICA MATEMÁTICA Y POISSON
# =========================================================
def poisson_prob(lambda_val, k):
    if lambda_val <= 0:
        return 1.0 if k == 0 else 0.0
    return (exp(-lambda_val) * (lambda_val**k)) / factorial(k)

def calcular_probabilidades_poisson(media_local, media_visitante):
    p_local, p_empate, p_visitante = 0, 0, 0
    max_goles = 10
    prob_btts = 0
    prob_over15 = 0
    prob_over25 = 0
    for i in range(max_goles):
        for j in range(max_goles):
            prob = poisson_prob(media_local, i) * poisson_prob(media_visitante, j)
            if i > j:
                p_local += prob
            elif i == j:
                p_empate += prob
            else:
                p_visitante += prob
            if i > 0 and j > 0:
                prob_btts += prob
            if (i + j) > 1.5:
                prob_over15 += prob
            if (i + j) > 2.5:
                prob_over25 += prob
    return {
        "1": p_local,
        "X": p_empate,
        "2": p_visitante,
        "BTTS": prob_btts,
        "OVER15": prob_over15,
        "OVER25": prob_over25
    }

def get_data_from_sheet(sheet_name):
    try:
        sh = client.open_by_key(ID_CONTROL)
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error cargando hoja {sheet_name}: {e}")
        return pd.DataFrame()

def obtener_historico_equipo(df, equipo):
    if df.empty:
        return pd.DataFrame()
    return df[(df['LOCAL'] == equipo) | (df['VISITANTE'] == equipo)].copy()

# =========================================================
# CARGA DE DATOS Y MODELOS (post login)
# =========================================================
with st.spinner("Cargando cerebro del sistema..."):
    modelos_ml = cargar_modelos_ml()
    df_ligas = get_data_from_sheet("LIGAS")
    df_datos = get_data_from_sheet("DATOS")

st.sidebar.success("Conexión establecida y Modelos cargados")

# =========================================================
# INTERFAZ DE SELECCIÓN DE EQUIPOS
# =========================================================
st.title("⚽ Analizador de Partidos PRO")

if not df_ligas.empty:
    # Ajuste: si la columna se llama 'Nombre de la liga' o 'LIGA'
    if 'LIGA' in df_ligas.columns:
        ligas_disponibles = df_ligas['LIGA'].unique().tolist()
        col_equipo = 'EQUIPO'
    elif 'Nombre de la liga' in df_ligas.columns:
        ligas_disponibles = df_ligas['Nombre de la liga'].unique().tolist()
        col_equipo = 'Equipo'  # según tu estructura
    else:
        st.error("Formato de hoja LIGAS no reconocido")
        st.stop()
    
    liga_seleccionada = st.selectbox("Selecciona la Liga:", ligas_disponibles)
    
    # Filtrar equipos
    equipos_liga = df_ligas[df_ligas.iloc[:, 0] == liga_seleccionada][col_equipo].unique().tolist()
    
    col1, col2 = st.columns(2)
    with col1:
        local = st.selectbox("Equipo Local:", ["Seleccionar..."] + equipos_liga)
    with col2:
        visitante = st.selectbox("Equipo Visitante:", ["Seleccionar..."] + equipos_liga)

    jornada = st.number_input("Jornada Actual:", min_value=1, max_value=44, value=15)
    pos_rival_local = st.number_input("Posición en tabla del Visitante (para el Local):", 1, 22, 10)
    pos_rival_visit = st.number_input("Posición en tabla del Local (para el Visitante):", 1, 22, 10)

    if st.button("🚀 GENERAR ANÁLISIS PROFESIONAL"):
        if local == "Seleccionar..." or visitante == "Seleccionar..." or local == visitante:
            st.warning("Por favor, selecciona dos equipos diferentes.")
        else:
            hist_local = obtener_historico_equipo(df_datos, local)
            hist_visit = obtener_historico_equipo(df_datos, visitante)
            media_g_local = calcular_ma(hist_local, "GOL FAVOR", 5)
            media_g_visitante = calcular_ma(hist_visit, "GOL FAVOR", 5)
            f_loc = construir_features_ml(hist_local, pd.DataFrame(), True, jornada, pos_rival_local)
            f_vis = construir_features_ml(pd.DataFrame(), hist_visit, False, jornada, pos_rival_visit)
            preds_ml = predecir_ml(modelos_ml, f_loc, f_vis)
            st.session_state['resultados_analisis'] = {
                "media_g_local": media_g_local,
                "media_g_visitante": media_g_visitante,
                "preds_ml": preds_ml,
                "local": local,
                "visitante": visitante,
                "jornada": jornada
            }
            st.success("¡Análisis completado! Desliza hacia abajo.")

# =========================================================
# VISUALIZACIÓN DE RESULTADOS
# =========================================================
if 'resultados_analisis' in st.session_state:
    res = st.session_state['resultados_analisis']
    preds_ml = res['preds_ml']
    j = res['jornada']
    if j <= 5:
        w_math, w_ml = 0.20, 0.80
    elif j <= 10:
        w_math, w_ml = 0.30, 0.70
    elif j <= 14:
        w_math, w_ml = 0.40, 0.60
    elif j <= 20:
        w_math, w_ml = 0.50, 0.50
    elif j <= 30:
        w_math, w_ml = 0.60, 0.40
    else:
        w_math, w_ml = 0.65, 0.35
    st.divider()
    st.subheader(f"📊 Análisis: {res['local']} vs {res['visitante']}")
    if preds_ml:
        g_loc_final = (res['media_g_local'] * w_math) + (preds_ml.get('goles_local', 0) * w_ml)
        g_vis_final = (res['media_g_visitante'] * w_math) + (preds_ml.get('goles_visitante', 0) * w_ml)
    else:
        g_loc_final, g_vis_final = res['media_g_local'], res['media_g_visitante']
    probs = calcular_probabilidades_poisson(g_loc_final, g_vis_final)
    c1, c2, c3 = st.columns(3)
    c1.metric("Victoria Local (1)", f"{probs['1']:.1%}")
    c2.metric("Empate (X)", f"{probs['X']:.1%}")
    c3.metric("Victoria Visitante (2)", f"{probs['2']:.1%}")
    c4, c5, c6 = st.columns(3)
    c4.metric("Más de 1.5 Goles", f"{probs['OVER15']:.1%}")
    c5.metric("Más de 2.5 Goles", f"{probs['OVER25']:.1%}")
    c6.metric("Ambos Marcan (BTTS)", f"{probs['BTTS']:.1%}")
    st.write("### 📈 Proyecciones Detalladas (ML + Stats)")
    if preds_ml:
        metrics_data = {
            "Métrica": ["Goles", "Remates Totales", "Remates a Puerta", "Paradas", "Córners", "Tarjetas"],
            "Local": [
                f"{g_loc_final:.2f}",
                f"{preds_ml.get('remates_totales', 0)/2:.2f}",
                f"{preds_ml.get('remates_puerta', 0)/2:.2f}",
                f"{preds_ml.get('paradas', 0)/2:.2f}",
                f"{preds_ml.get('corners', 0)/2:.2f}",
                f"{preds_ml.get('tarjetas', 0)/2:.2f}"
            ],
            "Visitante": [
                f"{g_vis_final:.2f}",
                f"{preds_ml.get('remates_totales', 0)/2:.2f}",
                f"{preds_ml.get('remates_puerta', 0)/2:.2f}",
                f"{preds_ml.get('paradas', 0)/2:.2f}",
                f"{preds_ml.get('corners', 0)/2:.2f}",
                f"{preds_ml.get('tarjetas', 0)/2:.2f}"
            ],
            "Total Partido": [
                f"{g_loc_final + g_vis_final:.2f}",
                f"{preds_ml.get('remates_totales_partido', 0):.2f}",
                f"{preds_ml.get('remates_puerta_partido', 0):.2f}",
                f"{preds_ml.get('paradas_partido', 0):.2f}",
                f"{preds_ml.get('corners_partido', 0):.2f}",
                f"{preds_ml.get('tarjetas_partido', 0):.2f}"
            ]
        }
        st.table(pd.DataFrame(metrics_data))
    else:
        st.info("No hay modelos ML disponibles para mostrar proyecciones detalladas. Se muestran solo datos matemáticos.")
