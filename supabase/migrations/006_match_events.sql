-- ====================================================================
-- 006_match_events.sql
-- H4: Tabla de eventos de partido en directo
-- Ejecutar en el SQL Editor de Supabase (una sola vez, tras 005)
-- ====================================================================

CREATE TABLE IF NOT EXISTS match_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id    UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL CHECK (event_type IN (
                    'gol_a_favor', 'gol_en_contra', 'amarilla', 'roja', 'cambio', 'medio_tiempo'
                )),
    minuto      INT,
    player_id   UUID REFERENCES players(id) ON DELETE SET NULL,
    player_id2  UUID REFERENCES players(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- RLS: acceso solo al entrenador propietario del equipo
ALTER TABLE match_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "owner access match_events" ON match_events USING (
    EXISTS (
        SELECT 1 FROM matches m
        JOIN teams t ON t.id = m.team_id
        WHERE m.id = match_events.match_id
          AND t.owner_id = auth.uid()
    )
);
