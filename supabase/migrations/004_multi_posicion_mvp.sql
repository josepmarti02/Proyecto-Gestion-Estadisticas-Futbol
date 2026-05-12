-- ====================================================================
-- 004_multi_posicion_mvp.sql
-- F2: Posiciones alternativas (multi-posición)
-- F6: MVP del partido
-- Ejecutar en el SQL Editor de Supabase (una sola vez, tras 003)
-- ====================================================================

-- ── F2: Posiciones alternativas ──────────────────────────────────────────────
ALTER TABLE players ADD COLUMN IF NOT EXISTS alt_positions TEXT[] NOT NULL DEFAULT '{}';

-- ── F6: MVP del partido ──────────────────────────────────────────────────────
ALTER TABLE matches ADD COLUMN IF NOT EXISTS mvp_player_id UUID
  REFERENCES players(id) ON DELETE SET NULL;
