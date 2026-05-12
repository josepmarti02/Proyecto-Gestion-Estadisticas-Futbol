from fpdf import FPDF
import pandas as pd
from datetime import datetime


_COLUMNAS_PDF = [
    "JUGADOR", "CONVOCADO", "TITULAR", "GOL", "ASIST",
    "TOTAL MINUTOS JUGADOS", "% MINUTOS", "PRODUCTIVIDAD OFENSIVA",
]

_ANCHOS = {
    "JUGADOR": 48, "CONVOCADO": 24, "TITULAR": 22,
    "GOL": 16, "ASIST": 16, "TOTAL MINUTOS JUGADOS": 34,
    "% MINUTOS": 24, "PRODUCTIVIDAD OFENSIVA": 30,
}

_CABECERAS = {
    "TOTAL MINUTOS JUGADOS": "MINUTOS",
    "PRODUCTIVIDAD OFENSIVA": "PRODUC.",
}


def generar_pdf_estadisticas(equipo: dict, df: pd.DataFrame, totales: dict) -> bytes:
    """Genera un PDF A4 horizontal con las estadísticas de la temporada."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.set_margins(10, 10, 10)
    pdf.add_page()

    # ── Título ────────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, txt=f"Estadisticas  {equipo.get('name', '')}", ln=1, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0, 6,
        txt=f"Categoria: {equipo.get('category', '')}  |  Generado: {datetime.today().strftime('%d/%m/%Y')}",
        ln=1, align="C",
    )
    pdf.ln(4)

    # ── Resumen del equipo ────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, txt="Resumen del equipo", ln=1)
    pdf.set_font("Helvetica", "", 10)

    goles_f = totales.get("total_goles", 0)
    goles_c = totales.get("total_goles_contra", 0)
    datos_totales = [
        ("Partidos jugados",    totales.get("total_partidos", 0)),
        ("Goles a favor",       goles_f),
        ("Goles en contra",     goles_c),
        ("Diferencia de goles", goles_f - goles_c),
        ("Asistencias",         totales.get("total_asist", 0)),
    ]
    for label, valor in datos_totales:
        pdf.cell(75, 6, txt=label, border="B")
        pdf.cell(25, 6, txt=str(valor), border="B", ln=1)
    pdf.ln(6)

    # ── Tabla de jugadores ────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, txt="Estadisticas por jugador", ln=1)

    cols = [c for c in _COLUMNAS_PDF if c in df.columns]

    # Cabecera
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(200, 200, 200)
    for col in cols:
        pdf.cell(_ANCHOS.get(col, 25), 7, txt=_CABECERAS.get(col, col), border=1, fill=True)
    pdf.ln()

    # Filas
    pdf.set_font("Helvetica", "", 8)
    for i, (_, row) in enumerate(df[cols].iterrows()):
        pdf.set_fill_color(245, 245, 245) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
        for col in cols:
            val = row[col]
            txt = f"{val:.1f}" if isinstance(val, float) else str(val)
            pdf.cell(_ANCHOS.get(col, 25), 6, txt=txt[:22], border=1, fill=True)
        pdf.ln()

    return bytes(pdf.output())
