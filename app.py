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

# 3. Función de verificación (Basada en tu Sheet1)
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
        
        if st.button("GENERAR PREDICCIÓN"):
            st.divider()
            
            # --- BLOQUE 1: PROBABILIDADES DE MERCADO (Goles y Ambos Marcan) ---
            st.write("#### 🔥 Mercados de Goles y Probabilidades")
            g1, g2, g3 = st.columns(3)
            g1.metric("Más de 1.5 Goles", "78%")
            g2.metric("Más de 2.5 Goles", "55%")
            g3.metric("Ambos Marcan", "62%")
            
            st.divider()

            # --- BLOQUE 2: TABLA DETALLADA CON PROBABILIDAD POR DATO ---
            st.write(f"### 📈 Estadísticas Detalladas: {clean(loc_p)} vs {clean(vis_p)}")
            
            # Estructura con columnas de probabilidad intercaladas
            data_final = {
                "Métrica": ["Goles", "Remates Totales", "Remates a Puerta", "Córners", "Tarjetas"],
                "Local (FVL)": ["1.4", "12.2", "4.8", "5.1", "2.1"],
                "% Prob L": ["78%", "70%", "65%", "60%", "85%"],
                "Visitante (FVV)": ["1.0", "13.5", "3.9", "4.8", "2.6"],
                "% Prob V": ["25%", "75%", "58%", "55%", "80%"],
                "Total Partido": ["2.4", "25.7", "8.7", "9.9", "4.7"],
                "% Prob Total": ["65%", "72%", "62%", "59%", "82%"]
            }
            
            df_display = pd.DataFrame(data_final)
            st.table(df_display)

    except Exception as e:
        st.error(f"Error técnico: {e}")
