import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
from math import exp, factorial
import re
import os
import joblib
import traceback

st.set_page_config(page_title="Analizador de Partidos PRO", layout="wide")

# =========================================================
# CONEXIÓN A GOOGLE SHEETS CON CACHÉ
# =========================================================
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)
ID_CONTROL = "1E0oz34jM0-kAyh_XUVwRrI_wy2VK3Rmr9ExgxbkLXSA"

@st.cache_data(ttl=3600)
def get_data_from_sheet(sheet_name, worksheet_name=None):
    try:
        if worksheet_name:
            sh = client.open_by_key(sheet_name)
            ws = sh.worksheet(worksheet_name)
        else:
            sh = client.open_by_key(ID_CONTROL)
            ws = sh.worksheet(sheet_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error cargando {sheet_name}/{worksheet_name}: {e}")
        return pd.DataFrame()

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
    "TARJETAS": "tarjetas",
    "RESULTADO": "resultado",
    "OVER_1_5": "over_1_5",
    "OVER_2_5": "over_2_5",
    "BTTS": "btts",
}

FEATURES_MODELO_REFERENCIA = [
    "ES_LOCAL", "JORNADA", "DIF_POSICION",
    "GOLES_FAVOR_MA3", "GOLES_CONTRA_MA3", "REMATES_TOTALES_MA3",
    "REMATES_PUERTA_MA3", "PARADAS_MA3", "CORNERS_MA3", "TARJETAS_MA3",
    "GOLES_FAVOR_MA5", "GOLES_CONTRA_MA5", "REMATES_TOTALES_MA5",
    "REMATES_PUERTA_MA5", "PARADAS_MA5", "CORNERS_MA5", "TARJETAS_MA5",
    "GOLES_FAVOR_MA10", "GOLES_CONTRA_MA10", "REMATES_TOTALES_MA10",
    "REMATES_PUERTA_MA10", "PARADAS_MA10", "CORNERS_MA10", "TARJETAS_MA10",
]

def extraer_prefijo_modelo(nombre_archivo):
    nombre = nombre_archivo.replace(".pkl", "").upper()
    for prefijo in PREFIJOS_METRICAS.keys():
        if nombre.startswith(prefijo):
            return prefijo
        if f"_{prefijo}_" in nombre or f"_{prefijo}" in nombre:
            return prefijo
    return None

@st.cache_resource
def cargar_modelos_ml():
    modelos = {}
    carpeta = "models"
    st.sidebar.markdown("### 🔍 Diagnóstico ML")
    st.sidebar.write(f"📁 Carpeta: {carpeta}")
    st.sidebar.write(f"✅ ¿Existe? {os.path.exists(carpeta)}")
    if not os.path.exists(carpeta):
        st.sidebar.error("No se encontró la carpeta 'models'")
        return modelos
    archivos = [f for f in os.listdir(carpeta) if f.endswith(".pkl")]
    st.sidebar.write(f"📄 Archivos .pkl encontrados: {len(archivos)}")
    if not archivos:
        st.sidebar.error("No hay archivos .pkl en la carpeta")
        return modelos
    for archivo in archivos:
        ruta = os.path.join(carpeta, archivo)
        try:
            obj = joblib.load(ruta)
            prefijo = extraer_prefijo_modelo(archivo)
            if prefijo is None:
                st.sidebar.warning(f"⚠️ {archivo}: prefijo no reconocido")
                continue
            clave_base = PREFIJOS_METRICAS.get(prefijo)
            if clave_base is None:
                continue
            if hasattr(obj, 'predict'):
                modelos.setdefault(clave_base, []).append(obj)
                st.sidebar.success(f"✅ {archivo} → {clave_base}")
            else:
                st.sidebar.warning(f"⚠️ {archivo} no tiene .predict")
        except Exception as e:
            st.sidebar.error(f"❌ Error en {archivo}: {e}")
    total = sum(len(v) for v in modelos.values())
    st.sidebar.markdown("---")
    st.sidebar.write(f"**Total modelos cargados:** {total}")
    if total > 0:
        st.sidebar.success(f"✅ ML ACTIVO: {list(modelos.keys())}")
        st.sidebar.info("ℹ️ Los modelos usan solo las features con las que fueron entrenados.")
    else:
        st.sidebar.warning("⚠️ Sin modelos ML – usando solo rama métrica")
    return modelos

# =========================================================
# FUNCIONES AUXILIARES
# =========================================================
def calcular_ma(df, col, ventana):
    if col not in df.columns or df.empty:
        return 0.0
    valores = df[col].dropna().tolist()
    if not valores:
        return 0.0
    if len(valores) < ventana:
        return float(np.mean(valores))
    return float(np.mean(valores[-ventana:]))

def construir_features_ml(df_propio, df_rival, es_local, jornada, pos_propia, pos_rival):
    col_map = {
        "GOLES_FAVOR": "GOL FAVOR",
        "GOLES_CONTRA": "GOL CONTRA",
        "REMATES_TOTALES": "REMATES TOTALES FAVOR",
        "REMATES_PUERTA": "REMATES PUERTA FAVOR",
        "PARADAS": "PARADAS FAVOR",
        "CORNERS": "CORNERES FAVOR",
        "TARJETAS": "TARJETAS AMARILLAS FAVOR",
    }
    df_propio_filtrado = df_propio.copy() if not df_propio.empty else pd.DataFrame()
    df_rival_filtrado = df_rival.copy() if not df_rival.empty else pd.DataFrame()
    feats = {
        "ES_LOCAL": 1 if es_local else 0,
        "JORNADA": jornada,
        "DIF_POSICION": (pos_propia - pos_rival) if (pos_propia is not None and pos_rival is not None) else 0,
    }
    for nombre_feat, col_sheet in col_map.items():
        for ventana in (3, 5, 10):
            feats[f"{nombre_feat}_MA{ventana}"] = calcular_ma(df_propio_filtrado, col_sheet, ventana)
    for nombre_feat, col_sheet in col_map.items():
        for ventana in (3, 5, 10):
            feats[f"{nombre_feat}_MA{ventana}_RIVAL"] = calcular_ma(df_rival_filtrado, col_sheet, ventana)
    return feats

def predecir_ml(modelos_ml, feats_local, feats_visit):
    if not modelos_ml:
        return None
    resultados = {}
    mapeo_salida = {
        "goles_local": "goles_local",
        "goles_visitante": "goles_visitante",
        "remates_totales_local": "remates_totales",
        "remates_totales_visitante": "remates_totales",
        "remates_puerta_local": "remates_puerta",
        "remates_puerta_visitante": "remates_puerta",
        "paradas_local": "paradas",
        "paradas_visitante": "paradas",
        "corners_local": "corners",
        "corners_visitante": "corners",
        "tarjetas_local": "tarjetas",
        "tarjetas_visitante": "tarjetas",
    }
    datos_feats = {
        "goles_local": feats_local,
        "goles_visitante": feats_visit,
        "remates_totales_local": feats_local,
        "remates_totales_visitante": feats_visit,
        "remates_puerta_local": feats_local,
        "remates_puerta_visitante": feats_visit,
        "paradas_local": feats_local,
        "paradas_visitante": feats_visit,
        "corners_local": feats_local,
        "corners_visitante": feats_visit,
        "tarjetas_local": feats_local,
        "tarjetas_visitante": feats_visit,
    }
    if "ml_warning_shown" not in st.session_state:
        st.session_state.ml_warning_shown = False
    for clave_resultado, clave_modelo in mapeo_salida.items():
        lista_modelos = modelos_ml.get(clave_modelo, [])
        if not lista_modelos:
            continue
        feats = datos_feats[clave_resultado]
        predicciones = []
        for modelo in lista_modelos:
            try:
                X_full = pd.DataFrame([feats])
                if hasattr(modelo, "feature_names_in_"):
                    expected_cols = modelo.feature_names_in_
                    X = X_full.reindex(columns=expected_cols, fill_value=0)
                else:
                    X = X_full.reindex(columns=FEATURES_MODELO_REFERENCIA, fill_value=0)
                pred = modelo.predict(X)[0]
                predicciones.append(float(pred))
            except Exception as e:
                if not st.session_state.ml_warning_shown:
                    st.warning(f"Error en predicción {clave_modelo}: {e}")
                    st.session_state.ml_warning_shown = True
                continue
        if predicciones:
            resultados[clave_resultado] = float(np.median(predicciones))
    for base in ["goles", "remates_totales", "remates_puerta", "paradas", "corners", "tarjetas"]:
        kL = f"{base}_local"
        kV = f"{base}_visitante"
        if kL in resultados and kV in resultados:
            resultados[f"{base}_partido"] = resultados[kL] + resultados[kV]
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
    mapeo_directo = {
        "goles_local": "goles_local",
        "goles_visitante": "goles_visitante",
        "goles_partido": "goles_partido",
        "remates_totales_local": "remates_totales_local",
        "remates_totales_visitante": "remates_totales_visitante",
        "remates_totales_partido": "remates_totales_partido",
        "remates_puerta_local": "remates_puerta_local",
        "remates_puerta_visitante": "remates_puerta_visitante",
        "remates_puerta_partido": "remates_puerta_partido",
        "paradas_local": "paradas_local",
        "paradas_visitante": "paradas_visitante",
        "paradas_partido": "paradas_partido",
        "corners_local": "corners_local",
        "corners_visitante": "corners_visitante",
        "corners_partido": "corners_partido",
        "tarjetas_local": "tarjetas_local",
        "tarjetas_visitante": "tarjetas_visitante",
        "tarjetas_partido": "tarjetas_partido",
    }
    combinado = False
    for k_met, v_met in metricas_metrica.items():
        clave_ml = mapeo_directo.get(k_met)
        if clave_ml and clave_ml in pred_ml:
            final[k_met] = w_met * v_met + w_ml * pred_ml[clave_ml]
            combinado = True
        else:
            final[k_met] = v_met
    return final, combinado

# =========================================================
# AUTENTICACIÓN
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
    except Exception as e:
        st.error(f"Error de autenticación: {e}")
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
# CLASIFICACIÓN Y EQUIVALENCIAS (con caché)
# =========================================================
def obtener_clasificacion_desde_historico(id_libro_historico, nombre_pestana_clasificacion, jornada_buscada):
    try:
        libro_historico = client.open_by_key(id_libro_historico)
        ws_clasificacion = libro_historico.worksheet(nombre_pestana_clasificacion)
        data = ws_clasificacion.get_all_values()
        if not data or len(data) < 2:
            return pd.DataFrame()
        cabecera = data[0]
        col_jornada = None
        for idx, celda in enumerate(cabecera):
            celda_limpia = str(celda).strip()
            numeros = re.findall(r'\d+', celda_limpia)
            if numeros and int(numeros[0]) == int(jornada_buscada):
                col_jornada = idx
                break
        if col_jornada is None:
            return pd.DataFrame()
        clasificacion = []
        for fila in data[1:]:
            if len(fila) <= col_jornada:
                continue
            pos_raw = str(fila[0]).strip()
            equipo_raw = str(fila[col_jornada]).strip()
            if not pos_raw or not equipo_raw:
                continue
            try:
                pos_int = int(pos_raw)
            except ValueError:
                continue
            if equipo_raw.upper() in ("", "NONE", "N/A", "-"):
                continue
            clasificacion.append({"EQUIPO": equipo_raw.upper().strip(), "POS": pos_int})
        return pd.DataFrame(clasificacion) if clasificacion else pd.DataFrame()
    except Exception as e:
        st.warning(f"Error leyendo clasificación: {e}")
        return pd.DataFrame()

def cargar_equivalencias(id_libro_historico, nombre_pestana_equivalencias):
    try:
        libro_historico = client.open_by_key(id_libro_historico)
        ws_equiv = libro_historico.worksheet(nombre_pestana_equivalencias)
        data = ws_equiv.get_all_values()
        if not data or len(data) < 2:
            return pd.DataFrame()
        cabecera = data[0]
        filas = data[1:]
        return pd.DataFrame(filas, columns=cabecera if cabecera else None)
    except Exception as e:
        st.warning(f"Error cargando equivalencias: {e}")
        return pd.DataFrame()

def obtener_equivalencia_nombre(nombre_app, df_equivalencias):
    if df_equivalencias.empty:
        return nombre_app.upper().strip()
    nombre_buscar = nombre_app.upper().strip()
    pares = []
    for _, row in df_equivalencias.iterrows():
        col_a = str(row.iloc[0]).upper().strip() if pd.notna(row.iloc[0]) else ""
        col_b = str(row.iloc[1]).upper().strip() if pd.notna(row.iloc[1]) else ""
        if col_a or col_b:
            pares.append((col_a, col_b))
    for col_a, col_b in pares:
        if col_a == nombre_buscar and col_b:
            return col_b
    for col_a, col_b in pares:
        if col_a and col_a in nombre_buscar and col_b:
            return col_b
    for col_a, col_b in pares:
        if col_b and nombre_buscar in col_b and col_b:
            return col_b
    for col_a, col_b in pares:
        if col_b and col_b in nombre_buscar and col_b:
            return col_b
    return nombre_buscar

# =========================================================
# DETECCIÓN DE COLUMNAS (CON NORMALIZACIÓN UNICODE Y PATRONES AMPLIADOS)
# =========================================================
def detectar_columna(df, palabras_clave):
    for col in df.columns.tolist():
        col_lower = col.lower()
        for palabra in palabras_clave:
            if palabra.lower() in col_lower:
                return col
    return None

def mapear_columnas(df):
    mapeo = {}
    columnas_buscar = {
        "GOL FAVOR": [
            "gol favor", "goles favor", "gf", "goles_marcados",
            "gol local", "goles local", "goles locales", "goles a favor", "gf local"
        ],
        "GOL CONTRA": [
            "gol contra", "goles contra", "gc", "goles_recibidos",
            "gol visitante", "goles visitante", "goles visitantes", "goles en contra", "gc visitante"
        ],
        "REMATES TOTALES FAVOR": [
            "remates totales favor", "remates totales f", "total shots for", "remates favor",
            "remates totales local", "remates totales locales", "total shots local"
        ],
        "REMATES TOTALES CONTRA": [
            "remates totales contra", "remates totales c", "total shots against", "remates contra",
            "remates totales visitante", "remates totales visitantes", "total shots visitante"
        ],
        "REMATES PUERTA FAVOR": [
            "remates puerta favor", "remates a puerta favor", "remates puerta f", "shots on target for",
            "remates puerta local", "remates a puerta local", "shots on target local",
            "tiros a puerta local", "tiros a puerta favor", "shots on target", "tiros a puerta",
            "remates a puerta", "remates al arco", "remates al arco local", "tiros portería local",
            "sot local", "sot favor", "remates al arco favor",
            "rematrs puerta favor", "rematrs puerta local", "rematrs a puerta favor"
        ],
        "REMATES PUERTA CONTRA": [
            "remates puerta contra", "remates a puerta contra", "remates puerta c", "shots on target against",
            "remates puerta visitante", "remates a puerta visitante", "shots on target visitante",
            "tiros a puerta visitante", "tiros a puerta contra", "remates a puerta visitante",
            "sot visitante", "sot contra", "remates al arco visitante",
            "rematrs puerta contra", "rematrs puerta visitante", "rematrs a puerta contra"
        ],
        "PARADAS FAVOR": [
            "paradas favor", "paradas f", "saves for", "paradas realizadas",
            "paradas local", "paradas locales", "saves local"
        ],
        "PARADAS CONTRA": [
            "paradas contra", "paradas c", "saves against",
            "paradas visitante", "paradas visitantes", "saves visitante"
        ],
        "CORNERES FAVOR": [
            "corneres favor", "corners favor", "corner favor",
            "corneres local", "corners local", "córners local"
        ],
        "CORNERES CONTRA": [
            "corneres contra", "corners contra", "corner contra",
            "corneres visitante", "corners visitante", "córners visitante"
        ],
        "TARJETAS AMARILLAS FAVOR": [
            "tarjetas amarillas favor", "amarillas favor", "yellow cards for",
            "tarjetas amarillas local", "amarillas local"
        ],
        "TARJETAS AMARILLAS CONTRA": [
            "tarjetas amarillas contra", "amarillas contra", "yellow cards against",
            "tarjetas amarillas visitante", "amarillas visitante"
        ],
        "JORNADA": ["jornada", "jor", "round", "matchday"],
        "RIVAL": ["rival", "oponente", "equipo rival", "opponent"],
        "POSICION RIVAL": ["posicion rival", "posición rival", "pos rival"],
        "FECHA": ["fecha", "date", "fecha partido"],
    }
    for nombre_estandar, patrones in columnas_buscar.items():
        col_encontrada = detectar_columna(df, patrones)
        if col_encontrada:
            mapeo[col_encontrada] = nombre_estandar
    return mapeo

def normalizar_y_validar(df):
    if df.empty:
        return df
    # Normalizar espacios no-rompibles y otros caracteres de espacio
    df.columns = [' '.join(col.split()).strip().upper() for col in df.columns]
    mapeo = mapear_columnas(df)
    if mapeo:
        df = df.rename(columns=mapeo)
    # Segunda pasada: volver a limpiar por si el renombrado introdujo espacios raros
    df.columns = [' '.join(col.split()).strip().upper() for col in df.columns]
    columnas_numericas = [
        "GOL FAVOR", "GOL CONTRA", "REMATES TOTALES FAVOR", "REMATES TOTALES CONTRA",
        "REMATES PUERTA FAVOR", "REMATES PUERTA CONTRA", "PARADAS FAVOR", "PARADAS CONTRA",
        "CORNERES FAVOR", "CORNERES CONTRA", "TARJETAS AMARILLAS FAVOR", "TARJETAS AMARILLAS CONTRA",
        "JORNADA", "POSICION RIVAL"
    ]
    for col in columnas_numericas:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')
        else:
            if col not in st.session_state.get("faltantes", set()):
                st.session_state.setdefault("faltantes", set()).add(col)
                st.warning(f"⚠️ Columna '{col}' no encontrada en los datos. Se usará valor 0 por defecto.")
    if "FECHA" in df.columns:
        df["FECHA"] = pd.to_datetime(df["FECHA"], errors='coerce', dayfirst=True)
        df = df.dropna(subset=["FECHA"])
        df = df.sort_values("FECHA")
    if "JORNADA" in df.columns:
        df = df.dropna(subset=["JORNADA"])
        df["JORNADA"] = df["JORNADA"].astype(int)
    if "RIVAL" in df.columns:
        df["RIVAL"] = df["RIVAL"].astype(str).str.upper().str.strip()
    return df

def cargar_pestana_equipo(ws):
    try:
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if df.empty or len(df.columns) == 0:
            return pd.DataFrame()
        df = normalizar_y_validar(df)
        return df
    except Exception as e:
        st.warning(f"Error cargando pestaña: {e}\n{traceback.format_exc()}")
        return pd.DataFrame()

def filtrar_bloque(df, tipo, grupo=None):
    if df.empty:
        return df
    if tipo == 1:
        return df.copy()
    if tipo == 2:
        return df[df["JORNADA"] >= 1].copy() if "JORNADA" in df.columns else df.copy()
    if tipo == 3:
        return df.tail(5).copy()
    if tipo == 4:
        return df.tail(3).copy()
    if tipo == 5:
        if grupo is not None and "POSICION RIVAL" in df.columns:
            return df[df["POSICION RIVAL"].isin(grupo)].copy()
    return df.copy()

def limpiar_ruido(lista):
    lista = [x for x in lista if pd.notna(x)]
    if len(lista) < 5:
        return lista
    lista = sorted(lista)
    return lista[1:-1]

def calcular_metricas(dfL, dfV, jornada):
    metricas = {}
    columnas_def = [
        ("GOL FAVOR", "GOL CONTRA", "goles"),
        ("REMATES TOTALES FAVOR", "REMATES TOTALES CONTRA", "remates_totales"),
        ("REMATES PUERTA FAVOR", "REMATES PUERTA CONTRA", "remates_puerta"),
        ("PARADAS FAVOR", "PARADAS CONTRA", "paradas"),
        ("CORNERES FAVOR", "CORNERES CONTRA", "corners"),
        ("TARJETAS AMARILLAS CONTRA", "TARJETAS AMARILLAS FAVOR", "tarjetas"),
    ]
    for colF, colC, nombre in columnas_def:
        tieneF_L = colF in dfL.columns
        tieneC_L = colC in dfL.columns
        tieneF_V = colF in dfV.columns
        tieneC_V = colC in dfV.columns
        if not (tieneF_L and tieneC_L and tieneF_V and tieneC_V):
            metricas[nombre + "_local"] = 0
            metricas[nombre + "_visitante"] = 0
            metricas[nombre + "_partido"] = 0
            continue
        try:
            lista_L_fav = dfL[colF].dropna().tolist()
            lista_V_contra = dfV[colC].dropna().tolist()
            if jornada >= 14:
                lista_L_fav = limpiar_ruido(lista_L_fav)
                lista_V_contra = limpiar_ruido(lista_V_contra)
            m_local = (np.mean(lista_L_fav) + np.mean(lista_V_contra)) / 2 if lista_L_fav and lista_V_contra else 0
            lista_V_fav = dfV[colF].dropna().tolist()
            lista_L_contra = dfL[colC].dropna().tolist()
            if jornada >= 14:
                lista_V_fav = limpiar_ruido(lista_V_fav)
                lista_L_contra = limpiar_ruido(lista_L_contra)
            m_visit = (np.mean(lista_V_fav) + np.mean(lista_L_contra)) / 2 if lista_V_fav and lista_L_contra else 0
            metricas[nombre + "_local"] = m_local
            metricas[nombre + "_visitante"] = m_visit
            metricas[nombre + "_partido"] = m_local + m_visit
        except Exception as e:
            st.warning(f"Error calculando métricas para {nombre}: {e}")
            metricas[nombre + "_local"] = 0
            metricas[nombre + "_visitante"] = 0
            metricas[nombre + "_partido"] = 0
    return metricas

def combinar_bloques(b1, b2, b3, b4, b5):
    final = {}
    for k in b1.keys():
        final[k] = (b1[k] * 0.10 + b2[k] * 0.40 + b3[k] * 0.15 + b4[k] * 0.25 + b5[k] * 0.10)
    return final

def poisson(lam, k):
    if lam <= 0:
        return 1 if k == 0 else 0
    try:
        return (lam**k * exp(-lam)) / factorial(k)
    except:
        return 0

def prob_1x2(gL, gV):
    max_g = 10
    pL = pE = pV = 0.0
    for i in range(max_g + 1):
        for j in range(max_g + 1):
            try:
                p = poisson(gL, i) * poisson(gV, j)
                if i > j:
                    pL += p
                elif i == j:
                    pE += p
                else:
                    pV += p
            except:
                continue
    total = pL + pE + pV
    if total > 0:
        pL /= total
        pE /= total
        pV /= total
    return pL, pE, pV

def grupo(pos):
    if 1 <= pos <= 4:
        return [1, 2, 3, 4]
    if 5 <= pos <= 10:
        return [5, 6, 7, 8, 9, 10]
    if 11 <= pos <= 16:
        return [11, 12, 13, 14, 15, 16]
    return list(range(17, 26))

# =========================================================
# INTERFAZ PRINCIPAL
# =========================================================
st.markdown("<h2 style='text-align: center;'>⚽ ANALIZADOR DE PARTIDOS PRO</h2>", unsafe_allow_html=True)

modelos_ml = cargar_modelos_ml()
n_modelos = sum(len(v) for v in modelos_ml.values())
hay_ml = n_modelos > 0

if hay_ml:
    st.sidebar.success(f"🤖 ML activo: {n_modelos} modelos cargados ({len(modelos_ml)} métricas)")
else:
    st.sidebar.info("Sin modelos ML. Usando solo rama métrica.")

try:
    df_ligas = get_data_from_sheet("LIGAS")
    if df_ligas.empty:
        st.error("No se pudo cargar la hoja LIGAS")
        st.stop()
    with st.expander("🔧 DIAGNÓSTICO - Hoja LIGAS"):
        st.dataframe(df_ligas)

    mask_historico = df_ligas['Nombre de la liga'].str.upper().str.contains('HISTORICO|HISTÓRICO', na=False)
    df_historico = df_ligas[mask_historico]
    df_competiciones = df_ligas[~mask_historico]

    id_historico = None
    if not df_historico.empty:
        id_historico = str(df_historico.iloc[0]['ID del libro']).strip()

    if df_competiciones.empty:
        st.error("No hay competiciones disponibles en la hoja LIGAS.")
        st.stop()

    col1, col2 = st.columns(2)
    liga_sel = col1.selectbox("🏆 Seleccionar Liga", df_competiciones['Nombre de la liga'].tolist())

    PESTANA_CLASIFICACION = "CLASIFICACION LALIGA 25/26"
    PESTANA_EQUIVALENCIAS = "EQUIVALENCIA NOMENCLATURA LALIGA25/26"

    id_actual = df_competiciones[df_competiciones['Nombre de la liga'] == liga_sel]['ID del libro'].values[0]
    jor_sel = col2.selectbox("📅 Jornada", list(range(1, 45)))

    cache_key = f"pestanas_{id_actual}"
    if cache_key not in st.session_state:
        libro_temp = client.open_by_key(id_actual)
        excluir = ["config", "partido a analizar", "predicciones"]
        st.session_state[cache_key] = [
            s.title for s in libro_temp.worksheets()
            if s.title.lower() not in [e.lower() for e in excluir]
        ]
    pestanas = st.session_state[cache_key]
    locales = [t for t in pestanas if "LOCAL" in t.upper()]
    visitantes = [t for t in pestanas if "VISITANTE" in t.upper()]

    def clean(n):
        return n.replace(" LOCAL", "").replace(" VISITANTE", "").strip()

    cl, cv = st.columns(2)
    eq_l = cl.selectbox("🏠 Equipo Local", locales, format_func=clean)
    visitantes_filtrados = [v for v in visitantes if clean(eq_l).upper() not in v.upper()]
    eq_v = cv.selectbox("🚀 Equipo Visitante", visitantes_filtrados, format_func=clean)

    # Selector de modo
    if "modo_prediccion" not in st.session_state:
        st.session_state.modo_prediccion = "Combinada (Métrica + ML)"
    opciones_modo = ["Métrica únicamente", "ML únicamente", "Combinada (Métrica + ML)"]
    modo = st.selectbox(
        "📊 Modo de predicción",
        opciones_modo,
        index=2,
        help="Métrica: solo reglas estadísticas. ML: solo modelos entrenados. Combinada: pesos dinámicos según jornada."
    )
    st.session_state.modo_prediccion = modo

    if st.button("📊 GENERAR ANÁLISIS"):
        st.divider()
        try:
            libro = client.open_by_key(id_actual)
            ws_local = libro.worksheet(eq_l)
            ws_visit = libro.worksheet(eq_v)

            df_local = cargar_pestana_equipo(ws_local)
            df_visit = cargar_pestana_equipo(ws_visit)

            with st.expander("🔧 Diagnóstico - Columnas encontradas en equipos"):
                st.write("**Columnas LOCAL:**", list(df_local.columns) if not df_local.empty else "Vacío")
                st.write("**Columnas VISITANTE:**", list(df_visit.columns) if not df_visit.empty else "Vacío")
                st.write(f"**Filas LOCAL:** {len(df_local)}")
                st.write(f"**Filas VISITANTE:** {len(df_visit)}")
                # Depuración adicional: mostrar primeras filas de la columna de remates si existe
                if "REMATES PUERTA FAVOR" in df_local.columns:
                    st.write("**Ejemplo valores REMATES PUERTA FAVOR:**", df_local["REMATES PUERTA FAVOR"].head(3).tolist())
                if "REMATES PUERTA CONTRA" in df_local.columns:
                    st.write("**Ejemplo valores REMATES PUERTA CONTRA:**", df_local["REMATES PUERTA CONTRA"].head(3).tolist())

            if df_local.empty or df_visit.empty:
                st.error("No se pudieron cargar los datos de los equipos.")
                st.stop()

            if not id_historico:
                st.error("No se encontró el ID del libro HISTÓRICO DE PREDICCIONES.")
                st.stop()

            jornada_clasificacion = jor_sel - 1
            if jornada_clasificacion < 1:
                st.error("No hay clasificación disponible para la Jornada 1.")
                st.stop()

            df_equivalencias = cargar_equivalencias(id_historico, PESTANA_EQUIVALENCIAS)
            clasif = obtener_clasificacion_desde_historico(id_historico, PESTANA_CLASIFICACION, jornada_clasificacion)

            if clasif.empty:
                st.error(f"No se pudo obtener la clasificación para la Jornada {jornada_clasificacion}.")
                st.stop()

            with st.expander("🔍 Clasificación obtenida (jornada histórica)"):
                st.write(f"**Jornada consultada:** {jornada_clasificacion}")
                st.dataframe(clasif, use_container_width=True)

            nombre_local_clean = clean(eq_l).upper()
            nombre_visit_clean = clean(eq_v).upper()
            nombre_local_clasif = obtener_equivalencia_nombre(nombre_local_clean, df_equivalencias)
            nombre_visit_clasif = obtener_equivalencia_nombre(nombre_visit_clean, df_equivalencias)

            local_info = clasif[clasif["EQUIPO"] == nombre_local_clasif]
            visit_info = clasif[clasif["EQUIPO"] == nombre_visit_clasif]

            if local_info.empty or visit_info.empty:
                st.error("No se encontraron los equipos en la clasificación.")
                st.stop()

            pos_local = local_info.iloc[0]["POS"]
            pos_visit = visit_info.iloc[0]["POS"]
            st.success(f"Clasificación Jornada {jornada_clasificacion}: {nombre_local_clean} → {nombre_local_clasif} (Pos {pos_local}) | {nombre_visit_clean} → {nombre_visit_clasif} (Pos {pos_visit})")

            grupo_local_rival = grupo(pos_visit)
            grupo_visit_rival = grupo(pos_local)

            # Rama métrica
            bloques = []
            for b in [1, 2, 3, 4, 5]:
                dfL_b = filtrar_bloque(df_local, b, grupo_local_rival if b == 5 else None)
                dfV_b = filtrar_bloque(df_visit, b, grupo_visit_rival if b == 5 else None)
                metricas_b = calcular_metricas(dfL_b, dfV_b, jor_sel)
                bloques.append(metricas_b)
            b1, b2, b3, b4, b5 = bloques
            metricas_metrica = combinar_bloques(b1, b2, b3, b4, b5)

            # ML (si hay modelos)
            pred_ml = None
            if hay_ml:
                feats_local = construir_features_ml(df_local, df_visit, True, jor_sel, pos_local, pos_visit)
                feats_visit = construir_features_ml(df_visit, df_local, False, jor_sel, pos_visit, pos_local)
                pred_ml = predecir_ml(modelos_ml, feats_local, feats_visit)

            # Aplicar modo
            modo_actual = st.session_state.modo_prediccion
            st.info(f"📌 Modo activo: **{modo_actual}**")

            if modo_actual == "Métrica únicamente":
                metricas_finales = metricas_metrica
                usado_ml = False
            elif modo_actual == "ML únicamente":
                if pred_ml is not None:
                    metricas_finales = {}
                    for key in metricas_metrica.keys():
                        base_key = key.replace("_local", "").replace("_visitante", "").replace("_partido", "")
                        if base_key == "goles":
                            if key.endswith("_local") and "goles_local" in pred_ml:
                                metricas_finales[key] = pred_ml["goles_local"]
                            elif key.endswith("_visitante") and "goles_visitante" in pred_ml:
                                metricas_finales[key] = pred_ml["goles_visitante"]
                            elif key.endswith("_partido") and "goles_partido" in pred_ml:
                                metricas_finales[key] = pred_ml["goles_partido"]
                            else:
                                metricas_finales[key] = 0.0
                        else:
                            if key.endswith("_local") and f"{base_key}_local" in pred_ml:
                                metricas_finales[key] = pred_ml[f"{base_key}_local"]
                            elif key.endswith("_visitante") and f"{base_key}_visitante" in pred_ml:
                                metricas_finales[key] = pred_ml[f"{base_key}_visitante"]
                            elif key.endswith("_partido") and f"{base_key}_partido" in pred_ml:
                                metricas_finales[key] = pred_ml[f"{base_key}_partido"]
                            else:
                                metricas_finales[key] = 0.0
                    usado_ml = True
                else:
                    st.warning("⚠️ No hay predicciones ML disponibles. Fallback a métrica únicamente.")
                    metricas_finales = metricas_metrica
                    usado_ml = False
            else:  # Combinada
                metricas_finales, usado_ml = combinar_metrica_ml(metricas_metrica, pred_ml, jor_sel)
                if not usado_ml:
                    st.info("ℹ️ No se pudo combinar con ML (quizás faltan predicciones). Mostrando solo métrica.")

            # Asegurar métricas visitante
            for met in ["remates_totales", "remates_puerta", "paradas", "corners", "tarjetas"]:
                key_vis = f"{met}_visitante"
                if key_vis not in metricas_finales:
                    local_val = metricas_finales.get(f"{met}_local", 0)
                    total_val = metricas_finales.get(f"{met}_partido", 0)
                    metricas_finales[key_vis] = max(total_val - local_val, 0)
            if "goles_visitante" not in metricas_finales:
                metricas_finales["goles_visitante"] = max(
                    metricas_finales.get("goles_partido", 0) - metricas_finales.get("goles_local", 0), 0
                )

            gL = metricas_finales.get("goles_local", 0)
            gV = metricas_finales.get("goles_visitante", 0)
            pL, pE, pV = prob_1x2(gL, gV)

            st.markdown("---")
            st.markdown("### 🏆 PROBABILIDAD DE RESULTADO (1X2)")
            r1, r2, r3 = st.columns(3)
            r1.metric("Victoria Local", f"{pL*100:.1f}%")
            r2.metric("Empate", f"{pE*100:.1f}%")
            r3.metric("Victoria Visitante", f"{pV*100:.1f}%")

            st.markdown("### 🔥 MERCADOS DE GOLES")
            total_goles = gL + gV
            p_over15 = 1 - (poisson(total_goles, 0) + poisson(total_goles, 1))
            p_over25 = 1 - (poisson(total_goles, 0) + poisson(total_goles, 1) + poisson(total_goles, 2))
            p_btts = (1 - poisson(gL, 0)) * (1 - poisson(gV, 0))

            g1, g2, g3 = st.columns(3)
            g1.metric("Más de 1.5 Goles", f"{p_over15*100:.1f}%")
            g2.metric("Más de 2.5 Goles", f"{p_over25*100:.1f}%")
            g3.metric("Ambos Marcan", f"{p_btts*100:.1f}%")

            st.markdown("### 📈 PREDICCIÓN DE ESTADÍSTICAS")
            tabla = pd.DataFrame({
                "Métrica": ["Goles", "Remates Totales", "Remates a Puerta", "Paradas", "Córners", "Tarjetas"],
                "Local": [
                    f"{metricas_finales.get('goles_local', 0):.1f}",
                    f"{metricas_finales.get('remates_totales_local', 0):.1f}",
                    f"{metricas_finales.get('remates_puerta_local', 0):.1f}",
                    f"{metricas_finales.get('paradas_local', 0):.1f}",
                    f"{metricas_finales.get('corners_local', 0):.1f}",
                    f"{metricas_finales.get('tarjetas_local', 0):.1f}",
                ],
                "Visitante": [
                    f"{metricas_finales.get('goles_visitante', 0):.1f}",
                    f"{metricas_finales.get('remates_totales_visitante', 0):.1f}",
                    f"{metricas_finales.get('remates_puerta_visitante', 0):.1f}",
                    f"{metricas_finales.get('paradas_visitante', 0):.1f}",
                    f"{metricas_finales.get('corners_visitante', 0):.1f}",
                    f"{metricas_finales.get('tarjetas_visitante', 0):.1f}",
                ],
                "Total": [
                    f"{metricas_finales.get('goles_partido', 0):.1f}",
                    f"{metricas_finales.get('remates_totales_partido', 0):.1f}",
                    f"{metricas_finales.get('remates_puerta_partido', 0):.1f}",
                    f"{metricas_finales.get('paradas_partido', 0):.1f}",
                    f"{metricas_finales.get('corners_partido', 0):.1f}",
                    f"{metricas_finales.get('tarjetas_partido', 0):.1f}",
                ],
            })
            st.dataframe(tabla, use_container_width=True)

        except Exception as e:
            st.error(f"Error en el análisis: {e}")
            st.info("Revisa el panel de diagnóstico para ver las columnas disponibles.")
            st.code(traceback.format_exc())

except Exception as e:
    st.error(f"Error general: {e}")
    st.code(traceback.format_exc())
