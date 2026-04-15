import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np

# --- 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS MEJORADOS ---
st.set_page_config(page_title="Analizador de Partidos PRO", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Título Principal - Azul profundo y fuerte */
    .main-title {
        text-align: center;
        color: #1f3b4d;
        font-size: 2.2rem;
        font-weight: 800;
        margin-bottom: 25px;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-family: 'Arial Black', Gadget, sans-serif;
    }

    /* Contenedores de métricas adaptables */
    .stMetric {
        background-color: rgba(255, 255, 255, 0.95);
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* Números de métricas (Rojo vibrante y grande) */
    [data-testid="stMetricValue"] {
        color: #ff4b4b !important;
        font-size: 2.2rem !important;
        font-weight: 800 !important;
    }
    
    /* Etiquetas de métricas (Gris oscuro legible) */
    [data-testid="stMetricLabel"] {
        color: #333333 !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
    }

    /* Encabezados de sección - Recuperando el estilo visual potente */
    .section-header {
        color: #1f3b4d;
        font-size: 1.3rem;
        font-weight: 800;
        border-left: 10px solid #ff4b4b;
        padding: 12px 18px;
        margin: 35px 0 15px 0;
        background-color: #fce8e8; /* Fondo suave para resaltar el texto oscuro */
        border-radius: 4px;
        text-transform: uppercase;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }

    /* Ajuste de tablas */
    .stTable {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #eeeeee;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN A GOOGLE SHEETS ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)
ID_CONTROL = "1E0oz34jM0-kAyh_XUVwRrI_wy2VK3Rmr9ExgxbkLXSA"

def check_user(user_in, pass_in):
    try:
        sh = client.open_by_key(ID_CONTROL).worksheet("Sheet1")
        data = sh.get_all_values()
        for fila in data:
            u_excel = str(fila[0]).strip()
            p_excel = str(fila[1]).strip().replace(".0", "") 
            if u_excel == str(user_in).strip() and p_excel == str(pass_in).strip():
                return True
        return False
    except:
        return False

# --- 3. LÓGICA DE SESIÓN ---
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.markdown("<h2 style='text-align: center;'>🔐 Acceso al Sistema</h2>", unsafe_allow_html=True)
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
    # --- 4. INTERFAZ PRINCIPAL ---
    st.markdown("<div class='main-title'>⚽ ANALIZADOR DE PARTIDOS PRO</div>", unsafe_allow_html=True)
    
    try:
        sh_ligas = client.open_by_key(ID_CONTROL).worksheet("LIGAS")
        df_ligas = pd.DataFrame(sh_ligas.get_all_records())
        
        col1, col2 = st.columns(2)
        liga_sel = col1.selectbox("🏆 Seleccionar Liga", df_ligas['Nombre de la liga'])
        id_actual = df_ligas[df_ligas['Nombre de la liga'] == liga_sel]['ID del libro'].values[0]
        jor_sel = col2.selectbox("📅 Jornada", list(range(1, 45)))

        libro = client.open_by_key(id_actual)
        excluir = ["config", "partido a analizar", "predicciones", "LIGAS", "Sheet1", "Hoja1"]
        pestanas = [s.title for s in libro.worksheets() if s.title not in excluir]
        
        locales = [t for t in pestanas if "LOCAL" in t.upper()]
        visitantes = [t for t in pestanas if "VISITANTE" in t.upper()]

        def clean(n): return n.replace(" LOCAL","").replace(" local","").replace(" VISITANTE","").replace(" visitante","").strip()

        cl, cv = st.columns(2)
        eq_l = cl.selectbox("🏠 Equipo Local", locales, format_func=clean)
        eq_v = cv.selectbox("🚀 Equipo Visitante", [v for v in visitantes if clean(eq_l) not in v.upper()], format_func=clean)
        
        if st.button("📊 GENERAR ANÁLISIS"):
            st.divider()
            
            # SECCIÓN 1: PROBABILIDAD (1X2)
            st.markdown("<div class='section-header'>🏆 PROBABILIDAD DE RESULTADO (1X2)</div>", unsafe_allow_html=True)
            r1, r2, r3 = st.columns(3)
            r1.metric("Victoria Local", "45%")
            r2.metric("Empate", "25%")
            r3.metric("Victoria Visitante", "30%")
            
            # SECCIÓN 2: MERCADOS RÁPIDOS
            st.markdown("<div class='section-header'>🔥 MERCADOS DE GOLES PRINCIPALES</div>", unsafe_allow_html=True)
            g1, g2, g3 = st.columns(3)
            g1.metric("Más de 1.5 Goles", "78%")
            g2.metric("Más de 2.5 Goles", "55%")
            g3.metric("Ambos Marcan (SÍ)", "62%")
            
            # SECCIÓN 3: TABLA DETALLADA CON PARADAS
            st.markdown("<div class='section-header'>📈 PREDICCIÓN DE ESTADÍSTICAS DETALLADAS</div>", unsafe_allow_html=True)
            
            datos_intercalados = {
                "Métrica": ["Goles", "Remates Totales", "Remates a Puerta", "Paradas", "Córners", "Tarjetas"],
                "Local (FVL)": ["1.4", "12.2", "4.8", "3.2", "5.1", "2.1"],
                "Prob. L (%)": ["78%", "70%", "65%", "72%", "60%", "85%"],
                "Visitante (FVV)": ["1.0", "13.5", "3.9", "4.1", "4.8", "2.6"],
                "Prob. V (%)": ["25%", "75%", "58%", "68%", "55%", "80%"],
                "Total Partido": ["2.4", "25.7", "8.7", "7.3", "9.9", "4.7"],
                "Prob. Tot (%)": ["65%", "72%", "62%", "70%", "59%", "82%"]
            }
            st.table(pd.DataFrame(datos_intercalados))

    except Exception as e:
        st.error(f"Error en el sistema: {e}")
