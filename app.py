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
# CARGA DE MODELOS ML CON DIAGNÓSTICO
# =========================================================
PREFIJOS_METRICAS = {
    "GOLES_FAVOR": "goles_local",
    "GOLES_CONTRA": "goles_visitante",
    "REMATES_TOTALES": "remates_totales",
    "REMATES_PUERTA": "remates_puerta",
    "PARADAS": "paradas",
    "CORNERS": "corners",
    "TARJETAS": "tarjetas",
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
    
    st.sidebar.markdown("### 🔍 Diagnóstico ML")
    st.sidebar.write(f"¿Carpeta 'models' existe? {os.path.exists(carpeta)}")
    
    if not os.path.exists(carpeta):
        st.sidebar.error("No existe carpeta 'models'")
        return modelos
    
    archivos = [f for f in os.listdir(carpeta) if f.endswith(".pkl")]
    st.sidebar.write(f"Archivos .pkl: {archivos}")
    
    if not archivos:
        st.sidebar.error("No hay archivos .pkl")
        return modelos
    
    for archivo in archivos:
        ruta = os.path.join(carpeta, archivo)
        st.sidebar.write(f"---\nAnalizando: {archivo}")
        
        try:
            obj = joblib.load(ruta)
            st.sidebar.write(f"Tipo: {type(obj).__name__}")
            
            if isinstance(obj, dict):
                claves = list(obj.keys())
                st.sidebar.write(f"Claves del diccionario: {claves}")
                
                for clave, valor in obj.items():
                    if hasattr(valor, 'predict'):
                        clave_upper = clave.upper()
                        if "GOLES_FAVOR" in clave_upper:
                            modelos.setdefault("goles_local", []).append(valor)
                            st.sidebar.success(f"  → goles_local")
                        elif "GOLES_CONTRA" in clave_upper:
                            modelos.setdefault("goles_visitante", []).append(valor)
                            st.sidebar.success(f"  → goles_visitante")
                        elif "REMATES_TOTALES" in clave_upper:
                            modelos.setdefault("remates_totales", []).append(valor)
                            st.sidebar.success(f"  → remates_totales")
                        elif "REMATES_PUERTA" in clave_upper:
                            modelos.setdefault("remates_puerta", []).append(valor)
                            st.sidebar.success(f"  → remates_puerta")
                        elif "PARADAS" in clave_upper:
                            modelos.setdefault("paradas", []).append(valor)
                            st.sidebar.success(f"  → paradas")
                        elif "CORNERS" in clave_upper:
                            modelos.setdefault("corners", []).append(valor)
                            st.sidebar.success(f"  → corners")
                        elif "TARJETAS" in clave_upper:
                            modelos.setdefault("tarjetas", []).append(valor)
                            st.sidebar.success(f"  → tarjetas")
                        else:
                            modelos.setdefault("goles_local", []).append(valor)
                            st.sidebar.success(f"  → goles_local (default)")
                    elif isinstance(valor, list):
                        for item in valor:
                            if hasattr(item, 'predict'):
                                modelos.setdefault("goles_local", []).append(item)
                                st.sidebar.success(f"  → modelo desde lista")
            elif hasattr(obj, 'predict'):
                modelos.setdefault("goles_local", []).append(obj)
                st.sidebar.success(f"Modelo directo → goles_local")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")
    
    total = sum(len(v) for v in modelos.values())
    st.sidebar.markdown("---")
    st.sidebar.write(f"Total modelos cargados: {total}")
    if total > 0:
        st.sidebar.success(f"✅ ML ACTIVO: {list(modelos.keys())}")
    else:
        st.sidebar.warning("⚠️ Sin modelos ML - Usando solo métricas")
    
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
    
    feats = {"ES_LOCAL": 1 if es_local else 0, "JORNADA": jornada, "POSICION_RIVAL": pos_rival if pos_rival else 10}
    
    for nombre_feat, col_sheet in col_map.items():
        for ventana in [3, 5, 10]:
            feats[f"{nombre_feat}_MA{ventana}"] = calcular_ma(df_hist, col_sheet, ventana)
    
    return feats

def predecir_ml(modelos_ml, feats_local, feats_visit):
    if not modelos_ml:
        return None
    
    resultados = {}
    metricas_local = {
        "goles_local": feats_local,
        "remates_totales": feats_local,
        "remates_puerta": feats_local,
        "paradas": feats_local,
        "corners": feats_local,
        "tarjetas": feats_local,
    }
    metricas_visit = {"goles_visitante": feats_visit}
    todas = {**metricas_local, **metricas_visit}
    
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

def combinar_metrica_ml(metricas_metrica, pred_ml, jornada):
    if pred_ml is None:
        return metricas_metrica, False
    
    if jornada <= 5:
        w_met, w_ml = 0.8, 0.2
    elif jornada <= 10:
        w_met, w_ml = 0.7, 0.3
    elif jornada <= 20:
        w_met, w_ml = 0.6, 0.4
    elif jornada <= 30:
        w_met, w_ml = 0.5, 0.5
    else:
        w_met, w_ml = 0.4, 0.6
    
    final = {}
    clave_map = {
        "goles_local": "goles_local",
        "goles_visitante": "goles_visitante",
        "goles_partido": "goles_partido",
        "remates_totales": "remates_totales_local",
        "remates_totales_partido": "remates_totales_partido",
        "remates_puerta": "remates_puerta_local",
        "remates_puerta_partido": "remates_puerta_partido",
        "paradas": "paradas_local",
        "paradas_partido": "paradas_partido",
        "corners": "corners_local",
        "corners_partido": "corners_partido",
        "tarjetas": "tarjetas_local",
        "tarjetas_partido": "tarjetas_partido",
    }
    
    for k_met, v_met in metricas_metrica.items():
        ml_val = None
        for k_ml, k_met2 in clave_map.items():
            if k_met2 == k_met and k_ml in pred_ml:
                ml_val = pred_ml[k_ml]
                break
        if ml_val is not None:
            final[k_met] = w_met * v_met + w_ml * ml_val
        else:
            final[k_met] = v_met
    
    return final, True

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

st.markdown("<h2 style='text-align: center;'>⚽ ANALIZADOR DE PARTIDOS PRO</h2>", unsafe_allow_html=True)

modelos_ml = cargar_modelos_ml()

try:
    sh_ligas = client.open_by_key(ID_CONTROL).worksheet("LIGAS")
    df_ligas = pd.DataFrame(sh_ligas.get_all_records())
    
    with st.expander("🔧 DIAGNÓSTICO - Hoja LIGAS"):
        st.dataframe(df_ligas)
    
    mask_historico = df_ligas['Nombre de la liga'].str.upper().str.contains('HISTORICO|HISTÓRICO', na=False)
    df_historico = df_ligas[mask_historico]
    df_competiciones = df_ligas[~mask_historico]
    
    id_historico = None
    if not df_historico.empty:
        id_historico = str(df_historico.iloc[0]['ID del libro']).strip()
    
    if df_competiciones.empty:
        st.error("No hay competiciones disponibles")
        st.stop()
    
    col1, col2 = st.columns(2)
    liga_sel = col1.selectbox("Seleccionar Liga", df_competiciones['Nombre de la liga'].tolist())
    jor_sel = col2.selectbox("Jornada", list(range(1, 45)))
    
    id_actual = df_competiciones[df_competiciones['Nombre de la liga'] == liga_sel]['ID del libro'].values[0]
    
    cache_key = f"pestanas_{id_actual}"
    if cache_key not in st.session_state:
        libro_temp = client.open_by_key(id_actual)
        excluir = ["config", "partido a analizar", "predicciones"]
        st.session_state[cache_key] = [s.title for s in libro_temp.worksheets() if s.title.lower() not in [e.lower() for e in excluir]]
    
    pestanas = st.session_state[cache_key]
    locales = [t for t in pestanas if "LOCAL" in t.upper()]
    visitantes = [t for t in pestanas if "VISITANTE" in t.upper()]
    
    def clean(n):
        return n.replace(" LOCAL", "").replace(" VISITANTE", "").strip()
    
    cl, cv = st.columns(2)
    eq_l = cl.selectbox("Equipo Local", locales, format_func=clean)
    visitantes_filtrados = [v for v in visitantes if clean(eq_l).upper() not in v.upper()]
    eq_v = cv.selectbox("Equipo Visitante", visitantes_filtrados, format_func=clean)
    
    if st.button("GENERAR ANALISIS"):
        st.divider()
        st.info("Analisis generado correctamente. Revisa el sidebar para ver el diagnostico ML.")
        
except Exception as e:
    st.error(f"Error: {e}")
