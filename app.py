import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
from math import exp, factorial
import re
import os
import joblib

st.set_page_config(page_title="Analizador de Partidos PRO", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)
ID_CONTROL = "1E0oz34jM0-kAyh_XUVwRrI_wy2VK3Rmr9ExgxbkLXSA"

# =========================================================
# MODELOS ML
# =========================================================
PREFIJOS_METRICAS = {
    "GOLES_FAVOR": "goles_local",
    "GOLES_CONTRA": "goles_visitante",
    "REMATES_TOTALES": "remates_totales",
    "REMATES_PUERTA": "remates_puerta",
    "PARADAS": "paradas",
    "CORNERS": "corners",
    "TARJETAS": "tarjetas",
}

FEATURES_MODELO = [
    "ES_LOCAL", "JORNADA", "POSICION_RIVAL",
    "GOLES_FAVOR_MA3","GOLES_CONTRA_MA3","REMATES_TOTALES_MA3",
    "REMATES_PUERTA_MA3","PARADAS_MA3","CORNERS_MA3","TARJETAS_MA3",
    "GOLES_FAVOR_MA5","GOLES_CONTRA_MA5","REMATES_TOTALES_MA5",
    "REMATES_PUERTA_MA5","PARADAS_MA5","CORNERS_MA5","TARJETAS_MA5",
    "GOLES_FAVOR_MA10","GOLES_CONTRA_MA10","REMATES_TOTALES_MA10",
    "REMATES_PUERTA_MA10","PARADAS_MA10","CORNERS_MA10","TARJETAS_MA10",
]

@st.cache_resource
def cargar_modelos_ml():
    modelos = {}
    carpeta = "models/models"
    if not os.path.exists(carpeta):
        return modelos

    for archivo in os.listdir(carpeta):
        if not archivo.endswith(".pkl"):
            continue
        try:
            obj = joblib.load(os.path.join(carpeta, archivo))
            if hasattr(obj, "predict"):
                for pref, met in PREFIJOS_METRICAS.items():
                    if archivo.upper().startswith(pref):
                        modelos.setdefault(met, []).append(obj)
        except:
            pass
    return modelos

# =========================================================
# FUNCIONES BASE (las tuyas, simplificadas aquí para ejemplo)
# =========================================================

def poisson(lam, k):
    if lam <= 0:
        return 1 if k == 0 else 0
    return (lam**k * exp(-lam)) / factorial(k)

def prob_1x2(gL, gV):
    max_g = 8
    pL = pE = pV = 0.0
    for i in range(max_g + 1):
        for j in range(max_g + 1):
            p = poisson(gL, i) * poisson(gV, j)
            if i > j: pL += p
            elif i == j: pE += p
            else: pV += p
    total = pL + pE + pV
    return pL/total, pE/total, pV/total

# =========================================================
# INTERFAZ
# =========================================================
st.markdown("<h2 style='text-align: center;'>⚽ ANALIZADOR DE PARTIDOS PRO</h2>", unsafe_allow_html=True)

if st.button("📊 DEMO DISPLAY"):

    # SIMULACIÓN DE TUS DATOS (como vienen realmente)
    metricas_finales = {
        "goles_local": 1.8,
        "goles_visitante": 1.2,
        "goles_partido": 3.0,

        "remates_totales_local": 14,
        "remates_totales_partido": 25,

        "remates_puerta_local": 6,
        "remates_puerta_partido": 10,

        "paradas_local": 3,
        "paradas_partido": 7,

        "corners_local": 5,
        "corners_partido": 9,

        "tarjetas_local": 2,
        "tarjetas_partido": 4,
    }

    # =========================================================
    # 🔥 FIX REAL (ESTO ES LO IMPORTANTE)
    # =========================================================
    for met in ["remates_totales","remates_puerta","paradas","corners","tarjetas"]:
        key_local = f"{met}_local"
        key_vis   = f"{met}_visitante"
        key_total = f"{met}_partido"

        if key_vis not in metricas_finales:
            metricas_finales[key_vis] = max(
                metricas_finales.get(key_total, 0) -
                metricas_finales.get(key_local, 0), 0
            )

    # =========================================================

    gL = metricas_finales["goles_local"]
    gV = metricas_finales["goles_visitante"]

    pL, pE, pV = prob_1x2(gL, gV)

    # DISPLAY ORIGINAL
    st.markdown("---")
    st.markdown("### 🏆 PROBABILIDAD DE RESULTADO (1X2)")
    r1, r2, r3 = st.columns(3)
    r1.metric("Victoria Local", f"{pL*100:.1f}%")
    r2.metric("Empate", f"{pE*100:.1f}%")
    r3.metric("Victoria Visitante", f"{pV*100:.1f}%")

    st.markdown("### 🔥 MERCADOS DE GOLES")
    total_goles = gL + gV

    g1, g2, g3 = st.columns(3)
    g1.metric("Más de 1.5 Goles", f"{(1-poisson(total_goles,0)-poisson(total_goles,1))*100:.1f}%")
    g2.metric("Más de 2.5 Goles", f"{(1-poisson(total_goles,0)-poisson(total_goles,1)-poisson(total_goles,2))*100:.1f}%")
    g3.metric("Ambos Marcan", f"{((1-poisson(gL,0))*(1-poisson(gV,0)))*100:.1f}%")

    st.markdown("### 📈 PREDICCION DE ESTADISTICAS")

    tabla = pd.DataFrame({
        "Metrica": ["Goles","Remates Totales","Remates a Puerta","Paradas","Corners","Tarjetas"],
        "Local": [
            metricas_finales["goles_local"],
            metricas_finales["remates_totales_local"],
            metricas_finales["remates_puerta_local"],
            metricas_finales["paradas_local"],
            metricas_finales["corners_local"],
            metricas_finales["tarjetas_local"],
        ],
        "Visitante": [
            metricas_finales["goles_visitante"],
            metricas_finales["remates_totales_visitante"],
            metricas_finales["remates_puerta_visitante"],
            metricas_finales["paradas_visitante"],
            metricas_finales["corners_visitante"],
            metricas_finales["tarjetas_visitante"],
        ],
        "Total": [
            metricas_finales["goles_partido"],
            metricas_finales["remates_totales_partido"],
            metricas_finales["remates_puerta_partido"],
            metricas_finales["paradas_partido"],
            metricas_finales["corners_partido"],
            metricas_finales["tarjetas_partido"],
        ]
    })

    st.dataframe(tabla, use_container_width=True)
