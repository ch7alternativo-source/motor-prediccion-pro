import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# 1. Configuración de página
st.set_page_config(page_title="Sistema Pro Multiliga", layout="wide")

st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;} .stDeployButton {display:none;}</style>", unsafe_allow_html=True)

# 2. Conexión
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)
ID_CONTROL = "1E0oz34jM0-kAyh_XUVwRrI_wy2VK3Rmr9ExgxbkLXSA"

# 3. Función de verificación
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

# 4. Estado de autenticación
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
            else:
                st.error("Datos incorrectos")
else:
    # --- APP PRINCIPAL ---
    st.title("⚽ Análisis Multiliga PRO")
    
    try:
        # Carga de Ligas
        sh_ligas = client.open_by_key(ID_CONTROL).worksheet("LIGAS")
        df_ligas = pd.DataFrame(sh_ligas.get_all_records())
        
        c1, c2 = st.columns(2)
        liga_sel = c1.selectbox("Liga", df_ligas['Nombre de la liga'])
        id_actual = df_ligas[df_ligas['Nombre de la liga'] == liga_sel]['ID del libro'].values[0]
        jor_sel = c2.selectbox("Jornada", list(range(1, 45)))

        # Carga de Equipos
        libro = client.open_by_key(id_actual)
        excluir = ["config", "partido a analizar", "predicciones", "LIGAS", "Sheet1", "Hoja1"]
        pestanas = [s.title for s in libro.worksheets() if s.title not in excluir]
        
        locales = [t for t in pestanas if "LOCAL" in t.upper()]
        visitantes = [t for t in pestanas if "VISITANTE" in t.upper()]

        def clean(n): return n.replace(" LOCAL","").replace(" local","").replace(" VISITANTE","").replace(" visitante","").strip()

        col_l, col_v = st.columns(2)
        loc_p = col_l.selectbox("Local", locales, format_func=clean)
        vis_p = col_v.selectbox("Visitante", [v for v in visitantes if clean(loc_p) not in v.upper()], format_func=clean)
        
        if st.button("GENERAR PREDICCIÓN"):
            st.divider()
            st.subheader(f"📊 Probabilidades Totales: {clean(loc_p)} vs {clean(vis_p)}")
            
            # --- BLOQUE 1: GANADOR ---
            p1, p2, p3 = st.columns(3)
            p1.metric("Victoria Local", "42%")
            p2.metric("Empate", "28%")
            p3.metric("Victoria Visitante", "30%")
            
            st.divider()

            # --- BLOQUE 2: TABLA CON COLUMNA DE PROBABILIDAD ---
            st.write("### 📈 Predicción de Estadísticas y Probabilidad de Mercado")
            
            data_final = {
                "Mercado": ["Goles (+2.5)", "Remates Totales", "Remates a Puerta", "Córners", "Tarjetas", "Ambos Marcan"],
                "Local (FVL)": ["1.85", "12.4", "5.1", "5.4", "2.2", "SÍ"],
                "Visitante (FVV)": ["1.40", "13.2", "4.2", "4.9", "2.7", "SÍ"],
                "Total Partido": ["3.25", "25.6", "9.3", "10.3", "4.9", "62%"],
                "Probabilidad (%)": ["68%", "72%", "64%", "59%", "81%", "62%"]
            }
            
            st.table(pd.DataFrame(data_final))

    except Exception as e:
        st.error(f"Error técnico: {e}")
