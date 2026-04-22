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

# --- CONEXIÓN ---
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

def calcular_ma(df, col, n):
    if col not in df.columns or df.empty:
        return 0
    return float(np.mean(df[col].dropna().tolist()[-n:]))

def construir_features_ml(df, es_local, jornada, pos):
    feats = {"ES_LOCAL":1 if es_local else 0,"JORNADA":jornada,"POSICION_RIVAL":pos}
    for c in ["GOL FAVOR","GOL CONTRA"]:
        for n in [3,5,10]:
            feats[f"{c.replace(' ','_')}_MA{n}"] = calcular_ma(df, c, n)
    return feats

def predecir_ml(modelos, featsL, featsV):
    if not modelos:
        return None
    res={}
    for met,mods in modelos.items():
        vals=[]
        for m in mods:
            try:
                X=pd.DataFrame([featsL])[FEATURES_MODELO].fillna(0)
                vals.append(float(m.predict(X)[0]))
            except: pass
        if vals: res[met]=np.mean(vals)
    return res

def combinar(metricas, ml, j):
    if ml is None:
        return metricas
    w=0.6 if j>20 else 0.3
    final={}
    for k,v in metricas.items():
        final[k]=v*(1-w)+ml.get(k.replace("_local","").replace("_visitante",""),0)*w
    return final

# =========================================================
# UI
# =========================================================
st.title("⚽ ANALIZADOR PRO")

modelos_ml=cargar_modelos_ml()

if st.button("TEST DEMO"):
    # SIMULACION (para ver display funcionando)
    metricas_finales={
        "goles_local":1.8,
        "goles_visitante":1.2,
        "goles_partido":3.0,
        "remates_totales_local":14,
        "remates_totales_partido":25,
        "remates_puerta_local":6,
        "remates_puerta_partido":10,
        "paradas_local":3,
        "paradas_partido":7,
        "corners_local":5,
        "corners_partido":9,
        "tarjetas_local":2,
        "tarjetas_partido":4,
    }

    # ✅ FIX CLAVE
    for met in ["remates_totales","remates_puerta","paradas","corners","tarjetas"]:
        if f"{met}_visitante" not in metricas_finales:
            metricas_finales[f"{met}_visitante"]=max(
                metricas_finales.get(f"{met}_partido",0)-
                metricas_finales.get(f"{met}_local",0),0
            )

    gL=metricas_finales["goles_local"]
    gV=metricas_finales["goles_visitante"]

    # RESULTADO
    st.subheader("🏆 1X2")
    c1,c2,c3=st.columns(3)
    c1.metric("Local",f"{gL:.2f}")
    c2.metric("Empate","--")
    c3.metric("Visitante",f"{gV:.2f}")

    # GOLES
    st.subheader("🔥 GOLES")
    total=gL+gV
    st.metric("Total esperado",f"{total:.2f}")

    # TABLA
    st.subheader("📊 ESTADISTICAS")

    tabla=pd.DataFrame({
        "Metrica":["Goles","Remates","Puerta","Paradas","Corners","Tarjetas"],
        "Local":[
            metricas_finales["goles_local"],
            metricas_finales["remates_totales_local"],
            metricas_finales["remates_puerta_local"],
            metricas_finales["paradas_local"],
            metricas_finales["corners_local"],
            metricas_finales["tarjetas_local"],
        ],
        "Visitante":[
            metricas_finales["goles_visitante"],
            metricas_finales["remates_totales_visitante"],
            metricas_finales["remates_puerta_visitante"],
            metricas_finales["paradas_visitante"],
            metricas_finales["corners_visitante"],
            metricas_finales["tarjetas_visitante"],
        ],
        "Total":[
            metricas_finales["goles_partido"],
            metricas_finales["remates_totales_partido"],
            metricas_finales["remates_puerta_partido"],
            metricas_finales["paradas_partido"],
            metricas_finales["corners_partido"],
            metricas_finales["tarjetas_partido"],
        ]
    })

    st.dataframe(tabla,use_container_width=True)
