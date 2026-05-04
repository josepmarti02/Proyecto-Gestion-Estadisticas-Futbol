import json
import streamlit as st
import pandas as pd
from pathlib import Path
import numpy as np
from datetime import datetime

TU_EQUIPO = "Nules Benj 'A'"
MAX_TITULARES = 8
MINUTOS_PARTIDO = 50

CARPETA_BASE = Path(__file__).parent
CARPETA_PARTIDOS = CARPETA_BASE / "partidos"
CARPETA_PARTIDOS.mkdir(exist_ok=True)
FICHERO_JUGADORES = CARPETA_BASE / "jugadores.json"

columnas_datos_individuales = [
    "CONVOCADO", "% CONVOCADO", "TITULAR", "% TITULAR", "SUPLENTE", "% SUPLENTE",
    "GOL", "% GOLES", "ASIST", "% ASIST", "MINUTOS 1a PARTE", "MINUTOS 2a PARTE",
    "TOTAL MINUTOS JUGADOS", "POSIBLES MINUTOS", "% MINUTOS"]

opciones_ranking = ["GOL", "ASIST", "TOTAL MINUTOS JUGADOS",
                    "% MINUTOS", "% TITULAR", "PRODUCTIVIDAD OFENSIVA",
                    "EFICIENCIA GOLEADORA"]


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_valid_match_files() -> list:
    """Devuelve la lista de ficheros CSV válidos de partidos."""
    todos = list(CARPETA_PARTIDOS.glob("*.csv"))
    return [
        f for f in todos
        if f.stem.startswith("estadisticas_")
        and "_" in f.stem
        and "estadisticas_generadas" not in f.name
    ]


def load_jugadores() -> list:
    """Carga la lista de jugadores desde jugadores.json. Devuelve lista vacía si no existe."""
    if not FICHERO_JUGADORES.exists():
        return []
    try:
        with open(FICHERO_JUGADORES, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_jugadores(jugadores: list):
    """Guarda la lista de jugadores en jugadores.json."""
    with open(FICHERO_JUGADORES, "w", encoding="utf-8") as f:
        json.dump(jugadores, f, ensure_ascii=False, indent=2)


def guardar_partido(df: pd.DataFrame, ruta: Path):
    """Guarda un DataFrame de partido en la ruta indicada."""
    df.to_csv(ruta, index=False, encoding="utf-8")


# ── Lógica de estadísticas ────────────────────────────────────────────────────

def estadisticas_generales(df) -> dict:
    if df.empty:
        return {"Partidos": 0, "Goles a favor": 0, "Asistencias": 0,
                "Goles en contra": 0, "Diferencia de goles": 0}

    data = df.copy()
    for col in ["GOL", "ASIST", "PARTIDOS"]:
        if col not in data.columns:
            data[col] = 0

    data["GOL"] = pd.to_numeric(data["GOL"], errors="coerce").fillna(0)
    data["ASIST"] = pd.to_numeric(data["ASIST"], errors="coerce").fillna(0)

    goles_a_favor = data[data["GOL"] >= 0]
    goles_en_contra = data[data["GOL"] < 0]

    total_goles = int(goles_a_favor["GOL"].sum())
    total_asist = int(goles_a_favor["ASIST"].sum())
    total_partidos = int(data["PARTIDOS"].iloc[0])
    total_gol_en_contra = abs(int(goles_en_contra["GOL"].sum()))
    diferencia_goles = total_goles - total_gol_en_contra
    media_a_favor = total_goles / total_partidos if total_partidos else 0
    media_en_contra = total_gol_en_contra / total_partidos if total_partidos else 0

    return {
        "Partidos": total_partidos,
        "Goles a favor": total_goles,
        "Media goles a favor": media_a_favor,
        "Asistencias": total_asist,
        "Goles en contra": total_gol_en_contra,
        "Media goles en contra": media_en_contra,
        "Diferencia de goles": diferencia_goles,
    }


def ranking(df, columna, top=3):
    if columna not in df.columns:
        return pd.DataFrame()
    df_ranking = df[["JUGADOR", columna]].sort_values(by=columna, ascending=False).head(top)
    df_ranking.columns = ["Jugador", columna]
    return df_ranking


def metricas_extra(df):
    data = df.copy()
    data["PRODUCTIVIDAD OFENSIVA"] = data["GOL"] + data["ASIST"]
    data["EFICIENCIA GOLEADORA"] = data["GOL"] / data["PARTIDOS"].iloc[0]
    return data


def generar_acumulado_desde_partidos():
    archivos_validos = get_valid_match_files()
    if not archivos_validos:
        return None, "No hay archivos de partidos con formato válido"

    dfs = []
    for archivo in archivos_validos:
        try:
            df = pd.read_csv(archivo)
            dfs.append(df)
        except Exception as e:
            return None, f"Error al leer {archivo.name}: {e}"

    df_all = pd.concat(dfs, ignore_index=True)
    jugadores = df_all["JUGADOR"].unique()
    total_partidos = len(archivos_validos)
    total_goles_favor = df_all[df_all["GOL"] > 0]["GOL"].sum()
    total_goles_contra = abs(df_all[df_all["GOL"] < 0]["GOL"].sum())
    total_asist = df_all["ASIST"].sum()
    total_min = total_partidos * MINUTOS_PARTIDO

    acumulado = []
    for jugador in jugadores:
        df_j = df_all[df_all["JUGADOR"] == jugador]
        conv = (df_j["CONVOCADO"] == "SÍ").sum()
        tit = (df_j["TITULAR"] == "SÍ").sum()
        sup = (df_j["SUPLENTE"] == "SÍ").sum()
        gol = df_j["GOL"].sum()
        asist = df_j["ASIST"].sum()
        min1 = df_j["MINUTOS 1a PARTE"].sum()
        min2 = df_j["MINUTOS 2a PARTE"].sum()
        min_total = min1 + min2
        pos_min = conv * MINUTOS_PARTIDO

        if gol > 0:
            pct_gol = round(gol / total_goles_favor * 100, 2) if total_goles_favor > 0 else 0
        elif gol < 0:
            pct_gol = round(gol / total_goles_contra * 100, 2) if total_goles_contra > 0 else 0
        else:
            pct_gol = 0

        acumulado.append({
            "JUGADOR": jugador,
            "CONVOCADO": conv,
            "% CONVOCADO": round(conv / total_partidos * 100, 2),
            "TITULAR": tit,
            "% TITULAR": round((tit / conv * 100) if conv > 0 else 0, 2),
            "SUPLENTE": sup,
            "% SUPLENTE": round((sup / conv * 100) if conv > 0 else 0, 2),
            "GOL": gol,
            "% GOL": pct_gol,
            "ASIST": asist,
            "% ASIST": round((asist / total_asist * 100) if total_asist > 0 else 0, 2),
            "MINUTOS 1a PARTE": min1,
            "MINUTOS 2a PARTE": min2,
            "TOTAL MINUTOS JUGADOS": min_total,
            "POSIBLES MINUTOS": pos_min,
            "% MINUTOS POSIBLES": round((min_total / pos_min * 100) if pos_min > 0 else 0, 2),
            "% MINUTOS TOTALES": round((min_total / total_min * 100) if total_min > 0 else 0, 2),
            "PARTIDOS": total_partidos,
            "TOTAL GOLES": total_goles_favor,
            "TOTAL ASIST": total_asist,
            "MINUTOS TOTALES": total_min,
        })

    df_acum = pd.DataFrame(acumulado)
    columnas_globales = ["PARTIDOS", "TOTAL GOLES", "TOTAL ASIST", "MINUTOS TOTALES"]
    df_acum.loc[1:, columnas_globales] = np.nan
    return df_acum, None


# ── Configuración de la app ───────────────────────────────────────────────────

st.set_page_config(
    page_title="Proyecto estadísticas benjamín A",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.header("Estadísticas Benjamín A 25-26")

if "df" not in st.session_state:
    st.session_state["df"] = pd.DataFrame()


# ── Páginas ───────────────────────────────────────────────────────────────────

def page_1():
    st.subheader("Estadísticas del equipo")

    archivo_subido = st.file_uploader("Sube el archivo de estadísticas", type=["ods", "csv"])
    if archivo_subido:
        extension = Path(archivo_subido.name).suffix.lower()
        if extension == ".ods":
            st.session_state["df"] = pd.read_excel(archivo_subido, engine="odf")
        elif extension == ".csv":
            st.session_state["df"] = pd.read_csv(archivo_subido)
        else:
            st.error("Tipo de archivo no compatible. Usa .ods o .csv")

    st.markdown("🔄 Generar estadísticas acumuladas desde partidos guardados")
    if st.button("Generar archivo acumulado"):
        df_acum, err = generar_acumulado_desde_partidos()
        if err:
            st.error(err)
        else:
            st.session_state["acumulado_generado"] = df_acum
            st.session_state["mostrar_confirm_guardado"] = True
            st.rerun()

    if st.session_state.get("mostrar_confirm_guardado", False):
        df_acum = st.session_state["acumulado_generado"]
        st.success("Estadísticas acumuladas generadas. Revisa antes de guardar.")
        st.dataframe(df_acum, width="stretch")
        st.warning("¿Quieres guardar este archivo? (No sobrescribe el original)")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Guardar archivo generado"):
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                nombre_archivo = f"estadisticas_generadas_{timestamp}.csv"
                ruta_salida = CARPETA_PARTIDOS / nombre_archivo
                guardar_partido(df_acum, ruta_salida)
                st.success(f"Archivo guardado como '{ruta_salida.name}'")
                st.session_state.pop("mostrar_confirm_guardado", None)
                st.session_state.pop("acumulado_generado", None)
        with col2:
            if st.button("❌ Cancelar"):
                st.session_state.pop("mostrar_confirm_guardado", None)
                st.session_state.pop("acumulado_generado", None)
                st.rerun()

    df = st.session_state["df"]
    if df.empty:
        st.info("📁 Sube un archivo con las estadísticas para ver el resumen")
        return

    resumen_estadisticas = estadisticas_generales(df)
    with st.expander("Resumen estadísticas equipo"):
        df_resumen = pd.DataFrame({
            "Estadística": resumen_estadisticas.keys(),
            "Total": resumen_estadisticas.values(),
        })
        st.dataframe(df_resumen, width="stretch")


def page_2():
    st.header("Estadísticas individuales")
    df = st.session_state["df"]
    if df.empty:
        st.info("📁 Sube un archivo con las estadísticas para ver el resumen")
        return
    data = df.copy()
    data.columns = [col.strip() for col in data.columns]

    jugadores = data["JUGADOR"].dropna().astype(str).tolist()
    select_jugador = st.multiselect(
        "Selecciona jugador(es):",
        options=jugadores,
        default=jugadores,
    )
    if select_jugador:
        df_select_jugadores = data[data["JUGADOR"].isin(select_jugador)]
        columnas = [col for col in columnas_datos_individuales if col in data.columns]
        df_mostrar = df_select_jugadores[["JUGADOR"] + columnas]
        st.dataframe(df_mostrar, width="stretch")
    else:
        st.warning("Selecciona al menos un jugador para ver sus estadísticas")

    data = metricas_extra(data)
    seleccion_rankings = st.multiselect("🏆 Mostrar ránkings", options=opciones_ranking)
    if seleccion_rankings:
        num_cols = min(len(seleccion_rankings), 3)
        for i in range(0, len(seleccion_rankings), 3):
            cols = st.columns(num_cols)
            for j, col in enumerate(cols):
                if i + j < len(seleccion_rankings):
                    metrica = seleccion_rankings[i + j]
                    col.markdown(f"🏅 {metrica}")
                    df_rank = ranking(data, metrica)
                    col.dataframe(df_rank, width="stretch")
    else:
        st.warning("Selecciona al menos un ranking para mostrar resultados.")


def page_3():
    st.header("📅 Añadir partido")

    tab1, tab2 = st.tabs(["📤 Subir archivo de partido", "✍️ Añadir estadísticas manualmente"])

    # ── Tab 1: subir fichero ──────────────────────────────────────────────────
    with tab1:
        st.subheader("📤 Subir archivo de partido")
        archivo_partido = st.file_uploader(
            "Sube un archivo con las estadísticas de un partido (.ods o .csv)",
            type=["ods", "csv"],
            key="partido_uploader",
        )

        # Confirmación de sobreescritura
        if st.session_state.get("mostrar_confirmacion", False):
            ruta_guardado = Path(st.session_state["archivo_a_guardar"]["ruta"])
            df_guardar = pd.DataFrame(st.session_state["archivo_a_guardar"]["df"])
            st.warning(f"⚠️ Ya existe '{ruta_guardado.name}'. ¿Quieres sobrescribirlo?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Sobrescribir archivo"):
                    guardar_partido(df_guardar, ruta_guardado)
                    st.success(f"✅ Archivo sobrescrito correctamente: '{ruta_guardado.name}'")
                    st.session_state.pop("archivo_a_guardar", None)
                    st.session_state.pop("mostrar_confirmacion", None)
                    st.rerun()
            with col2:
                if st.button("❌ Cancelar"):
                    st.session_state.pop("archivo_a_guardar", None)
                    st.session_state.pop("mostrar_confirmacion", None)
                    st.rerun()
            st.dataframe(df_guardar, width="stretch")
            return

        if archivo_partido:
            try:
                extension = Path(archivo_partido.name).suffix.lower()
                if extension == ".ods":
                    df_partido = pd.read_excel(archivo_partido, engine="odf")
                elif extension == ".csv":
                    df_partido = pd.read_csv(archivo_partido)
                else:
                    st.error("Tipo de archivo no compatible. Usa .ods o .csv")
                    return

                st.subheader("📋 Estadísticas del partido")
                st.dataframe(df_partido, width="stretch")

                nombre_original = Path(archivo_partido.name).stem
                formato_correcto = nombre_original.startswith("estadisticas_") and "_" in nombre_original
                if formato_correcto:
                    nombre_guardado = Path(archivo_partido.name).name
                    st.info("📁 Archivo detectado en formato correcto")
                else:
                    st.warning("⚠️ El archivo no sigue el formato esperado (`estadisticas_<rival>_<fecha>.csv`).")
                    rival_manual = st.text_input("🏟️ Introduce el nombre del rival:")
                    fecha_manual = st.date_input("📅 Fecha del partido:", value=datetime.today())
                    fecha_str = fecha_manual.strftime("%Y-%m-%d")
                    nombre_guardado = (
                        f"estadisticas_{rival_manual.replace(' ', '_')}_{fecha_str}.csv"
                        if rival_manual else None
                    )

                editar = st.checkbox("✏️ Editar archivo")
                if editar:
                    st.markdown("### 🔧 Edita los datos del partido si es necesario")
                    df_editado = st.data_editor(df_partido, width="stretch")
                    if st.button("💾 Guardar cambios"):
                        if not nombre_guardado:
                            st.error("❌ Introduce un nombre de rival válido antes de guardar.")
                        else:
                            ruta_guardado = CARPETA_PARTIDOS / nombre_guardado
                            st.session_state["archivo_a_guardar"] = {
                                "ruta": str(ruta_guardado),
                                "df": df_editado.to_dict(orient="list"),
                            }
                            if ruta_guardado.exists():
                                st.session_state["mostrar_confirmacion"] = True
                                st.rerun()
                            else:
                                guardar_partido(df_editado, ruta_guardado)
                                st.success(f"✅ Archivo guardado en '{ruta_guardado.name}'")
                                st.dataframe(df_editado, width="stretch")
                else:
                    if st.button("📦 Guardar partido sin editar"):
                        if not nombre_guardado:
                            st.error("❌ Introduce un nombre de rival válido antes de guardar.")
                        else:
                            ruta_guardado = CARPETA_PARTIDOS / nombre_guardado
                            st.session_state["archivo_a_guardar"] = {
                                "ruta": str(ruta_guardado),
                                "df": df_partido.to_dict(orient="list"),
                            }
                            if ruta_guardado.exists():
                                st.session_state["mostrar_confirmacion"] = True
                                st.rerun()
                            else:
                                guardar_partido(df_partido, ruta_guardado)
                                st.success(f"✅ Archivo guardado en '{ruta_guardado.name}'")
                                st.dataframe(df_partido, width="stretch")

            except Exception as e:
                st.error(f"Error al leer el archivo: {e}")

    # ── Tab 2: entrada manual ─────────────────────────────────────────────────
    with tab2:
        st.subheader("✍️ Añadir estadísticas manualmente")

        jugadores = load_jugadores()
        if not jugadores:
            st.warning("⚠️ No hay jugadores en la plantilla. Ve a la página **Plantilla** para añadirlos.")
            return

        for key in ["no_convocados", "suplentes", "rival", "local_visitante", "goles_a_favor", "goles_en_contra"]:
            st.session_state.setdefault(key, [] if key in ["no_convocados", "suplentes"] else 0)

        st.markdown("### 👥 Convocatoria y alineación")

        no_convocados = st.multiselect(
            "Jugadores no convocados",
            options=jugadores,
            default=[j for j in st.session_state["no_convocados"] if j in jugadores],
            key="multiselect_no_convocados",
        )

        jugadores_disponibles = [j for j in jugadores if j not in no_convocados]
        max_suplentes = max(len(jugadores_disponibles) - MAX_TITULARES, 0)
        suplentes_validos = [j for j in st.session_state["suplentes"] if j in jugadores_disponibles]
        if max_suplentes <= 0:
            suplentes_validos = []
        elif len(suplentes_validos) > max_suplentes:
            suplentes_validos = suplentes_validos[:max_suplentes]

        if max_suplentes == 0:
            st.info("ℹ️ No hay margen para suplentes")
            suplentes = []
        else:
            suplentes = st.multiselect(
                "Jugadores suplentes",
                options=jugadores_disponibles,
                default=suplentes_validos,
                max_selections=max_suplentes,
                key="multiselect_suplentes",
            )

        if st.button("🔄 Actualizar convocatoria"):
            st.session_state["no_convocados"] = no_convocados
            st.session_state["suplentes"] = suplentes
            st.success("✅ Convocatoria actualizada correctamente.")
            st.rerun()

        titulares = [j for j in jugadores_disponibles if j not in suplentes]
        num_titulares = len(titulares)

        if num_titulares < MAX_TITULARES:
            st.warning(f"⚠️ Hay menos de {MAX_TITULARES} titulares ({num_titulares}). Faltan jugadores.")
        elif num_titulares > MAX_TITULARES:
            st.warning(f"⚠️ Hay más de {MAX_TITULARES} titulares ({num_titulares}). Revisa la convocatoria.")

        st.divider()

        with st.form("form_partido_manual"):
            fecha_partido = st.date_input("📅 Fecha del partido", value=datetime.today())
            fecha_str = fecha_partido.strftime("%Y-%m-%d")
            rival = st.text_input("🏟️ Rival", value=st.session_state.get("rival", ""))
            local_visitante = st.toggle("¿Tu equipo es el local?", value=st.session_state.get("local_visitante", False))
            goles_a_favor = st.number_input("⚽ Goles a favor", min_value=0, step=1, value=st.session_state.get("goles_a_favor", 0))
            goles_en_contra = st.number_input("🥅 Goles en contra", min_value=0, step=1, value=st.session_state.get("goles_en_contra", 0))
            resultado = (
                f"{TU_EQUIPO} {goles_a_favor} - {goles_en_contra} {rival}"
                if local_visitante
                else f"{rival} {goles_en_contra} - {goles_a_favor} {TU_EQUIPO}"
            )

            df_manual = pd.DataFrame({
                "JUGADOR": jugadores,
                "CONVOCADO": ["SÍ" if j not in no_convocados else "NO" for j in jugadores],
                "TITULAR": ["SÍ" if j in titulares else "NO" for j in jugadores],
                "SUPLENTE": ["SÍ" if j in suplentes else "NO" for j in jugadores],
                "GOL": [0] * len(jugadores),
                "ASIST": [0] * len(jugadores),
                "MINUTOS 1a PARTE": [0] * len(jugadores),
                "MINUTOS 2a PARTE": [0] * len(jugadores),
            })

            st.markdown("### ✏️ Introducir estadísticas individuales")
            df_editado = st.data_editor(df_manual, num_rows="fixed", width="stretch")

            submitted = st.form_submit_button("✅ Guardar partido")

        if submitted:
            if num_titulares != MAX_TITULARES:
                st.error(f"⚠️ El número de titulares debe ser exactamente {MAX_TITULARES}. Actualmente hay {num_titulares}.")
            elif len(jugadores_disponibles) < MAX_TITULARES:
                st.error(f"⚠️ Hay menos de {MAX_TITULARES} jugadores disponibles ({len(jugadores_disponibles)}).")
            else:
                mitad = MINUTOS_PARTIDO / 2
                invalidos = df_editado[
                    (df_editado["MINUTOS 1a PARTE"] > mitad) | (df_editado["MINUTOS 2a PARTE"] > mitad)
                ]
                if not invalidos.empty:
                    st.warning("⚠️ Algunos jugadores tienen minutos superiores al máximo permitido por parte.")
                    st.dataframe(invalidos[["JUGADOR", "MINUTOS 1a PARTE", "MINUTOS 2a PARTE"]], width="stretch")
                else:
                    df_editado["TOTAL MINUTOS JUGADOS"] = df_editado["MINUTOS 1a PARTE"] + df_editado["MINUTOS 2a PARTE"]
                    df_editado["% MINUTOS"] = (df_editado["TOTAL MINUTOS JUGADOS"] / MINUTOS_PARTIDO * 100).round(2)
                    df_editado.loc[0, "LOCAL"] = "Sí" if local_visitante else "No"
                    nombre_archivo = f"estadisticas_{rival.replace(' ', '_')}_{fecha_str}.csv"
                    ruta_archivo = CARPETA_PARTIDOS / nombre_archivo

                    if ruta_archivo.exists():
                        st.warning(f"⚠️ Ya existe '{ruta_archivo.name}'. Se sobrescribirá.")

                    guardar_partido(df_editado, ruta_archivo)
                    st.success(f"{resultado} ✅ Guardado correctamente")
                    st.dataframe(df_editado, width="stretch")


def page_4():
    st.header("📜 Histórico de partidos")

    archivos_validos = get_valid_match_files()
    todos_los_csv = list(CARPETA_PARTIDOS.glob("*.csv"))
    archivos_invalidos = [
        f for f in todos_los_csv
        if f not in archivos_validos and "estadisticas_generadas" not in f.name
    ]

    if archivos_invalidos:
        with st.expander("⚠️ Archivos no válidos detectados en la carpeta 'partidos'"):
            archivo_invalido = st.selectbox(
                "📂 Selecciona un archivo para revisar:",
                [f.name for f in archivos_invalidos],
                index=None,
            )
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
                            nueva_ruta = CARPETA_PARTIDOS / nuevo_nombre
                            if nueva_ruta.exists():
                                st.warning(f"⚠️ Ya existe '{nuevo_nombre}'. Se sobrescribirá.")
                            ruta_invalida.rename(nueva_ruta)
                            st.success(f"✅ Archivo renombrado como '{nuevo_nombre}'.")
                            st.rerun()
                except Exception as e:
                    st.error(f"⚠️ No se pudo leer '{archivo_invalido}': {type(e).__name__} - {e}")

    if not archivos_validos:
        st.info("📁 No hay partidos guardados todavía.")
        return

    resumen_partidos = []
    for archivo in archivos_validos:
        try:
            df = pd.read_csv(archivo)
            nombre_limpio = archivo.stem.replace("estadisticas_", "")
            partes = nombre_limpio.split("_")
            rival = " ".join(partes[:-1])
            fecha = partes[-1]

            goles_a_favor = df["GOL"][df["GOL"] > 0].sum()
            goles_en_contra = abs(df["GOL"][df["GOL"] < 0].sum())
            resultado = (
                "✅ Victoria" if goles_a_favor > goles_en_contra else
                "➖ Empate" if goles_a_favor == goles_en_contra else
                "❌ Derrota"
            )
            es_local = False
            if "LOCAL" in df.columns and pd.notna(df.loc[0, "LOCAL"]):
                es_local = str(df.loc[0, "LOCAL"]).strip().lower() in ["si", "sí", "true"]

            marcador = (
                f"{TU_EQUIPO} {int(goles_a_favor)} - {int(goles_en_contra)} {rival}"
                if es_local
                else f"{rival} {int(goles_en_contra)} - {int(goles_a_favor)} {TU_EQUIPO}"
            )
            resumen_partidos.append({
                "Archivo": str(archivo),
                "Fecha": fecha,
                "Rival": rival,
                "Resultado": resultado,
                "Marcador": marcador,
            })
        except Exception as e:
            st.error(f"⚠️ Error al leer {archivo.name}: {e}")

    df_resumen = pd.DataFrame(resumen_partidos)
    df_resumen["Fecha"] = pd.to_datetime(df_resumen["Fecha"], errors="coerce").dt.date
    df_resumen = df_resumen.sort_values("Fecha", ascending=False)

    st.subheader("📅 Partidos jugados")
    st.dataframe(df_resumen[["Fecha", "Rival", "Resultado", "Marcador"]], width="stretch")

    partidos_opciones = [f"{row.Fecha} - {row.Rival}" for _, row in df_resumen.iterrows()]
    partido_seleccionado = st.selectbox("🔍 Selecciona un partido para ver detalles", partidos_opciones, index=None)

    if partido_seleccionado:
        fila = df_resumen.iloc[partidos_opciones.index(partido_seleccionado)]
        archivo_detalle = Path(fila["Archivo"])

        st.markdown(f"### 📊 Detalles: **{fila['Rival']}** ({fila['Fecha']})")
        st.info(f"📍 **Marcador:** {fila['Marcador']}")

        # Modo edición
        editando = st.session_state.get("editando_partido") == str(archivo_detalle)

        _, col_editar = st.columns([4, 1])
        with col_editar:
            if not editando:
                if st.button("✏️ Editar partido"):
                    st.session_state["editando_partido"] = str(archivo_detalle)
                    st.rerun()
            else:
                if st.button("❌ Cancelar edición"):
                    st.session_state.pop("editando_partido", None)
                    st.rerun()

        if not editando:
            df_detalle = pd.read_csv(archivo_detalle)
            st.dataframe(df_detalle, width="stretch")
        else:
            st.warning("Estás editando este partido. Modifica los datos y pulsa Guardar.")
            df_detalle = pd.read_csv(archivo_detalle)
            df_editado = st.data_editor(df_detalle, width="stretch", num_rows="fixed")
            if st.button("💾 Guardar cambios"):
                guardar_partido(df_editado, archivo_detalle)
                st.success(f"✅ Partido guardado correctamente.")
                st.session_state.pop("editando_partido", None)
                st.rerun()


def page_plantilla():
    st.header("👥 Plantilla")
    st.markdown("Gestiona la lista de jugadores del equipo.")

    jugadores = load_jugadores()

    # Añadir jugador
    with st.form("form_añadir_jugador", clear_on_submit=True):
        nuevo = st.text_input("Nombre del nuevo jugador")
        if st.form_submit_button("➕ Añadir jugador"):
            nuevo = nuevo.strip()
            if not nuevo:
                st.error("❌ El nombre no puede estar vacío.")
            elif nuevo in jugadores:
                st.warning(f"⚠️ '{nuevo}' ya está en la plantilla.")
            else:
                jugadores.append(nuevo)
                save_jugadores(jugadores)
                st.success(f"✅ '{nuevo}' añadido a la plantilla.")
                st.rerun()

    st.divider()

    if not jugadores:
        st.info("La plantilla está vacía. Añade jugadores usando el formulario de arriba.")
        return

    st.subheader(f"Jugadores en plantilla ({len(jugadores)})")

    # Confirmar eliminación
    eliminar_key = "confirmar_eliminar"
    jugador_a_eliminar = st.session_state.get(eliminar_key)

    if jugador_a_eliminar:
        st.warning(f"¿Seguro que quieres eliminar a **{jugador_a_eliminar}** de la plantilla?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Sí, eliminar"):
                jugadores = [j for j in jugadores if j != jugador_a_eliminar]
                save_jugadores(jugadores)
                st.session_state.pop(eliminar_key, None)
                st.success(f"'{jugador_a_eliminar}' eliminado de la plantilla.")
                st.rerun()
        with c2:
            if st.button("❌ Cancelar"):
                st.session_state.pop(eliminar_key, None)
                st.rerun()

    for jugador in jugadores:
        col_nombre, col_btn = st.columns([5, 1])
        col_nombre.write(jugador)
        if col_btn.button("🗑️", key=f"del_{jugador}", help=f"Eliminar {jugador}"):
            st.session_state[eliminar_key] = jugador
            st.rerun()


# ── Navegación ────────────────────────────────────────────────────────────────

pg = st.navigation({
    "Estadísticas equipo": [
        st.Page(page_1, title="General", icon="😎"),
        st.Page(page_2, title="Individuales", icon="🪄"),
    ],
    "Estadísticas por partido": [
        st.Page(page_3, title="Añadir partido", icon="📅"),
        st.Page(page_4, title="Histórico de partidos", icon="📜"),
    ],
    "Equipo": [
        st.Page(page_plantilla, title="Plantilla", icon="👥"),
    ],
})
pg.run()
