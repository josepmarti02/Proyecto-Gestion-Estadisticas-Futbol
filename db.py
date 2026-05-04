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
        except Exception:
            st.session_state.pop("_sb_tokens", None)
            st.session_state.pop("_sb_user", None)
    return client


# ── Auth ──────────────────────────────────────────────────────────────────────

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
    except Exception:
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


def add_player(team_id: str, name: str) -> Optional[dict]:
    """Añade un jugador a la plantilla."""
    try:
        res = get_client().table("players").insert({"team_id": team_id, "name": name}).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None


def deactivate_player(player_id: str) -> bool:
    """Da de baja a un jugador conservando su histórico de partidos."""
    try:
        get_client().table("players").update({"active": False}).eq("id", player_id).execute()
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
) -> Optional[dict]:
    """
    Crea un partido completo con sus estadísticas de jugadores.
    stats: lista de dicts con keys player_id, convocado, titular, suplente,
           goles, asistencias, minutos_1a, minutos_2a.
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

def get_team_aggregates(team_id: str, minutos_partido: int) -> pd.DataFrame:
    """
    Devuelve el DataFrame de estadísticas acumuladas por jugador.
    Usa la función SQL get_team_aggregates() y calcula los porcentajes en Python.
    Las columnas son compatibles con las funciones puras del código original
    (estadisticas_generales, ranking, metricas_extra).
    """
    try:
        res = get_client().rpc("get_team_aggregates", {"p_team_id": team_id}).execute()
        if not res.data:
            return pd.DataFrame()

        df = pd.DataFrame(res.data)
        total_partidos = len(list_matches(team_id))
        total_goles = int(df["gol"].clip(lower=0).sum())
        total_asist = int(df["asist"].sum())
        total_minutos = int(df["total_min"].sum())

        # Porcentajes
        df["% CONVOCADO"] = (df["convocado"] / total_partidos * 100).round(1) if total_partidos else 0.0
        df["% TITULAR"] = (df["titular"] / df["convocado"].replace(0, pd.NA) * 100).fillna(0).round(1)
        df["% SUPLENTE"] = (df["suplente"] / df["convocado"].replace(0, pd.NA) * 100).fillna(0).round(1)
        df["% GOLES"] = (df["gol"] / total_goles * 100).round(1) if total_goles else 0.0
        df["% ASIST"] = (df["asist"] / total_asist * 100).round(1) if total_asist else 0.0
        posibles = df["convocado"] * minutos_partido
        df["POSIBLES MINUTOS"] = posibles
        df["% MINUTOS"] = (df["total_min"] / posibles.replace(0, pd.NA) * 100).fillna(0).round(1)
        df["PRODUCTIVIDAD OFENSIVA"] = df["gol"] + df["asist"]
        df["EFICIENCIA GOLEADORA"] = (df["gol"] / df["convocado"].replace(0, pd.NA)).fillna(0).round(2)

        # Renombrar a los nombres que espera el resto de la app
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
        })

        # Columnas globales del equipo en la primera fila (igual que el código original)
        df.insert(0, "PARTIDOS", pd.NA)
        df.insert(1, "TOTAL GOLES", pd.NA)
        df.insert(2, "TOTAL ASIST", pd.NA)
        df.insert(3, "MINUTOS TOTALES", pd.NA)
        if not df.empty:
            df.loc[df.index[0], "PARTIDOS"] = total_partidos
            df.loc[df.index[0], "TOTAL GOLES"] = total_goles
            df.loc[df.index[0], "TOTAL ASIST"] = total_asist
            df.loc[df.index[0], "MINUTOS TOTALES"] = total_minutos

        columnas = [
            "JUGADOR", "PARTIDOS", "TOTAL GOLES", "TOTAL ASIST", "MINUTOS TOTALES",
            "CONVOCADO", "% CONVOCADO", "TITULAR", "% TITULAR", "SUPLENTE", "% SUPLENTE",
            "GOL", "% GOLES", "ASIST", "% ASIST",
            "MINUTOS 1a PARTE", "MINUTOS 2a PARTE", "TOTAL MINUTOS JUGADOS",
            "POSIBLES MINUTOS", "% MINUTOS",
            "PRODUCTIVIDAD OFENSIVA", "EFICIENCIA GOLEADORA",
        ]
        return df[[c for c in columnas if c in df.columns]]

    except Exception as e:
        st.error(f"Error al obtener acumulado: {e}")
        return pd.DataFrame()
