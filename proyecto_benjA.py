import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import db
import pdf_export


PERIODOS = {
    "Toda la temporada": {},
    "Últimos 5 partidos": {"last_n_matches": 5},
    "Últimos 10 partidos": {"last_n_matches": 10},
    "Último mes":         {"since_date": "MONTH"},
}


def selector_periodo(key: str) -> dict:
    """Renderiza un selectbox de periodo y devuelve los kwargs para get_team_aggregates."""
    sel = st.selectbox("📅 Periodo", options=list(PERIODOS.keys()), key=f"periodo_{key}")
    kwargs = dict(PERIODOS[sel])
    if kwargs.get("since_date") == "MONTH":
        kwargs["since_date"] = date.today() - timedelta(days=30)
    return kwargs

columnas_datos_individuales = [
    "CONVOCADO", "% CONVOCADO", "TITULAR", "% TITULAR", "SUPLENTE", "% SUPLENTE",
    "GOL", "% GOLES", "ASIST", "% ASIST", "MINUTOS 1a PARTE", "MINUTOS 2a PARTE",
    "TOTAL MINUTOS JUGADOS", "POSIBLES MINUTOS", "% MINUTOS"]

opciones_ranking = ["GOL", "ASIST", "TOTAL MINUTOS JUGADOS",
                    "% MINUTOS", "% TITULAR", "PRODUCTIVIDAD OFENSIVA",
                    "EFICIENCIA GOLEADORA"]


# ── Funciones puras de estadísticas ──────────────────────────────────────────

def estadisticas_generales(totales: dict) -> dict:
    """Devuelve el resumen del equipo usando el dict de totales ya calculado."""
    total_partidos   = totales.get("total_partidos", 0)
    total_goles      = totales.get("total_goles", 0)
    total_asist      = totales.get("total_asist", 0)
    total_goles_contra = totales.get("total_goles_contra", 0)
    diferencia = total_goles - total_goles_contra
    media_favor  = round(total_goles / total_partidos, 2) if total_partidos else 0
    media_contra = round(total_goles_contra / total_partidos, 2) if total_partidos else 0
    return {
        "Partidos":              total_partidos,
        "Goles a favor":         total_goles,
        "Media goles a favor":   media_favor,
        "Asistencias":           total_asist,
        "Goles en contra":       total_goles_contra,
        "Media goles en contra": media_contra,
        "Diferencia de goles":   diferencia,
    }


def ranking(df, columna, top=3):
    if columna not in df.columns:
        return pd.DataFrame()
    df_r = df[["JUGADOR", columna]].sort_values(by=columna, ascending=False).head(top)
    df_r.columns = ["Jugador", columna]
    return df_r


def metricas_extra(df: pd.DataFrame, total_partidos: int) -> pd.DataFrame:
    data = df.copy()
    if "GOL" in data.columns and "ASIST" in data.columns:
        data["PRODUCTIVIDAD OFENSIVA"] = data["GOL"] + data["ASIST"]
    if "GOL" in data.columns and total_partidos:
        data["EFICIENCIA GOLEADORA"] = (data["GOL"] / total_partidos).round(2)
    return data


def calcular_racha(partidos: list) -> tuple[str, int]:
    """Racha consecutiva del resultado más reciente (partidos ordenados desc por fecha)."""
    if not partidos:
        return "", 0
    racha_tipo = None
    racha_count = 0
    for p in partidos:
        gf, gc = p["goals_for"], p["goals_against"]
        tipo = "Victoria" if gf > gc else ("Empate" if gf == gc else "Derrota")
        if racha_tipo is None:
            racha_tipo, racha_count = tipo, 1
        elif tipo == racha_tipo:
            racha_count += 1
        else:
            break
    return racha_tipo, racha_count


def mejor_resultado(partidos: list) -> dict | None:
    """Partido con mayor diferencia de goles a favor."""
    if not partidos:
        return None
    return max(partidos, key=lambda p: p["goals_for"] - p["goals_against"])


def partido_mas_goles(partidos: list) -> dict | None:
    """Partido con más goles totales entre ambos equipos."""
    if not partidos:
        return None
    return max(partidos, key=lambda p: p["goals_for"] + p["goals_against"])


FORMACIONES = {
    "1-3-3-1": ["Portero", "Lateral Derecho", "Defensa Central", "Lateral Izquierdo",
                "Banda Derecha", "Centrocampista", "Banda Izquierda", "Delantero"],
    "1-3-2-2": ["Portero", "Lateral Derecho", "Defensa Central", "Lateral Izquierdo",
                "Centrocampista", "Centrocampista", "Delantero", "Delantero"],
    "1-2-3-2": ["Portero", "Lateral Derecho", "Lateral Izquierdo",
                "Banda Derecha", "Centrocampista", "Banda Izquierda", "Delantero", "Delantero"],
}


def sugerir_alineacion(disponibles: list[dict], stats_min: dict[str, float],
                       formacion: list[str]) -> list[tuple[str, dict | None]]:
    """
    Asigna jugadores a las posiciones de la formación priorizando:
    1. Posición primaria coincide → preferido
    2. Posición alternativa coincide → segundo nivel
    3. Sin coincidencia (fallback) → último recurso
    En cada nivel, ordena por % MINUTOS ascendente (rotación justa).

    `disponibles`: lista de jugadores (dicts con id, name, position, alt_positions).
    `stats_min`: dict {nombre: % MINUTOS acumulado}.
    `formacion`: lista de posiciones en orden.
    Devuelve lista de tuplas (posicion, jugador_dict|None).
    """
    asignados: set[str] = set()
    resultado: list[tuple[str, dict | None]] = []

    def pct_min(p): return stats_min.get(p["name"], 0.0)

    for pos in formacion:
        candidatos = [p for p in disponibles if p["id"] not in asignados]
        # Nivel 1: posición primaria
        primarios = sorted([p for p in candidatos if p.get("position") == pos], key=pct_min)
        # Nivel 2: alternativa
        alternos = sorted([p for p in candidatos
                           if p.get("position") != pos and pos in (p.get("alt_positions") or [])],
                          key=pct_min)
        elegido = primarios[0] if primarios else (alternos[0] if alternos else None)
        if elegido is None and candidatos:
            # Fallback: el que menos ha jugado, sin importar posición
            elegido = sorted(candidatos, key=pct_min)[0]
        if elegido:
            asignados.add(elegido["id"])
        resultado.append((pos, elegido))
    return resultado


def comparar_jugadores(df: pd.DataFrame, j_a: str, j_b: str,
                       metricas: list[str]) -> pd.DataFrame:
    """Devuelve un DataFrame con la comparativa side-by-side de 2 jugadores."""
    fila_a = df[df["JUGADOR"] == j_a].iloc[0] if not df[df["JUGADOR"] == j_a].empty else None
    fila_b = df[df["JUGADOR"] == j_b].iloc[0] if not df[df["JUGADOR"] == j_b].empty else None
    if fila_a is None or fila_b is None:
        return pd.DataFrame()
    rows = []
    for m in metricas:
        if m not in df.columns:
            continue
        va, vb = fila_a[m], fila_b[m]
        if va > vb:
            lider = j_a
        elif vb > va:
            lider = j_b
        else:
            lider = "Empate"
        rows.append({"Métrica": m, j_a: va, j_b: vb, "Líder": lider})
    return pd.DataFrame(rows)


def calcular_distintivos(df: pd.DataFrame) -> dict[str, str]:
    """Devuelve {nombre_jugador: emojis} con los líderes de cada categoría."""
    if df.empty:
        return {}
    badges: dict[str, str] = {}
    reglas = [
        ("GOL",                   "🥇"),
        ("ASIST",                 "🎯"),
        ("TOTAL MINUTOS JUGADOS", "⏱️"),
    ]
    for col, emoji in reglas:
        if col not in df.columns:
            continue
        max_v = df[col].max()
        if pd.isna(max_v) or max_v <= 0:
            continue
        for nombre in df[df[col] == max_v]["JUGADOR"]:
            badges[nombre] = badges.get(nombre, "") + emoji
    return badges


def calcular_balance(partidos: list) -> dict:
    """Balance de liga: PJ / V / E / D / GF / GC / DIF / PTS."""
    v = sum(1 for p in partidos if p["goals_for"] > p["goals_against"])
    e = sum(1 for p in partidos if p["goals_for"] == p["goals_against"])
    d = sum(1 for p in partidos if p["goals_for"] < p["goals_against"])
    gf = sum(p["goals_for"] for p in partidos)
    gc = sum(p["goals_against"] for p in partidos)
    return {"PJ": len(partidos), "V": v, "E": e, "D": d,
            "GF": gf, "GC": gc, "DIF": gf - gc, "PTS": v * 3 + e}


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

    periodo_kwargs = selector_periodo("general")
    df, totales = db.get_team_aggregates(equipo["id"], equipo["minutos_partido"], **periodo_kwargs)
    partidos_raw = db.list_matches(equipo["id"])

    if df.empty:
        st.info("📁 Aún no hay partidos registrados. Ve a **Añadir partido** para empezar.")
        return

    # Tarjetas de totales del equipo (A1) + botón PDF (B2)
    c1, c2, c3, c4, c_pdf = st.columns([2, 2, 2, 2, 1])
    c1.metric("Partidos", totales["total_partidos"])
    c2.metric("Goles a favor", totales["total_goles"])
    c3.metric("Goles en contra", totales["total_goles_contra"])
    c4.metric("Asistencias", totales["total_asist"])
    with c_pdf:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        pdf_bytes = pdf_export.generar_pdf_estadisticas(equipo, df, totales)
        st.download_button(
            "📄 PDF",
            data=pdf_bytes,
            file_name=f"estadisticas_{equipo['name'].replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    # C2: Racha y récords
    if partidos_raw:
        st.subheader("🏆 Récords de la temporada")
        tipo_racha, n_racha = calcular_racha(partidos_raw)
        p_mejor = mejor_resultado(partidos_raw)
        p_goles = partido_mas_goles(partidos_raw)

        def fmt_marcador(p: dict) -> str:
            gf, gc = p["goals_for"], p["goals_against"]
            return (f"{equipo['name']} {gf}-{gc} {p['rival']}"
                    if p["is_home"] else f"{p['rival']} {gc}-{gf} {equipo['name']}")

        icono_racha = {"Victoria": "✅", "Empate": "➖", "Derrota": "❌"}.get(tipo_racha, "")
        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("Racha actual", f"{icono_racha} {n_racha} {tipo_racha.lower()}")
        rc2.metric("Mejor resultado", fmt_marcador(p_mejor), p_mejor["match_date"])
        rc3.metric("Partido más goleador", fmt_marcador(p_goles), p_goles["match_date"])

    # D7: Balance de liga
    if partidos_raw:
        st.subheader("📋 Balance de la temporada")
        bal = calcular_balance(partidos_raw)
        st.dataframe(pd.DataFrame([bal]), hide_index=True, width="stretch")

    # F6: MVPs de la temporada
    mvp_ranking = db.get_mvp_ranking(equipo["id"])
    if mvp_ranking:
        st.subheader("🌟 MVPs de la temporada")
        st.dataframe(pd.DataFrame(mvp_ranking[:5]), hide_index=True, width="stretch")

    with st.expander("📋 Resumen del equipo", expanded=False):
        resumen = estadisticas_generales(totales)
        df_resumen = pd.DataFrame({"Estadística": resumen.keys(), "Total": resumen.values()})
        st.dataframe(df_resumen, width="stretch")

    st.subheader("📈 Estadísticas acumuladas por jugador")
    st.dataframe(df, width="stretch")

    # A6: Gráfico de % de minutos por jugador
    st.subheader("⏱️ % de minutos jugados por jugador")
    df_min_chart = df.set_index("JUGADOR")[["% MINUTOS"]].sort_values("% MINUTOS")
    st.bar_chart(df_min_chart)


def page_2():
    equipo = get_equipo()
    st.header("🪄 Estadísticas individuales")

    periodo_kwargs = selector_periodo("indiv")
    df, totales = db.get_team_aggregates(equipo["id"], equipo["minutos_partido"], **periodo_kwargs)
    if df.empty:
        st.info("📁 Aún no hay partidos registrados.")
        return

    # D2/F2: Filtro por posición (primaria o alternativa)
    players_data = db.list_players(equipo["id"])
    name_to_id = {p["name"]: p["id"] for p in players_data}
    posiciones_de = lambda p: ([p["position"]] if p.get("position") else []) + list(p.get("alt_positions") or [])
    positions_available = sorted({pos for p in players_data for pos in posiciones_de(p)})
    if positions_available:
        pos_filter = st.multiselect("Filtrar por posición:", options=positions_available, default=[])
        if pos_filter:
            jugadores_con_pos = {p["name"] for p in players_data
                                 if any(pos in pos_filter for pos in posiciones_de(p))}
            df = df[df["JUGADOR"].isin(jugadores_con_pos)]

    jugadores = df["JUGADOR"].dropna().astype(str).tolist()
    select_jugador = st.multiselect("Selecciona jugador(es):", options=jugadores, default=jugadores)
    if select_jugador:
        df_sel = df[df["JUGADOR"].isin(select_jugador)]
        columnas = [c for c in columnas_datos_individuales if c in df.columns]
        st.dataframe(df_sel[["JUGADOR"] + columnas], width="stretch")
    else:
        st.warning("Selecciona al menos un jugador.")

    df_extra = metricas_extra(df, totales["total_partidos"])
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

    # A6: Distribución de goles del equipo
    if totales["total_goles"] > 0:
        st.subheader("⚽ Distribución de goles del equipo")
        df_goles_chart = (
            df[df["GOL"] > 0][["JUGADOR", "GOL"]]
            .set_index("JUGADOR")
            .sort_values("GOL", ascending=False)
        )
        st.bar_chart(df_goles_chart)

    # F5: Comparativa entre 2 jugadores
    with st.expander("🆚 Comparar 2 jugadores", expanded=False):
        all_jugadores = df["JUGADOR"].dropna().astype(str).tolist()
        if len(all_jugadores) < 2:
            st.info("Hacen falta al menos 2 jugadores con datos para comparar.")
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                j_a = st.selectbox("Jugador A", options=all_jugadores, key="cmp_a", index=0)
            with col_b:
                opciones_b = [j for j in all_jugadores if j != j_a]
                j_b = st.selectbox("Jugador B", options=opciones_b, key="cmp_b", index=0)
            metricas_cmp = ["GOL", "ASIST", "% MINUTOS", "% TITULAR", "% CONVOCADO",
                            "PRODUCTIVIDAD OFENSIVA", "EFICIENCIA GOLEADORA",
                            "AMARILLAS", "ROJAS"]
            df_cmp = comparar_jugadores(df, j_a, j_b, metricas_cmp)
            if not df_cmp.empty:
                st.dataframe(df_cmp, hide_index=True, width="stretch")
                metricas_chart = ["GOL", "ASIST", "% MINUTOS", "% TITULAR"]
                df_chart = (df_cmp[df_cmp["Métrica"].isin(metricas_chart)]
                            [["Métrica", j_a, j_b]].set_index("Métrica"))
                if not df_chart.empty:
                    st.bar_chart(df_chart)

    # F1: Historial de partidos del jugador
    st.subheader("📋 Historial de partidos del jugador")
    all_jugadores = df["JUGADOR"].dropna().astype(str).tolist()
    jugador_evol = st.selectbox(
        "Selecciona un jugador:",
        options=all_jugadores,
        index=None,
        key="evol_selectbox",
    )
    if jugador_evol and jugador_evol in name_to_id:
        historial = db.get_player_history(name_to_id[jugador_evol])
        if historial:
            st.dataframe(pd.DataFrame(historial), hide_index=True, width="stretch")
        else:
            st.info("Este jugador no tiene partidos registrados como convocado.")


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

    # F7: Sugerir alineación
    with st.expander("💡 Sugerir alineación (rotación + posiciones)", expanded=False):
        col_f, col_btn = st.columns([2, 1])
        formacion_sel = col_f.selectbox(
            "Formación", options=list(FORMACIONES.keys()),
            help="Para fútbol 8. La sugerencia prioriza la rotación justa (% minutos)."
        )
        sugerir_btn = col_btn.button("💡 Sugerir titular", use_container_width=True)
        if sugerir_btn:
            df_stats_sug, _ = db.get_team_aggregates(equipo["id"], equipo["minutos_partido"])
            stats_min = (dict(zip(df_stats_sug["JUGADOR"], df_stats_sug["% MINUTOS"]))
                         if not df_stats_sug.empty else {})
            asignacion = sugerir_alineacion(players_data, stats_min, FORMACIONES[formacion_sel])
            titulares_sug = [j["name"] for _, j in asignacion if j]
            if len(titulares_sug) == MAX_TITULARES:
                st.session_state["no_convocados"] = []
                st.session_state["suplentes"] = [j for j in jugadores if j not in titulares_sug]
                st.success(f"Alineación {formacion_sel} sugerida — pulsa 'Actualizar convocatoria'.")
                for pos, j in asignacion:
                    nombre = j["name"] if j else "—"
                    st.write(f"**{pos}** → {nombre}")
            else:
                st.warning("No se ha podido completar la alineación (faltan jugadores).")

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
        notas = st.text_area("📝 Notas del partido (opcional)", value="", placeholder="Observaciones, clima, táctica…")

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
            "AMARILLAS":        [0] * len(jugadores),
            "ROJAS":            [0] * len(jugadores),
        })

        st.markdown("### ✏️ Estadísticas individuales")
        df_editado = st.data_editor(df_manual, num_rows="fixed", width="stretch")

        # F6: MVP del partido (entre los convocados)
        opciones_mvp = ["— Sin MVP —"] + [j for j in jugadores if j not in no_convocados]
        mvp_sel = st.selectbox("🌟 MVP del partido (opcional)", options=opciones_mvp)

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
                        "amarillas":   int(row["AMARILLAS"]),
                        "rojas":       int(row["ROJAS"]),
                    }
                    for _, row in df_editado.iterrows()
                ]
                mvp_id = player_ids.get(mvp_sel) if mvp_sel != "— Sin MVP —" else None
                match = db.create_match(
                    team_id=equipo["id"],
                    rival=rival.strip(),
                    match_date=fecha_partido,
                    is_home=local_visitante,
                    goals_for=int(goles_a_favor),
                    goals_against=int(goles_en_contra),
                    stats=stats,
                    notes=notas.strip(),
                    mvp_player_id=mvp_id,
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

    # A6: Evolución de goles por jornada
    if len(partidos) > 1:
        st.subheader("📈 Evolución de goles")
        df_evol = pd.DataFrame([
            {
                "Partido": f"{p['match_date']} vs {p['rival']}",
                "Goles a favor": p["goals_for"],
                "Goles en contra": p["goals_against"],
            }
            for p in reversed(partidos)
        ]).set_index("Partido")
        st.line_chart(df_evol)

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
    if match_data.get("notes"):
        st.markdown(f"📝 **Notas:** {match_data['notes']}")
    # F6: MVP destacado
    mvp_id_actual = match_data.get("mvp_player_id")
    if mvp_id_actual:
        nombre_mvp = next((s["players"]["name"] for s in stats_data
                           if s.get("players") and s["player_id"] == mvp_id_actual), None)
        if nombre_mvp:
            st.success(f"🌟 **MVP del partido:** {nombre_mvp}")

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
            "AMARILLAS":        s.get("amarillas", 0),
            "ROJAS":            s.get("rojas", 0),
        })
    df_detalle = pd.DataFrame(filas)

    editando = st.session_state.get("editando_partido") == partido["id"]
    confirmando_borrar = st.session_state.get("confirmar_eliminar_partido") == partido["id"]

    # Botones de acción (A2: añadido Eliminar)
    _, col_editar, col_borrar = st.columns([3, 1, 1])
    with col_editar:
        if not editando:
            if st.button("✏️ Editar partido", use_container_width=True):
                st.session_state["editando_partido"] = partido["id"]
                st.session_state.pop("confirmar_eliminar_partido", None)
                st.rerun()
        else:
            if st.button("❌ Cancelar edición", use_container_width=True):
                st.session_state.pop("editando_partido", None)
                st.rerun()

    with col_borrar:
        if not confirmando_borrar:
            if st.button("🗑️ Eliminar", use_container_width=True):
                st.session_state["confirmar_eliminar_partido"] = partido["id"]
                st.session_state.pop("editando_partido", None)
                st.rerun()
        else:
            if st.button("⚠️ Confirmar borrado", use_container_width=True, type="primary"):
                if db.delete_match(partido["id"]):
                    st.session_state.pop("confirmar_eliminar_partido", None)
                    st.success("Partido eliminado.")
                    st.rerun()
                else:
                    st.error("No se pudo eliminar el partido.")

    # Aviso de confirmación
    if confirmando_borrar:
        st.warning(f"¿Seguro que quieres eliminar el partido contra **{partido['Rival']}** del {partido['Fecha']}? Esta acción no se puede deshacer.")
        if st.button("↩️ Cancelar"):
            st.session_state.pop("confirmar_eliminar_partido", None)
            st.rerun()

    if not editando:
        # C1: Ficha visual del partido
        goleadores = df_detalle[df_detalle["GOL"] > 0][["JUGADOR", "GOL"]].sort_values("GOL", ascending=False)
        asistentes = df_detalle[df_detalle["ASIST"] > 0][["JUGADOR", "ASIST"]].sort_values("ASIST", ascending=False)

        col_gol, col_asist = st.columns(2)
        with col_gol:
            st.markdown("**⚽ Goleadores**")
            if goleadores.empty:
                st.caption("Sin goles propios en este partido.")
            else:
                for _, row in goleadores.iterrows():
                    st.write(f"{'⚽' * int(row['GOL'])} {row['JUGADOR']}")
        with col_asist:
            st.markdown("**🎯 Asistencias**")
            if asistentes.empty:
                st.caption("Sin asistencias registradas.")
            else:
                for _, row in asistentes.iterrows():
                    st.write(f"{'🎯' * int(row['ASIST'])} {row['JUGADOR']}")

        # D3: Tarjetas
        df_tarjetas = df_detalle[
            (df_detalle["CONVOCADO"] == "SÍ") &
            ((df_detalle["AMARILLAS"] > 0) | (df_detalle["ROJAS"] > 0))
        ][["JUGADOR", "AMARILLAS", "ROJAS"]]
        if not df_tarjetas.empty:
            st.markdown("**🟨 Tarjetas**")
            for _, row in df_tarjetas.iterrows():
                badges = "🟨" * int(row["AMARILLAS"]) + "🟥" * int(row["ROJAS"])
                st.write(f"{badges} {row['JUGADOR']}")

        st.markdown("**⏱️ Minutos jugados**")
        df_min = df_detalle[df_detalle["CONVOCADO"] == "SÍ"][
            ["JUGADOR", "MINUTOS 1a PARTE", "MINUTOS 2a PARTE"]
        ].copy()
        df_min["TOTAL"] = df_min["MINUTOS 1a PARTE"] + df_min["MINUTOS 2a PARTE"]
        st.dataframe(
            df_min,
            column_config={
                "TOTAL": st.column_config.ProgressColumn(
                    "Total minutos",
                    min_value=0,
                    max_value=equipo["minutos_partido"],
                    format="%d min",
                )
            },
            hide_index=True,
            width="stretch",
        )

        with st.expander("📋 Tabla completa de estadísticas"):
            st.dataframe(df_detalle, width="stretch")
    else:
        st.warning("Estás editando este partido. Modifica los datos y pulsa Guardar.")
        notas_edit = st.text_area("📝 Notas del partido", value=match_data.get("notes", ""))

        # F6: editar MVP
        convocados_edit = [r["JUGADOR"] for _, r in df_detalle.iterrows() if r["CONVOCADO"] == "SÍ"]
        opciones_mvp_edit = ["— Sin MVP —"] + convocados_edit
        nombre_mvp_actual = next(
            (s["players"]["name"] for s in stats_data
             if s.get("players") and s["player_id"] == match_data.get("mvp_player_id")),
            None,
        )
        idx_mvp = (opciones_mvp_edit.index(nombre_mvp_actual)
                   if nombre_mvp_actual in opciones_mvp_edit else 0)
        mvp_edit = st.selectbox("🌟 MVP del partido", options=opciones_mvp_edit, index=idx_mvp)

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
                    "amarillas":   int(row["AMARILLAS"]),
                    "rojas":       int(row["ROJAS"]),
                }
                for _, row in df_edit.iterrows()
            ]
            mvp_id_edit = (player_ids_map.get(mvp_edit)
                           if mvp_edit and mvp_edit != "— Sin MVP —" else None)
            ok = db.update_match(
                match_id=partido["id"],
                rival=match_data["rival"],
                match_date=datetime.strptime(match_data["match_date"], "%Y-%m-%d").date(),
                is_home=match_data["is_home"],
                goals_for=match_data["goals_for"],
                goals_against=match_data["goals_against"],
                stats=stats_upd,
                notes=notas_edit.strip(),
                mvp_player_id=mvp_id_edit,
            )
            if ok:
                st.success("✅ Partido guardado correctamente.")
                st.session_state.pop("editando_partido", None)
                st.rerun()
            else:
                st.error("❌ No se pudo guardar.")


POSICIONES = [
    "Portero", "Defensa Central", "Lateral Derecho", "Lateral Izquierdo",
    "Centrocampista", "Banda Derecha", "Banda Izquierda", "Mediapunta", "Delantero",
]


def page_plantilla():
    equipo = get_equipo()
    st.header("👥 Plantilla")
    st.markdown(f"Gestiona los jugadores de **{equipo['name']}**.")

    players = db.list_players(equipo["id"])

    with st.form("form_añadir_jugador", clear_on_submit=True):
        nuevo = st.text_input("Nombre del nuevo jugador")
        posicion_nueva = st.selectbox("Posición primaria", options=["— Sin asignar —"] + POSICIONES)
        alt_nuevas = st.multiselect(
            "Posiciones alternativas (opcional)",
            options=[p for p in POSICIONES if p != posicion_nueva],
        )
        if st.form_submit_button("➕ Añadir jugador"):
            nuevo = nuevo.strip()
            nombres_actuales = [p["name"] for p in players]
            if not nuevo:
                st.error("❌ El nombre no puede estar vacío.")
            elif nuevo in nombres_actuales:
                st.warning(f"⚠️ '{nuevo}' ya está en la plantilla.")
            else:
                pos = "" if posicion_nueva == "— Sin asignar —" else posicion_nueva
                result = db.add_player(equipo["id"], nuevo, pos, alt_nuevas)
                if result:
                    st.success(f"✅ '{nuevo}' añadido a la plantilla.")
                    st.rerun()
                else:
                    st.error("No se pudo añadir el jugador.")

    st.divider()

    if not players:
        st.info("La plantilla está vacía. Añade jugadores usando el formulario de arriba.")
    else:
        st.subheader(f"Jugadores en plantilla ({len(players)})")

        # F3: distintivos top X
        df_stats, _ = db.get_team_aggregates(equipo["id"], equipo["minutos_partido"])
        distintivos = calcular_distintivos(df_stats)
        if distintivos:
            st.caption("🥇 max goleador · 🎯 max asistente · ⏱️ más minutos")

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
            col_nombre, col_pos, col_edit_pos, col_btn = st.columns([4, 3, 1, 1])
            pos_primaria = jugador.get("position", "") or "—"
            alts = jugador.get("alt_positions") or []
            badge = distintivos.get(jugador["name"], "")
            col_nombre.write(f"{jugador['name']} {badge}".rstrip())
            col_pos.caption(
                f"{pos_primaria}" + (f"  ·  alt: {', '.join(alts)}" if alts else "")
            )

            edit_pos_key = f"editando_pos_{jugador['id']}"
            if col_edit_pos.button("✏️", key=f"btn_editpos_{jugador['id']}", help="Editar posiciones"):
                st.session_state[edit_pos_key] = True
                st.rerun()
            if col_btn.button("🗑️", key=f"del_{jugador['id']}", help=f"Dar de baja a {jugador['name']}"):
                st.session_state[eliminar_key] = jugador
                st.rerun()

            if st.session_state.get(edit_pos_key):
                opciones_primaria = ["— Sin asignar —"] + POSICIONES
                pos_actual = jugador.get("position", "")
                pos_idx = opciones_primaria.index(pos_actual) if pos_actual in opciones_primaria else 0
                nueva_pos = st.selectbox(
                    f"Posición primaria de {jugador['name']}",
                    options=opciones_primaria,
                    index=pos_idx,
                    key=f"sel_pos_{jugador['id']}",
                )
                nuevas_alts = st.multiselect(
                    "Posiciones alternativas",
                    options=[p for p in POSICIONES if p != nueva_pos],
                    default=[a for a in alts if a in POSICIONES and a != nueva_pos],
                    key=f"sel_alts_{jugador['id']}",
                )
                c_save, c_cancel = st.columns(2)
                if c_save.button("💾 Guardar", key=f"save_pos_{jugador['id']}"):
                    pos = "" if nueva_pos == "— Sin asignar —" else nueva_pos
                    db.update_player_positions(jugador["id"], pos, nuevas_alts)
                    st.session_state.pop(edit_pos_key, None)
                    st.rerun()
                if c_cancel.button("✗ Cancelar", key=f"cancel_pos_{jugador['id']}"):
                    st.session_state.pop(edit_pos_key, None)
                    st.rerun()

    # Jugadores dados de baja (A3)
    st.divider()
    bajas = [p for p in db.list_players(equipo["id"], only_active=False) if not p["active"]]
    if bajas:
        with st.expander(f"👤 Jugadores dados de baja ({len(bajas)})"):
            reactivar_key = "confirmar_reactivar"
            jugador_a_reactivar = st.session_state.get(reactivar_key)

            if jugador_a_reactivar:
                nombre_reac = jugador_a_reactivar["name"]
                st.info(f"¿Reactivar a **{nombre_reac}**? Volverá a aparecer en la plantilla.")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Sí, reactivar"):
                        db.activate_player(jugador_a_reactivar["id"])
                        st.session_state.pop(reactivar_key, None)
                        st.success(f"'{nombre_reac}' reactivado.")
                        st.rerun()
                with c2:
                    if st.button("❌ Cancelar", key="cancel_reactivar"):
                        st.session_state.pop(reactivar_key, None)
                        st.rerun()

            for jugador in bajas:
                col_nombre, col_btn = st.columns([5, 1])
                col_nombre.write(jugador["name"])
                if col_btn.button("↩️", key=f"react_{jugador['id']}", help=f"Reactivar a {jugador['name']}"):
                    st.session_state[reactivar_key] = jugador
                    st.rerun()


def page_config():
    """A4 + B1: Configuración del equipo y visibilidad pública."""
    equipo = get_equipo()
    st.header("⚙️ Configuración del equipo")

    with st.form("form_config_equipo"):
        nombre = st.text_input("Nombre del equipo", value=equipo.get("name", ""))
        categoria = st.text_input("Categoría", value=equipo.get("category", ""))
        max_titulares = st.number_input(
            "Titulares por partido",
            min_value=5, max_value=11,
            value=equipo.get("max_titulares", 8),
        )
        minutos_partido = st.number_input(
            "Minutos por partido",
            min_value=20, max_value=90,
            value=equipo.get("minutos_partido", 50),
        )
        publico = st.toggle(
            "Hacer el equipo público (visible para padres sin login)",
            value=bool(equipo.get("public", False)),
            help="Los padres podrán ver las estadísticas desde un enlace directo sin necesidad de cuenta.",
        )
        guardado = st.form_submit_button("💾 Guardar cambios")

    if guardado:
        nombre = nombre.strip()
        if not nombre:
            st.error("❌ El nombre no puede estar vacío.")
        else:
            ok = db.update_team(
                equipo["id"],
                name=nombre,
                category=categoria.strip(),
                max_titulares=int(max_titulares),
                minutos_partido=int(minutos_partido),
                public=publico,
            )
            if ok:
                st.session_state["current_team"] = {
                    **equipo,
                    "name": nombre,
                    "category": categoria.strip(),
                    "max_titulares": int(max_titulares),
                    "minutos_partido": int(minutos_partido),
                    "public": publico,
                }
                st.success("✅ Configuración guardada.")
                st.rerun()
            else:
                st.error("❌ No se pudo guardar la configuración.")

    # B1: URL pública compartible
    if equipo.get("public"):
        base_url = st.secrets.get("app_url", "https://proyecto-gestion-estadisticas-futbol.streamlit.app")
        share_url = f"{base_url}?team={equipo['id']}"
        st.divider()
        st.subheader("🔗 Enlace para padres")
        st.success("El equipo es visible públicamente. Comparte esta URL:")
        st.code(share_url, language=None)


def page_publica(equipo: dict):
    """B1: Vista de solo lectura para padres (sin autenticación)."""
    st.title(f"⚽ {equipo['name']} — {equipo['category']}")
    st.caption("Vista pública · Solo lectura")
    st.divider()

    tab_g, tab_i, tab_h = st.tabs(["📊 General", "🪄 Individuales", "📜 Histórico"])

    with tab_g:
        df, totales = db.get_team_aggregates(equipo["id"], equipo["minutos_partido"])
        partidos_raw = db.list_matches(equipo["id"])
        if df.empty:
            st.info("No hay datos disponibles.")
        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Partidos", totales["total_partidos"])
            c2.metric("Goles a favor", totales["total_goles"])
            c3.metric("Goles en contra", totales["total_goles_contra"])
            c4.metric("Asistencias", totales["total_asist"])

            if partidos_raw:
                tipo_racha, n_racha = calcular_racha(partidos_raw)
                p_mejor = mejor_resultado(partidos_raw)
                p_goles = partido_mas_goles(partidos_raw)

                def _fmt(p: dict) -> str:
                    gf, gc = p["goals_for"], p["goals_against"]
                    return (f"{equipo['name']} {gf}-{gc} {p['rival']}"
                            if p["is_home"] else f"{p['rival']} {gc}-{gf} {equipo['name']}")

                st.subheader("🏆 Récords de la temporada")
                icono = {"Victoria": "✅", "Empate": "➖", "Derrota": "❌"}.get(tipo_racha, "")
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Racha actual", f"{icono} {n_racha} {tipo_racha.lower()}")
                rc2.metric("Mejor resultado", _fmt(p_mejor), p_mejor["match_date"])
                rc3.metric("Partido más goleador", _fmt(p_goles), p_goles["match_date"])

            st.subheader("📈 Estadísticas acumuladas por jugador")
            st.dataframe(df, width="stretch")
            st.subheader("⏱️ % de minutos por jugador")
            st.bar_chart(df.set_index("JUGADOR")[["% MINUTOS"]].sort_values("% MINUTOS"))

    with tab_i:
        df, totales = db.get_team_aggregates(equipo["id"], equipo["minutos_partido"])
        if df.empty:
            st.info("No hay datos disponibles.")
        else:
            jugadores = df["JUGADOR"].dropna().astype(str).tolist()
            sel = st.multiselect("Selecciona jugador(es):", options=jugadores, default=jugadores,
                                 key="pub_multiselect")
            if sel:
                df_sel = df[df["JUGADOR"].isin(sel)]
                cols_ind = [c for c in columnas_datos_individuales if c in df.columns]
                st.dataframe(df_sel[["JUGADOR"] + cols_ind], width="stretch")
            df_extra = metricas_extra(df, totales["total_partidos"])
            sel_rank = st.multiselect("🏆 Mostrar rankings", options=opciones_ranking, key="pub_ranking")
            if sel_rank:
                for i in range(0, len(sel_rank), 3):
                    cols = st.columns(min(len(sel_rank) - i, 3))
                    for j, col in enumerate(cols):
                        if i + j < len(sel_rank):
                            metrica = sel_rank[i + j]
                            col.markdown(f"🏅 {metrica}")
                            col.dataframe(ranking(df_extra, metrica), width="stretch")

    with tab_h:
        partidos = db.list_matches(equipo["id"])
        if not partidos:
            st.info("No hay partidos registrados.")
        else:
            resumen_pub = []
            for p in partidos:
                gf, gc = p["goals_for"], p["goals_against"]
                resultado = "✅ Victoria" if gf > gc else ("➖ Empate" if gf == gc else "❌ Derrota")
                marcador = (f"{equipo['name']} {gf} - {gc} {p['rival']}"
                            if p["is_home"] else f"{p['rival']} {gc} - {gf} {equipo['name']}")
                resumen_pub.append({"id": p["id"], "Fecha": p["match_date"],
                                    "Rival": p["rival"], "Resultado": resultado, "Marcador": marcador})
            st.dataframe(
                pd.DataFrame(resumen_pub)[["Fecha", "Rival", "Resultado", "Marcador"]],
                width="stretch",
            )
            if len(partidos) > 1:
                st.subheader("📈 Evolución de goles")
                df_evol = pd.DataFrame([
                    {"Partido": f"{p['match_date']} vs {p['rival']}",
                     "Goles a favor": p["goals_for"], "Goles en contra": p["goals_against"]}
                    for p in reversed(partidos)
                ]).set_index("Partido")
                st.line_chart(df_evol)
            opciones_pub = [f"{r['Fecha']} - {r['Rival']}" for r in resumen_pub]
            sel_partido = st.selectbox("🔍 Ver detalles de un partido", opciones_pub, index=None,
                                       key="pub_selectbox")
            if sel_partido:
                partido_pub = resumen_pub[opciones_pub.index(sel_partido)]
                match_data, stats_data = db.get_match(partido_pub["id"])
                if match_data:
                    st.markdown(f"### {partido_pub['Marcador']}")
                    filas_pub = []
                    for s in stats_data:
                        nombre = s["players"]["name"] if s.get("players") else s["player_id"]
                        filas_pub.append({
                            "JUGADOR": nombre,
                            "GOL": s["goles"], "ASIST": s["asistencias"],
                            "MINUTOS 1a PARTE": s["minutos_1a"], "MINUTOS 2a PARTE": s["minutos_2a"],
                        })
                    df_det = pd.DataFrame(filas_pub)
                    goleadores_p = df_det[df_det["GOL"] > 0].sort_values("GOL", ascending=False)
                    asistentes_p = df_det[df_det["ASIST"] > 0].sort_values("ASIST", ascending=False)
                    cg, ca = st.columns(2)
                    with cg:
                        st.markdown("**⚽ Goleadores**")
                        if goleadores_p.empty:
                            st.caption("Sin goles")
                        else:
                            for _, row in goleadores_p.iterrows():
                                st.write(f"{'⚽' * int(row['GOL'])} {row['JUGADOR']}")
                    with ca:
                        st.markdown("**🎯 Asistencias**")
                        if asistentes_p.empty:
                            st.caption("Sin asistencias")
                        else:
                            for _, row in asistentes_p.iterrows():
                                st.write(f"{'🎯' * int(row['ASIST'])} {row['JUGADOR']}")
                    with st.expander("📋 Estadísticas completas"):
                        st.dataframe(df_det, width="stretch")


# ── Main ──────────────────────────────────────────────────────────────────────

# B1: Vista pública para padres (sin login)
_team_param = st.query_params.get("team")
if _team_param and not db.current_user():
    _equipo_pub = db.get_public_team(_team_param)
    if _equipo_pub:
        page_publica(_equipo_pub)
    else:
        st.error("Este equipo no existe o no está habilitado para vista pública.")
        st.info("Si eres el entrenador, inicia sesión para acceder.")
        mostrar_login()
    st.stop()

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
        st.Page(page_config, title="Configuración", icon="⚙️"),
    ],
})
pg.run()
