import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np

# 1. Configuración de la página
st.set_page_config(page_title="Sistema Pro Multiliga", layout="wide")

st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;} .stDeployButton {display:none;}</style>", unsafe_allow_html=True)

# 2. Conexión
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

if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False

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
    # --- APP PRINCIPAL ---
    st.title("⚽ Análisis Multiliga PRO")
    
    try:
        sh_ligas = client.open_by_key(ID_CONTROL).worksheet("LIGAS")
        df_ligas = pd.DataFrame(sh_ligas.get_all_records())
        
        c1, c2 = st.columns(2)
        liga_sel = c1.selectbox("Liga", df_ligas['Nombre de la liga'])
        id_actual = df_ligas[df_ligas['Nombre de la liga'] == liga_sel]['ID del libro'].values[0]
        jor_sel = c2.selectbox("Jornada", list(range(1, 45)))

        libro = client.open_by_key(id_actual)
        excluir = ["config", "partido a analizar", "predicciones", "LIGAS", "Sheet1", "Hoja1"]
        pestanas = [s.title for s in libro.worksheets() if s.title not in excluir]
        
        locales = [t for t in pestanas if "LOCAL" in t.upper()]
        visitantes = [t for t in pestanas if "VISITANTE" in t.upper()]

        def clean(n): return n.replace(" LOCAL","").replace(" local","").replace(" VISITANTE","").replace(" visitante","").strip()

        col_l, col_v = st.columns(2)
        loc_p = col_l.selectbox("Local", locales, format_func=clean)
        vis_p = col_v.selectbox("Visitante", [v for v in visitantes if clean(loc_p) not in v.upper()], format_func=clean)
        
        if st.button("GENERAR PREDICCIÓN COMPLETA"):
            with st.spinner('Analizando tendencias y probabilidades...'):
                # 1. Obtener datos reales para cálculos (Simulación de los últimos 5 partidos)
                # En un caso real, aquí leemos las columnas de las pestañas de cada equipo
                st.divider()
                st.subheader(f"📊 Informe de Probabilidades: {clean(loc_p)} vs {clean(vis_p)}")
                
                # --- BLOQUE 1: RESULTADO FINAL (1X2) ---
                st.write("#### 🏆 Probabilidades de Resultado")
                p1, p2, p3 = st.columns(3)
                p1.metric("Victoria Local", "42%")
                p2.metric("Empate", "28%")
                p3.metric("Victoria Visitante", "30%")
                
                st.divider()

                # --- BLOQUE 2: TABLA DE ESTADÍSTICAS CON COLUMNA DE PROB ---
                st.write("### 📈 Predicción de Estadísticas y Probabilidad de Mercado")
                
                # Definimos los datos integrando las probabilidades solicitadas
                data
