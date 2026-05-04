# Plan: lanzamiento de la app a producción

## Contexto

La app `proyecto_benjA.py` gestiona estadísticas de un equipo de fútbol 8 (Nules Benj A) y se ejecuta hoy localmente con `streamlit run`. Los datos se guardan en CSVs sueltos dentro de `partidos/` y la plantilla en `jugadores.json`. Esto:

- Obliga a tener el portátil delante para usarla.
- No permite que otros entrenadores (amigos del usuario) la prueben.
- Hace frágil la persistencia (cada partido es un archivo, fácil de corromper o renombrar mal).
- Mezcla datos en disco con código en el repo, ensuciando los commits.

El objetivo es **lanzar la app en producción gratis**, accesible desde el móvil con login, con los datos en una base de datos real, lista para que otros entrenadores la prueben con sus propios equipos. Adicionalmente hay deprecaciones de Streamlit (`use_container_width`) que conviene arreglar antes del despliegue.

## Stack recomendado

| Capa | Elección | Por qué |
|---|---|---|
| **Hosting** | Streamlit Community Cloud | Gratis, conecta directo a GitHub, redeploy en cada push, dominio `tu-app.streamlit.app`. Es la vía nativa para Streamlit y no requiere Docker. |
| **Base de datos** | Supabase (Postgres) | Free tier de 500 MB (más que de sobra). Postgres real, escalable, con SQL estándar. Permite Row-Level Security (RLS) para aislar datos por entrenador sin lógica extra en la app. |
| **Auth** | Supabase Auth (email + password) | Integrada con la BD vía RLS — cada usuario ve sólo sus equipos automáticamente. Gratis e ilimitada en el free tier. |
| **Mobile** | Streamlit responsive nativo + ajustes de layout | Streamlit ya se adapta a móvil; sólo hay que evitar tablas demasiado anchas y sustituir `st.columns` por layouts apilados donde rompa. |

Este stack es **0 € recurrentes**, profesional, y si en el futuro la app crece (más entrenadores, más equipos) Supabase escala vertical y horizontalmente sin reescribir nada.

## Modelo de datos (Supabase)

Cinco tablas, separación clara entre plantilla y estadísticas de partido:

```
auth.users               -- gestionada por Supabase Auth
  id (uuid)
  email

teams                    -- un entrenador puede tener varios equipos
  id (uuid, pk)
  owner_id (uuid, fk → auth.users)
  name (text)            -- p.ej. "Nules Benj 'A'"
  category (text)        -- p.ej. "Benjamín 25-26"
  max_titulares (int)    -- 8 por defecto
  minutos_partido (int)  -- 50 por defecto
  created_at (timestamp)

players                  -- la plantilla, sustituye jugadores.json
  id (uuid, pk)
  team_id (uuid, fk → teams)
  name (text)
  active (bool)          -- para "dar de baja" sin perder histórico
  created_at (timestamp)

matches                  -- un partido (cabecera), sustituye el CSV por partido
  id (uuid, pk)
  team_id (uuid, fk → teams)
  rival (text)
  match_date (date)
  is_home (bool)
  goals_for (int)
  goals_against (int)
  created_at (timestamp)

match_stats              -- una fila por jugador y partido
  id (uuid, pk)
  match_id (uuid, fk → matches, on delete cascade)
  player_id (uuid, fk → players)
  convocado (bool)
  titular (bool)
  suplente (bool)
  goles (int)
  asistencias (int)
  minutos_1a (int)
  minutos_2a (int)
  -- minutos totales y % se calculan en la app, no se guardan
```

**RLS**: política simple en `teams` — `owner_id = auth.uid()`. Las tablas hijas (`players`, `matches`, `match_stats`) se filtran cruzando con `teams`. Resultado: cada entrenador entra y ve sólo lo suyo, sin ningún `if` en el código de la app.

## Fases de implementación

### Fase 1 — Higiene previa (sin tocar lógica)

Ficheros a tocar / crear:

- **`requirements.txt`** (nuevo): `streamlit`, `pandas`, `numpy`, `supabase`, `python-dotenv`. Sin pinear versiones todavía; pinear cuando todo funcione.
- **`.gitignore`**: añadir `.env`, `.streamlit/secrets.toml`, `*.db`, `partidos/` (los CSVs ya no deben ir al repo).
- **`.streamlit/config.toml`** (nuevo): configurar tema y `[server] headless = true`.
- **`README.md`**: actualizar con instrucciones de despliegue y desarrollo local.
- **Limpieza de deprecaciones** en `proyecto_benjA.py` — sustituir las **15 ocurrencias** de `use_container_width=True` por `width="stretch"`.

### Fase 2 — Capa de datos (`db.py`)

Crear un módulo nuevo **`db.py`** que envuelva Supabase y exponga una API limpia. Toda la app pasará por aquí — ningún `pd.read_csv` ni `to_csv` quedará vivo.

API mínima a implementar:

```python
# Conexión
get_client() -> supabase.Client          # cachea con st.cache_resource

# Auth
sign_in(email, password) -> session
sign_up(email, password) -> session
sign_out()
current_user() -> User | None

# Equipos
list_teams() -> list[Team]
create_team(name, category, max_titulares, minutos_partido) -> Team
update_team(team_id, **fields) -> Team

# Plantilla
list_players(team_id, only_active=True) -> list[Player]
add_player(team_id, name) -> Player
deactivate_player(player_id)
rename_player(player_id, new_name)

# Partidos
list_matches(team_id) -> list[Match]   # ordenados por fecha desc
get_match(match_id) -> (Match, list[MatchStat])
create_match(team_id, rival, date, is_home, gf, ga, stats) -> Match
update_match(match_id, **fields, stats=...) -> Match
delete_match(match_id)

# Acumulado (se calcula con SQL en Supabase, no agregando en pandas)
get_team_aggregates(team_id) -> DataFrame
```

El acumulado actualmente vive en `generar_acumulado_desde_partidos()` (líneas 115-183). Migra a una **vista SQL en Supabase** (`v_team_aggregates`) que haga el GROUP BY por jugador. Eso elimina cientos de líneas de pandas y devuelve datos ya listos para mostrar.

Las funciones puras existentes que **se conservan tal cual**:
- `estadisticas_generales(df)` — opera sobre el DataFrame del acumulado, no toca I/O.
- `ranking(df, columna, top=3)`.
- `metricas_extra(df)`.

### Fase 3 — Auth y selector de equipo

Antes de mostrar cualquier página, gating de auth:

- Página de **login/registro** (`page_auth`) — formulario simple email + password con tabs "Entrar" / "Crear cuenta".
- Una vez autenticado, **selector de equipo** en la sidebar (`st.selectbox` con los equipos del usuario). Si no tiene ninguno, ofrecerle crear uno.
- Guardar `team_id` en `st.session_state["current_team"]` y pasarlo a todas las llamadas al data layer.
- Las constantes `TU_EQUIPO`, `MAX_TITULARES`, `MINUTOS_PARTIDO` **dejan de ser hardcoded** — se leen del equipo actual.

### Fase 4 — Migrar páginas a Supabase

Sustituir, página por página, las llamadas a archivos por llamadas a `db.py`. Orden propuesto (de más simple a más compleja, así se valida la base antes):

1. **Plantilla** → `db.list_players` / `db.add_player` / `db.deactivate_player`. Se quita `jugadores.json` y la helper `load_jugadores()`.
2. **Histórico de partidos** → `db.list_matches` / `db.get_match`. Desaparece toda la lógica de "archivos inválidos" — ya no hay archivos.
3. **Añadir partido manual** → `db.create_match` con la lista de stats. Validaciones de minutos y de número de titulares se conservan tal cual, son reglas de negocio.
4. **Añadir partido subiendo archivo** → **se elimina**. Ya no tiene sentido; el flujo es "manual" o "importar antiguos" (ver Fase 6).
5. **General + Individuales** → consumen el acumulado desde `db.get_team_aggregates(team_id)`. Las funciones puras se quedan.

Estado de sesión a limpiar:
- `df`, `acumulado_generado` → ya no hacen falta, se consulta a la BD bajo demanda.
- `mostrar_confirm_guardado`, `archivo_a_guardar`, `mostrar_confirmacion` → ya no hay archivos que sobrescribir.
- `no_convocados`, `suplentes`, `rival`, `local_visitante`, `goles_a_favor`, `goles_en_contra` → permanecen, son estado del formulario.
- `editando_partido` → permanece, ahora guarda `match_id` (uuid) en lugar de nombre de archivo.
- `confirmar_eliminar` → permanece.

### Fase 5 — UI mobile-friendly

Revisar la app abierta en navegador móvil (Chrome DevTools en modo móvil sirve) y ajustar:

- Tablas con muchas columnas (acumulado, individuales) — usar `st.dataframe(..., width="stretch", height=...)` con scroll horizontal.
- En rankings, apilar los 3 rankings verticalmente cuando el viewport es pequeño.
- Botones grandes y `st.tabs` en vez de selectboxes anidados donde sea posible.
- Ocultar la sidebar por defecto en móvil con `st.set_page_config(initial_sidebar_state="collapsed")`.

No es bloqueante para el lanzamiento — se puede iterar después del primer despliegue.

### Fase 6 — Migración de datos existentes (one-shot)

Hay 7 CSVs en `partidos/` con datos reales. Un script `scripts/import_csvs.py` que:

1. Pide credenciales del usuario (su login Supabase).
2. Crea el equipo "Nules Benj 'A'" si no existe.
3. Lee cada CSV de `partidos/`, extrae rival y fecha del nombre, parsea las filas y llama a `db.create_match`.
4. Loguea qué importó y qué falló.

Se ejecuta una sola vez, después se borran los CSVs locales (ya están en `.gitignore` desde Fase 1).

### Fase 7 — Despliegue

1. En Supabase: crear proyecto, ejecutar las migraciones SQL (tablas + RLS + vista de acumulado).
2. En GitHub: subir las ramas/cambios.
3. En **share.streamlit.io**: New app → conectar con el repo → entrypoint `proyecto_benjA.py`.
4. **Secrets** (en el panel de Streamlit Cloud, sección "Secrets"):
   ```toml
   [supabase]
   url = "https://xxxxx.supabase.co"
   anon_key = "eyJ..."
   ```
5. Deploy → la app queda en `https://nules-benj-a.streamlit.app` (o nombre similar).
6. Añadir la URL como app web al móvil (en Android: "Añadir a pantalla de inicio"; en iOS: lo mismo desde Safari). Se comporta como app nativa.

## Resumen de archivos afectados

| Archivo | Acción |
|---|---|
| `proyecto_benjA.py` | Refactor mayor: quita I/O de archivos, usa `db.py`, fix deprecaciones, gating de auth |
| `db.py` | **Nuevo** — capa de acceso a Supabase |
| `requirements.txt` | **Nuevo** |
| `.streamlit/config.toml` | **Nuevo** |
| `.gitignore` | Añade datos locales y secrets |
| `README.md` | Actualizar |
| `scripts/import_csvs.py` | **Nuevo** — migración de datos existentes |
| `supabase/migrations/*.sql` | **Nuevo** — esquema y RLS |
| `jugadores.json` | **Eliminado** |
| `partidos/` | Se borra del tracking de Git (queda local hasta migrar) |
| `estadisticas_generadas.csv` | **Eliminado** |

## Verificación end-to-end

1. **Local con Supabase**: `streamlit run proyecto_benjA.py` apuntando a un proyecto Supabase de pruebas. Probar: registro, crear equipo, añadir 5 jugadores, crear un partido manual, ver acumulado, editar partido, eliminar partido.
2. **RLS**: crear un segundo usuario con otro email, comprobar que no ve el equipo del primero.
3. **Mobile**: abrir la URL pública desde el móvil, ejecutar el mismo flujo. Verificar que las tablas son legibles y que ningún botón queda fuera del viewport.
4. **Migración**: ejecutar `scripts/import_csvs.py` y verificar que los 7 partidos aparecen en histórico con marcadores correctos.
5. **Redeploy**: hacer un cambio cosmético, hacer push, comprobar que Streamlit Cloud rebuildea automáticamente.

## Mejoras opcionales (no bloqueantes)

- **Tests** con `pytest` para las funciones puras (`estadisticas_generales`, `ranking`, etc.).
- **Exportar a PDF** un resumen de partido (útil para mandar al chat del equipo).
- **Notificaciones** cuando un jugador roza el % mínimo de minutos.
- **Compartir vista de sólo lectura** con un link público (un padre quiere ver las stats sin login).
- **Pinning de versiones** en `requirements.txt` una vez todo estabilizado.
- **Logging** y monitorización vía Logflare (Supabase) o Sentry (free tier).