import streamlit as st
import pandas as pd
from datetime import datetime
import db

columnas_datos_individuales = [
    "CONVOCADO", "% CONVOCADO", "TITULAR", "% TITULAR", "SUPLENTE", "% SUPLENTE",
    "GOL", "% GOLES", "ASIST", "% ASIST", "MINUTOS 1a PARTE", "MINUTOS 2a PARTE",
    "TOTAL MINUTOS JUGADOS", "POSIBLES MINUTOS", "% MINUTOS"]

opciones_ranking = ["GOL", "ASIST", "TOTAL MINUTOS JUGADOS",
                    "% MINUTOS", "% TITULAR", "PRODUCTIVIDAD OFENSIVA",
                    "EFICIENCIA GOLEADORA"]


# ── Funciones puras de estadísticas ──────────────────────────────────────────

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
    total_goles = int(data[data["GOL"] >= 0]["GOL"].sum())
    total_goles_contra = abs(int(data[data["GOL"] < 0]["GOL"].sum()))
    total_asist = int(data[data["GOL"] >= 0]["ASIST"].sum())
    total_partidos = int(pd.to_numeric(data["PARTIDOS"].iloc[0], errors="coerce") or 0)
    diferencia = total_goles - total_goles_contra
    media_favor = round(total_goles / total_partidos, 2) if total_partidos else 0
    media_contra = round(total_goles_contra / total_partidos, 2) if total_partidos else 0
    return {
        "Partidos": total_partidos,
        "Goles a favor": total_goles,
        "Media goles a favor": media_favor,
        "Asistencias": total_asist,
        "Goles en contra": total_goles_contra,
        "Media goles en contra": media_contra,
        "Diferencia de goles": diferencia,
    }


def ranking(df, columna, top=3):
    if columna not in df.columns:
        return pd.DataFrame()
    df_r = df[["JUGADOR", columna]].sort_values(by=columna, ascending=False).head(top)
    df_r.columns = ["Jugador", columna]
    return df_r


def metricas_extra(df):
    data = df.copy()
    if "GOL" in data.columns and "ASIST" in data.columns:
        data["PRODUCTIVIDAD OFENSIVA"] = data["GOL"] + data["ASIST"]
    if "GOL" in data.columns and "PARTIDOS" in data.columns:
        partidos = pd.to_numeric(data["PARTIDOS"].iloc[0], errors="coerce") or 1
        data["EFICIENCIA GOLEADORA"] = (data["GOL"] / partidos).round(2)
    return data


# ── Configuración de la app ───────────────────────────────────────────────────

st.set_page_config(
    page_title="Gestión estadísticas fútbol",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Auth ──────────────────────────────────────────────────────────────────────

def mostrar_login():
    st.title("⚽ Gestión de estadísticas")
    st.markdown("Inicia sesión para acceder a tu equipo.")
    tab_login, tab_registro = st.tabs(["Iniciar sesión", "Crear cuenta"])

    with tab_login:
        with st.form("form_login"):
            email = st.text_input("Email")
            password = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                if email and password:
                    ok, msg = db.sign_in(email, password)
                    if ok:
                        st.rerun()
                    else:
                        st.error(f"Error al iniciar sesión: {msg}")
                else:
                    st.warning("Rellena email y contraseña.")

    with tab_registro:
        with st.form("form_registro"):
            email_r = st.text_input("Email")
            password_r = st.text_input("Contraseña", type="password")
            password_r2 = st.text_input("Repite la contraseña", type="password")
            if st.form_submit_button("Crear cuenta"):
                if not email_r or not password_r:
                    st.warning("Rellena todos los campos.")
                elif password_r != password_r2:
                    st.error("Las contraseñas no coinciden.")
                elif len(password_r) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres.")
                else:
                    ok, msg = db.sign_up(email_r, password_r)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)


# ── Sidebar: selector de equipo ───────────────────────────────────────────────

def sidebar_equipo() -> bool:
    """Gestiona la selección de equipo en el sidebar. Devuelve True si hay equipo activo."""
    user = db.current_user()
    with st.sidebar:
        st.markdown(f"👤 **{user['email']}**")
        if st.button("Cerrar sesión", use_container_width=True):
            db.sign_out()
            st.rerun()
        st.divider()

        equipos = db.list_teams()

        if not equipos:
            st.info("No tienes ningún equipo. Crea uno:")
            with st.form("form_crear_equipo"):
                nombre = st.text_input("Nombre del equipo")
                categoria = st.text_input("Categoría", value="Benjamín")
                max_tit = st.number_input("Titulares por partido", min_value=5, max_value=11, value=8)
                minutos = st.number_input("Minutos por partido", min_value=20, max_value=90, value=50)
                if st.form_submit_button("Crear equipo"):
                    if nombre.strip():
                        equipo = db.create_team(nombre.strip(), categoria.strip(), int(max_tit), int(minutos))
                        if equipo:
                            st.session_state["current_team"] = equipo
                            st.rerun()
                        else:
                            st.error("No se pudo crear el equipo.")
                    else:
                        st.warning("El nombre no puede estar vacío.")
            return False

        nombres = [e["name"] for e in equipos]
        equipo_actual = st.session_state.get("current_team")
        idx_default = 0
        if equipo_actual:
            ids = [e["id"] for e in equipos]
            if equipo_actual["id"] in ids:
                idx_default = ids.index(equipo_actual["id"])

        seleccion = st.selectbox("⚽ Equipo", nombres, index=idx_default)
        equipo_sel = next(e for e in equipos if e["name"] == seleccion)
        if not equipo_actual or equipo_actual["id"] != equipo_sel["id"]:
            st.session_state["current_team"] = equipo_sel

        with st.expander("➕ Nuevo equipo"):
            nombre_n = st.text_input("Nombre", key="nombre_nuevo_equipo")
            cat_n = st.text_input("Categoría", value="Benjamín", key="cat_nuevo_equipo")
            max_n = st.number_input("Titulares", min_value=5, max_value=11, value=8, key="max_nuevo_equipo")
            min_n = st.number_input("Minutos", min_value=20, max_value=90, value=50, key="min_nuevo_equipo")
            if st.button("Crear equipo", key="btn_nuevo_equipo"):
                if nombre_n.strip():
                    nuevo = db.create_team(nombre_n.strip(), cat_n.strip(), int(max_n), int(min_n))
                    if nuevo:
                        st.session_state["current_team"] = nuevo
                        st.rerun()
                else:
                    st.warning("El nombre no puede estar vacío.")

        return True


def get_equipo() -> dict:
    return st.session_state.get("current_team", {})


# ── Páginas ───────────────────────────────────────────────────────────────────

def page_1():
    equipo = get_equipo()
    st.subheader(f"📊 Estadísticas de {equipo['name']}")

    df = db.get_team_aggregates(equipo["id"], equipo["minutos_partido"])
    if df.empty:
        st.info("📁 Aún no hay partidos registrados. Ve a **Añadir partido** para empezar.")
        return

    with st.expander("📋 Resumen del equipo", expanded=True):
        resumen = estadisticas_generales(df)
        df_resumen = pd.DataFrame({"Estadística": resumen.keys(), "Total": resumen.values()})
        st.dataframe(df_resumen, width="stretch")

    st.subheader("📈 Estadísticas acumuladas")
    st.dataframe(df, width="stretch")


def page_2():
    equipo = get_equipo()
    st.header("🪄 Estadísticas individuales")

    df = db.get_team_aggregates(equipo["id"], equipo["minutos_partido"])
    if df.empty:
        st.info("📁 Aún no hay partidos registrados.")
        return

    jugadores = df["JUGADOR"].dropna().astype(str).tolist()
    select_jugador = st.multiselect("Selecciona jugador(es):", options=jugadores, default=jugadores)
    if select_jugador:
        df_sel = df[df["JUGADOR"].isin(select_jugador)]
        columnas = [c for c in columnas_datos_individuales if c in df.columns]
        st.dataframe(df_sel[["JUGADOR"] + columnas], width="stretch")
    else:
        st.warning("Selecciona al menos un jugador.")

    df_extra = metricas_extra(df)
    seleccion_rankings = st.multiselect("🏆 Mostrar rankings", options=opciones_ranking)
    if seleccion_rankings:
        num_cols = min(len(seleccion_rankings), 3)
        for i in range(0, len(seleccion_rankings), 3):
            cols = st.columns(num_cols)
            for j, col in enumerate(cols):
                if i + j < len(seleccion_rankings):
                    metrica = seleccion_rankings[i + j]
                    col.markdown(f"🏅 {metrica}")
                    col.dataframe(ranking(df_extra, metrica), width="stretch")
    else:
        st.warning("Selecciona al menos un ranking para mostrar resultados.")


def page_3():
    equipo = get_equipo()
    MAX_TITULARES = equipo["max_titulares"]
    MINUTOS_PARTIDO = equipo["minutos_partido"]

    st.header("📅 Añadir partido")

    players_data = db.list_players(equipo["id"])
    if not players_data:
        st.warning("⚠️ No hay jugadores en la plantilla. Ve a **Plantilla** para añadirlos.")
        return

    jugadores = [p["name"] for p in players_data]
    player_ids = {p["name"]: p["id"] for p in players_data}

    for key in ["no_convocados", "suplentes"]:
        st.session_state.setdefault(key, [])
    for key in ["goles_a_favor", "goles_en_contra"]:
        st.session_state.setdefault(key, 0)
    st.session_state.setdefault("rival", "")
    st.session_state.setdefault("local_visitante", False)

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
    if max_suplentes == 0:
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
        st.success("✅ Convocatoria actualizada.")
        st.rerun()

    titulares = [j for j in jugadores_disponibles if j not in suplentes]
    num_titulares = len(titulares)

    if num_titulares < MAX_TITULARES:
        st.warning(f"⚠️ Hay {num_titulares} titulares. Se necesitan {MAX_TITULARES}.")
    elif num_titulares > MAX_TITULARES:
        st.warning(f"⚠️ Hay {num_titulares} titulares. Máximo {MAX_TITULARES}.")

    st.divider()

    with st.form("form_partido_manual"):
        fecha_partido = st.date_input("📅 Fecha del partido", value=datetime.today())
        rival = st.text_input("🏟️ Rival", value=st.session_state.get("rival", ""))
        local_visitante = st.toggle("¿Tu equipo es el local?", value=st.session_state.get("local_visitante", False))
        goles_a_favor = st.number_input("⚽ Goles a favor", min_value=0, step=1, value=st.session_state.get("goles_a_favor", 0))
        goles_en_contra = st.number_input("🥅 Goles en contra", min_value=0, step=1, value=st.session_state.get("goles_en_contra", 0))

        resultado = (
            f"{equipo['name']} {goles_a_favor} - {goles_en_contra} {rival}"
            if local_visitante
            else f"{rival} {goles_en_contra} - {goles_a_favor} {equipo['name']}"
        )

        df_manual = pd.DataFrame({
            "JUGADOR":          jugadores,
            "CONVOCADO":        ["SÍ" if j not in no_convocados else "NO" for j in jugadores],
            "TITULAR":          ["SÍ" if j in titulares else "NO" for j in jugadores],
            "SUPLENTE":         ["SÍ" if j in suplentes else "NO" for j in jugadores],
            "GOL":              [0] * len(jugadores),
            "ASIST":            [0] * len(jugadores),
            "MINUTOS 1a PARTE": [0] * len(jugadores),
            "MINUTOS 2a PARTE": [0] * len(jugadores),
        })

        st.markdown("### ✏️ Estadísticas individuales")
        df_editado = st.data_editor(df_manual, num_rows="fixed", width="stretch")
        submitted = st.form_submit_button("✅ Guardar partido")

    if submitted:
        if not rival.strip():
            st.error("❌ Introduce el nombre del rival.")
        elif num_titulares != MAX_TITULARES:
            st.error(f"⚠️ El número de titulares debe ser exactamente {MAX_TITULARES} (hay {num_titulares}).")
        else:
            mitad = MINUTOS_PARTIDO / 2
            invalidos = df_editado[
                (df_editado["MINUTOS 1a PARTE"] > mitad) | (df_editado["MINUTOS 2a PARTE"] > mitad)
            ]
            if not invalidos.empty:
                st.warning("⚠️ Algunos jugadores superan los minutos máximos por parte.")
                st.dataframe(invalidos[["JUGADOR", "MINUTOS 1a PARTE", "MINUTOS 2a PARTE"]], width="stretch")
            else:
                stats = [
                    {
                        "player_id":   player_ids[row["JUGADOR"]],
                        "convocado":   row["CONVOCADO"] == "SÍ",
                        "titular":     row["TITULAR"] == "SÍ",
                        "suplente":    row["SUPLENTE"] == "SÍ",
                        "goles":       int(row["GOL"]),
                        "asistencias": int(row["ASIST"]),
                        "minutos_1a":  int(row["MINUTOS 1a PARTE"]),
                        "minutos_2a":  int(row["MINUTOS 2a PARTE"]),
                    }
                    for _, row in df_editado.iterrows()
                ]
                match = db.create_match(
                    team_id=equipo["id"],
                    rival=rival.strip(),
                    match_date=fecha_partido,
                    is_home=local_visitante,
                    goals_for=int(goles_a_favor),
                    goals_against=int(goles_en_contra),
                    stats=stats,
                )
                if match:
                    st.success(f"✅ {resultado} — Partido guardado correctamente.")
                    for k in ["no_convocados", "suplentes", "rival", "goles_a_favor", "goles_en_contra", "local_visitante"]:
                        st.session_state.pop(k, None)
                    st.rerun()
                else:
                    st.error("❌ No se pudo guardar el partido. Inténtalo de nuevo.")


def page_4():
    equipo = get_equipo()
    st.header("📜 Histórico de partidos")

    partidos = db.list_matches(equipo["id"])
    if not partidos:
        st.info("📁 No hay partidos registrados todavía.")
        return

    resumen = []
    for p in partidos:
        gf, gc = p["goals_for"], p["goals_against"]
        resultado = (
            "✅ Victoria" if gf > gc else
            "➖ Empate"   if gf == gc else
            "❌ Derrota"
        )
        marcador = (
            f"{equipo['name']} {gf} - {gc} {p['rival']}"
            if p["is_home"]
            else f"{p['rival']} {gc} - {gf} {equipo['name']}"
        )
        resumen.append({"id": p["id"], "Fecha": p["match_date"],
                        "Rival": p["rival"], "Resultado": resultado, "Marcador": marcador})

    df_resumen = pd.DataFrame(resumen)
    st.subheader("📅 Partidos jugados")
    st.dataframe(df_resumen[["Fecha", "Rival", "Resultado", "Marcador"]], width="stretch")

    opciones = [f"{r['Fecha']} - {r['Rival']}" for r in resumen]
    seleccion = st.selectbox("🔍 Selecciona un partido para ver detalles", opciones, index=None)
    if not seleccion:
        return

    partido = resumen[opciones.index(seleccion)]
    match_data, stats_data = db.get_match(partido["id"])
    if not match_data:
        st.error("No se pudo cargar el partido.")
        return

    st.markdown(f"### 📊 Detalles: **{partido['Rival']}** ({partido['Fecha']})")
    st.info(f"📍 **Marcador:** {partido['Marcador']}")

    player_ids_map = {}
    filas = []
    for s in stats_data:
        nombre = s["players"]["name"] if s.get("players") else s["player_id"]
        player_ids_map[nombre] = s["player_id"]
        filas.append({
            "JUGADOR":          nombre,
            "CONVOCADO":        "SÍ" if s["convocado"] else "NO",
            "TITULAR":          "SÍ" if s["titular"] else "NO",
            "SUPLENTE":         "SÍ" if s["suplente"] else "NO",
            "GOL":              s["goles"],
            "ASIST":            s["asistencias"],
            "MINUTOS 1a PARTE": s["minutos_1a"],
            "MINUTOS 2a PARTE": s["minutos_2a"],
        })
    df_detalle = pd.DataFrame(filas)

    editando = st.session_state.get("editando_partido") == partido["id"]
    _, col_editar = st.columns([4, 1])
    with col_editar:
        if not editando:
            if st.button("✏️ Editar partido"):
                st.session_state["editando_partido"] = partido["id"]
                st.rerun()
        else:
            if st.button("❌ Cancelar edición"):
                st.session_state.pop("editando_partido", None)
                st.rerun()

    if not editando:
        st.dataframe(df_detalle, width="stretch")
    else:
        st.warning("Estás editando este partido. Modifica los datos y pulsa Guardar.")
        df_edit = st.data_editor(df_detalle, width="stretch", num_rows="fixed")
        if st.button("💾 Guardar cambios"):
            stats_upd = [
                {
                    "player_id":   player_ids_map[row["JUGADOR"]],
                    "convocado":   row["CONVOCADO"] == "SÍ",
                    "titular":     row["TITULAR"] == "SÍ",
                    "suplente":    row["SUPLENTE"] == "SÍ",
                    "goles":       int(row["GOL"]),
                    "asistencias": int(row["ASIST"]),
                    "minutos_1a":  int(row["MINUTOS 1a PARTE"]),
                    "minutos_2a":  int(row["MINUTOS 2a PARTE"]),
                }
                for _, row in df_edit.iterrows()
            ]
            ok = db.update_match(
                match_id=partido["id"],
                rival=match_data["rival"],
                match_date=datetime.strptime(match_data["match_date"], "%Y-%m-%d").date(),
                is_home=match_data["is_home"],
                goals_for=match_data["goals_for"],
                goals_against=match_data["goals_against"],
                stats=stats_upd,
            )
            if ok:
                st.success("✅ Partido guardado correctamente.")
                st.session_state.pop("editando_partido", None)
                st.rerun()
            else:
                st.error("❌ No se pudo guardar.")


def page_plantilla():
    equipo = get_equipo()
    st.header("👥 Plantilla")
    st.markdown(f"Gestiona los jugadores de **{equipo['name']}**.")

    players = db.list_players(equipo["id"])

    with st.form("form_añadir_jugador", clear_on_submit=True):
        nuevo = st.text_input("Nombre del nuevo jugador")
        if st.form_submit_button("➕ Añadir jugador"):
            nuevo = nuevo.strip()
            nombres_actuales = [p["name"] for p in players]
            if not nuevo:
                st.error("❌ El nombre no puede estar vacío.")
            elif nuevo in nombres_actuales:
                st.warning(f"⚠️ '{nuevo}' ya está en la plantilla.")
            else:
                result = db.add_player(equipo["id"], nuevo)
                if result:
                    st.success(f"✅ '{nuevo}' añadido a la plantilla.")
                    st.rerun()
                else:
                    st.error("No se pudo añadir el jugador.")

    st.divider()

    if not players:
        st.info("La plantilla está vacía. Añade jugadores usando el formulario de arriba.")
        return

    st.subheader(f"Jugadores en plantilla ({len(players)})")

    eliminar_key = "confirmar_eliminar"
    jugador_a_eliminar = st.session_state.get(eliminar_key)

    if jugador_a_eliminar:
        nombre_eli = jugador_a_eliminar["name"]
        st.warning(f"¿Dar de baja a **{nombre_eli}**? Se conservará su histórico de partidos.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Sí, dar de baja"):
                db.deactivate_player(jugador_a_eliminar["id"])
                st.session_state.pop(eliminar_key, None)
                st.success(f"'{nombre_eli}' dado de baja.")
                st.rerun()
        with c2:
            if st.button("❌ Cancelar"):
                st.session_state.pop(eliminar_key, None)
                st.rerun()

    for jugador in players:
        col_nombre, col_btn = st.columns([5, 1])
        col_nombre.write(jugador["name"])
        if col_btn.button("🗑️", key=f"del_{jugador['id']}", help=f"Dar de baja a {jugador['name']}"):
            st.session_state[eliminar_key] = jugador
            st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

if not db.current_user():
    mostrar_login()
    st.stop()

equipo_disponible = sidebar_equipo()
if not equipo_disponible or "current_team" not in st.session_state:
    st.stop()

equipo_actual = get_equipo()
st.header(f"⚽ {equipo_actual['name']} — {equipo_actual['category']}")

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
