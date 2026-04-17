import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
from math import exp, factorial
import re

st.set_page_config(page_title="Analizador de Partidos PRO", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
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
# NORMALIZACIÓN DE NOMBRES DE EQUIPOS (APP -> CLASIFICACION)
# =========================================================
def obtener_equivalencia_nombre(nombre_app, df_equivalencias):
    """
    Busca en la pestaña de equivalencias a qué nombre de clasificación corresponde el equipo de la app.
    """
    if df_equivalencias.empty:
        return nombre_app.upper().strip()
    
    nombre_buscar = nombre_app.upper().strip()
    
    # Buscar en la columna A (NOMBRE EN LIBRO LALIGA 25/26)
    for idx, row in df_equivalencias.iterrows():
        nombre_app_sheet = str(row.iloc[0]).upper().strip() if pd.notna(row.iloc[0]) else ""
        if nombre_app_sheet == nombre_buscar:
            nombre_clasificacion = str(row.iloc[1]).upper().strip() if pd.notna(row.iloc[1]) else ""
            if nombre_clasificacion:
                return nombre_clasificacion
    
    return nombre_buscar


# =========================================================
# LECTURA DE CLASIFICACIÓN DESDE LIBRO HISTÓRICO
# =========================================================
def obtener_clasificacion_desde_historico(id_libro_historico, nombre_pestana_clasificacion, jornada_buscada):
    """
    Lee la clasificación desde el libro HISTORICO DE PREDICCIONES.
    Busca la jornada (número anterior a la seleccionada) y devuelve un DataFrame con EQUIPO y POS.
    """
    try:
        libro_historico = client.open_by_key(id_libro_historico)
        ws_clasificacion = libro_historico.worksheet(nombre_pestana_clasificacion)
        data = ws_clasificacion.get_all_values()
        
        if not data:
            return pd.DataFrame()
        
        # Buscar la fila que contiene "JORNADA X"
        jornada_str = f"JORNADA {jornada_buscada}"
        fila_inicio = None
        
        for i, fila in enumerate(data):
            if fila and len(fila) > 0:
                if jornada_str.upper() in str(fila[0]).upper():
                    fila_inicio = i + 1  # +1 porque las filas son 0-indexed
                    break
        
        if fila_inicio is None:
            st.warning(f"No se encontró la clasificación para la Jornada {jornada_buscada}")
            return pd.DataFrame()
        
        # Leer desde la fila siguiente hasta encontrar otra jornada o fin
        clasificacion = []
        for i in range(fila_inicio, len(data)):
            fila = data[i]
            if not fila or len(fila) < 2:
                continue
            # Si encontramos otra "JORNADA", paramos
            if fila[0] and "JORNADA" in str(fila[0]).upper():
                break
            
            # Extraer posición y equipo
            posicion = fila[1] if len(fila) > 1 else None
            equipo = fila[2] if len(fila) > 2 else None
            
            if posicion and equipo:
                try:
                    pos_int = int(posicion)
                    clasificacion.append({
                        "EQUIPO": str(equipo).upper().strip(),
                        "POS": pos_int
                    })
                except ValueError:
                    continue
        
        return pd.DataFrame(clasificacion)
        
    except Exception as e:
        st.warning(f"Error leyendo clasificación histórica: {e}")
        return pd.DataFrame()


# =========================================================
# DETECCIÓN INTELIGENTE DE COLUMNAS
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
        "TARJETAS AMARILLAS FAVOR": ["tarjetas amarillas favor", "amarillas favor", "yellow cards for", "tarjetas amarillas favor("],
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


def cargar_equivalencias(id_libro_historico, nombre_pestana_equivalencias):
    """
    Carga la pestaña de equivalencias de nombres de equipos.
    """
    try:
        libro_historico = client.open_by_key(id_libro_historico)
        ws_equiv = libro_historico.worksheet(nombre_pestana_equivalencias)
        data = ws_equiv.get_all_records()
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data)
    except Exception as e:
        st.warning(f"Error cargando equivalencias: {e}")
        return pd.DataFrame()


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
        except Exception as e:
            metricas[nombre + "_local"] = 0
            metricas[nombre + "_visitante"] = 0
            metricas[nombre + "_partido"] = 0
    
    return metricas


def pesos_por_jornada(j):
    if j <= 5: return (0.2, 0.8)
    if j <= 10: return (0.3, 0.7)
    if j <= 14: return (0.4, 0.6)
    if j <= 20: return (0.5, 0.5)
    if j <= 30: return (0.6, 0.4)
    return (0.65, 0.35)


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
    if 1 <= pos <= 4: return [1,2,3,4]
    if 5 <= pos <= 10: return [5,6,7,8,9,10]
    if 11 <= pos <= 16: return [11,12,13,14,15,16]
    return list(range(17, 26))


# =========================================================
# INTERFAZ PRINCIPAL
# =========================================================
st.markdown("<h2 style='text-align: center;'>⚽ ANALIZADOR DE PARTIDOS PRO</h2>", unsafe_allow_html=True)

try:
    sh_ligas = client.open_by_key(ID_CONTROL).worksheet("LIGAS")
    df_ligas = pd.DataFrame(sh_ligas.get_all_records())

    col1, col2 = st.columns(2)
    liga_sel = col1.selectbox("🏆 Seleccionar Liga", df_ligas['Nombre de la liga'])
    
    # Obtener la fila de la liga seleccionada
    liga_fila = df_ligas[df_ligas['Nombre de la liga'] == liga_sel].iloc[0]
    
    # Buscar el ID del libro histórico (puede estar en columna "ID del libro historico" o "ID del libro" si es la misma fila)
    if 'ID del libro historico' in df_ligas.columns:
        id_historico = liga_fila['ID del libro historico']
    else:
        # Si no existe columna específica, usamos la misma lógica pero necesitamos distinguir
        # En tu caso, la fila 3 tiene el histórico. Buscamos por coincidencia de nombre exacto
        fila_historico = df_ligas[df_ligas['Nombre de la liga'] == "HISTÓRICO DE PREDICCIONES"]
        if not fila_historico.empty:
            id_historico = fila_historico.iloc[0]['ID del libro']
        else:
            id_historico = None
    
    # ID del libro de datos (el que contiene las pestañas LOCAL/VISITANTE)
    id_actual = liga_fila['ID del libro']
    
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
            # Cargar datos de los equipos
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
                st.error("❌ No se pudieron cargar los datos de los equipos.")
                st.stop()
            
            # OBTENER CLASIFICACIÓN DESDE LIBRO HISTÓRICO
            if id_historico is None:
                st.error("❌ No se encontró el ID del libro histórico en la configuración.")
                st.info("Asegúrate de que en la hoja 'LIGAS' existe una fila con 'HISTÓRICO DE PREDICCIONES' y su ID del libro.")
                st.stop()
            
            # Jornada anterior a la seleccionada (clasificación previa al partido)
            jornada_clasificacion = jor_sel - 1
            if jornada_clasificacion < 1:
                st.error("❌ No hay clasificación disponible para la jornada 1 (no hay jornada anterior).")
                st.stop()
            
            # Cargar equivalencias de nombres
            df_equivalencias = cargar_equivalencias(id_historico, "EQUIVALENCIA NOMENCLATURA LALIGA25/26")
            
            # Obtener clasificación
            clasif = obtener_clasificacion_desde_historico(id_historico, "CLASIFICACION LALIGA 25/26", jornada_clasificacion)
            
            if clasif.empty:
                st.error(f"❌ No se pudo obtener la clasificación para la Jornada {jornada_clasificacion}.")
                st.info(f"Asegúrate de que en el libro histórico, pestaña 'CLASIFICACION LALIGA 25/26', existe la línea 'JORNADA {jornada_clasificacion}' con los equipos y posiciones.")
                st.stop()
            
            with st.expander("🔍 Clasificación obtenida (histórica)"):
                st.write(f"**Jornada anterior:** {jornada_clasificacion}")
                st.dataframe(clasif, use_container_width=True)
            
            nombre_local_clean = clean(eq_l).upper()
            nombre_visit_clean = clean(eq_v).upper()
            
            # Convertir nombres usando equivalencias
            nombre_local_clasif = obtener_equivalencia_nombre(nombre_local_clean, df_equivalencias)
            nombre_visit_clasif = obtener_equivalencia_nombre(nombre_visit_clean, df_equivalencias)
            
            # Buscar posiciones en la clasificación
            local_info = clasif[clasif["EQUIPO"] == nombre_local_clasif]
            visit_info = clasif[clasif["EQUIPO"] == nombre_visit_clasif]
            
            if local_info.empty:
                st.error(f"❌ No se encontró '{nombre_local_clasif}' en la clasificación de la Jornada {jornada_clasificacion}")
                st.info(f"Equipos disponibles en clasificación: {clasif['EQUIPO'].tolist()}")
                st.stop()
            
            if visit_info.empty:
                st.error(f"❌ No se encontró '{nombre_visit_clasif}' en la clasificación de la Jornada {jornada_clasificacion}")
                st.info(f"Equipos disponibles en clasificación: {clasif['EQUIPO'].tolist()}")
                st.stop()
            
            pos_local = local_info.iloc[0]["POS"]
            pos_visit = visit_info.iloc[0]["POS"]
            
            st.success(f"✅ Clasificación Jornada {jornada_clasificacion}: {nombre_local_clasif} (Pos {pos_local}) | {nombre_visit_clasif} (Pos {pos_visit})")
            
            grupo_local_rival = grupo(pos_visit)
            grupo_visit_rival = grupo(pos_local)
            
            # Calcular métricas por bloque
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
            st.info("Revisa el panel de diagnóstico para ver las columnas disponibles.")

except Exception as e:
    st.error(f"Error general: {e}")
