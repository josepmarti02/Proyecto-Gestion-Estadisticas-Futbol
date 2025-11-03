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

    archivo_subido = st.file_uploader("Sube el archivo de estadísticas", type=["ods"])
    if archivo_subido:
        st.session_state['df'] = pd.read_excel(archivo_subido, engine="odf")
    
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
            "Sube un archivo con las estadísticas de un partido (.ods)",
            type="ods",
            key = "partido_uploader"
        )
        if archivo_partido:
            try:
                df_partido = pd.read_excel(archivo_partido, engine="odf")
                st.subheader("📋 Estadísticas del partido")
                st.dataframe(df_partido, width='stretch')

            
            # PODEMOS DARLE LOGICA PARA QUE MUESTRE LAS ESTADÍSTICAS DE LOS JUGADORES QUE ELIJAMOS
            # PERO DE MOMENTO LO DEJAMOS PORQUE PUEDEN SER MUY VARIADOS LOS ARCHIVOS. 
            # NOS CENTRAMOS EN LA ENTRADA MANUAL
            
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
                "CONVOCADO":[1 if j not in no_convocados else 0 for j in jugadores],
                "TITULAR":[1 if j in titulares else 0 for j in jugadores],
                "SUPLENTE":[1 if j in suplentes else 0 for j in jugadores],
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
                    
                    CARPETA_PARTIDOS = Path(__file__).parent / "partidos"
                    CARPETA_PARTIDOS.mkdir(exist_ok=True)
                    nombre_archivo = f"estadisticas_{rival.replace(' ', '_')}_{fecha_str}.csv"
                    ruta_archivo = CARPETA_PARTIDOS / nombre_archivo


                    df_editado.to_csv(ruta_archivo, index=False, encoding="utf-8")

                    st.success(f"{resultado} ✅ Guardado correctamente")
                    st.dataframe(df_editado, width='stretch')

def page_4():
    st.header("📜 Histórico de partidos")
    CARPETA_PARTIDOS = Path(__file__).parent / "partidos"
    CARPETA_PARTIDOS.mkdir(exist_ok=True)
    archivos = CARPETA_PARTIDOS.glob("*.csv")
    
    if not archivos:
        st.info("📁 No hay partidos guardados todavía. Guarda un partido desde la pestaña 'Estadísticas por partido'.")
        return
    
    resumen_partidos = []
    dfs_partidos = {}
    for archivo in archivos:
        try:
            df = pd.read_csv(archivo)
            dfs_partidos[archivo.name] = df

            nombre_limpio = archivo.stem.replace("estadisticas_","").replace("_"," ")
            partes = nombre_limpio.split(" ")
            rival = partes[0]
            fecha = partes[1]
            goles_a_favor = df["GOL"][df["GOL"] > 0].sum()
            goles_en_contra = abs(df["GOL"][df["GOL"] < 0].sum())
            resultado = "✅ Victoria" if goles_a_favor > goles_en_contra else \
                    "➖ Empate" if goles_a_favor == goles_en_contra else "❌ Derrota"
            resumen_partidos.append({
                "Fecha": fecha,
                "Rival": rival,
                "Resultado": resultado,
            })

        except Exception as e:
            st.error(f"⚠️ Error al leer el archivo {archivo.name}: {e}")

    df_resumen = pd.DataFrame(resumen_partidos)
    df_resumen["Fecha"] = pd.to_datetime(df_resumen["Fecha"], errors="coerce").dt.date
    df_resumen = df_resumen.sort_values("Fecha", ascending=False)
    st.write(df_resumen)


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