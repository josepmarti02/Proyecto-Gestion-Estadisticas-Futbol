-- ====================================================================
-- 007_match_drafts.sql
-- I1: Borrador de partido en directo (persistencia ante bloqueo de pantalla)
-- Ejecutar en el SQL Editor de Supabase (una sola vez, tras 006)
-- ====================================================================

CREATE TABLE IF NOT EXISTS match_drafts (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id               UUID NOT NULL UNIQUE REFERENCES teams(id) ON DELETE CASCADE,
    eventos               JSONB NOT NULL DEFAULT '[]',
    lineup                JSONB NOT NULL DEFAULT '{}',
    formacion             TEXT NOT NULL DEFAULT '',
    no_convocados         JSONB NOT NULL DEFAULT '[]',
    timer_offset_secs     FLOAT NOT NULL DEFAULT 0,
    timer_start_timestamp FLOAT,          -- Unix timestamp de cuando se pulsó ▶️ (NULL si pausado)
    timer_running         BOOL NOT NULL DEFAULT FALSE,
    medio_tiempo_min      INT,
    num_partes            INT NOT NULL DEFAULT 2,
    updated_at            TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE match_drafts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "owner access match_drafts" ON match_drafts USING (
    EXISTS (
        SELECT 1 FROM teams t
        WHERE t.id = match_drafts.team_id AND t.owner_id = auth.uid()
    )
);
