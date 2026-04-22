@st.cache_resource
def cargar_modelos_ml():
    """
    Carga modelos desde la carpeta 'models/' con diagnóstico completo
    """
    modelos = {}
    carpeta = "models"
    
    # DIAGNÓSTICO 1: ¿Existe la carpeta?
    st.sidebar.markdown("### 🔍 Diagnóstico ML")
    st.sidebar.write(f"**1. ¿Existe carpeta 'models'?** {os.path.exists(carpeta)}")
    
    if not os.path.exists(carpeta):
        st.sidebar.error("❌ La carpeta 'models' no existe")
        return modelos
    
    # DIAGNÓSTICO 2: ¿Qué archivos .pkl hay?
    archivos = [f for f in os.listdir(carpeta) if f.endswith(".pkl")]
    st.sidebar.write(f"**2. Archivos .pkl encontrados:** {archivos if archivos else 'Ninguno'}")
    
    if not archivos:
        st.sidebar.error("❌ No hay archivos .pkl en la carpeta")
        return modelos
    
    # DIAGNÓSTICO 3: Intentar cargar cada archivo
    for archivo in archivos:
        ruta = os.path.join(carpeta, archivo)
        st.sidebar.write(f"---")
        st.sidebar.write(f"**📄 Analizando:** {archivo}")
        
        try:
            obj = joblib.load(ruta)
            st.sidebar.write(f"   ✅ Cargado correctamente")
            st.sidebar.write(f"   📦 Tipo de objeto: {type(obj).__name__}")
            
            # Si es un diccionario, mostrar sus claves
            if isinstance(obj, dict):
                claves = list(obj.keys())
                st.sidebar.write(f"   📑 Claves del diccionario: {claves}")
                
                # Intentar extraer modelos del diccionario
                for clave, valor in obj.items():
                    st.sidebar.write(f"      🔑 '{clave}' → tipo: {type(valor).__name__}")
                    
                    # Ver si tiene .predict (es un modelo)
                    if hasattr(valor, 'predict'):
                        st.sidebar.write(f"         ✅ Este es un modelo (tiene .predict)")
                        # Intentar mapear la clave a una métrica
                        clave_upper = clave.upper()
                        if "GOLES_FAVOR" in clave_upper or "LOCAL" in clave_upper:
                            modelos.setdefault("goles_local", []).append(valor)
                            st.sidebar.success(f"         → Asignado a: goles_local")
                        elif "GOLES_CONTRA" in clave_upper or "VISITANTE" in clave_upper:
                            modelos.setdefault("goles_visitante", []).append(valor)
                            st.sidebar.success(f"         → Asignado a: goles_visitante")
                        elif "REMATES_TOTALES" in clave_upper:
                            modelos.setdefault("remates_totales", []).append(valor)
                            st.sidebar.success(f"         → Asignado a: remates_totales")
                        elif "REMATES_PUERTA" in clave_upper:
                            modelos.setdefault("remates_puerta", []).append(valor)
                            st.sidebar.success(f"         → Asignado a: remates_puerta")
                        elif "PARADAS" in clave_upper:
                            modelos.setdefault("paradas", []).append(valor)
                            st.sidebar.success(f"         → Asignado a: paradas")
                        elif "CORNERS" in clave_upper or "CORNERES" in clave_upper:
                            modelos.setdefault("corners", []).append(valor)
                            st.sidebar.success(f"         → Asignado a: corners")
                        elif "TARJETAS" in clave_upper:
                            modelos.setdefault("tarjetas", []).append(valor)
                            st.sidebar.success(f"         → Asignado a: tarjetas")
                    elif isinstance(valor, list):
                        st.sidebar.write(f"         📋 Es una lista de {len(valor)} elementos")
                        for i, item in enumerate(valor):
                            if hasattr(item, 'predict'):
                                st.sidebar.write(f"            ✅ Elemento {i} es un modelo")
                                # Asignar según la clave padre
                                for metrica in ["goles_local", "goles_visitante", "remates_totales", "remates_puerta", "paradas", "corners", "tarjetas"]:
                                    modelos.setdefault(metrica, []).append(item)
                    else:
                        st.sidebar.write(f"         ⚠️ No es un modelo (no tiene .predict)")
            
            # Si es directamente un modelo
            elif hasattr(obj, 'predict'):
                st.sidebar.write(f"   ✅ Es un modelo directamente")
                # Lo asignamos como goles_local por defecto
                modelos.setdefault("goles_local", []).append(obj)
                st.sidebar.success(f"   → Asignado a: goles_local (por defecto)")
            
            else:
                st.sidebar.write(f"   ⚠️ No es un modelo reconocible")
                
        except Exception as e:
            st.sidebar.error(f"   ❌ Error al cargar: {e}")
    
    # DIAGNÓSTICO 4: Resumen final
    st.sidebar.markdown("---")
    st.sidebar.write("### 📊 RESUMEN FINAL")
    total_modelos = sum(len(v) for v in modelos.values())
    st.sidebar.write(f"**Total modelos cargados:** {total_modelos}")
    if total_modelos > 0:
        st.sidebar.write(f"**Métricas con modelos:** {list(modelos.keys())}")
    else:
        st.sidebar.warning("⚠️ NO SE CARGÓ NINGÚN MODELO")
    
    return modelos
