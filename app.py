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
# CARGA DE MODELOS ML
# =========================================================
PREFIJOS_METRICAS = {
    "GOLES_FAVOR": "goles_local",
    "GOLES_CONTRA": "goles_visitante",
    "REMATES_TOTALES": "remates_totales",
    "REMATES_PUERTA": "remates_puerta",
    "PARADAS": "paradas",
    "CORNERS": "corners",
    "TARJETAS": "tarjetas",
    "RESULTADO": "resultado",
    "OVER_1_5": "over_1_5",
    "OVER_2_5": "over_2_5",
    "BTTS": "btts",
}


FEATURES_MODELO = [
    "ES_LOCAL", "JORNADA", "POSICION_RIVAL",
    "GOLES_FAVOR_MA3", "GOLES_CONTRA_MA3", "REMATES_TOTALES_MA3",
    "REMATES_PUERTA_MA3", "PARADAS_MA3", "CORNERS_MA3", "TARJETAS_MA3",
    "GOLES_FAVOR_MA5", "GOLES_CONTRA_MA5", "REMATES_TOTALES_MA5",
    "REMATES_PUERTA_MA5", "PARADAS_MA5", "CORNERS_MA5", "TARJETAS_MA5",
    "GOLES_FAVOR_MA10", "GOLES_CONTRA_MA10", "REMATES_TOTALES_MA10",
    "REMATES_PUERTA_MA10", "PARADAS_MA10", "CORNERS_MA10", "TARJETAS_MA10",
]


@st.cache_resource
def cargar_modelos_ml():
    modelos = {}
    carpeta = "models"
    if not os.path.exists(carpeta):
        return modelos
    archivos = [f for f in os.listdir(carpeta) if f.endswith(".pkl")]
    for archivo in archivos:
        ruta = os.path.join(carpeta, archivo)
        nombre = archivo.replace(".pkl", "")
        try:
            obj = joblib.load(ruta)
            if isinstance(obj, dict):
                for clave, valor in obj.items():
                    metrica_interna = PREFIJOS_METRICAS.get(clave.upper())
                    if metrica_interna is None:
                        continue
                    if isinstance(valor, list):
                        for item in valor:
                            if isinstance(item, dict) and "modelo" in item:
                                modelos.setdefault(metrica_interna, []).append(item["modelo"])
                            else:
                                try:
                                    item.predict
                                    modelos.setdefault(metrica_interna, []).append(item)
                                except AttributeError:
                                    pass
                    else:
                        try:
                            valor.predict
                            modelos.setdefault(metrica_interna, []).append(valor)
                        except AttributeError:
                            pass
            else:
                try:
                    obj.predict
                    nombre_upper = nombre.upper()
                    for prefijo, metrica_interna in PREFIJOS_METRICAS.items():
                        if nombre_upper.startswith(prefijo):
                            modelos.setdefault(metrica_interna, []).append(obj)
                            break
                except AttributeError:
                    pass
        except Exception:
            pass
    return modelos


def calcular_ma(df, col, ventana):
    if col not in df.columns or df.empty:
        return 0.0
    valores = df[col].dropna().tolist()
    if not valores:
        return 0.0
    return float(np.mean(valores[-ventana:]))


def construir_features_ml(df_local, df_visit, es_local, jornada, pos_rival):
    col_map = {
        "GOLES_FAVOR": "GOL FAVOR",
        "GOLES_CONTRA": "GOL CONTRA",
        "REMATES_TOTALES": "REMATES TOTALES FAVOR",
        "REMATES_PUERTA": "REMATES PUERTA FAVOR",
        "PARADAS": "PARADAS FAVOR",
        "CORNERS": "CORNERES FAVOR",
        "TARJETAS": "TARJETAS AMARILLAS FAVOR",
    }
    if not df_local.empty and not df_visit.empty:
        df_hist = (pd.concat([df_local, df_visit]).sort_values("FECHA")
                   if "FECHA" in df_local.columns
                   else pd.concat([df_local, df_visit]))
    elif not df_local.empty:
        df_hist = df_local
    elif not df_visit.empty:
        df_hist = df_visit
    else:
        df_hist = pd.DataFrame()
    feats = {
        "ES_LOCAL": 1 if es_local else 0,
        "JORNADA": jornada,
        "POSICION_RIVAL": pos_rival if pos_rival else 10,
    }
    for nombre_feat, col_sheet in col_map.items():
        for ventana in [3, 5, 10]:
            feats[f"{nombre_feat}_MA{ventana}"] = calcular_ma(df_hist, col_sheet, ventana)
    return feats


def predecir_ml(modelos_ml, feats_local, feats_visit):
    if not modelos_ml:
        return None
    resultados = {}
    metricas_local = {
        "goles_local": feats_local,
        "remates_totales": feats_local,
        "remates_puerta": feats_local,
        "paradas": feats_local,
        "corners": feats_local,
        "tarjetas": feats_local,
    }
    metricas_visit = {"goles_visitante": feats_visit}
    todas = {**metricas_local, **metricas_visit}
    for metrica, feats in todas.items():
        lista_modelos = modelos_ml.get(metrica, [])
        if not lista_modelos:
            continue
        predicciones = []
        for modelo in lista_modelos:
            try:
                X = pd.DataFrame([feats])[FEATURES_MODELO].fillna(0)
                pred = modelo.predict(X)[0]
                predicciones.append(float(pred))
            except Exception:
                continue
        if predicciones:
            resultados[metrica] = float(np.mean(predicciones))
    pares = [
        ("goles_local", "goles_visitante", "goles_partido"),
        ("remates_totales", "remates_totales", "remates_totales_partido"),
        ("remates_puerta", "remates_puerta", "remates_puerta_partido"),
        ("paradas", "paradas", "paradas_partido"),
        ("corners", "corners", "corners_partido"),
        ("tarjetas", "tarjetas", "tarjetas_partido"),
    ]
    for k_loc, k_vis, k_partido in pares:
        v_loc = resultados.get(k_loc)
        v_vis = resultados.get(k_vis) if k_loc != k_vis else resultados.get("goles_visitante")
        if v_loc is not None and v_vis is not None:
            resultados[k_partido] = v_loc + v_vis
    return resultados if resultados else None


def combinar_metrica_ml(metricas_metrica, pred_ml, jornada):
    if pred_ml is None:
        return metricas_metrica, False
    if jornada <= 5:
        w_met, w_ml = 0.8, 0.2
    elif jornada <= 10:
        w_met, w_ml = 0.7, 0.3
    elif jornada <= 20:
        w_met, w_ml = 0.6, 0.4
    elif jornada <= 30:
        w_met, w_ml = 0.5, 0.5
    else:
        w_met, w_ml = 0.4, 0.6
    final = {}
    clave_map = {
        "goles_local": "goles_local",
        "goles_visitante": "goles_visitante",
        "goles_partido": "goles_partido",
        "remates_totales": "remates_totales_local",
        "remates_totales_partido": "remates_totales_partido",
        "remates_puerta": "remates_puerta_local",
        "remates_puerta_partido": "remates_puerta_partido",
        "paradas": "paradas_local",
        "paradas_partido": "paradas_partido",
        "corners": "corners_local",
        "corners_partido": "corners_partido",
        "tarjetas": "tarjetas_local",
        "tarjetas_partido": "tarjetas_partido",
    }
    for k_met, v_met in metricas_metrica.items():
        ml_val = None
        for k_ml, k_met2 in clave_map.items():
            if k_met2 == k_met and k_ml in pred_ml:
                ml_val = pred_ml[k_ml]
                break
        if ml_val is not None:
            final[k_met] = w_met * v_met + w_ml * ml_val
        else:
            final[k_met] = v_met
    return final, True


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


def obtener_clasificacion_desde_historico(id_libro_historico, nombre_pestana_clasificacion, jornada_buscada):
    try:
        libro_historico = client.open_by_key(id_libro_historico)
        ws_clasificacion = libro_historico.worksheet(nombre_pestana_clasificacion)
        data = ws_clasificacion.get_all_values()
        if not data or len(data) < 2:
            return pd.DataFrame()
        cabecera = data[0]
        col_jornada = None
        for idx, celda in enumerate(cabecera):
            celda_limpia = str(celda).strip()
            numeros = re.findall(r'\d+', celda_limpia)
            if numeros and int(numeros[0]) == int(jornada_buscada):
                col_jornada = idx
                break
        if col_jornada is None:
            return pd.DataFrame()
        clasificacion = []
        for fila in data[1:]:
            if len(fila) <= col_jornada:
                continue
            pos_raw = str(fila[0]).strip()
            equipo_raw = str(fila[col_jornada]).strip()
            if not pos_raw or not equipo_raw:
                continue
            try:
                pos_int = int(pos_raw)
            except ValueError:
                continue
            if equipo_raw.upper() in ("", "NONE", "N/A", "-"):
                continue
            clasificacion.append({"EQUIPO": equipo_raw.upper().strip(), "POS": pos_int})
        return pd.DataFrame(clasificacion) if clasificacion else pd.DataFrame()
    except Exception as e:
        st.warning(f"Error leyendo clasificacion: {e}")
        return pd.DataFrame()


def cargar_equivalencias(id_libro_historico, nombre_pestana_equivalencias):
    try:
        libro_historico = client.open_by_key(id_libro_historico)
        ws_equiv = libro_historico.worksheet(nombre_pestana_equivalencias)
        data = ws_equiv.get_all_values()
        if not data or len(data) < 2:
            return pd.DataFrame()
        cabecera = data[0]
        filas = data[1:]
        return pd.DataFrame(filas, columns=cabecera if cabecera else None)
    except Exception as e:
        st.warning(f"Error cargando equivalencias: {e}")
        return pd.DataFrame()


def obtener_equivalencia_nombre(nombre_app, df_equivalencias):
    if df_equivalencias.empty:
        return nombre_app.upper().strip()
    nombre_buscar = nombre_app.upper().strip()
    pares = []
    for _, row in df_equivalencias.iterrows():
        col_a = str(row.iloc[0]).upper().strip() if pd.notna(row.iloc[0]) else ""
        col_b = str(row.iloc[1]).upper().strip() if pd.notna(row.iloc[1]) else ""
        if col_a or col_b:
            pares.append((col_a, col_b))
    for col_a, col_b in pares:
        if col_a == nombre_buscar and col_b:
            return col_b
    for col_a, col_b in pares:
        if col_a and col_a in nombre_buscar and col_b:
            return col_b
    for col_a, col_b in pares:
        if col_b and nombre_buscar in col_b and col_b:
            return col_b
    for col_a, col_b in pares:
        if col_b and col_b in nombre_buscar and col_b:
            return col_b
    return nombre_buscar


def detectar_columna(df, palabras_clave):
    for col in df.columns.tolist():
        col_lower = col.lower()
        for palabra in palabras_clave:
            if palabra.lower() in col_lower:
                return col
    return None


def mapear_columnas(df):
    mapeo = {}
    columnas_buscar = {
        "GOL FAVOR": ["gol favor", "goles favor", "gf", "goles_marcados"],
        "GOL CONTRA": ["gol contra", "goles contra", "gc", "goles_recibidos"],
        "REMATES TOTALES FAVOR": ["remates totales favor", "remates totales f", "total shots for", "remates favor"],
        "REMATES TOTALES CONTRA": ["remates totales contra", "remates totales c", "total shots against", "remates contra"],
        "REMATES PUERTA FAVOR": ["remates puerta favor", "remates a puerta favor", "remates puerta f", "shots on target for"],
        "REMATES PUERTA CONTRA": ["remates puerta contra", "remates a puerta contra", "remates puerta c", "shots on target against"],
        "PARADAS FAVOR": ["paradas favor", "paradas f", "saves for", "paradas realizadas"],
        "PARADAS CONTRA": ["paradas contra", "paradas c", "saves against"],
        "CORNERES FAVOR": ["corneres favor", "corners favor", "corner favor"],
        "CORNERES CONTRA": ["corneres contra", "corners contra", "corner contra"],
        "TARJETAS AMARILLAS FAVOR": ["tarjetas amarillas favor", "amarillas favor", "yellow cards for"],
        "TARJETAS AMARILLAS CONTRA": ["tarjetas amarillas contra", "amarillas contra", "yellow cards against"],
        "JORNADA": ["jornada", "jor", "round", "matchday"],
        "RIVAL": ["rival", "oponente", "equipo rival", "opponent"],
        "POSICION RIVAL": ["posicion rival", "posición rival", "pos rival"],
        "FECHA": ["fecha", "date", "fecha partido"],
    }
    for nombre_estandar, patrones in columnas_buscar.items():
        col_encontrada = detectar_columna(df, patrones)
        if col_encontrada:
            mapeo[col_encontrada] = nombre_estandar
    return mapeo


def normalizar_y_validar(df):
    if df.empty:
        return df
    mapeo = mapear_columnas(df)
    if mapeo:
        df = df.rename(columns=mapeo)
    df.columns = [str(col).strip().upper() for col in df.columns]
    columnas_numericas = [
        "GOL FAVOR", "GOL CONTRA", "REMATES TOTALES FAVOR", "REMATES TOTALES CONTRA",
        "REMATES PUERTA FAVOR", "REMATES PUERTA CONTRA", "PARADAS FAVOR", "PARADAS CONTRA",
        "CORNERES FAVOR", "CORNERES CONTRA", "TARJETAS AMARILLAS FAVOR", "TARJETAS AMARILLAS CONTRA",
        "JORNADA", "POSICION RIVAL"
    ]
    for col in columnas_numericas:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')
    if "FECHA" in df.columns:
        df["FECHA"] = pd.to_datetime(df["FECHA"], errors='coerce', dayfirst=True)
        df = df.dropna(subset=["FECHA"])
        df = df.sort_values("FECHA")
    if "JORNADA" in df.columns:
        df = df.dropna(subset=["JORNADA"])
        df["JORNADA"] = df["JORNADA"].astype(int)
    if "RIVAL" in df.columns:
        df["RIVAL"] = df["RIVAL"].astype(str).str.upper().str.strip()
    return df


def cargar_pestana_equipo(ws):
    try:
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if df.empty or len(df.columns) == 0:
            return pd.DataFrame()
        df = normalizar_y_validar(df)
        return df
    except Exception as e:
        st.warning(f"Error cargando pestaña: {e}")
        return pd.DataFrame()


def filtrar_bloque(df, tipo, grupo=None):
    if df.empty:
        return df
    if tipo == 1:
        return df.copy()
    if tipo == 2:
        return df[df["JORNADA"] >= 1].copy() if "JORNADA" in df.columns else df.copy()
    if tipo == 3:
        return df.tail(5).copy()
    if tipo == 4:
        return df.tail(3).copy()
    if tipo == 5:
        if grupo is not None and "POSICION RIVAL" in df.columns:
            return df[df["POSICION RIVAL"].isin(grupo)].copy()
    return df.copy()


def limpiar_ruido(lista):
    lista = [x for x in lista if pd.notna(x)]
    if len(lista) <= 2:
        return lista
    lista = sorted(lista)
    return lista[1:-1]


def calcular_metricas(dfL, dfV, jornada):
    metricas = {}
    columnas_def = [
        ("GOL FAVOR", "GOL CONTRA", "goles"),
        ("REMATES TOTALES FAVOR", "REMATES TOTALES CONTRA", "remates_totales"),
        ("REMATES PUERTA FAVOR", "REMATES PUERTA CONTRA", "remates_puerta"),
        ("PARADAS FAVOR", "PARADAS CONTRA", "paradas"),
        ("CORNERES FAVOR", "CORNERES CONTRA", "corners"),
        ("TARJETAS AMARILLAS CONTRA", "TARJETAS AMARILLAS FAVOR", "tarjetas"),
    ]
    for colF, colC, nombre in columnas_def:
        tieneF_L = colF in dfL.columns
        tieneC_L = colC in dfL.columns
        tieneF_V = colF in dfV.columns
        tieneC_V = colC in dfV.columns
        if not (tieneF_L and tieneC_L and tieneF_V and tieneC_V):
            metricas[nombre + "_local"] = 0
            metricas[nombre + "_visitante"] = 0
            metricas[nombre + "_partido"] = 0
            continue
        try:
            lista_L_fav = dfL[colF].dropna().tolist()
            lista_V_contra = dfV[colC].dropna().tolist()
            if jornada >= 14:
                lista_L_fav = limpiar_ruido(lista_L_fav)
                lista_V_contra = limpiar_ruido(lista_V_contra)
            m_local = (np.mean(lista_L_fav) + np.mean(lista_V_contra)) / 2 if lista_L_fav and lista_V_contra else 0
            lista_V_fav = dfV[colF].dropna().tolist()
            lista_L_contra = dfL[colC].dropna().tolist()
            if jornada >= 14:
                lista_V_fav = limpiar_ruido(lista_V_fav)
                lista_L_contra = limpiar_ruido(lista_L_contra)
            m_visit = (np.mean(lista_V_fav) + np.mean(lista_L_contra)) / 2 if lista_V_fav and lista_L_contra else 0
            metricas[nombre + "_local"] = m_local
            metricas[nombre + "_visitante"] = m_visit
            metricas[nombre + "_partido"] = m_local + m_visit
        except:
            metricas[nombre + "_local"] = 0
            metricas[nombre + "_visitante"] = 0
            metricas[nombre + "_partido"] = 0
    return metricas


def combinar_bloques(b1, b2, b3, b4, b5):
    final = {}
    for k in b1.keys():
        final[k] = (b1[k] * 0.10 + b2[k] * 0.40 + b3[k] * 0.15 + b4[k] * 0.25 + b5[k] * 0.10)
    return final


def poisson(lam, k):
    if lam <= 0:
        return 1 if k == 0 else 0
    try:
        return (lam**k * exp(-lam)) / factorial(k)
    except:
        return 0


def prob_1x2(gL, gV):
    max_g = 8
    pL = pE = pV = 0.0
    for i in range(max_g + 1):
        for j in range(max_g + 1):
            try:
                p = poisson(gL, i) * poisson(gV, j)
                if i > j:
                    pL += p
                elif i == j:
                    pE += p
                else:
                    pV += p
            except:
                continue
    total = pL + pE + pV
    if total > 0:
        pL /= total
        pE /= total
        pV /= total
    return pL, pE, pV


def grupo(pos):
    if 1 <= pos <= 4:
        return [1, 2, 3, 4]
    if 5 <= pos <= 10:
        return [5, 6, 7, 8, 9, 10]
    if 11 <= pos <= 16:
        return [11, 12, 13, 14, 15, 16]
    return list(range(17, 26))


# =========================================================
# AUTENTICACION
# =========================================================
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False


if not st.session_state['autenticado']:
    st.markdown("<h2 style='text-align: center;'>🔐 Acceso al Sistema</h2>", unsafe_allow_html=True)
    with st.form("login"):
        u = st.text_input("Usuario:")
        p = st.text_input("Contrasena:", type="password")
        if st.form_submit_button("Entrar"):
            if check_user(u, p):
                st.session_state['autenticado'] = True
                st.rerun()
            else:
                st.error("Datos incorrectos")
    st.stop()


# =========================================================
# INTERFAZ PRINCIPAL
# =========================================================
st.markdown("<h2 style='text-align: center;'>⚽ ANALIZADOR DE PARTIDOS PRO</h2>", unsafe_allow_html=True)


modelos_ml = cargar_modelos_ml()
n_modelos = sum(len(v) for v in modelos_ml.values())
if n_modelos > 0:
    st.sidebar.success(f"🤖 ML activo: {n_modelos} modelos cargados ({len(modelos_ml)} metricas)")
else:
    st.sidebar.info("Sin modelos ML. Usando solo rama metrica.")


try:
    sh_ligas = client.open_by_key(ID_CONTROL).worksheet("LIGAS")
    df_ligas = pd.DataFrame(sh_ligas.get_all_records())


    with st.expander("🔧 DIAGNOSTICO - Hoja LIGAS"):
        st.dataframe(df_ligas)


    mask_historico = df_ligas['Nombre de la liga'].str.upper().str.contains('HISTORICO|HISTÓRICO', na=False)
    df_historico = df_ligas[mask_historico]
    df_competiciones = df_ligas[~mask_historico]


    id_historico = None
    if not df_historico.empty:
        id_historico = str(df_historico.iloc[0]['ID del libro']).strip()


    if df_competiciones.empty:
        st.error("No hay competiciones disponibles en la hoja LIGAS.")
        st.stop()


    col1, col2 = st.columns(2)
    liga_sel = col1.selectbox("🏆 Seleccionar Liga", df_competiciones['Nombre de la liga'].tolist())


    PESTANA_CLASIFICACION = "CLASIFICACION LALIGA 25/26"
    PESTANA_EQUIVALENCIAS = "EQUIVALENCIA NOMENCLATURA LALIGA25/26"


    id_actual = df_competiciones[df_competiciones['Nombre de la liga'] == liga_sel]['ID del libro'].values[0]
    jor_sel = col2.selectbox("📅 Jornada", list(range(1, 45)))


    cache_key = f"pestanas_{id_actual}"
    if cache_key not in st.session_state:
        libro_temp = client.open_by_key(id_actual)
        excluir = ["config", "partido a analizar", "predicciones"]
        st.session_state[cache_key] = [
            s.title for s in libro_temp.worksheets()
            if s.title.lower() not in [e.lower() for e in excluir]
        ]


    pestanas = st.session_state[cache_key]
    locales = [t for t in pestanas if "LOCAL" in t.upper()]
    visitantes = [t for t in pestanas if "VISITANTE" in t.upper()]


    def clean(n):
        return n.replace(" LOCAL", "").replace(" VISITANTE", "").strip()


    cl, cv = st.columns(2)
    eq_l = cl.selectbox("🏠 Equipo Local", locales, format_func=clean)
    visitantes_filtrados = [v for v in visitantes if clean(eq_l).upper() not in v.upper()]
    eq_v = cv.selectbox("🚀 Equipo Visitante", visitantes_filtrados, format_func=clean)


    if st.button("📊 GENERAR ANALISIS"):
        st.divider()


        try:
            libro = client.open_by_key(id_actual)
            ws_local = libro.worksheet(eq_l)
            ws_visit = libro.worksheet(eq_v)


            df_local = cargar_pestana_equipo(ws_local)
            df_visit = cargar_pestana_equipo(ws_visit)


            with st.expander("🔧 Diagnostico - Columnas encontradas en equipos"):
                st.write("**Columnas LOCAL:**", list(df_local.columns) if not df_local.empty else "DataFrame vacio")
                st.write("**Columnas VISITANTE:**", list(df_visit.columns) if not df_visit.empty else "DataFrame vacio")
                st.write(f"**Filas LOCAL:** {len(df_local)}")
                st.write(f"**Filas VISITANTE:** {len(df_visit)}")


            if df_local.empty or df_visit.empty:
                st.error("No se pudieron cargar los datos de los equipos.")
                st.stop()


            if not id_historico:
                st.error("No se encontro el ID del libro HISTORICO DE PREDICCIONES.")
                st.stop()


            jornada_clasificacion = jor_sel - 1
            if jornada_clasificacion < 1:
                st.error("No hay clasificacion disponible para la Jornada 1.")
                st.stop()


            df_equivalencias = cargar_equivalencias(id_historico, PESTANA_EQUIVALENCIAS)


            clasif = obtener_clasificacion_desde_historico(id_historico, PESTANA_CLASIFICACION, jornada_clasificacion)


            if clasif.empty:
                st.error(f"No se pudo obtener la clasificacion para la Jornada {jornada_clasificacion}.")
                st.stop()


            with st.expander("🔍 Clasificacion obtenida (jornada historica)"):
                st.write(f"**Jornada consultada:** {jornada_clasificacion}")
                st.dataframe(clasif, use_container_width=True)


            nombre_local_clean = clean(eq_l).upper()
            nombre_visit_clean = clean(eq_v).upper()


            nombre_local_clasif = obtener_equivalencia_nombre(nombre_local_clean, df_equivalencias)
            nombre_visit_clasif = obtener_equivalencia_nombre(nombre_visit_clean, df_equivalencias)


            local_info = clasif[clasif["EQUIPO"] == nombre_local_clasif]
            visit_info = clasif[clasif["EQUIPO"] == nombre_visit_clasif]


            if local_info.empty:
                st.error(f"No se encontro '{nombre_local_clasif}' en la clasificacion.")
                st.info(f"Equipos disponibles: {clasif['EQUIPO'].tolist()}")
                st.stop()


            if visit_info.empty:
                st.error(f"No se encontro '{nombre_visit_clasif}' en la clasificacion.")
                st.info(f"Equipos disponibles: {clasif['EQUIPO'].tolist()}")
                st.stop()


            pos_local = local_info.iloc[0]["POS"]
            pos_visit = visit_info.iloc[0]["POS"]


            st.success(f"Clasificacion Jornada {jornada_clasificacion}: {nombre_local_clean} -> {nombre_local_clasif} (Pos {pos_local}) | {nombre_visit_clean} -> {nombre_visit_clasif} (Pos {pos_visit})")


            grupo_local_rival = grupo(pos_visit)
            grupo_visit_rival = grupo(pos_local)


            bloques = []
            for b in [1, 2, 3, 4, 5]:
                dfL_b = filtrar_bloque(df_local, b, grupo_local_rival if b == 5 else None)
                dfV_b = filtrar_bloque(df_visit, b, grupo_visit_rival if b == 5 else None)
                metricas_b = calcular_metricas(dfL_b, dfV_b, jor_sel)
                bloques.append(metricas_b)


            b1, b2, b3, b4, b5 = bloques
            metricas_metrica = combinar_bloques(b1, b2, b3, b4, b5)


            feats_local = construir_features_ml(df_local, pd.DataFrame(), True, jor_sel, pos_visit)
            feats_visit = construir_features_ml(pd.DataFrame(), df_visit, False, jor_sel, pos_local)
            pred_ml = predecir_ml(modelos_ml, feats_local, feats_visit)


            metricas_finales, usado_ml = combinar_metrica_ml(metricas_metrica, pred_ml, jor_sel)


            if usado_ml:
                st.info(f"🤖 ML activo — combinando {n_modelos} modelos con rama metrica (jornada {jor_sel})")
            else:
                st.info("📐 Solo rama metrica (no hay modelos ML disponibles)")


            # Asegurar que existan las métricas visitante si no están
            for met in ["remates_totales", "remates_puerta", "paradas", "corners", "tarjetas"]:
                key_local = f"{met}_local"
                key_vis = f"{met}_visitante"
                key_total = f"{met}_partido"
                if key_vis not in metricas_finales:
                    local_val = metricas_finales.get(key_local, 0)
                    total_val = metricas_finales.get(key_total, 0)
                    metricas_finales[key_vis] = max(total_val - local_val, 0)
            if "goles_visitante" not in metricas_finales:
                metricas_finales["goles_visitante"] = max(
                    metricas_finales.get("goles_partido", 0) - metricas_finales.get("goles_local", 0), 0
                )


            gL = metricas_finales.get("goles_local", 0)
            gV = metricas_finales.get("goles_visitante", 0)


            pL, pE, pV = prob_1x2(gL, gV)


            st.markdown("---")
            st.markdown("### 🏆 PROBABILIDAD DE RESULTADO (1X2)")
            r1, r2, r3 = st.columns(3)
            r1.metric("Victoria Local", f"{pL*100:.1f}%")
            r2.metric("Empate", f"{pE*100:.1f}%")
            r3.metric("Victoria Visitante", f"{pV*100:.1f}%")


            st.markdown("### 🔥 MERCADOS DE GOLES")
            total_goles = gL + gV
            p_over15 = 1 - (poisson(total_goles, 0) + poisson(total_goles, 1))
            p_over25 = 1 - (poisson(total_goles, 0) + poisson(total_goles, 1) + poisson(total_goles, 2))
            p_btts = (1 - poisson(gL, 0)) * (1 - poisson(gV, 0))


            g1, g2, g3 = st.columns(3)
            g1.metric("Mas de 1.5 Goles", f"{p_over15*100:.1f}%")
            g2.metric("Mas de 2.5 Goles", f"{p_over25*100:.1f}%")
            g3.metric("Ambos Marcan", f"{p_btts*100:.1f}%")


            st.markdown("### 📈 PREDICCION DE ESTADISTICAS")
            tabla = pd.DataFrame({
                "Metrica": ["Goles", "Remates Totales", "Remates a Puerta", "Paradas", "Corners", "Tarjetas"],
                "Local": [
                    f"{metricas_finales.get('goles_local', 0):.1f}",
                    f"{metricas_finales.get('remates_totales_local', 0):.1f}",
                    f"{metricas_finales.get('remates_puerta_local', 0):.1f}",
                    f"{metricas_finales.get('paradas_local', 0):.1f}",
                    f"{metricas_finales.get('corners_local', 0):.1f}",
                    f"{metricas_finales.get('tarjetas_local', 0):.1f}",
                ],
                "Visitante": [
                    f"{metricas_finales.get('goles_visitante', 0):.1f}",
                    f"{metricas_finales.get('remates_totales_visitante', 0):.1f}",
                    f"{metricas_finales.get('remates_puerta_visitante', 0):.1f}",
                    f"{metricas_finales.get('paradas_visitante', 0):.1f}",
                    f"{metricas_finales.get('corners_visitante', 0):.1f}",
                    f"{metricas_finales.get('tarjetas_visitante', 0):.1f}",
                ],
                "Total": [
                    f"{metricas_finales.get('goles_partido', 0):.1f}",
                    f"{metricas_finales.get('remates_totales_partido', 0):.1f}",
                    f"{metricas_finales.get('remates_puerta_partido', 0):.1f}",
                    f"{metricas_finales.get('paradas_partido', 0):.1f}",
                    f"{metricas_finales.get('corners_partido', 0):.1f}",
                    f"{metricas_finales.get('tarjetas_partido', 0):.1f}",
                ],
            })
            st.dataframe(tabla, use_container_width=True)


        except Exception as e:
            st.error(f"Error en el analisis: {e}")
            st.info("Revisa el panel de diagnostico para ver las columnas disponibles.")


except Exception as e:
    st.error(f"Error general: {e}")
