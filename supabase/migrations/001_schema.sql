-- ====================================================================
-- 001_schema.sql
-- Esquema inicial: equipos, plantilla, partidos y estadísticas
-- Ejecutar en el SQL Editor de Supabase (una sola vez)
-- ====================================================================

-- ── Tablas ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS teams (
  id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  owner_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  name             TEXT NOT NULL,
  category         TEXT NOT NULL DEFAULT '',
  max_titulares    INT  NOT NULL DEFAULT 8,
  minutos_partido  INT  NOT NULL DEFAULT 50,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS players (
  id         UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  team_id    UUID REFERENCES teams(id) ON DELETE CASCADE NOT NULL,
  name       TEXT NOT NULL,
  active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS matches (
  id             UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  team_id        UUID REFERENCES teams(id) ON DELETE CASCADE NOT NULL,
  rival          TEXT NOT NULL,
  match_date     DATE NOT NULL,
  is_home        BOOLEAN NOT NULL DEFAULT TRUE,
  goals_for      INT NOT NULL DEFAULT 0,
  goals_against  INT NOT NULL DEFAULT 0,
  created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS match_stats (
  id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  match_id     UUID REFERENCES matches(id) ON DELETE CASCADE NOT NULL,
  player_id    UUID REFERENCES players(id) ON DELETE CASCADE NOT NULL,
  convocado    BOOLEAN NOT NULL DEFAULT FALSE,
  titular      BOOLEAN NOT NULL DEFAULT FALSE,
  suplente     BOOLEAN NOT NULL DEFAULT FALSE,
  goles        INT NOT NULL DEFAULT 0,
  asistencias  INT NOT NULL DEFAULT 0,
  minutos_1a   INT NOT NULL DEFAULT 0,
  minutos_2a   INT NOT NULL DEFAULT 0,
  UNIQUE(match_id, player_id)
);

-- ── Row Level Security ────────────────────────────────────────────────────────

ALTER TABLE teams       ENABLE ROW LEVEL SECURITY;
ALTER TABLE players     ENABLE ROW LEVEL SECURITY;
ALTER TABLE matches     ENABLE ROW LEVEL SECURITY;
ALTER TABLE match_stats ENABLE ROW LEVEL SECURITY;

-- Solo el propietario del equipo puede ver y modificar sus datos
CREATE POLICY "propietario_equipos" ON teams
  FOR ALL USING (owner_id = auth.uid());

CREATE POLICY "propietario_jugadores" ON players
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM teams
      WHERE teams.id = players.team_id
        AND teams.owner_id = auth.uid()
    )
  );

CREATE POLICY "propietario_partidos" ON matches
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM teams
      WHERE teams.id = matches.team_id
        AND teams.owner_id = auth.uid()
    )
  );

CREATE POLICY "propietario_estadisticas" ON match_stats
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM matches
      JOIN teams ON teams.id = matches.team_id
      WHERE matches.id = match_stats.match_id
        AND teams.owner_id = auth.uid()
    )
  );

-- ── Función de acumulado por equipo ──────────────────────────────────────────
-- Se llama con: SELECT * FROM get_team_aggregates('<team_id>');
-- SECURITY INVOKER garantiza que respeta el RLS del usuario autenticado.

CREATE OR REPLACE FUNCTION get_team_aggregates(p_team_id UUID)
RETURNS TABLE (
  player_id  UUID,
  jugador    TEXT,
  convocado  BIGINT,
  titular    BIGINT,
  suplente   BIGINT,
  gol        BIGINT,
  asist      BIGINT,
  minutos_1a BIGINT,
  minutos_2a BIGINT,
  total_min  BIGINT
)
SECURITY INVOKER
STABLE
LANGUAGE sql
AS $$
  SELECT
    p.id,
    p.name,
    COUNT(ms.id) FILTER (WHERE ms.convocado = TRUE),
    COUNT(ms.id) FILTER (WHERE ms.titular  = TRUE),
    COUNT(ms.id) FILTER (WHERE ms.suplente = TRUE),
    COALESCE(SUM(CASE WHEN ms.goles > 0 THEN ms.goles ELSE 0 END), 0),
    COALESCE(SUM(ms.asistencias), 0),
    COALESCE(SUM(ms.minutos_1a),  0),
    COALESCE(SUM(ms.minutos_2a),  0),
    COALESCE(SUM(ms.minutos_1a + ms.minutos_2a), 0)
  FROM players p
  LEFT JOIN match_stats ms ON ms.player_id = p.id
  LEFT JOIN matches m      ON m.id = ms.match_id AND m.team_id = p_team_id
  WHERE p.team_id = p_team_id
    AND p.active  = TRUE
  GROUP BY p.id, p.name
  ORDER BY p.name;
$$;
