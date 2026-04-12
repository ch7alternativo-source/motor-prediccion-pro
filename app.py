import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# 1. Configuración de la página (SIEMPRE PRIMERO)
st.set_page_config(page_title="Sistema Pro Multiliga", layout="wide")

# Ocultar menús de Streamlit
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    </style>
    """, unsafe_allow_html=True)

# 2. Configuración de Conexión a Google Sheets
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

ID_CONTROL = "1E0oz34jM0-kAyh_XUVwRrI_wy2VK3Rmr9ExgxbkLXSA"

# 3. Función para verificar Usuario y Contraseña
def check_user(usuario_intento, pass_intento):
    try:
        sh_control = client.open_by_key(ID_CONTROL).worksheet("Hoja1")
        usuarios_data = sh_control.get_all_values() 
        
        for fila in usuarios_data:
            # Convertimos a texto y limpiamos espacios
            u_excel = str(fila[0]).strip()
            p_excel = str(fila[1]).strip()
            
            # Quitamos el .0 que Google Sheets añade a veces a los números
            if p_excel.endswith('.0'):
                p_excel = p_excel[:-2]

            if u_excel == str(usuario_intento).strip() and p_excel == str(pass_intento).strip():
                return True
        return False
    except:
        return False

# 4. Estado de autenticación
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

# --- INTERFAZ DE LOGIN ---
if not st.session_state['autenticado']:
    st.title("🔐 Acceso Privado")
    with st.form("login_form"):
        user_input = st.text_input("Usuario:")
        pass_input = st.text_input("Contraseña:", type="password")
        submit_button = st.form_submit_button("Entrar")
        
        if submit_button:
            if check_user(user_input, pass_input):
                st.session_state['autenticado'] = True
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")

# --- APP PRINCIPAL (SI YA ESTÁ LOGUEADO) ---
else:
    st.title("⚽ Análisis Multiliga")
    
    try:
        # 1. Cargar Ligas desde Excel de Control
        sh_ligas = client.open_by_key(ID_CONTROL).worksheet("LIGAS")
        df_ligas = pd.DataFrame(sh_ligas.get_all_records())
        
        col_liga, col_jor = st.columns(2)
        
        with col_liga:
            liga_seleccionada = st.selectbox("Selecciona la Competición", df_ligas['Nombre de la liga'])
            id_liga_actual = df_ligas[df_ligas['Nombre de la liga'] == liga_seleccionada]['ID del libro'].values[0]

        with col_jor:
            jornadas = list(range(1, 45))
            jornada_seleccionada = st.selectbox("Selecciona la Jornada", jornadas)

        # 2. Cargar Equipos de la Liga seleccionada
        libro_datos = client.open_by_key(id_liga_actual)
        excluir = ["config", "partido a analizar", "predicciones", "LIGAS", "Sheet1", "Hoja1"]
        
        pestanas_validas = [sh.title for sh in libro_datos.worksheets() if sh.title not in excluir]
        
        listado
