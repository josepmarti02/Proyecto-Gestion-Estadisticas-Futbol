import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date
from typing import Optional


# ── Conexión ──────────────────────────────────────────────────────────────────

def get_client() -> Client:
    """Crea un cliente Supabase y restaura la sesión activa si la hay."""
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    client = create_client(url, key)
    tokens = st.session_state.get("_sb_tokens")
    if tokens:
        try:
            client.auth.set_session(tokens["access_token"], tokens["refresh_token"])
            # Propagar el token JWT al cliente PostgREST para que RLS funcione
            client.postgrest.auth(tokens["access_token"])
        except Exception:
            st.session_state.pop("_sb_tokens", None)
            st.session_state.pop("_sb_user", None)
    return client


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_public_team(team_id: str) -> Optional[dict]:
    """Lee un equipo marcado como público sin autenticación."""
    try:
        client = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
        res = (
            client.table("teams")
            .select("*")
            .eq("id", team_id)
            .eq("public", True)
            .single()
            .execute()
        )
        return res.data
    except Exception:
        return None


def sign_in(email: str, password: str) -> tuple[bool, str]:
    """Inicia sesión. Devuelve (éxito, mensaje_error)."""
    try:
        client = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
        res = client.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state["_sb_tokens"] = {
            "access_token": res.session.access_token,
            "refresh_token": res.session.refresh_token,
        }
        st.session_state["_sb_user"] = {"id": res.user.id, "email": res.user.email}
        return True, ""
    except Exception as e:
        return False, str(e)


def sign_up(email: str, password: str) -> tuple[bool, str]:
    """Registra un nuevo usuario. Devuelve (éxito, mensaje)."""
    try:
        client = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
        res = client.auth.sign_up({"email": email, "password": password})
        if res.user:
            return True, "Cuenta creada. Inicia sesión para continuar."
        return False, "No se pudo crear la cuenta."
    except Exception as e:
        return False, str(e)


def sign_out() -> None:
    """Cierra sesión y limpia el estado de la sesión."""
    try:
        get_client().auth.sign_out()
    except Exception:
        pass
    for k in ["_sb_tokens", "_sb_user", "current_team_id", "current_team"]:
        st.session_state.pop(k, None)


def current_user() -> Optional[dict]:
    """Devuelve el usuario autenticado o None."""
    return st.session_state.get("_sb_user")


# ── Equipos ───────────────────────────────────────────────────────────────────

def list_teams() -> list[dict]:
    """Lista todos los equipos del usuario autenticado."""
    try:
        res = get_client().table("teams").select("*").order("created_at").execute()
        return res.data or []
    except Exception:
        return []


def create_team(name: str, category: str, max_titulares: int = 8, minutos_partido: int = 50) -> Optional[dict]:
    """Crea un equipo nuevo para el usuario actual."""
    user = current_user()
    if not user:
        st.error("Error al crear equipo: no hay usuario autenticado en sesión.")
        return None
    try:
        res = get_client().table("teams").insert({
            "owner_id": user["id"],
            "name": name,
            "category": category,
            "max_titulares": max_titulares,
            "minutos_partido": minutos_partido,
        }).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        st.error(f"Error al crear equipo: {e}")
        return None


def update_team(team_id: str, **fields) -> bool:
    """Actualiza campos de un equipo (name, category, max_titulares, minutos_partido)."""
    try:
        get_client().table("teams").update(fields).eq("id", team_id).execute()
        return True
    except Exception:
        return False


# ── Plantilla ─────────────────────────────────────────────────────────────────

def list_players(team_id: str, only_active: bool = True) -> list[dict]:
    """Lista los jugadores de un equipo ordenados por nombre."""
    try:
        q = get_client().table("players").select("*").eq("team_id", team_id).order("name")
        if only_active:
            q = q.eq("active", True)
        return q.execute().data or []
    except Exception:
        return []


def add_player(team_id: str, name: str, position: str = "",
               alt_positions: Optional[list[str]] = None) -> Optional[dict]:
    """Añade un jugador a la plantilla con posición primaria y alternativas."""
    try:
        res = get_client().table("players").insert({
            "team_id": team_id,
            "name": name,
            "position": position,
            "alt_positions": alt_positions or [],
        }).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None


def update_player_positions(player_id: str, position: str,
                            alt_positions: Optional[list[str]] = None) -> bool:
    """Actualiza la posición primaria y las alternativas de un jugador."""
    try:
        get_client().table("players").update({
            "position": position,
            "alt_positions": alt_positions or [],
        }).eq("id", player_id).execute()
        return True
    except Exception:
        return False


def update_player_status(player_id: str, status: str) -> bool:
    """Actualiza el estado del jugador: 'disponible', 'lesionado' o 'sancionado'."""
    try:
        get_client().table("players").update({"status": status}).eq("id", player_id).execute()
        return True
    except Exception:
        return False


def deactivate_player(player_id: str) -> bool:
    """Da de baja a un jugador conservando su histórico de partidos."""
    try:
        get_client().table("players").update({"active": False}).eq("id", player_id).execute()
        return True
    except Exception:
        return False


def activate_player(player_id: str) -> bool:
    """Reactiva un jugador dado de baja."""
    try:
        get_client().table("players").update({"active": True}).eq("id", player_id).execute()
        return True
    except Exception:
        return False


def rename_player(player_id: str, new_name: str) -> bool:
    """Renombra un jugador."""
    try:
        get_client().table("players").update({"name": new_name}).eq("id", player_id).execute()
        return True
    except Exception:
        return False


# ── Partidos ──────────────────────────────────────────────────────────────────

def list_matches(team_id: str) -> list[dict]:
    """Lista los partidos de un equipo, del más reciente al más antiguo."""
    try:
        res = (
            get_client()
            .table("matches")
            .select("*")
            .eq("team_id", team_id)
            .order("match_date", desc=True)
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def get_match(match_id: str) -> tuple[Optional[dict], list[dict]]:
    """Devuelve la cabecera del partido y la lista de estadísticas de jugadores."""
    try:
        client = get_client()
        match = client.table("matches").select("*").eq("id", match_id).single().execute()
        stats = (
            client.table("match_stats")
            .select("*, players(name)")
            .eq("match_id", match_id)
            .execute()
        )
        return match.data, stats.data or []
    except Exception:
        return None, []


def create_match(
    team_id: str,
    rival: str,
    match_date: date,
    is_home: bool,
    goals_for: int,
    goals_against: int,
    stats: list[dict],
    notes: str = "",
    mvp_player_ids: Optional[list[str]] = None,
) -> Optional[dict]:
    """
    Crea un partido completo con sus estadísticas de jugadores.
    stats: lista de dicts con keys player_id, convocado, titular, suplente,
           goles, asistencias, minutos_1a, minutos_2a, amarillas, rojas,
           y opcionalmente position_played.
    mvp_player_ids: lista de hasta 3 UUIDs de jugadores MVP.
    """
    try:
        client = get_client()
        match_res = client.table("matches").insert({
            "team_id": team_id,
            "rival": rival,
            "match_date": match_date.isoformat(),
            "is_home": is_home,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "notes": notes,
            "mvp_player_ids": mvp_player_ids or [],
        }).execute()
        if not match_res.data:
            return None
        match_id = match_res.data[0]["id"]
        client.table("match_stats").insert(
            [{"match_id": match_id, **s} for s in stats]
        ).execute()
        return match_res.data[0]
    except Exception:
        return None


def update_match(
    match_id: str,
    rival: str,
    match_date: date,
    is_home: bool,
    goals_for: int,
    goals_against: int,
    stats: list[dict],
    notes: str = "",
    mvp_player_ids: Optional[list[str]] = None,
) -> bool:
    """Actualiza la cabecera y reemplaza las estadísticas de un partido."""
    try:
        client = get_client()
        client.table("matches").update({
            "rival": rival,
            "match_date": match_date.isoformat(),
            "is_home": is_home,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "notes": notes,
            "mvp_player_ids": mvp_player_ids or [],
        }).eq("id", match_id).execute()
        client.table("match_stats").delete().eq("match_id", match_id).execute()
        client.table("match_stats").insert(
            [{"match_id": match_id, **s} for s in stats]
        ).execute()
        return True
    except Exception:
        return False


def delete_match(match_id: str) -> bool:
    """Elimina un partido y sus estadísticas (ON DELETE CASCADE)."""
    try:
        get_client().table("matches").delete().eq("id", match_id).execute()
        return True
    except Exception:
        return False


# ── Acumulado ─────────────────────────────────────────────────────────────────

_COLUMNAS_ACUMULADO = [
    "JUGADOR",
    "CONVOCADO", "% CONVOCADO", "TITULAR", "% TITULAR", "SUPLENTE", "% SUPLENTE",
    "GOL", "% GOLES", "ASIST", "% ASIST",
    "AMARILLAS", "ROJAS",
    "MINUTOS 1a PARTE", "MINUTOS 2a PARTE", "TOTAL MINUTOS JUGADOS",
    "POSIBLES MINUTOS", "% MINUTOS",
    "PRODUCTIVIDAD OFENSIVA", "EFICIENCIA GOLEADORA",
    "MVPs",
]


def _post_process_aggregates(df: pd.DataFrame, total_partidos: int,
                             minutos_partido: int) -> tuple[pd.DataFrame, dict]:
    """Recibe un df con columnas crudas (jugador, convocado, titular, ...) y aplica
    los porcentajes y renames. Devuelve (df_renombrado, totales_dict)."""
    total_goles   = int(df["gol"].clip(lower=0).sum())
    total_asist   = int(df["asist"].sum())
    total_minutos = int(df["total_min"].sum())

    totales = {
        "total_partidos":   total_partidos,
        "total_goles":      total_goles,
        "total_asist":      total_asist,
        "total_minutos":    total_minutos,
    }

    df["% CONVOCADO"] = (df["convocado"] / total_partidos * 100).round(1) if total_partidos else 0.0
    df["% TITULAR"]   = (df["titular"]  / df["convocado"].replace(0, pd.NA) * 100).fillna(0).round(1)
    df["% SUPLENTE"]  = (df["suplente"] / df["convocado"].replace(0, pd.NA) * 100).fillna(0).round(1)
    df["% GOLES"]     = (df["gol"]   / total_goles * 100).round(1) if total_goles else 0.0
    df["% ASIST"]     = (df["asist"] / total_asist * 100).round(1) if total_asist else 0.0
    posibles = df["convocado"] * minutos_partido
    df["POSIBLES MINUTOS"]      = posibles
    df["% MINUTOS"]             = (df["total_min"] / posibles.replace(0, pd.NA) * 100).fillna(0).round(1)
    df["PRODUCTIVIDAD OFENSIVA"] = df["gol"] + df["asist"]
    df["EFICIENCIA GOLEADORA"]   = (df["gol"] / total_partidos).round(2) if total_partidos else 0.0

    df = df.rename(columns={
        "jugador":    "JUGADOR",
        "convocado":  "CONVOCADO",
        "titular":    "TITULAR",
        "suplente":   "SUPLENTE",
        "gol":        "GOL",
        "asist":      "ASIST",
        "minutos_1a": "MINUTOS 1a PARTE",
        "minutos_2a": "MINUTOS 2a PARTE",
        "total_min":  "TOTAL MINUTOS JUGADOS",
        "amarillas":  "AMARILLAS",
        "rojas":      "ROJAS",
        "mvps":       "MVPs",
    })
    return df[[c for c in _COLUMNAS_ACUMULADO if c in df.columns]], totales


def _aggregate_from_matches(team_id: str, partidos: list[dict]) -> Optional[pd.DataFrame]:
    """Agrega match_stats en Python para un subconjunto de partidos. Devuelve
    DataFrame con las columnas crudas (jugador, convocado, titular, ...).
    Incluye TODOS los jugadores activos del equipo aunque no hayan jugado."""
    client = get_client()
    players_res = (client.table("players").select("id, name")
                   .eq("team_id", team_id).eq("active", True)
                   .order("name").execute())
    jugadores = players_res.data or []
    if not jugadores:
        return pd.DataFrame()

    base = {p["id"]: {
        "player_id": p["id"], "jugador": p["name"],
        "convocado": 0, "titular": 0, "suplente": 0,
        "gol": 0, "asist": 0,
        "minutos_1a": 0, "minutos_2a": 0, "total_min": 0,
        "amarillas": 0, "rojas": 0,
    } for p in jugadores}

    if partidos:
        match_ids = [p["id"] for p in partidos]
        stats_res = (client.table("match_stats")
                     .select("player_id, convocado, titular, suplente, goles, asistencias, "
                             "minutos_1a, minutos_2a, amarillas, rojas")
                     .in_("match_id", match_ids).execute())
        for s in (stats_res.data or []):
            row = base.get(s["player_id"])
            if not row:
                continue
            row["convocado"]  += 1 if s["convocado"] else 0
            row["titular"]    += 1 if s["titular"]   else 0
            row["suplente"]   += 1 if s["suplente"]  else 0
            row["gol"]        += max(s["goles"] or 0, 0)
            row["asist"]      += s["asistencias"] or 0
            row["minutos_1a"] += s["minutos_1a"] or 0
            row["minutos_2a"] += s["minutos_2a"] or 0
            row["total_min"]  += (s["minutos_1a"] or 0) + (s["minutos_2a"] or 0)
            row["amarillas"]  += s.get("amarillas") or 0
            row["rojas"]      += s.get("rojas") or 0

    return pd.DataFrame(list(base.values()))


def get_team_aggregates(team_id: str, minutos_partido: int,
                        last_n_matches: Optional[int] = None,
                        since_date: Optional[date] = None) -> tuple[pd.DataFrame, dict]:
    """
    Devuelve (df_jugadores, totales_equipo).
    Si last_n_matches o since_date están definidos, agrega solo sobre esos partidos.
    """
    _vacio = {"total_partidos": 0, "total_goles": 0, "total_asist": 0,
              "total_minutos": 0, "total_goles_contra": 0}
    try:
        partidos = list_matches(team_id)
        # Filtros temporales (F4)
        if since_date is not None:
            partidos = [p for p in partidos if p["match_date"] >= since_date.isoformat()]
        if last_n_matches is not None:
            partidos = partidos[:last_n_matches]

        total_partidos = len(partidos)
        total_goles_contra = sum(m["goals_against"] for m in partidos)

        if last_n_matches is None and since_date is None:
            # Vía RPC para toda la temporada
            res = get_client().rpc("get_team_aggregates", {"p_team_id": team_id}).execute()
            if not res.data:
                return pd.DataFrame(), {**_vacio, "total_partidos": total_partidos,
                                        "total_goles_contra": total_goles_contra}
            df_raw = pd.DataFrame(res.data)
        else:
            # Agregación en Python sobre el subconjunto de partidos
            df_raw = _aggregate_from_matches(team_id, partidos)
            if df_raw is None or df_raw.empty:
                return pd.DataFrame(), {**_vacio, "total_partidos": total_partidos,
                                        "total_goles_contra": total_goles_contra}

        # Contar MVPs por jugador desde los partidos ya filtrados (respeta filtros temporales)
        mvp_count: dict[str, int] = {}
        for p in partidos:
            for pid in (p.get("mvp_player_ids") or []):
                mvp_count[pid] = mvp_count.get(pid, 0) + 1
        if "player_id" in df_raw.columns:
            df_raw["mvps"] = df_raw["player_id"].map(mvp_count).fillna(0).astype(int)
        else:
            df_raw["mvps"] = 0

        df, totales = _post_process_aggregates(df_raw, total_partidos, minutos_partido)
        totales["total_goles_contra"] = total_goles_contra
        return df, totales

    except Exception as e:
        st.error(f"Error al obtener acumulado: {e}")
        return pd.DataFrame(), _vacio


# ── Historial individual ───────────────────────────────────────────────────────

def get_player_history(player_id: str) -> list[dict]:
    """Historial de partidos de un jugador (solo convocados), ordenado por fecha."""
    try:
        res = (
            get_client()
            .table("match_stats")
            .select("goles, asistencias, amarillas, rojas, minutos_1a, minutos_2a, matches(match_date, rival)")
            .eq("player_id", player_id)
            .eq("convocado", True)
            .execute()
        )
        historial = []
        for row in (res.data or []):
            m = row.get("matches") or {}
            historial.append({
                "Fecha":       m.get("match_date", ""),
                "Rival":       m.get("rival", ""),
                "Minutos":     row["minutos_1a"] + row["minutos_2a"],
                "Goles":       row["goles"],
                "Asistencias": row["asistencias"],
                "Amarillas":   row.get("amarillas", 0),
                "Rojas":       row.get("rojas", 0),
            })
        historial.sort(key=lambda x: x["Fecha"])
        return historial
    except Exception:
        return []


# ── MVP ───────────────────────────────────────────────────────────────────────

def create_match_events(match_id: str, events: list[dict]) -> bool:
    """Guarda el log de eventos del partido en la tabla match_events."""
    if not events:
        return True
    try:
        client = get_client()
        rows = [{"match_id": match_id, **{k: v for k, v in e.items()
                 if k in ("event_type", "minuto", "player_id", "player_id2")}}
                for e in events]
        client.table("match_events").insert(rows).execute()
        return True
    except Exception:
        return False


def get_mvp_ranking(team_id: str) -> list[dict]:
    """Ranking de MVPs de la temporada: [{Jugador, MVPs}], ordenado desc."""
    try:
        client = get_client()
        # Fetch all matches with mvp_player_ids arrays
        matches_res = (
            client.table("matches")
            .select("mvp_player_ids")
            .eq("team_id", team_id)
            .execute()
        )
        # Count occurrences of each player_id across all arrays
        id_count: dict[str, int] = {}
        all_ids: list[str] = []
        for row in (matches_res.data or []):
            for pid in (row.get("mvp_player_ids") or []):
                id_count[pid] = id_count.get(pid, 0) + 1
                all_ids.append(pid)
        if not id_count:
            return []
        # Resolve names
        unique_ids = list(id_count.keys())
        players_res = (
            client.table("players")
            .select("id, name")
            .in_("id", unique_ids)
            .execute()
        )
        id_to_name = {p["id"]: p["name"] for p in (players_res.data or [])}
        ranking = [
            {"Jugador": id_to_name.get(pid, pid), "MVPs": cnt}
            for pid, cnt in id_count.items()
            if id_to_name.get(pid)
        ]
        ranking.sort(key=lambda x: x["MVPs"], reverse=True)
        return ranking
    except Exception:
        return []
