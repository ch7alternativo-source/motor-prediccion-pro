import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# 1. Configuración de la página
st.set_page_config(page_title="Motor de Predicción PRO", layout="wide")

# Estilos CSS para que se vea "bonito" y profesional
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stMetric {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .section-header {
        color: #1f3b4d;
        font-weight: bold;
        border-left: 6px solid #ff4b4b;
        padding-left: 12px;
        margin-top: 25px;
        margin-bottom: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. Conexión (Usa tus secrets actuales)
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)
ID_CONTROL = "1E0oz34jM0-kAyh_XUVwRrI_wy2VK3Rmr9ExgxbkLXSA"

def check_user(user_in, pass_in):
    try:
        sh = client.open_by_key(ID_CONTROL).worksheet("Sheet1")
        data = sh.get_all_values()
        for fila in data:
            if str(fila[0]).strip() == str(user_in).strip() and str(fila[1]).strip() == str(pass_in).strip():
                return True
        return False
    except: return False

if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.title("🔐 Acceso Privado")
    with st.form("login"):
        u = st.text_input("Usuario:")
        p = st.text_input("Contraseña:", type="password")
        if st.form_submit_button("Entrar"):
            if check_user(u, p):
                st.session_state['autenticado'] = True
                st.rerun()
            else: st.error("Datos incorrectos")
else:
    # --- INTERFAZ PRINCIPAL ---
    st.markdown("<h1 style='text-align: center;'>📊 ANALIZADOR MULTILIGA PRO</h1>", unsafe_allow_html=True)
    
    try:
        sh_ligas = client.open_by_key(ID_CONTROL).worksheet("LIGAS")
        df_ligas = pd.DataFrame(sh_ligas.get_all_records())
        
        c1, c2 = st.columns(2)
        liga_sel = c1.selectbox("Liga", df_ligas['Nombre de la liga'])
        id_actual = df_ligas[df_ligas['Nombre de la liga'] == liga_sel]['ID del libro'].values[0]
        jor
