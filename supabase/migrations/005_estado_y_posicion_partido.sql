-- ====================================================================
-- 005_estado_y_posicion_partido.sql
-- G1: MVPs múltiples (hasta 3 por partido)
-- G4: Estado del jugador (disponible / lesionado / sancionado)
-- G6: Posición inicial de titulares (solo informativa)
-- Ejecutar en el SQL Editor de Supabase (una sola vez, tras 004)
-- ====================================================================

-- ── G1: MVPs múltiples (sustituye mvp_player_id por mvp_player_ids) ──────────
ALTER TABLE matches ADD COLUMN IF NOT EXISTS mvp_player_ids UUID[] NOT NULL DEFAULT '{}';
UPDATE matches
   SET mvp_player_ids = ARRAY[mvp_player_id]
 WHERE mvp_player_id IS NOT NULL AND cardinality(mvp_player_ids) = 0;
ALTER TABLE matches DROP COLUMN IF EXISTS mvp_player_id;

-- ── G4: Estado del jugador ───────────────────────────────────────────────────
ALTER TABLE players ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'disponible'
  CHECK (status IN ('disponible', 'lesionado', 'sancionado'));

-- ── G6: Posición inicial de titulares (alineación de salida) ────────────────
ALTER TABLE match_stats ADD COLUMN IF NOT EXISTS position_played TEXT NOT NULL DEFAULT '';
