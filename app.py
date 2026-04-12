import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# 1. Configuración de la página
st.set_page_config(page_title="Sistema Pro Multiliga", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    </style>
    """, unsafe_allow_html=True)

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
            u_excel = str(fila[0]).strip()
            p_excel = str(fila[1]).strip()
            if p_excel.endswith('.0'): p_excel = p_excel[:-2]
            if u_excel == str(user_in).strip() and p_excel == str(pass_in).strip():
                return True
        return False
    except:
        return False

# 4. Lógica de acceso
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
    st.title("⚽ Análisis Multiliga")
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
        loc = col_l.selectbox("Local", locales, format_func=clean)
        vis = col_v.selectbox("Visitante", [v for v in visitantes if clean(loc) not in v.upper()], format_func=clean)
        
        if st.button("CALCULAR PREDICCIÓN"):
            st.divider()
            st.subheader(f"📊 Probabilidades: {clean(loc)} vs {clean(vis)}")
            
            # --- SECCIÓN DE PROBABILIDADES ---
            # Nota: Aquí irán los porcentajes reales de tu XGBoost
            p_col1, p_col2, p_col3 = st.columns(3)
            p_col1.metric("Victoria Local", "45%")
            p_col2.metric("Empate", "25%")
            p_col3.metric("Victoria Visitante", "30%")
            
            st.divider()
            
            # --- TABLA DE MÉTRICAS DEL PDF ---
            st.write("### 📈 Predicción de Estadísticas Detalladas")
            
            # Recreamos la estructura de tu PDF
            data_pred = {
                "Categoría": ["Goles", "Remates Totales", "Remates a Puerta", "Paradas", "Córners", "Tarjetas Totales"],
                "Local (FVL)": ["1.75", "12.30", "5.11", "2.73", "5.41", "2.42"],
                "Visitante (FVV)": ["1.42", "14.44", "4.21", "4.22", "6.17", "2.54"],
                "Total Partido": ["3.17", "26.74", "9.32", "6.95", "11.58", "4.96"]
            }
            
            df_res = pd.DataFrame(data_pred)
            st.table(df_res) # Esto muestra la tabla limpia como en tu imagen
            
    except Exception as e:
        st.error(f"Error: {e}")
