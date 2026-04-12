import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURACIÓN DE CONEXIÓN ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
# Railway leerá esto desde sus "Variables de Entorno"
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)


ID_CONTROL = "1E0oz34jM0-kAyh_XUVwRrI_wy2VK3Rmr9ExgxbkLXSA"


st.set_page_config(page_title="Sistema Pro Multiliga", layout="wide")


if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False


# --- FUNCIÓN PARA VERIFICAR AMIGOS ---
def check_user(usuario_intento):
    try:
        sh_control = client.open_by_key(ID_CONTROL).worksheet("Sheet1") # O el nombre de tu pestaña 1
        usuarios = sh_control.col_values(1)
        return usuario_intento in usuarios
    except: return False


def check_user(usuario_intento, pass_intento):
    try:
        sh_control = client.open_by_key(ID_CONTROL).worksheet("Hoja1")
        usuarios_data = sh_control.get_all_values() 
        
        for fila in usuarios_data:
            # Comparamos usuario (fila 0) y contraseña (fila 1)
            if fila[0] == usuario_intento and str(fila[1]) == str(pass_intento):
                return True
        return False
    except:
        return False
else:
    # --- APP PRINCIPAL (OPCIÓN B) ---
    st.title("⚽ Análisis Multiliga")
    
    # 1. Cargar Ligas disponibles desde el Excel de Control
    try:
        sh_ligas = client.open_by_key(ID_CONTROL).worksheet("LIGAS")
        df_ligas = pd.DataFrame(sh_ligas.get_all_records())
        
        liga_seleccionada = st.selectbox("Selecciona la Competición", df_ligas['Nombre de la liga'])
        id_liga_actual = df_ligas[df_ligas['Nombre de la liga'] == liga_seleccionada]['ID del libro'].values[0]

        # --- NUEVO: Selección de Jornada ---
        jornadas = list(range(1, 45))
        jornada_seleccionada = st.selectbox("Selecciona la Jornada", jornadas)
        
      # 2. Cargar Equipos de esa Liga
        libro_datos = client.open_by_key(id_liga_actual)
        
        # Pestañas que NO son equipos
        excluir = ["config", "partido a analizar", "predicciones", "LIGAS", "Sheet1", "Hoja1"]
        
        # Obtenemos todas las pestañas válidas
        pestanas_validas = [sh.title for sh in libro_datos.worksheets() if sh.title not in excluir]
        
        # Separamos las pestañas reales de Google Sheets
        listado_local = [t for t in pestanas_validas if "LOCAL" in t.upper()]
        listado_visitante = [t for t in pestanas_validas if "VISITANTE" in t.upper()]

        # Función para mostrar solo el nombre del equipo en el menú
        def limpiar_nombre(nombre_pestana):
            return nombre_pestana.replace(" LOCAL", "").replace(" local", "").replace(" VISITANTE", "").replace(" visitante", "").strip()

        col1, col2 = st.columns(2)

        with col1:
            local = st.selectbox(
                "Selecciona Local", 
                listado_local, 
                format_func=limpiar_nombre  # Aquí ocurre la magia: limpia el nombre solo para la vista
            )

        with col2:
            # Filtramos para que no aparezca el mismo equipo que elegiste en Local
            equipo_base_sel = limpiar_nombre(local)
            opciones_v = [v for v in listado_visitante if equipo_base_sel not in v.upper()]
            
            visitante = st.selectbox(
                "Selecciona Visitante", 
                opciones_v, 
                format_func=limpiar_nombre  # También limpiamos el nombre aquí
            )
        
        if st.button("CALCULAR PREDICCIÓN"):
            st.success(f"Analizando {local} vs {visitante} en la liga {liga_seleccionada}...")
            # Aquí va tu lógica XGBoost leyendo las pestañas...
            
    except Exception as e:
        st.error(f"Error: Asegúrate de que la pestaña 'LIGAS' existe y el ID es correcto. {e}")
