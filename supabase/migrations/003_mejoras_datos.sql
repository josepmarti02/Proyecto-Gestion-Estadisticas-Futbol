-- ====================================================================
-- 003_mejoras_datos.sql
-- D2: posición de jugadores
-- D3: tarjetas amarillas y rojas en estadísticas de partido
-- D5: notas de partido
-- También actualiza la función get_team_aggregates para incluir tarjetas
-- Ejecutar en el SQL Editor de Supabase (una sola vez, tras 002)
-- ====================================================================

-- ── D2: Posición del jugador ──────────────────────────────────────────────────
ALTER TABLE players ADD COLUMN IF NOT EXISTS position TEXT NOT NULL DEFAULT '';

-- ── D3: Tarjetas por jugador y partido ───────────────────────────────────────
ALTER TABLE match_stats ADD COLUMN IF NOT EXISTS amarillas INT NOT NULL DEFAULT 0;
ALTER TABLE match_stats ADD COLUMN IF NOT EXISTS rojas     INT NOT NULL DEFAULT 0;

-- ── D5: Notas de partido ──────────────────────────────────────────────────────
ALTER TABLE matches ADD COLUMN IF NOT EXISTS notes TEXT NOT NULL DEFAULT '';

-- ── Actualización de la función de acumulado (incluye tarjetas) ──────────────
DROP FUNCTION IF EXISTS get_team_aggregates(UUID);
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
  total_min  BIGINT,
  amarillas  BIGINT,
  rojas      BIGINT
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
    COALESCE(SUM(ms.minutos_1a + ms.minutos_2a), 0),
    COALESCE(SUM(ms.amarillas), 0),
    COALESCE(SUM(ms.rojas),     0)
  FROM players p
  LEFT JOIN match_stats ms ON ms.player_id = p.id
  LEFT JOIN matches m      ON m.id = ms.match_id AND m.team_id = p_team_id
  WHERE p.team_id = p_team_id
    AND p.active  = TRUE
  GROUP BY p.id, p.name
  ORDER BY p.name;
$$;