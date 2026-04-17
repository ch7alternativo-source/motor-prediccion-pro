import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
from math import exp, factorial
from xgboost import XGBRegressor
import joblib
import os
import requests

st.set_page_config(page_title="Analizador de Partidos PRO", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope
)
client = gspread.authorize(creds)
ID_CONTROL = "1E0oz34jM0-kAyh_XUVwRrI_wy2VK3Rmr9ExgxbkLXSA"

# --- LOGIN ---
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
    st.markdown("<h2 style='text-align: center;'>🔐 Acceso</h2>", unsafe_allow_html=True)
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

# --- API CLASIFICACIÓN ---
@st.cache_data(ttl=300)
def obtener_clasificacion_api(codigo_liga="PD"):
    api_key = "816135609d2e40f2867713634c0aefab"

    url = f"https://api.football-data.org/v4/competitions/{codigo_liga}/standings"
    headers = {'X-Auth-Token': api_key}

    try:
        response = requests.get(url, headers=headers)

        # DEBUG útil
        if response.status_code != 200:
            st.error(f"Error API: {response.status_code}")
            st.write(response.text)
            return pd.DataFrame()

        data = response.json()

        if 'standings' not in data:
            st.error("Respuesta API sin 'standings'")
            st.write(data)
            return pd.DataFrame()

        tabla = []
        for team in data['standings'][0]['table']:
            tabla.append({
                "EQUIPO": team['team']['name'].upper(),
                "POS": team['position'],
                "PUNTOS": team['points']
            })

        return pd.DataFrame(tabla)

    except Exception as e:
        st.error(f"Error conexión API: {e}")
        return pd.DataFrame()

# --- FUNCIONES AUXILIARES ---
def cargar_pestana_equipo(ws):
    df = pd.DataFrame(ws.get_all_records())

    if df.empty:
        return df

    df.columns = [c.strip().upper() for c in df.columns]

    if "FECHA" in df.columns:
        df["FECHA"] = pd.to_datetime(df["FECHA"], errors="coerce")
        df = df.dropna(subset=["FECHA"]).sort_values("FECHA")

    for col in df.columns:
        if col != "RIVAL":
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

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

# --- UI ---
st.title("⚽ ANALIZADOR DE PARTIDOS PRO")

try:
    sh_ligas = client.open_by_key(ID_CONTROL).worksheet("LIGAS")
    df_ligas = pd.DataFrame(sh_ligas.get_all_records())

    col1, col2 = st.columns(2)

    liga_sel = col1.selectbox("Liga", df_ligas['Nombre de la liga'])
    id_actual = df_ligas[df_ligas['Nombre de la liga'] == liga_sel]['ID del libro'].values[0]
    jornada = col2.selectbox("Jornada", list(range(1, 45)))

    libro = client.open_by_key(id_actual)
    hojas = [s.title for s in libro.worksheets()]

    locales = [h for h in hojas if "LOCAL" in h.upper()]
    visitantes = [h for h in hojas if "VISITANTE" in h.upper()]

    def clean(x):
        return x.replace(" LOCAL", "").replace(" VISITANTE", "").strip()

    c1, c2 = st.columns(2)
    eq_l = c1.selectbox("Local", locales, format_func=clean)
    eq_v = c2.selectbox("Visitante", visitantes, format_func=clean)

    if st.button("Generar análisis"):

        df_local = cargar_pestana_equipo(libro.worksheet(eq_l))
        df_visit = cargar_pestana_equipo(libro.worksheet(eq_v))

        clasif = obtener_clasificacion_api()

        if clasif.empty:
            st.stop()

        # --- MATCH FLEXIBLE ---
        def buscar_equipo(nombre):
            fila = clasif[clasif["EQUIPO"].str.contains(nombre.upper(), na=False)]
            return fila

        fila_l = buscar_equipo(clean(eq_l))
        fila_v = buscar_equipo(clean(eq_v))

        if fila_l.empty or fila_v.empty:
            st.error("Equipo no encontrado en API")
            st.write("Equipos API:", clasif["EQUIPO"].tolist())
            st.stop()

        pos_l = fila_l["POS"].values[0]
        pos_v = fila_v["POS"].values[0]

        # --- EJEMPLO SIMPLE ---
        gL = 1.5
        gV = 1.2

        pL, pE, pV = prob_1x2(gL, gV)

        st.metric("Local", f"{pL*100:.1f}%")
        st.metric("Empate", f"{pE*100:.1f}%")
        st.metric("Visitante", f"{pV*100:.1f}%")

except Exception as e:
    st.error(f"Error general: {e}")
