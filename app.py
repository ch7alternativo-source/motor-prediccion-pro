import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
from math import exp, factorial
import requests
import re

st.set_page_config(page_title="Analizador de Partidos PRO", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)
ID_CONTROL = "1E0oz34jM0-kAyh_XUVwRrI_wy2VK3Rmr9ExgxbkLXSA"

# Nombre fijo del libro histórico (de momento solo este)
NOMBRE_LIBRO_HISTORICO = "HISTORICO DE PREDICCIONES"
HOJA_CLASIF_LALIGA = "CLASIFICACION LALIGA 25/26"
HOJA_EQUIVALENCIAS_LALIGA = "EQUIVALENCIA NOMENCLATURA LALIGA25/26"

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

# --- SESIÓN ---
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
    st.stop()

# =========================================================
# DETECCIÓN INTELIGENTE DE COLUMNAS (basada en palabras clave)
# =========================================================
def detectar_columna(df, palabras_clave):
    df_cols = df.columns.tolist()
    for col in df_cols:
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
        "REMATES PUERTA FAVOR": ["remates puerta favor", "remates a puerta favor", "remates puerta f", "rematrs puerta favor", "shots on target for"],
        "REMATES PUERTA CONTRA": ["remates puerta contra", "remates a puerta contra", "remates puerta c", "rematrs puerta contra", "shots on target against"],
        "PARADAS FAVOR": ["paradas favor", "paradas f", "saves for", "paradas realizadas"],
        "PARADAS CONTRA": ["paradas contra", "paradas c", "saves against"],
        "CORNERES FAVOR": ["corneres favor", "corners favor", "córners favor", "corner favor"],
        "CORNERES CONTRA": ["corneres contra", "corners contra", "córners contra", "corner contra"],
        "TARJETAS AMARILLAS FAVOR": ["tarjetas amarillas favor", "amarillas favor", "yellow cards for", "tarjetas amarillas favor", "tarjetas amarillas favor("],
        "TARJETAS AMARILLAS CONTRA": ["tarjetas amarillas contra", "amarillas contra", "yellow cards against", "tarjetas amarillas contra"],
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

# --- CARGA DE PESTAÑAS ---
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

# =========================================================
# CLASIFICACIÓN DESDE LIBRO "HISTORICO DE PREDICCIONES"
# =========================================================
@st.cache_data(ttl=300)
def cargar_clasificacion_laliga(jornada_objetivo: int) -> pd.DataFrame:
    """
    Carga la clasificación de LaLiga 25/26 para una jornada concreta
    desde el libro HISTORICO DE PREDICCIONES.
    """
    try:
        libro_hist = client.open(NOMBRE_LIBRO_HISTORICO)
        ws_clasif = libro_hist.worksheet(HOJA_CLASIF_LALIGA)
        df = pd.DataFrame(ws_clasif.get_all_records())
        if df.empty:
            return pd.DataFrame()
        # Normalizamos nombres de columnas esperadas
        df.columns = [str(c).strip().upper() for c in df.columns]
        # Esperamos columnas: JORNADA, POSICION, EQUIPO
        if "JORNADA" not in df.columns or "POSICION" not in df.columns or "EQUIPO" not in df.columns:
            return pd.DataFrame()
        df["JORNADA"] = pd.to_numeric(df["JORNADA"], errors="coerce").astype("Int64")
        df = df.dropna(subset=["JORNADA"])
        df["JORNADA"] = df["JORNADA"].astype(int)
        df["EQUIPO"] = df["EQUIPO"].astype(str).str.upper().str.strip()
        # Filtramos por jornada objetivo
        df_j = df[df["JORNADA"] == jornada_objetivo].copy()
        return df_j
    except Exception as e:
        st.warning(f"Error cargando clasificación histórica: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def cargar_equivalencias_laliga() -> pd.DataFrame:
    """
    Carga la tabla de equivalencias de nombres entre el libro LALIGA 25/26
    y la pestaña de clasificación del histórico.
    """
    try:
        libro_hist = client.open(NOMBRE_LIBRO_HISTORICO)
        ws_eq = libro_hist.worksheet(HOJA_EQUIVALENCIAS_LALIGA)
        df = pd.DataFrame(ws_eq.get_all_records())
        if df.empty:
            return pd.DataFrame()
        df.columns = [str(c).strip().upper() for c in df.columns]
        # Esperamos columnas tipo:
        # "NOMBRE EN LIBRO LALIGA 25/26" y "NOMBRE EN PESTAÑA CLASIFICACION LALIGA25/26"
        return df
    except Exception as e:
        st.warning(f"Error cargando equivalencias de nombres: {e}")
        return pd.DataFrame()

def obtener_posicion_equipo_laliga(nombre_en_libro: str, jornada_app: int) -> int:
    """
    Dado el nombre del equipo tal como aparece en el libro LALIGA 25/26
    y la jornada seleccionada en la app, devuelve la POSICION del equipo
    en la jornada anterior (jornada_app - 1) usando:
    - CLASIFICACION LALIGA 25/26
    - EQUIVALENCIA NOMENCLATURA LALIGA25/26
    """
    # Jornada anterior
    jornada_objetivo = max(1, jornada_app - 1)

    eq_df = cargar_equivalencias_laliga()
    if eq_df.empty:
        raise ValueError("No se pudo cargar la tabla de equivalencias de nombres.")

    cols = eq_df.columns.tolist()
    # Buscamos columnas por contenido aproximado
    col_libro = None
    col_clasif = None
    for c in cols:
        c_up = c.upper()
        if "NOMBRE EN LIBRO" in c_up:
            col_libro = c
        if "NOMBRE EN PESTAÑA" in c_up or "CLASIFICACION" in c_up:
            col_clasif = c

    if col_libro is None or col_clasif is None:
        raise ValueError("No se encontraron columnas de equivalencia esperadas en la hoja de equivalencias.")

    nombre_buscar = nombre_en_libro.upper().strip()
    eq_df[col_libro] = eq_df[col_libro].astype(str).str.upper().str.strip()
    fila_eq = eq_df[eq_df[col_libro] == nombre_buscar]

    if fila_eq.empty:
        raise ValueError(f"No se encontró equivalencia para el equipo '{nombre_en_libro}' en la hoja de equivalencias.")

    nombre_en_clasif = str(fila_eq.iloc[0][col_clasif]).upper().strip()

    clasif_df = cargar_clasificacion_laliga(jornada_objetivo)
    if clasif_df.empty:
        raise ValueError(f"No hay clasificación cargada para la jornada {jornada_objetivo}.")

    clasif_df["EQUIPO"] = clasif_df["EQUIPO"].astype(str).str.upper().str.strip()
    fila_clasif = clasif_df[clasif_df["EQUIPO"] == nombre_en_clasif]

    if fila_clasif.empty:
        raise ValueError(f"No se encontró el equipo '{nombre_en_clasif}' en la clasificación de la jornada {jornada_objetivo}.")

    pos = fila_clasif.iloc[0]["POSICION"]
    try:
        return int(pos)
    except:
        raise ValueError(f"Posición no válida para el equipo '{nombre_en_clasif}' en la clasificación.")

# --- FILTROS DE BLOQUES ---
def filtrar_bloque(df, tipo, grupo=None):
    if df.empty:
        return df
    if tipo == 1:
        return df.copy()
    if tipo == 2:
        return df[df["JORNADA"] >= 1].copy()
    if tipo == 3:
        return df.tail(5).copy()
    if tipo == 4:
        return df.tail(3).copy()
    if tipo == 5:
        if grupo is not None and "POSICION RIVAL" in df.columns:
            return df[df["POSICION RIVAL"].isin(grupo)].copy()
    return df.copy()

# --- LIMPIEZA DE RUIDO ---
def limpiar_ruido(lista):
    lista = [x for x in lista if pd.notna(x)]
    if len(lista) <= 2:
        return lista
    lista = sorted(lista)
    return lista[1:-1]

# --- CÁLCULO DE MÉTRICAS ---
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

            if len(lista_L_fav) > 0 and len(lista_V_contra) > 0:
                m_local = (np.mean(lista_L_fav) + np.mean(lista_V_contra)) / 2
            else:
                m_local = 0

            lista_V_fav = dfV[colF].dropna().tolist()
            lista_L_contra = dfL[colC].dropna().tolist()

            if jornada >= 14:
                lista_V_fav = limpiar_ruido(lista_V_fav)
                lista_L_contra = limpiar_ruido(lista_L_contra)

            if len(lista_V_fav) > 0 and len(lista_L_contra) > 0:
                m_visit = (np.mean(lista_V_fav) + np.mean(lista_L_contra)) / 2
            else:
                m_visit = 0

            metricas[nombre + "_local"] = m_local
            metricas[nombre + "_visitante"] = m_visit
            metricas[nombre + "_partido"] = m_local + m_visit

        except Exception:
            metricas[nombre + "_local"] = 0
            metricas[nombre + "_visitante"] = 0
            metricas[nombre + "_partido"] = 0

    return metricas

# --- PESOS POR JORNADA ---
def pesos_por_jornada(j):
    if j <= 5: return (0.2, 0.8)
    if j <= 10: return (0.3, 0.7)
    if j <= 14: return (0.4, 0.6)
    if j <= 20: return (0.5, 0.5)
    if j <= 30: return (0.6, 0.4)
    return (0.65, 0.35)

# --- COMBINACIÓN DE BLOQUES ---
def combinar_bloques(b1, b2, b3, b4, b5):
    final = {}
    for k in b1.keys():
        final[k] = (
            b1[k] * 0.10 +
            b2[k] * 0.40 +
            b3[k] * 0.15 +
            b4[k] * 0.25 +
            b5[k] * 0.10
        )
    return final

# --- POISSON ---
def poisson(lam, k):
    if lam <= 0:
        return 1 if k == 0 else 0
    try:
        return (lam**k * exp(-lam)) / factorial(k)
    except:
        return 0

# --- PROBABILIDAD 1X2 ---
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

# =========================================================
# INTERFAZ PRINCIPAL
# =========================================================
st.markdown("<h2 style='text-align: center;'>⚽ ANALIZADOR DE PARTIDOS PRO</h2>", unsafe_allow_html=True)

try:
    sh_ligas = client.open_by_key(ID_CONTROL).worksheet("LIGAS")
    df_ligas = pd.DataFrame(sh_ligas.get_all_records())

    col1, col2 = st.columns(2)
    liga_sel = col1.selectbox("🏆 Seleccionar Liga", df_ligas['Nombre de la liga'])
    id_actual = df_ligas[df_ligas['Nombre de la liga'] == liga_sel]['ID del libro'].values[0]
    jor_sel = col2.selectbox("📅 Jornada", list(range(1, 45)))

    cache_key = f"pestanas_{id_actual}"
    if cache_key not in st.session_state:
        libro_temp = client.open_by_key(id_actual)
        excluir = ["config", "partido a analizar", "predicciones"]
        st.session_state[cache_key] = [s.title for s in libro_temp.worksheets() if s.title.lower() not in [e.lower() for e in excluir]]

    pestanas = st.session_state[cache_key]

    locales = [t for t in pestanas if "LOCAL" in t.upper()]
    visitantes = [t for t in pestanas if "VISITANTE" in t.upper()]

    def clean(n):
        return n.replace(" LOCAL", "").replace(" VISITANTE", "").strip()

    cl, cv = st.columns(2)
    eq_l = cl.selectbox("🏠 Equipo Local", locales, format_func=clean)

    visitantes_filtrados = [v for v in visitantes if clean(eq_l).upper() not in v.upper()]
    eq_v = cv.selectbox("🚀 Equipo Visitante", visitantes_filtrados, format_func=clean)

    if st.button("📊 GENERAR ANÁLISIS"):
        st.divider()
        try:
            libro = client.open_by_key(id_actual)
            ws_local = libro.worksheet(eq_l)
            ws_visit = libro.worksheet(eq_v)

            df_local = cargar_pestana_equipo(ws_local)
            df_visit = cargar_pestana_equipo(ws_visit)

            with st.expander("🔧 Diagnóstico - Columnas encontradas"):
                st.write("**Columnas LOCAL:**", list(df_local.columns) if not df_local.empty else "DataFrame vacío")
                st.write("**Columnas VISITANTE:**", list(df_visit.columns) if not df_visit.empty else "DataFrame vacío")
                st.write(f"**Filas LOCAL:** {len(df_local)}")
                st.write(f"**Filas VISITANTE:** {len(df_visit)}")

            if df_local.empty or df_visit.empty:
                st.error("❌ No se pudieron cargar los datos de los equipos. Verifica que las pestañas tengan datos.")
                st.stop()

            # --- CLASIFICACIÓN DESDE HISTÓRICO (JORNADA ANTERIOR) ---
            nombre_local_clean = clean(eq_l).upper()
            nombre_visit_clean = clean(eq_v).upper()

            try:
                pos_local = obtener_posicion_equipo_laliga(nombre_local_clean, jor_sel)
                pos_visit = obtener_posicion_equipo_laliga(nombre_visit_clean, jor_sel)
            except Exception as e_pos:
                st.error(f"❌ Error obteniendo posiciones desde el histórico: {e_pos}")
                st.stop()

            st.success(f"✅ Clasificación (jornada {max(1, jor_sel-1)}): {nombre_local_clean} (Pos {pos_local}) | {nombre_visit_clean} (Pos {pos_visit})")

            def grupo(pos):
                if 1 <= pos <= 4: return [1,2,3,4]
                if 5 <= pos <= 10: return [5,6,7,8,9,10]
                if 11 <= pos <= 16: return [11,12,13,14,15,16]
                return list(range(17, 26))

            grupo_local_rival = grupo(pos_visit)
            grupo_visit_rival = grupo(pos_local)

            bloques = []
            for b in [1,2,3,4,5]:
                dfL_b = filtrar_bloque(df_local, b, grupo_local_rival if b == 5 else None)
                dfV_b = filtrar_bloque(df_visit, b, grupo_visit_rival if b == 5 else None)
                metricas_b = calcular_metricas(dfL_b, dfV_b, jor_sel)
                bloques.append(metricas_b)

            b1, b2, b3, b4, b5 = bloques
            metricas_finales = combinar_bloques(b1, b2, b3, b4, b5)

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
            g1.metric("Más de 1.5 Goles", f"{p_over15*100:.1f}%")
            g2.metric("Más de 2.5 Goles", f"{p_over25*100:.1f}%")
            g3.metric("Ambos Marcan", f"{p_btts*100:.1f}%")

            st.markdown("### 📈 PREDICCIÓN DE ESTADÍSTICAS")

            tabla = pd.DataFrame({
                "Métrica": ["Goles", "Remates Totales", "Remates a Puerta", "Paradas", "Córners", "Tarjetas"],
                "Local": [
                    f"{metricas_finales.get('goles_local', 0):.1f}",
                    f"{metricas_finales.get('remates_totales_local', 0):.1f}",
                    f"{metricas_finales.get('remates_puerta_local', 0):.1f}",
                    f"{metricas_finales.get('paradas_local', 0):.1f}",
                    f"{metricas_finales.get('corners_local', 0):.1f}",
                    f"{metricas_finales.get('tarjetas_local', 0):.1f}"
                ],
                "Visitante": [
                    f"{metricas_finales.get('goles_visitante', 0):.1f}",
                    f"{metricas_finales.get('remates_totales_visitante', 0):.1f}",
                    f"{metricas_finales.get('remates_puerta_visitante', 0):.1f}",
                    f"{metricas_finales.get('paradas_visitante', 0):.1f}",
                    f"{metricas_finales.get('corners_visitante', 0):.1f}",
                    f"{metricas_finales.get('tarjetas_visitante', 0):.1f}"
                ],
                "Total": [
                    f"{metricas_finales.get('goles_partido', 0):.1f}",
                    f"{metricas_finales.get('remates_totales_partido', 0):.1f}",
                    f"{metricas_finales.get('remates_puerta_partido', 0):.1f}",
                    f"{metricas_finales.get('paradas_partido', 0):.1f}",
                    f"{metricas_finales.get('corners_partido', 0):.1f}",
                    f"{metricas_finales.get('tarjetas_partido', 0):.1f}"
                ]
            })

            st.dataframe(tabla, use_container_width=True)

        except Exception as e:
            st.error(f"Error en el análisis: {e}")
            st.info("Revisa el panel de diagnóstico y la configuración del histórico.")

except Exception as e:
    st.error(f"Error general: {e}")
```
