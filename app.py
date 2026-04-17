import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
from math import exp, factorial
import requests
import os
import joblib

st.set_page_config(page_title="Analizador de Partidos PRO", layout="wide")

# --- CONEXIÓN GOOGLE SHEETS ---
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
            if str(fila[0]).strip() == str(user_in).strip() and str(fila[1]).strip() == str(pass_in).strip():
                return True
        return False
    except:
        return False

if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if check_user(u, p):
                st.session_state['autenticado'] = True
                st.rerun()
            else:
                st.error("Datos incorrectos")
    st.stop()

# --- MAPEO EQUIPOS (CLAVE) ---
MAPEO_EQUIPOS = {
    "LEVANTE": "LEVANTE UD",
    "ATLETICO MADRID": "CLUB ATLÉTICO DE MADRID",
    "SEVILLA": "SEVILLA FC",
    "ELCHE": "ELCHE CF",
    "VALENCIA": "VALENCIA CF",
    "ESPANYOL": "RCD ESPANYOL DE BARCELONA",
    "CELTA": "RC CELTA DE VIGO",
    "REAL SOCIEDAD": "REAL SOCIEDAD DE FÚTBOL",
    "REAL MADRID": "REAL MADRID CF",
    "OVIEDO": "REAL OVIEDO",
    "BETIS": "REAL BETIS BALOMPIÉ",
    "GETAFE": "GETAFE CF",
    "GIRONA": "GIRONA FC",
    "VILLARREAL": "VILLARREAL CF",
    "ATH BILBAO": "ATHLETIC CLUB",
    "MALLORCA": "RCD MALLORCA",
    "RAYO VALLECANO": "RAYO VALLECANO DE MADRID",
    "BARCELONA": "FC BARCELONA",
    "OSASUNA": "CA OSASUNA"
}

# --- API CLASIFICACIÓN ---
@st.cache_data(ttl=300)
def obtener_clasificacion_api():
    url = "https://api.football-data.org/v4/competitions/PD/standings"
    headers = {'X-Auth-Token': "816135609d2e40f2867713634c0aefab"}

    try:
        r = requests.get(url, headers=headers)

        if r.status_code != 200:
            st.error(f"Error API: {r.status_code}")
            return pd.DataFrame()

        data = r.json()

        tabla = []
        for t in data['standings'][0]['table']:
            tabla.append({
                "EQUIPO": t['team']['name'].upper(),
                "POS": t['position']
            })

        return pd.DataFrame(tabla)

    except Exception as e:
        st.error(f"Error API: {e}")
        return pd.DataFrame()

# --- BUSCAR EQUIPO ---
def buscar_equipo(nombre, clasif):
    nombre = nombre.upper().strip()

    if nombre in MAPEO_EQUIPOS:
        nombre_api = MAPEO_EQUIPOS[nombre]
        fila = clasif[clasif["EQUIPO"] == nombre_api]
        return fila

    return clasif[clasif["EQUIPO"].str.contains(nombre, na=False)]

# --- FUNCIONES ---
def poisson(lam, k):
    return (lam**k * exp(-lam)) / factorial(k)

def prob_1x2(gL, gV):
    pL = pE = pV = 0
    for i in range(11):
        for j in range(11):
            p = poisson(gL, i) * poisson(gV, j)
            if i > j:
                pL += p
            elif i == j:
                pE += p
            else:
                pV += p
    return pL, pE, pV

def cargar_df(ws):
    df = pd.DataFrame(ws.get_all_records())
    df.columns = [c.upper() for c in df.columns]
    return df

# --- UI ---
st.title("⚽ ANALIZADOR PRO")

try:
    sh_ligas = client.open_by_key(ID_CONTROL).worksheet("LIGAS")
    df_ligas = pd.DataFrame(sh_ligas.get_all_records())

    c1, c2 = st.columns(2)
    liga = c1.selectbox("Liga", df_ligas['Nombre de la liga'])
    jornada = c2.selectbox("Jornada", list(range(1, 45)))

    id_liga = df_ligas[df_ligas['Nombre de la liga'] == liga]['ID del libro'].values[0]
    libro = client.open_by_key(id_liga)

    hojas = [s.title for s in libro.worksheets()]

    locales = [h for h in hojas if "LOCAL" in h.upper()]
    visitantes = [h for h in hojas if "VISITANTE" in h.upper()]

    def clean(x):
        return x.replace(" LOCAL", "").replace(" VISITANTE", "").strip()

    l1, l2 = st.columns(2)
    eq_l = l1.selectbox("Local", locales, format_func=clean)
    eq_v = l2.selectbox("Visitante", visitantes, format_func=clean)

    if st.button("Generar análisis"):

        dfL = cargar_df(libro.worksheet(eq_l))
        dfV = cargar_df(libro.worksheet(eq_v))

        clasif = obtener_clasificacion_api()

        if clasif.empty:
            st.stop()

        fila_l = buscar_equipo(clean(eq_l), clasif)
        fila_v = buscar_equipo(clean(eq_v), clasif)

        if fila_l.empty or fila_v.empty:
            st.error("Equipo no encontrado en API")
            st.write(clasif["EQUIPO"].tolist())
            st.stop()

        pos_l = fila_l["POS"].values[0]
        pos_v = fila_v["POS"].values[0]

        # --- DEMO GOLES ---
        gL = 1.4 + (20 - pos_v) * 0.05
        gV = 1.2 + (20 - pos_l) * 0.05

        pL, pE, pV = prob_1x2(gL, gV)

        st.subheader("Probabilidades")
        c1, c2, c3 = st.columns(3)
        c1.metric("Local", f"{pL*100:.1f}%")
        c2.metric("Empate", f"{pE*100:.1f}%")
        c3.metric("Visitante", f"{pV*100:.1f}%")

except Exception as e:
    st.error(f"Error general: {e}")
