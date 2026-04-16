import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
from math import exp, factorial
from xgboost import XGBRegressor
import joblib
import os

st.set_page_config(page_title="Analizador de Partidos PRO", layout="wide")

# --- 2. CONEXIÓN A GOOGLE SHEETS ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)
ID_CONTROL = "1E0oz34jM0-kAyh_XUVwRrI_wy2VK3Rmr9ExgxbkLXSA"

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

# --- 3. SESIÓN ---
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

    st.stop()   # ← AQUÍ TERMINA EL LOGIN

# MOTOR MÉTRICO (RAMA 1)
def cargar_pestana_equipo(ws):
    data = ws.get_all_records()
    df = pd.DataFrame(data)

    if "FECHA" in df.columns:
        df["FECHA"] = pd.to_datetime(df["FECHA"], errors="coerce")

    for col in df.columns:
        if col != "RIVAL":
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["FECHA"])
    df = df.sort_values("FECHA")
    return df


def calcular_clasificacion(todas_pestanas):
    tabla = []

    for equipo, df in todas_pestanas.items():
        puntos = 0
        gf = df["GOL FAVOR"].sum()
        gc = df["GOL CONTRA"].sum()

        for _, row in df.iterrows():
            if row["GOL FAVOR"] > row["GOL CONTRA"]:
                puntos += 3
            elif row["GOL FAVOR"] == row["GOL CONTRA"]:
                puntos += 1

        tabla.append([equipo, puntos, gf, gc, gf - gc])

    clasif = pd.DataFrame(tabla, columns=["EQUIPO", "PUNTOS", "GF", "GC", "DG"])
    clasif = clasif.sort_values(["PUNTOS", "DG", "GF"], ascending=False)

    posiciones = []
    pos_real = 1
    prev = None

    for _, row in clasif.iterrows():
        if prev and row["PUNTOS"] == prev["PUNTOS"]:
            posiciones.append(pos_real - 1)
        else:
            posiciones.append(pos_real)
        prev = row
        pos_real += 1

    clasif["POS"] = posiciones
    return clasif


def filtrar_bloque(df, tipo, es_local, grupo=None):
    if tipo == 1:
        return df.copy()
    if tipo == 2:
        return df[df["JORNADA"] >= 1].copy()
    if tipo == 3:
        return df.tail(5).copy()
    if tipo == 4:
        return df.tail(3).copy()
    if tipo == 5:
        if grupo is None:
            return df.copy()
        return df[df["POSICION RIVAL"].isin(grupo)].copy()
    return df.copy()


def limpiar_ruido(lista):
    lista = [x for x in lista if pd.notna(x)]
    if len(lista) <= 2:
        return lista
    lista = sorted(lista)
    return lista[1:-1]


def calcular_metricas(dfL, dfV, jornada):
    metricas = {}

    columnas = [
        ("GOL FAVOR", "GOL CONTRA", "goles"),
        ("REMATES TOTALES FAVOR", "REMATES TOTALES CONTRA", "remates_totales"),
        ("REMATES PUERTA FAVOR", "REMATES PUERTA CONTRA", "remates_puerta"),
        ("PARADAS FAVOR", "PARADAS CONTRA", "paradas"),
        ("CORNERES FAVOR", "CORNERES CONTRA", "corners"),
        ("TARJETAS AMARILLAS CONTRA", "TARJETAS AMARILLAS FAVOR", "tarjetas"),
    ]

    for colF, colC, nombre in columnas:
        lista_L_fav = dfL[colF].tolist()
        lista_V_contra = dfV[colC].tolist()

        if jornada >= 14:
            lista_L_fav = limpiar_ruido(lista_L_fav)
            lista_V_contra = limpiar_ruido(lista_V_contra)

        if len(lista_L_fav) == 0 or len(lista_V_contra) == 0:
            metricas[nombre + "_local"] = 0
            metricas[nombre + "_visitante"] = 0
            metricas[nombre + "_partido"] = 0
            continue

        m_local = (np.mean(lista_L_fav) + np.mean(lista_V_contra)) / 2

        lista_V_fav = dfV[colF].tolist()
        lista_L_contra = dfL[colC].tolist()

        if jornada >= 14:
            lista_V_fav = limpiar_ruido(lista_V_fav)
            lista_L_contra = limpiar_ruido(lista_L_contra)

        m_visit = (np.mean(lista_V_fav) + np.mean(lista_L_contra)) / 2

        metricas[nombre + "_local"] = m_local
        metricas[nombre + "_visitante"] = m_visit
        metricas[nombre + "_partido"] = m_local + m_visit

    return metricas


def pesos_por_jornada(j):
    if j <= 5: return (0.2, 0.8)
    if j <= 10: return (0.3, 0.7)
    if j <= 14: return (0.4, 0.6)
    if j <= 20: return (0.5, 0.5)
    if j <= 30: return (0.6, 0.4)
    return (0.65, 0.35)


def combinar_bloques(b1, b2, b3, b4, b5):
    final = {}
    for k in b1.keys():
        final[k] = (
            b1[k] * 0.10 +
            b2[k] * 0.40 +
            b3[k] * 0.15 +
            b4[k] * 0.25 +
            b5[k] * 0.10
        )
    return final

def poisson(lam, k):
    return (lam**k * exp(-lam)) / factorial(k)


def prob_1x2(gL, gV):
    max_g = 10
    pL = pE = pV = 0

    for i in range(max_g + 1):
        for j in range(max_g + 1):
            p = poisson(gL, i) * poisson(gV, j)
            if i > j:
                pL += p
            elif i == j:
                pE += p
            else:
                pV += p

    return pL, pE, pV


RUTA_MODELOS = "models"


def cargar_modelo(nombre_fichero):
    ruta = os.path.join(RUTA_MODELOS, nombre_fichero)
    if not os.path.exists(ruta):
        return None
    try:
        return joblib.load(ruta)
    except:
        return None


def construir_features_equipo(df):
    feats = {}
    cols_numericas = [c for c in df.columns if c not in ["RIVAL", "FECHA"]]

    for col in cols_numericas:
        feats[f"{col}_media"] = df[col].mean()
        feats[f"{col}_std"] = df[col].std()

    return pd.DataFrame([feats])


def predecir_ml_metricas(df_local, df_visit):
    X_local = construir_features_equipo(df_local)
    X_visit = construir_features_equipo(df_visit)

    X = pd.concat([
        X_local.add_prefix("L_"),
        X_visit.add_prefix("V_")
    ], axis=1)

    modelos_info = {
        "goles_local": "goles_local_xgb.pkl",
        "goles_visitante": "goles_visitante_xgb.pkl",
        "remates_totales_local": "remates_totales_local_xgb.pkl",
        "remates_totales_visitante": "remates_totales_visitante_xgb.pkl",
        "remates_puerta_local": "remates_puerta_local_xgb.pkl",
        "remates_puerta_visitante": "remates_puerta_visitante_xgb.pkl",
        "paradas_local": "paradas_local_xgb.pkl",
        "paradas_visitante": "paradas_visitante_xgb.pkl",
        "corners_local": "corners_local_xgb.pkl",
        "corners_visitante": "corners_visitante_xgb.pkl",
        "tarjetas_local": "tarjetas_local_xgb.pkl",
        "tarjetas_visitante": "tarjetas_visitante_xgb.pkl",
    }

    resultados_ml = {}
    algun_modelo = False

    for clave, fichero in modelos_info.items():
        modelo = cargar_modelo(fichero)
        if modelo is None:
            resultados_ml[clave] = None
            continue

        algun_modelo = True
        try:
            pred = modelo.predict(X)[0]
            resultados_ml[clave] = float(pred)
        except:
            resultados_ml[clave] = None

    if not algun_modelo:
        return None

    for base in ["goles", "remates_totales", "remates_puerta", "paradas", "corners", "tarjetas"]:
        l = resultados_ml.get(f"{base}_local")
        v = resultados_ml.get(f"{base}_visitante")
        if l is not None and v is not None:
            resultados_ml[f"{base}_partido"] = l + v
        else:
            resultados_ml[f"{base}_partido"] = None

    return resultados_ml


def combinar_metrica_y_ml(metricas_metrica, metricas_ml, jornada):
    if metricas_ml is None:
        return metricas_metrica, False

    alpha_m, alpha_ml = pesos_por_jornada(jornada)
    final = {}

    for k, v in metricas_metrica.items():
        ml_val = metricas_ml.get(k)
        if ml_val is None:
            final[k] = v
        else:
            final[k] = alpha_m * v + alpha_ml * ml_val

    return final, True

st.markdown("<div class='main-title'>⚽ ANALIZADOR DE PARTIDOS PRO</div>", unsafe_allow_html=True)

try:
    sh_ligas = client.open_by_key(ID_CONTROL).worksheet("LIGAS")
    df_ligas = pd.DataFrame(sh_ligas.get_all_records())

    col1, col2 = st.columns(2)
    liga_sel = col1.selectbox("🏆 Seleccionar Liga", df_ligas['Nombre de la liga'])
    id_actual = df_ligas[df_ligas['Nombre de la liga'] == liga_sel]['ID del libro'].values[0]
    jor_sel = col2.selectbox("📅 Jornada", list(range(1, 45)))

    libro = client.open_by_key(id_actual)
    excluir = ["config", "partido a analizar", "predicciones", "LIGAS", "Sheet1", "Hoja1"]
    pestanas = [s.title for s in libro.worksheets() if s.title not in excluir]

    locales = [t for t in pestanas if "LOCAL" in t.upper()]
    visitantes = [t for t in pestanas if "VISITANTE" in t.upper()]

    def clean(n):
        return n.replace(" LOCAL","").replace(" VISITANTE","").strip()

    cl, cv = st.columns(2)
    eq_l = cl.selectbox("🏠 Equipo Local", locales, format_func=clean)
    eq_v = cv.selectbox("🚀 Equipo Visitante", [v for v in visitantes if clean(eq_l) not in v.upper()], format_func=clean)

    if st.button("📊 GENERAR ANÁLISIS"):

        st.divider()

        ws_local = libro.worksheet(eq_l)
        ws_visit = libro.worksheet(eq_v)

        df_local = cargar_pestana_equipo(ws_local)
        df_visit = cargar_pestana_equipo(ws_visit)

        todas = {}
        for p in pestanas:
            ws = libro.worksheet(p)
            dfp = cargar_pestana_equipo(ws)
            equipo = p.replace(" LOCAL", "").replace(" VISITANTE", "")
            if equipo not in todas:
                todas[equipo] = dfp

        clasif = calcular_clasificacion(todas)

        pos_local = clasif[clasif["EQUIPO"] == clean(eq_l)]["POS"].values[0]
        pos_visit = clasif[clasif["EQUIPO"] == clean(eq_v)]["POS"].values[0]

        def grupo(pos):
            if 1 <= pos <= 4: return [1,2,3,4]
            if 5 <= pos <= 10: return [5,6,7,8,9,10]
            if 11 <= pos <= 16: return [11,12,13,14,15,16]
            return list(range(17,26))

        grupo_local = grupo(pos_visit)
        grupo_visit = grupo(pos_local)

        bloques_local = []

        for b in [1,2,3,4,5]:
            dfL_b = filtrar_bloque(df_local, b, True, grupo_local if b == 5 else None)
            dfV_b = filtrar_bloque(df_visit, b, False, grupo_visit if b == 5 else None)

            metricas_b = calcular_metricas(dfL_b, dfV_b, jor_sel)
            bloques_local.append(metricas_b)

        b1, b2, b3, b4, b5 = bloques_local
        metricas_metrica = combinar_bloques(b1, b2, b3, b4, b5)

        metricas_ml = predecir_ml_metricas(df_local, df_visit)

        metricas_finales, usado_ml = combinar_metrica_y_ml(metricas_metrica, metricas_ml, jor_sel)

        if not usado_ml:
            st.info("Rama ML no activa (no hay modelos XGBoost). Usando solo rama métrica.")

        gL = metricas_finales["goles_local"]
        gV = metricas_finales["goles_visitante"]

        pL, pE, pV = prob_1x2(gL, gV)

        st.markdown("<div class='section-header'>🏆 PROBABILIDAD DE RESULTADO (1X2)</div>", unsafe_allow_html=True)
        r1, r2, r3 = st.columns(3)
        r1.metric("Victoria Local", f"{pL*100:.1f}%")
        r2.metric("Empate", f"{pE*100:.1f}%")
        r3.metric("Victoria Visitante", f"{pV*100:.1f}%")

        st.markdown("<div class='section-header'>🔥 MERCADOS DE GOLES PRINCIPALES</div>", unsafe_allow_html=True)

        p_over15 = 1 - (poisson(gL+gV,0) + poisson(gL+gV,1))
        p_over25 = 1 - (poisson(gL+gV,0) + poisson(gL+gV,1) + poisson(gL+gV,2))
        p_btts = (1 - poisson(gL,0)) * (1 - poisson(gV,0))

        g1, g2, g3 = st.columns(3)
        g1.metric("Más de 1.5 Goles", f"{p_over15*100:.1f}%")
        g2.metric("Más de 2.5 Goles", f"{p_over25*100:.1f}%")
        g3.metric("Ambos Marcan (SÍ)", f"{p_btts*100:.1f}%")

        st.markdown("<div class='section-header'>📈 PREDICCIÓN DE ESTADÍSTICAS DETALLADAS</div>", unsafe_allow_html=True)

        tabla = {
    "Métrica": ["Goles", "Remates Totales", "Remates a Puerta", "Paradas", "Córners", "Tarjetas"],

    "Local (FVL)": [
        f"{metricas_finales['goles_local']:.2f}",
        f"{metricas_finales['remates_totales_local']:.2f}",
        f"{metricas_finales['remates_puerta_local']:.2f}",
        f"{metricas_finales['paradas_local']:.2f}",
        f"{metricas_finales['corners_local']:.2f}",
        f"{metricas_finales['tarjetas_local']:.2f}"
    ],

    "Visitante (FVV)": [
        f"{metricas_finales['goles_visitante']:.2f}",
        f"{metricas_finales['remates_totales_visitante']:.2f}",
        f"{metricas_finales['remates_puerta_visitante']:.2f}",
        f"{metricas_finales['paradas_visitante']:.2f}",
        f"{metricas_finales['corners_visitante']:.2f}",
        f"{metricas_finales['tarjetas_visitante']:.2f}"
    ],

    "Total Partido": [
        f"{metricas_finales['goles_partido']:.2f}",
        f"{metricas_finales['remates_totales_partido']:.2f}",
        f"{metricas_finales['remates_puerta_partido']:.2f}",
        f"{metricas_finales['paradas_partido']:.2f}",
        f"{metricas_finales['corners_partido']:.2f}",
        f"{metricas_finales['tarjetas_partido']:.2f}"
    ]
}
st.table(pd.DataFrame(tabla))
except Exception as e:
    st.error(f"Error: {e}")
