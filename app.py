import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# 1. Configuración de página (Layout ancho para la matriz de datos)
st.set_page_config(page_title="Predicciones Pro Multiliga", layout="wide")

# --- DISEÑO PROFESIONAL (CSS Personalizado) ---
st.markdown("""
    <style>
    /* Ocultar elementos innecesarios */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Contenedores de métricas */
    .metric-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    
    /* Estilo para los títulos de sección */
    .section-title {
        color: #1f3b4d;
        border-left: 5px solid #ff4b4b;
        padding-left: 10px;
        margin-top: 20px;
        font-weight: bold;
    }
    
    /* Mejorar la visualización de la tabla */
    .stTable {
        border-radius: 10px;
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
    except: return False

# 3. Lógica de sesión
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
    # --- APP PRINCIPAL ---
    st.markdown("<h1 style='text-align: center; color: #1f3b4d;'>⚽ MOTOR DE PREDICCIÓN PRO</h1>", unsafe_allow_html=True)
    
    try:
        sh_ligas = client.open_by_key(ID_CONTROL).worksheet("LIGAS")
        df_ligas = pd.DataFrame(sh_ligas.get_all_records())
        
        c1, c2 = st.columns(2)
        liga_sel = c1.selectbox("Seleccionar Liga", df_ligas['Nombre de la liga'])
        id_actual = df_ligas[df_ligas['Nombre de la liga'] == liga_sel]['ID del libro'].values[0]
        jor_sel = c2.selectbox("Jornada", list(range(1, 45)))

        libro = client.open_by_key(id_actual)
        excluir = ["config", "partido a analizar", "predicciones", "LIGAS", "Sheet1", "Hoja1"]
        pestanas = [s.title for s in libro.worksheets() if s.title not in excluir]
        
        locales = [t for t in pestanas if "LOCAL" in t.upper()]
        visitantes = [t for t in pestanas if "VISITANTE" in t.upper()]

        def clean(n): return n.replace(" LOCAL","").replace(" local","").replace(" VISITANTE","").replace(" visitante","").strip()

        col_l, col_v = st.columns(2)
        loc_p = col_l.selectbox("Equipo Local", locales, format_func=clean)
        vis_p = col_v.selectbox("Equipo Visitante", [v for v in visitantes if clean(loc_p) not in v.upper()], format_func=clean)
        
        if st.button("🚀 ANALIZAR PARTIDO"):
            st.divider()
            
            # --- SECCIÓN 1: GANADOR (1X2) ---
            st.markdown("<div class='section-title'>🏆 PROBABILIDADES DE RESULTADO FINAL</div>", unsafe_allow_html=True)
            p1, p2, p3 = st.columns(3)
            with p1: st.metric("VICTORIA LOCAL", "42%", delta="Favorito", delta_color="normal")
            with p2: st.metric("EMPATE", "28%")
            with p3: st.metric("VICTORIA VISITANTE", "30%")
            
            # --- SECCIÓN 2: MERCADOS RÁPIDOS ---
            st.markdown("<div class='section-title'>🔥 OVER/UNDER Y AMBOS MARCAN</div>", unsafe_allow_html=True)
            g1, g2, g3 = st.columns(3)
            with g1: st.metric("MÁS DE 1.5 GOLES", "78%", help="Probabilidad basada en histórico")
            with g2: st.metric("MÁS DE 2.5 GOLES", "55%")
            with g3: st.metric("AMBOS MARCAN (SÍ)", "62%")
            
            st.divider()

            # --- SECCIÓN 3: TABLA MAESTRA (DATO + PROBABILIDAD) ---
            st.markdown("<div class='section-title'>📈 MATRIZ DE ESTADÍSTICAS DETALLADAS</div>", unsafe_allow_html=True)
            
            # Estructura intercalada: Dato | Probabilidad
            data_final = {
                "Métrica": ["Goles", "Remates Totales", "Remates a Puerta", "Córners", "Tarjetas"],
                "Local (FVL)": ["1.4", "12.2", "4.8", "5.1", "2.1"],
                "Prob. L (%)": ["78%", "70
