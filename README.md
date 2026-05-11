# Gestión de Estadísticas de Fútbol

App web para gestionar las estadísticas de equipos de fútbol 8, desarrollada con Streamlit y Supabase.

## Funcionalidades

- **Plantilla**: gestión de jugadores (altas y bajas conservando histórico)
- **Añadir partido**: entrada manual de estadísticas por jugador (minutos, goles, asistencias)
- **Histórico**: listado y edición de partidos registrados
- **Estadísticas generales**: resumen del equipo (goles, asistencias, diferencia)
- **Estadísticas individuales**: filtro por jugador y rankings (goles, minutos, productividad...)
- **Multi-equipo**: un mismo usuario puede gestionar varios equipos
- **Auth**: login con email/contraseña, cada entrenador ve solo sus datos

## Stack

- [Streamlit](https://streamlit.io) — interfaz web
- [Supabase](https://supabase.com) — base de datos (Postgres) y autenticación
- [Pandas](https://pandas.pydata.org) — cálculo de estadísticas

## Desarrollo local

1. Clona el repositorio
2. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Crea el archivo `.streamlit/secrets.toml` con tus credenciales de Supabase:
   ```toml
   [supabase]
   url = "https://tu-proyecto.supabase.co"
   key = "tu-publishable-key"
   ```
4. Ejecuta la migración SQL de `supabase/migrations/001_schema.sql` en el SQL Editor de tu proyecto Supabase
5. Lanza la app:
   ```bash
   streamlit run proyecto_benjA.py
   ```

## Despliegue (Streamlit Community Cloud)

1. Conecta el repositorio en [share.streamlit.io](https://share.streamlit.io)
2. Entrypoint: `proyecto_benjA.py`
3. En **Settings → Secrets**, añade el bloque `[supabase]` del paso 3 de arriba
4. Deploy
