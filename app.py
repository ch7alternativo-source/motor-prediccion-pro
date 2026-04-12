import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# 1. Configuración de página
st.set_page_config(page_title="Motor de Predicción PRO", layout="wide")

# Estilos CSS avanzados para una interfaz profesional
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stMetric {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .section-header {
        color: #1f3b4d;
        font-size: 1.5rem;
        font-weight: bold;
        border-left: 8px solid #ff4b4b;
        padding-left: 15px;
        margin: 30px 0 15px 0;
        background-color: #f8f9fa;
        padding-top: 5px;
        padding-bottom: 5px;
    }
    .custom-table {
        border-radius: 15px;
        overflow: hidden;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. Conexión a Google Sheets
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
    except:
        return False

# 3. Lógica de Login
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.markdown("<h2 style='text-align: center;'>🔐 Acceso al Sistema</h2>", unsafe_allow_html=True)
    with st.container():
        with st.form("login"):
            u = st.text_input("Usuario:")
            p = st.text_input("Contraseña:", type="password")
            if st.form_submit_button("Entrar"):
                if check_user(u, p):
                    st.session_state['autenticado'] = True
                    st.rerun()
                else:
                    st.error("Datos incorrectos")
else:
    # --- INTERFAZ DE USUARIO AUTENTICADO ---
    st.markdown("<h1 style='text-align: center; color: #1f3b4d;'>⚽ ANALIZADOR DE PARTIDOS PRO</h1>", unsafe_allow_html=True)
    
    try:
        # Carga de datos de ligas
        sh_ligas = client.open_by_key(ID_CONTROL).worksheet("LIGAS")
        df_ligas = pd.DataFrame(sh_ligas.get_all_records())
        
        col1, col2 = st.columns(2)
        liga_sel = col1.selectbox("🏆 Seleccionar Liga", df_ligas['Nombre de la liga'])
        id_actual = df_ligas[df_ligas['Nombre de la liga'] == liga_sel]['ID del libro'].values[0]
        jor_sel = col2.selectbox("📅 Jornada", list(range(1, 45)))

        # Acceso al libro de la liga
        libro = client.open_by_key(id_actual)
        excluir = ["config", "partido a analizar", "predicciones", "LIGAS", "Sheet1", "Hoja1"]
        pestanas = [s.title for s in libro.worksheets() if s.title not in excluir]
        
        locales = [t for t in pestanas if "LOCAL" in t.upper()]
        visitantes = [t for t in pestanas if "VISITANTE" in t.upper()]

        def clean(n): return n.replace(" LOCAL","").replace(" local","").replace(" VISITANTE","").replace(" visitante","").strip()

        cl, cv = st.columns(2)
        equipo_l = cl.selectbox("🏠 Equipo Local", locales, format_func=clean)
        equipo_v = cv.selectbox("🚀 Equipo Visitante", [v for v in visitantes if clean(equipo_l) not in v.upper()], format_func=clean)
        
        if st.button("📊 GENERAR ANÁLISIS COMPLETO"):
            st.divider()
            
            # --- SECCIÓN 1: GANADOR (1X2) ---
            st.markdown("<div class='section-header'>🏆 PROBABILIDAD DE RESULTADO (1X2)</div>", unsafe_allow_html=True)
            r1, r2, r3 = st.columns(3)
            r1.metric("Victoria Local", "45%", delta="Favorito", delta_color="normal")
            r2.metric("Empate", "25%")
            r3.metric("Victoria Visitante", "30%")
            
            # --- SECCIÓN 2: MERCADOS RÁPIDOS ---
            st.markdown("<div class='section-header'>🔥 MERCADOS DE GOLES PRINCIPALES</div>", unsafe_allow_html=True)
            g1, g2, g3 = st.columns(3)
            g1.metric("Más de 1.5 Goles", "78%")
            g2.metric("Más de 2.5 Goles", "55%")
            g3.metric("Ambos Marcan (SÍ)", "62%")
            
            st.divider()

            # --- SECCIÓN 3: TABLA MAESTRA ---
            st.markdown("<div class='section-header'>📈 PREDICCIÓN DE ESTADÍSTICAS DETALLADAS</div>", unsafe_allow_html=True)
            
            # Matriz con datos y probabilidades intercaladas
            datos_app = {
                "Métrica":
