import streamlit as st
import pandas as pd
from pathlib import Path
import os
from datetime import datetime

TU_EQUIPO = "Nules Benj 'A'"
MAX_TITULARES = 8
POSIBLES_MINUTOS = 50

CARPETA_BASE = Path(__file__).parent
CARPETA_PARTIDOS = CARPETA_BASE/"partidos"
CARPETA_PARTIDOS.mkdir(exist_ok=True)

columnas_datos_individuales = [
    "CONVOCADO", "% CONVOCADO", "TITULAR", "% TITULAR", "SUPLENTE", "% SUPLENTE",
    "GOL", "% GOLES", "ASIST", "% ASIST", "MINUTOS 1a PARTE", "MINUTOS 2a PARTE",
    "TOTAL MINUTOS JUGADOS", "POSIBLES MINUTOS", "% MINUTOS"]

opciones_ranking = ["GOL", "ASIST","TOTAL MINUTOS JUGADOS",
                    "% MINUTOS", "% TITULAR","PRODUCTIVIDAD OFENSIVA",
                      "EFICIENCIA GOLEADORA"]

def estadisticas_generales(df) -> dict:
    if df.empty:
        return{"Partidos":0,"Goles a favor":0,"Asistencias":0, "Goles en contra":0, "Diferencia de goles":0,}
    
    data = df.copy()
    
    for col in ["GOL","ASIST","PARTIDOS"]:
        if col not in df.columns:
            df[col] = 0
            
    #Convertimos valores a numeros y sustituimos no válidos por 0
    df["GOL"] = pd.to_numeric(data["GOL"], errors="coerce").fillna(0)
    df["ASIST"] = pd.to_numeric(data["ASIST"], errors="coerce").fillna(0)
    #Ignorar filas con goles negativos (portero)
    goles_a_favor = data[data["GOL"] >= 0]
    #Cojo solo valores negativos
    goles_en_contra = data[data["GOL"] < 0]

    total_goles = int(goles_a_favor["GOL"].sum())
    total_asist = int(goles_a_favor["ASIST"].sum())
    total_partidos = int(df["PARTIDOS"].iloc[0])
    total_gol_en_contra = int(goles_en_contra["GOL"].sum())
    diferencia_goles =  total_gol_en_contra + total_goles
    media_a_favor = total_goles/total_partidos
    media_en_contra = abs(total_gol_en_contra)/total_partidos

    return{
        "Partidos":total_partidos,
        "Goles a favor":total_goles,
        "Media goles a favor":media_a_favor,
        "Asistencias": total_asist,
        "Goles en contra": total_gol_en_contra,
        "Media goles en contra":media_en_contra,
        "Diferencia de goles": diferencia_goles
    }

def ranking(df, columna, top=3):
    if columna not in df.columns:
        return pd.DataFrame()
    df_ranking = df[["JUGADOR",columna]].sort_values(by=columna, ascending = False).head(top)
    df_ranking.columns = ["Jugador", columna]
    return df_ranking

def metricas_extra(df):
    data = df.copy()
    data["PRODUCTIVIDAD OFENSIVA"] = data["GOL"] + data["ASIST"]
    data["EFICIENCIA GOLEADORA"] = data["GOL"] / data["PARTIDOS"][0]
    return data

st.set_page_config(
    page_title="Proyecto estadísticas benjamín A",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.header("Estadísticas Benjamín A 25-26")

if 'df' not in st.session_state:
    st.session_state['df'] = pd.DataFrame()


def page_1():
    st.subheader("Estadísticas del equipo")

    archivo_subido = st.file_uploader("Sube el archivo de estadísticas", type=["ods", "csv"])
    if archivo_subido:
        extension = Path(archivo_subido.name).suffix.lower()
        if extension == ".ods":
            st.session_state['df'] = pd.read_excel(archivo_subido, engine="odf")
        elif extension == ".csv":
            st.session_state['df'] = pd.read_csv(archivo_subido)
        else:
            st.error("⚠️ Tipo de archivo no compatible. Usa .ods o .csv")

    
    df = st.session_state['df']
    if df.empty:
        st.info("📁 Sube un archivo con las estadísticas para ver el resumen")
        return
    #Nombres de las columnas
    #st.write(df.columns)
    
    resumen_estadisticas = estadisticas_generales(df)
    with st.expander("Resumen estadísticas equipo"):
        df_resumen = pd.DataFrame({
        "Estadística":resumen_estadisticas.keys(),
        "Total":resumen_estadisticas.values(),
       })
        st.dataframe(df_resumen, width="stretch")

    if st.button("🔄 Actualizar datos", help="Pulsar si se ha modificado la base de datos"):
        st.cache_data.clear()
        if archivo_subido:
            st.session_state['df'] = pd.read_excel(archivo_subido, engine="odf")
        else:
            st.session_state['df'] = pd.DataFrame()
        st.rerun()



def page_2():
    st.header("Estadísticas individuales")
    df = st.session_state['df']
    if df.empty:
        st.info("📁 Sube un archivo con las estadísticas para ver el resumen")
        return
    data = df.copy()
    data.columns = [col.strip() for col in data.columns]

    jugadores = data["JUGADOR"].dropna().astype(str).tolist()
    select_jugador = st.multiselect(
        "Selecciona jugador(es):",
        options=jugadores,
    )
    if select_jugador:
        df_select_jugadores = data[data["JUGADOR"].isin(select_jugador)]
        columnas = [col for col in columnas_datos_individuales if col in data.columns]
        df_mostrar = df_select_jugadores[["JUGADOR"]+ columnas]
        st.dataframe(df_mostrar, width='stretch')
        #KPIs resumen solo si se selecciona un jugador
        # if len(select_jugador) == 1:
        #     jugador = select_jugador[0]
        #     fila = df_select_jugadores.iloc[0]

        #     col1, col2, col3 = st.columns(3)
        #     col1.metric("⚽ Goles", int(fila["GOL"]))
        #     col2.metric("🎯 Asistencias", int(fila["ASIST"]))
        #     col3.metric("⏱️ Minutos jugados", int(fila["TOTAL MINUTOS JUGADOS"]))
    
    else:    
        st.warning("Selecciona al menos un jugador para ver sus estadísticas")
     

    
    data = metricas_extra(data)
    seleccion_rankings = st.multiselect("🏆 Mostrar ránkings", options=opciones_ranking)
    if seleccion_rankings:
        num_cols = min(len(seleccion_rankings), 3)
        for i in range (0,len(seleccion_rankings),3):
            cols = st.columns(num_cols)
            for j, col in enumerate(cols):
                if  i+j < len(seleccion_rankings):
                    metrica = seleccion_rankings[i+j]
                    col.markdown(f"🏅 {metrica}")
                    df_rank = ranking(data, metrica)
                    col.dataframe(df_rank, width='stretch')

        
    else:
        st.warning("Selecciona al menos un ranking para mostrar resultados.")
        

       

def page_3():
    st.header("📅 Añadir partido")
    
    tab1, tab2 = st.tabs(["📤 Subir archivo de partido", "✍️ Añadir estadísticas manualmente"])
    with tab1:
        st.subheader("📤 Subir archivo de partido")    
        archivo_partido = st.file_uploader(
            "Sube un archivo con las estadísticas de un partido (.ods o .csv)",
            type=["ods","csv"],
            key = "partido_uploader"
        )
        if archivo_partido:
            try:
                extension = Path(archivo_partido.name).suffix.lower()
                if extension == ".ods":           
                    df_partido = pd.read_excel(archivo_partido, engine="odf")
                elif extension == ".csv":           
                    df_partido = pd.read_csv(archivo_partido)
                else:
                    st.error("⚠️ Tipo de archivo no compatible. Usa .ods o .csv")
                    return
                
                
                st.subheader("📋 Estadísticas del partido")
                st.dataframe(df_partido, width='stretch')

                nombre_original = Path(archivo_partido.name).stem
                formato_correcto = nombre_original.startswith("estadisticas_") and "_" in nombre_original
                if formato_correcto:
                    nombre_guardado = Path(archivo_partido.name).name
                    st.info(f"📁 Archivo detectado en formato correcto")

                else: 
                    st.warning("⚠️ El archivo no sigue el formato esperado (`estadisticas_<rival>_<fecha>.csv`).")
                    rival_manual = st.text_input("🏟️ Introduce el nombre del rival:")
                    fecha_manual = st.date_input("📅 Fecha del partido:", value=datetime.today())
                    fecha_str = fecha_manual.strftime("%Y-%m-%d")

                    if rival_manual:
                        nombre_guardado = f"estadisticas_{rival_manual.replace(' ', '_')}_{fecha_str}.csv"
                    else:
                        nombre_guardado = None

                editar = st.checkbox("✏️ Editar archivo")
                if editar:
                    st.markdown("### 🔧 Edita los datos del partido si es necesario")
                    df_editado = st.data_editor(df_partido, width="stretch")
                    guardar = st.button("💾 Guardar cambios y sobrescribir")
                    if guardar:
                        if not nombre_guardado:
                            st.error("❌ Introduce un nombre de rival válido antes de guardar.")
                        else:
                            ruta_guardado = CARPETA_PARTIDOS/nombre_guardado
                            st.session_state['archivo_a_guardar'] = {
                                'ruta': str(ruta_guardado),
                                'df' : df_editado.to_dict(orient='list')
                            }
                            if Path(ruta_guardado).exists():
                                st.warning(f"⚠️ Ya existe un archivo llamado '{ruta_guardado.name}'. Se sobrescribirá al guardar.")
                                st.session_state['mostrar_confirmacion'] = True
                            else:
                                df_partido.to_csv(ruta_guardado, index=False, encoding="utf-8")
                                st.success(f"✅ Archivo actualizado correctamente en '{ruta_guardado.name}'")
                                st.session_state.pop("mostrar_confirmacion", None)
                                st.session_state.pop("archivo_a_guardar", None)
                                st.rerun()
                    if st.session_state.get("mostrar_confirmacion", False):
                                ruta_guardado = Path(st.session_state["archivo_a_guardar"]["ruta"])
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.button("✅ Sobrescribir archivo"):
                                        df_guardar = pd.DataFrame(st.session_state["archivo_a_guardar"]["df"])
                                        df_guardar.to_csv(ruta_guardado, index=False, encoding="utf-8")
                                        st.success(f"✅ Archivo sobrescrito correctamente en '{ruta_guardado.name}'")
                                        st.session_state.pop("archivo_a_guardar", None)
                                        st.session_state.pop("mostrar_confirmacion", None)
                                        st.rerun()
                                
                                with col2: 
                                    if st.button("❌ Cancelar"):
                                        st.info("❌ Operación cancelada. El archivo no fue modificado.")
                                        st.session_state.pop("archivo_a_guardar", None)
                                        st.session_state.pop("mostrar_confirmacion", None)
                                        st.rerun()
                                

                else:
                    guardar = st.button("📦 Guardar partido sin editar")
                    if guardar:
                        if not nombre_guardado:
                            st.error("❌ Introduce un nombre de rival válido antes de guardar.")
                        else:
                            ruta_guardado = CARPETA_PARTIDOS / nombre_guardado
                            if ruta_guardado.exists():
                                st.warning(f"⚠️ Ya existe un archivo llamado '{ruta_guardado.name}'. Se sobrescribirá al guardar.")

                            df_partido.to_csv(ruta_guardado, index=False, encoding="utf-8")
                            st.success(f"✅ Archivo guardado en '{ruta_guardado.name}'")
                            st.rerun()
            
            except Exception as e:
                st.error(f"Error al leer el archivo")

    with tab2:
        st.subheader("✍️ Añadir estadísticas manualmente")
        df_general = st.session_state['df']
        if df_general.empty:
            st.info("📁 Sube primero el archivo con las estadísticas en la pestaña 'General'")
            return
        
        jugadores = df_general["JUGADOR"].dropna().astype(str).tolist()

        for key in ["no_convocados", "suplentes", "rival", "local_visitante", "goles_a_favor", "goles_en_contra"]:
            st.session_state.setdefault(key, [] if key in ["no_convocados", "suplentes"] else 0)


        st.markdown("### 👥 Convocatoria y alineación")

        no_convocados = st.multiselect("Jugadores no convocados", options=jugadores, 
                                       default=st.session_state["no_convocados"],
                                       key = "multiselect_no_convocados")
    
        jugadores_disponibles = [j for j in jugadores if j not in no_convocados]
        max_suplentes = max(len(jugadores_disponibles) - MAX_TITULARES,0)
        suplentes_validos = [j for j in st.session_state["suplentes"] if j in jugadores_disponibles]
        if max_suplentes <= 0:
            suplentes_validos = []
        elif len(suplentes_validos) > max_suplentes:
            suplentes_validos = suplentes_validos[:max_suplentes]
        
        if max_suplentes == 0:
            st.info("ℹ️ No hay margen para suplentes")
            suplentes = []
        else:
            suplentes = st.multiselect("Jugadores suplentes", options=jugadores_disponibles,
                                   default=suplentes_validos,
                                   max_selections=max_suplentes,
                                   key="multiselect_suplentes")
        
        if st.button("🔄 Actualizar convocatoria"):
            st.session_state["no_convocados"] = no_convocados
            st.session_state["suplentes"] = suplentes
            st.session_state["rival"] = st.session_state.get("rival", "")
            st.session_state["local_visitante"] = st.session_state.get("local_visitante", False)
            st.session_state["goles_a_favor"] = st.session_state.get("goles_a_favor", 0)
            st.session_state["goles_en_contra"] = st.session_state.get("goles_en_contra", 0)
            st.success("✅ Convocatoria actualizada correctamente.")
            st.rerun()

        titulares = [j for j in jugadores_disponibles if j not in suplentes]
        num_titulares = len(titulares)

        if num_titulares< MAX_TITULARES:
            st.warning(f"⚠️ Hay menos de {MAX_TITULARES} titulares ({num_titulares}). Faltan jugadores.")
        elif num_titulares > MAX_TITULARES:
            st.warning(f"⚠️ Hay más de {MAX_TITULARES} titulares ({num_titulares}). Revisa la convocatoria.")

        with st.form("form_partido_manual"):
            fecha_partido = st.date_input("📅 Fecha del partido",
                                  value=datetime.today(),
                                  help="Selecciona la fecha en que se jugó el partido")
            fecha_str = fecha_partido.strftime("%Y-%m-%d")
            rival = st.text_input("🏟️ Rival", value=st.session_state.get("rival",""))
            local_visitante = st.toggle("Tu equipo es el local?", value=st.session_state.get("local_visitante", False))
            goles_a_favor = st.number_input("⚽ Goles a favor", min_value=0, step=1, value=st.session_state.get("goles_a_favor",0))
            goles_en_contra = st.number_input("🥅 Goles en contra", min_value=0, step=1, value=st.session_state.get("goles_en_contra",0))
            resultado = f"{TU_EQUIPO} {goles_a_favor} - {goles_en_contra} {rival}" if local_visitante else f"{rival} {goles_en_contra} - {goles_a_favor} {TU_EQUIPO}"

            df_manual = pd.DataFrame({
                "JUGADOR":jugadores,
                "CONVOCADO":["SÍ" if j not in no_convocados else "NO" for j in jugadores],
                "TITULAR":["SÍ" if j in titulares else "NO" for j in jugadores],
                "SUPLENTE":["SÍ" if j in suplentes else "NO" for j in jugadores],
                "GOL": [0] * len(jugadores),
                "ASIST":[0] * len(jugadores),
                "MINUTOS 1a PARTE":[0] * len(jugadores),
                "MINUTOS 2a PARTE":[0] * len(jugadores),
                

            })

            st.markdown("### ✏️ Introducir estadísticas individuales")
            df_editado = st.data_editor(df_manual, num_rows="fixed", width='stretch')

            
            submitted = st.form_submit_button("✅ Guardar partido")
        if submitted:
            if num_titulares != MAX_TITULARES:
                st.error(f"⚠️ El número de titulares debe ser exactamente {MAX_TITULARES}. Actualmente hay {num_titulares}.")
            elif len(jugadores_disponibles) < MAX_TITULARES:
                st.error(f"⚠️ Hay menos de {MAX_TITULARES} jugadores disponibles ({len(jugadores_disponibles)}).")
            else:

                mitad = POSIBLES_MINUTOS/2
                invalidos = df_editado[(df_editado["MINUTOS 1a PARTE"] > mitad)| (df_editado["MINUTOS 2a PARTE"]> mitad)]
                if not invalidos.empty:
                    st.warning("⚠️ Algunos jugadores tienen minutos superiores al máximo permitido por parte.")
                    st.dataframe(invalidos[["JUGADOR", "MINUTOS 1a PARTE", "MINUTOS 2a PARTE"]])
                
                else:
                    df_editado["TOTAL MINUTOS JUGADOS"] = df_editado["MINUTOS 1a PARTE"] + df_editado["MINUTOS 2a PARTE"]
                    df_editado["% MINUTOS"] = (df_editado["TOTAL MINUTOS JUGADOS"] / POSIBLES_MINUTOS * 100).round(2)
                    df_editado.loc[0,"LOCAL"] = "Sí" if local_visitante else "No"
                    nombre_archivo = f"estadisticas_{rival.replace(' ', '_')}_{fecha_str}.csv"
                    ruta_archivo = CARPETA_PARTIDOS / nombre_archivo

                    if ruta_archivo.exists():
                         st.warning(f"⚠️ Ya existe un archivo llamado '{ruta_archivo.name}'. Se sobrescribirá al guardar.")

                    df_editado.to_csv(ruta_archivo, index=False, encoding="utf-8")

                    st.success(f"{resultado} ✅ Guardado correctamente")
                    st.dataframe(df_editado, width='stretch')

def page_4():
    st.header("📜 Histórico de partidos")
    todos_los_csv = list(CARPETA_PARTIDOS.glob("*.csv"))
    archivos_validos =  [f for f in todos_los_csv if f.stem.startswith("estadisticas_") and "_" in f.stem]    
    archivos_invalidos = [f for f in todos_los_csv if f not in archivos_validos]

    if archivos_invalidos:
        with st.expander("⚠️ Archivos no válidos detectados en la carpeta 'partidos'"):
            archivo_invalido = st.selectbox("📂 Selecciona un archivo para revisar:", [f.name for f in archivos_invalidos], index=None)
            if archivo_invalido:
                ruta_invalida = next(f for f in archivos_invalidos if f.name == archivo_invalido)
                try:
                    df_preview = pd.read_csv(ruta_invalida)
                    st.markdown(f"### 👀 Vista previa de **{archivo_invalido}**")
                    st.dataframe(df_preview, width="stretch")
                    es_partido = st.toggle("El archivo seleccionado son las estadísticas de un partido", value=False)
                    if es_partido:
                        rival_nuevo = st.text_input("🏟️ Nombre del rival:")
                        fecha_nueva = st.date_input("📅 Fecha del partido:", value=datetime.today())
                        fecha_str = fecha_nueva.strftime("%Y-%m-%d")
                        if st.button("💾 Renombrar archivo seleccionado"):
                            nuevo_nombre = f"estadisticas_{rival_nuevo.replace(' ', '_')}_{fecha_str}.csv"
                            nueva_ruta = CARPETA_PARTIDOS/nuevo_nombre
                            if nueva_ruta.exists():
                                st.warning(f"⚠️ Ya existe un archivo llamado '{nuevo_nombre}'. Se sobrescribirá.")
                            ruta_invalida.rename(nueva_ruta)
                            st.success(f"✅ Archivo renombrado correctamente como '{nuevo_nombre}'.")
                            st.rerun()

                except Exception as e:
                      st.error(f"⚠️ No se pudo leer el archivo '{archivo_invalido}': {type(e).__name__} - {e}")

    if not todos_los_csv:
        st.info("📁 No hay partidos guardados todavía. Guarda un partido desde la pestaña 'Estadísticas por partido'.")
        return
    
    resumen_partidos = []
    for archivo in archivos_validos:
        try:
            df = pd.read_csv(archivo)
            nombre_limpio = archivo.stem.replace("estadisticas_","")
            partes = nombre_limpio.split("_")
            
            rival = partes[:-1]
            rival = " ".join(rival)
            fecha = partes[-1]
            st.write(rival,"->", fecha)
            goles_a_favor = df["GOL"][df["GOL"] > 0].sum()
            goles_en_contra = abs(df["GOL"][df["GOL"] < 0].sum())
            resultado = ("✅ Victoria" if goles_a_favor > goles_en_contra else
                         "➖ Empate" if goles_a_favor == goles_en_contra else 
                         "❌ Derrota"
                         )
            es_local = False
            if "LOCAL" in df.columns and pd.notna(df.loc[0,"LOCAL"]):
                valor_local = str(df.loc[0,"LOCAL"]).strip().lower()
                es_local = valor_local in ["si","sí","true"]
            if es_local:
                marcador = f"{TU_EQUIPO} {int(goles_a_favor)} - {int(goles_en_contra)} {rival}"
            else:
                marcador = f"{rival} {int(goles_en_contra)} - {int(goles_a_favor)} {TU_EQUIPO}"
            
            resumen_partidos.append({
                "Archivo": str(archivo),
                "Fecha": fecha,
                "Rival": rival,
                "Resultado": resultado,
                "Marcador" : marcador,
            })

        except Exception as e:
            st.error(f"⚠️ Error al leer el archivo {archivo.name}: {e}")

    df_resumen = pd.DataFrame(resumen_partidos)
    df_resumen["Fecha"] = pd.to_datetime(df_resumen["Fecha"], errors="coerce").dt.date
    df_resumen = df_resumen.sort_values("Fecha", ascending=False)
    st.subheader("📅 Partidos jugados")
    st.dataframe(df_resumen)

    partidos_opciones = [f"{row.Fecha} - {row.Rival}" for _,row in df_resumen.iterrows()]
    partido_seleccionado = st.selectbox("🔍 Selecciona un partido para ver detalles", partidos_opciones, index=None)
    if partido_seleccionado:
        fila = df_resumen.iloc[partidos_opciones.index(partido_seleccionado)]
        archivo_detalle = Path(fila["Archivo"])
        df_detalle = pd.read_csv(archivo_detalle)

        st.markdown(f"### 📊 Detalles del partido contra **{fila['Rival']}** ({fila['Fecha']})")
        st.dataframe(df_detalle, width="stretch")
        st.info(f"📍 **Marcador:** {fila['Marcador']}")


pg = st.navigation({
    "Estadísticas equipo":[
        st.Page(page_1, title="General", icon="😎"), 
        st.Page(page_2, title="Individuales", icon="🪄")
    ],
    "Estadísticas por partido":[
        st.Page(page_3, title="Añadir partido", icon="📅"),
        st.Page(page_4, title="Histórico de partidos", icon="📜"),
    ]
})
pg.run()