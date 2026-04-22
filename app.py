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
    "GOLES_FAVOR":     "goles_local",
    "GOLES_CONTRA":    "goles_visitante",
    "REMATES_TOTALES": "remates_totales",
    "REMATES_PUERTA":  "remates_puerta",
    "PARADAS":         "paradas",
    "CORNERS":         "corners",
    "TARJETAS":        "tarjetas",
    "RESULTADO":       "resultado",
    "OVER_1_5":        "over_1_5",
    "OVER_2_5":        "over_2_5",
    "BTTS":            "btts",
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

# (… TODO TU CÓDIGO ORIGINAL SIN CAMBIOS …)

# =========================================================
# AQUÍ LLEGA EL MOMENTO CLAVE
# =========================================================

            # -- Combinacion final --
            metricas_finales, usado_ml = combinar_metrica_ml(metricas_metrica, pred_ml, jor_sel)

            if usado_ml:
                st.info(f"🤖 ML activo — combinando {n_modelos} modelos con rama metrica (jornada {jor_sel})")
            else:
                st.info("📐 Solo rama metrica (no hay modelos ML disponibles)")

            # =========================================================
            # 🔥 FIX DISPLAY (ESTO ES LO QUE ARREGLA TODO)
            # =========================================================
            for met in ["remates_totales", "remates_puerta", "paradas", "corners", "tarjetas"]:
                key_local = f"{met}_local"
                key_vis   = f"{met}_visitante"
                key_total = f"{met}_partido"

                if key_vis not in metricas_finales:
                    local_val = metricas_finales.get(key_local, 0)
                    total_val = metricas_finales.get(key_total, 0)
                    metricas_finales[key_vis] = max(total_val - local_val, 0)

            if "goles_visitante" not in metricas_finales:
                metricas_finales["goles_visitante"] = max(
                    metricas_finales.get("goles_partido", 0) -
                    metricas_finales.get("goles_local", 0), 0
                )
            # =========================================================

            gL = metricas_finales.get("goles_local",     0)
            gV = metricas_finales.get("goles_visitante", 0)

            pL, pE, pV = prob_1x2(gL, gV)

            # -----------------------------------------------
            # DISPLAY ORIGINAL (NO TOCADO)
            # -----------------------------------------------
            st.markdown("---")
            st.markdown("### 🏆 PROBABILIDAD DE RESULTADO (1X2)")
            r1, r2, r3 = st.columns(3)
            r1.metric("Victoria Local",     f"{pL*100:.1f}%")
            r2.metric("Empate",             f"{pE*100:.1f}%")
            r3.metric("Victoria Visitante", f"{pV*100:.1f}%")

            st.markdown("### 🔥 MERCADOS DE GOLES")
            total_goles = gL + gV
            p_over15 = 1 - (poisson(total_goles, 0) + poisson(total_goles, 1))
            p_over25 = 1 - (poisson(total_goles, 0) + poisson(total_goles, 1) + poisson(total_goles, 2))
            p_btts   = (1 - poisson(gL, 0)) * (1 - poisson(gV, 0))

            g1, g2, g3 = st.columns(3)
            g1.metric("Mas de 1.5 Goles", f"{p_over15*100:.1f}%")
            g2.metric("Mas de 2.5 Goles", f"{p_over25*100:.1f}%")
            g3.metric("Ambos Marcan",      f"{p_btts*100:.1f}%")

            st.markdown("### 📈 PREDICCION DE ESTADISTICAS")
            tabla = pd.DataFrame({
                "Metrica": [
                    "Goles",
                    "Remates Totales",
                    "Remates a Puerta",
                    "Paradas",
                    "Corners",
                    "Tarjetas",
                ],
                "Local": [
                    f"{metricas_finales.get('goles_local',           0):.1f}",
                    f"{metricas_finales.get('remates_totales_local', 0):.1f}",
                    f"{metricas_finales.get('remates_puerta_local',  0):.1f}",
                    f"{metricas_finales.get('paradas_local',         0):.1f}",
                    f"{metricas_finales.get('corners_local',         0):.1f}",
                    f"{metricas_finales.get('tarjetas_local',        0):.1f}",
                ],
                "Visitante": [
                    f"{metricas_finales.get('goles_visitante',           0):.1f}",
                    f"{metricas_finales.get('remates_totales_visitante', 0):.1f}",
                    f"{metricas_finales.get('remates_puerta_visitante',  0):.1f}",
                    f"{metricas_finales.get('paradas_visitante',         0):.1f}",
                    f"{metricas_finales.get('corners_visitante',         0):.1f}",
                    f"{metricas_finales.get('tarjetas_visitante',        0):.1f}",
                ],
                "Total": [
                    f"{metricas_finales.get('goles_partido',           0):.1f}",
                    f"{metricas_finales.get('remates_totales_partido', 0):.1f}",
                    f"{metricas_finales.get('remates_puerta_partido',  0):.1f}",
                    f"{metricas_finales.get('paradas_partido',         0):.1f}",
                    f"{metricas_finales.get('corners_partido',         0):.1f}",
                    f"{metricas_finales.get('tarjetas_partido',        0):.1f}",
                ],
            })
            st.dataframe(tabla, use_container_width=True)
