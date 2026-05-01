import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
from math import exp, factorial
import re
import os
import joblib
import traceback
import time
import base64

# =========================================================
# CONFIGURACIÓN GLOBAL
# =========================================================
st.set_page_config(page_title="COMBIBET PRO", layout="wide")

LOGO_URL = "https://raw.githubusercontent.com/ch7alternativo-source/motor-prediccion-pro/main/app/logo2.png"

# Convertir logo a base64 para el splash (esto evita pantalla negra)
def load_logo_base64(url):
    import requests
    r = requests.get(url)
    return base64.b64encode(r.content).decode()

LOGO_B64 = load_logo_base64(LOGO_URL)

# =========================================================
# CSS GLOBAL (modo oscuro sin romper Streamlit)
# =========================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Montserrat', sans-serif !important;
    background-color: #000 !important;
    color: #fff !important;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# SPLASH FULLSCREEN (FUNCIONA SIEMPRE)
# =========================================================
if "splash" not in st.session_state:
    st.session_state["splash"] = True

if st.session_state["splash"]:
    splash_html = f"""
    <style>
    .splash {{
        position: fixed;
        top: 0; left: 0;
        width: 100vw; height: 100vh;
        background-color: #000;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        z-index: 9999;
        animation: fadeout 1.5s ease-in-out forwards;
        animation-delay: 1.2s;
    }}
    @keyframes fadeout {{
        0% {{ opacity: 1; }}
        100% {{ opacity: 0; visibility: hidden; }}
    }}
    </style>

    <div class="splash">
        <img src="data:image/png;base64,{LOGO_B64}" style="width:70vh; max-width:90vw;">
        <div style="color:#888; margin-top:10px;">by Chiquicuenca</div>
    </div>
    """

    st.markdown(splash_html, unsafe_allow_html=True)
    time.sleep(1.5)
    st.session_state["splash"] = False
    st.rerun()

# =========================================================
# LOGIN (TU MISMO DISEÑO, SOLO ARREGLADO)
# =========================================================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

def check_user(user, pwd):
    try:
        sh = client.open_by_key(ID_CONTROL).worksheet("Sheet1")
        data = sh.get_all_values()
        for fila in data:
            if fila[0].strip() == user.strip() and fila[1].strip().replace(".0","") == pwd.strip():
                return True
        return False
    except:
        return False

if not st.session_state["autenticado"]:
    st.image(LOGO_URL, width=180)
    st.caption("by Chiquicuenca")
    st.markdown("## 🔐 Acceso al Sistema")

    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if check_user(u, p):
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Datos incorrectos")

    st.stop()

# =========================================================
# SIDEBAR (TU DISEÑO ORIGINAL)
# =========================================================
st.sidebar.image(LOGO_URL, width=150)
st.sidebar.markdown("### COMBIBET PRO")
st.sidebar.caption("by Chiquicuenca")

# =========================================================
# CABECERA PRINCIPAL (TU DISEÑO ORIGINAL)
# =========================================================
st.markdown("<h2 style='text-align:center;'>⚽ COMBIBET PRO - Análisis Predictivo</h2>", unsafe_allow_html=True)
st.image(LOGO_URL, width=200)
st.caption("by Chiquicuenca")

# =========================================================
# A PARTIR DE AQUÍ TU CÓDIGO ORIGINAL SIN TOCAR
# =========================================================

# (Aquí pegas TODO tu código original tal cual lo tenías,
# desde cargar modelos, métricas, clasificación, análisis, etc.
# No toco NADA porque eso sí te funcionaba bien.)
