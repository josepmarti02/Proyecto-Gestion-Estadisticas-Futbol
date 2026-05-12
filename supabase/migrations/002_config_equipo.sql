-- ====================================================================
-- 002_config_equipo.sql
-- Añade campos de configuración avanzada y soporte de vista pública
-- Ejecutar en el SQL Editor de Supabase (una sola vez, tras 001)
-- ====================================================================

-- ── Nuevos campos en teams ────────────────────────────────────────────────────

ALTER TABLE teams ADD COLUMN IF NOT EXISTS public BOOLEAN NOT NULL DEFAULT FALSE;

-- ── Políticas de lectura pública (rol anon) ───────────────────────────────────
-- Permiten que cualquier visitante sin login vea los datos de equipos
-- marcados como públicos. RLS sigue activo — solo filas con public=true.

CREATE POLICY "lectura_publica_equipos" ON teams
  FOR SELECT USING (public = true);

CREATE POLICY "lectura_publica_jugadores" ON players
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM teams
      WHERE teams.id = players.team_id AND teams.public = true
    )
  );

CREATE POLICY "lectura_publica_partidos" ON matches
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM teams
      WHERE teams.id = matches.team_id AND teams.public = true
    )
  );

CREATE POLICY "lectura_publica_estadisticas" ON match_stats
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM matches
      JOIN teams ON teams.id = matches.team_id
      WHERE matches.id = match_stats.match_id AND teams.public = true
    )
  );

-- ── Permisos para el rol anon (solo lectura) ─────────────────────────────────
-- RLS controla qué filas ve cada usuario; GRANT controla si el rol puede
-- acceder a la tabla en absoluto. Ambos son necesarios.

GRANT SELECT ON public.teams       TO anon;
GRANT SELECT ON public.players     TO anon;
GRANT SELECT ON public.matches     TO anon;
GRANT SELECT ON public.match_stats TO anon;
GRANT EXECUTE ON FUNCTION get_team_aggregates(UUID) TO anon;
