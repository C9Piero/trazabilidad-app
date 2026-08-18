import datetime
import io
import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from supabase import Client, create_client

# --- CATÁLOGO BASE DE PRODUCTOS HISTÓRICOS ---
PRODUCTOS_CATALOGO_BASE = [
    "Estrellas", "Cartuchera", "Cúbica", "Bolso", "Mochila", "Llavero",
    "Monedero", "Canguro", "Tote bag", "Neceser", "Portalaptop",
    "Portacepillos", "Pelota", "Portacubierto", "Juguete", "Cubo",
    "Corazones", "Peluche", "Morral", "Portaútiles", "Portabotella",
    "Cama perrito", "Colets", "Rombo", "Mandiles", "Lonchera",
    " Otro (Escribir nuevo producto)",
]

# --- MATRIZ DE TIEMPOS ESTIMADOS SEGÚN TIPO Y COMPLEJIDAD (en horas/unidad) ---
TIEMPOS_ESTIMADOS_PRODUCTO = {
    "Mochila": 2.50, "Bolso": 1.50, "Tote bag": 0.80, "Portalaptop": 1.20,
    "Canguro": 1.10, "Neceser": 0.70, "Lonchera": 1.00, "Cartuchera": 0.50,
    "Morral": 1.20, "Mandiles": 0.60, "Cama perrito": 1.80, "Peluche": 1.50,
    "Pelota": 0.80, "Estrellas": 0.35, "Corazones": 0.35, "Rombo": 0.35,
    "Cúbica": 0.60, "Cubo": 0.50, "Llavero": 0.20, "Monedero": 0.30,
    "Portacepillos": 0.25, "Portacubierto": 0.25, "Portaútiles": 0.40,
    "Portabotella": 0.45, "Colets": 0.15, "Juguete": 0.75,
}

def estimar_tiempo_unidad(nombre_producto: str) -> float:
    if not nombre_producto:
        return 0.35
    for prod_key, tiempo in TIEMPOS_ESTIMADOS_PRODUCTO.items():
        if prod_key.lower() in nombre_producto.lower():
            return tiempo
    return 0.35

FACTORES_CO2 = {
    "Banner": 9.5, "Bata de laboratorio": 6.575, "Bolsas": 8.0, "Camisa": 6.575,
    "Camisa algodón": 5.0, "Camisa drill": 5.9, "Camisa ignífuga": 5.35,
    "Camisa jean / denim": 5.0, "Camisaco": 5.0, "Casaca": 6.575,
    "Casaca drill": 5.9, "Casaca polar": 6.0, "Chaleco": 6.575,
    "Chaleco de seguridad": 9.75, "Chompa": 7.1, "Enterizo": 6.575,
    "Gorro": 7.925, "Impermeable": 9.425, "Mameluco": 6.575,
    "Overol": 6.575, "Pantalón": 6.575, "Pantalón algodón": 5.0,
    "Pantalón drill": 5.9, "Pantalón jean": 5.0, "Polera": 5.0,
    "Polo": 6.8, "Polo algodón": 5.0, "Short": 6.575, "Toalla": 5.0, "Otro": 6.575,
}

FACTORES_TRANSPORTE = {
    "Auto": {"consumo": 0.10, "factor": 2.31},
    "Minivan": {"consumo": 0.12, "factor": 2.00},
    "Mototaxi": {"consumo": 0.04, "factor": 2.31},
    "Moto": {"consumo": 0.03, "factor": 2.31},
    "Camión mediano": {"consumo": 0.30, "factor": 2.68},
    "Camión grande": {"consumo": 0.40, "factor": 2.68},
}

FACTORES_BORDADO = {
    "Sin bordado / Ninguno": 0.0,
    "Simple (5 min/pieza)": 0.020,
    "Medio (9 min/pieza)": 0.037,
    "Complejo (10 min/pieza)": 0.041,
}

PERSONAL_FIJO_OPERACIONES = [
    {"rol": "Corte", "nombre": "Maria Isabel Estrada Sandoval"},
    {"rol": "Corte", "nombre": "Genaro Jara García"},
    {"rol": "Corte", "nombre": "Luciana Jara estrada"},
    {"rol": "Corte", "nombre": "Felicita Sandoval vilchez"},
    {"rol": "Corte", "nombre": "Nicolle Estrada"},
    {"rol": "Logística", "nombre": "Evelyn Prada Vizarreta"},
]

st.set_page_config(
    page_title="Pequeños Detalles - Sistema de Trazabilidad",
    page_icon="",
    layout="wide",
)

# --- ESTILOS CSS STREAMLIT ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    :root {
        --brand-900: #0F172A; --brand-700: #1E3A8A; --brand-500: #2563EB;
        --brand-100: #DBEAFE; --ink: #1E293B; --ink-muted: #64748B;
        --border: #E2E8F0; --surface: #F8FAFC; --radius: 14px;
    }
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .hero-header {
        background: linear-gradient(135deg, var(--brand-900) 0%, var(--brand-700) 50%, var(--brand-500) 100%);
        color: white; padding: 24px 30px; border-radius: var(--radius);
        box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.3); margin-bottom: 25px;
    }
    .hero-header h1 { color: #ffffff !important; font-weight: 800; font-size: 1.8rem; margin: 0; }
    .hero-header p { color: #93C5FD !important; margin: 4px 0 0 0; font-size: 0.95rem; }
    div[data-testid="stSidebar"] { background-color: var(--surface); border-right: 1px solid var(--border); }
    .sidebar-section-title { color: var(--ink-muted); font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 15px; margin-bottom: 8px; }
    </style>
""",
    unsafe_allow_html=True,
)

@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["SUPABASE_URL"]
    key = st.secrets["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"No se pudo conectar con Supabase: {e}")
    st.stop()

def cargar_proyectos(estado=None):
    try:
        query = supabase.table("proyectos").select("*")
        if estado:
            query = query.eq("estado", estado)
        return query.execute().data
    except Exception as e:
        st.warning(f"No se pudieron cargar los proyectos: {e}")
        return []

class ReporteCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        for page in self.pages:
            self.__dict__.update(page)
            self.draw_page_decorations()
            super().showPage()
        super().save()

    def draw_page_decorations(self):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#7F8C8D"))
        self.drawString(36, 20, "Pequeños Detalles Handmade Perú S.A.C. - Reporte Oficial de Impacto")
        self.drawRightString(576, 20, f"Página {self._pageNumber}")
        self.restoreState()


# --- GENERADOR DEL PDF OFICIAL CON CARÁTULA INICIAL ---
def generar_pdf_oficial(
    cliente, ruc, proyecto_nom, codigo_proy, fe_inicio, fe_fin,
    responsable, area, tipo_material, valorizacion, unidad_medida,
    guia_remision, origen, destino, lista_items, lista_trazabilidad,
    lista_productos, mat_transformado, retazos_aprovechables,
    perdida_no_aprovechable, total_procesado, pct_aprovechamiento_total,
    pct_perdida, lista_operaciones_pdf, lista_confeccion,
    total_horas_social, total_personas_social, co2_evitado_total,
    emisiones_transporte, emisiones_lavado, emisiones_corte, emisiones_bordado
):
    kg_recibidos = sum([item["peso_total"] for item in lista_items])
    emisiones_proceso = emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado
    co2_neto = co2_evitado_total - emisiones_proceso
    total_prod_unidades = sum([p["cantidad"] for p in lista_productos])
    total_unidades_ingreso = sum([item["unidades"] for item in lista_items])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Estilos tipográficos institucionales
    cover_title = ParagraphStyle("CoverT", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=22, textColor=colors.HexColor("#1E3A8A"), alignment=1, spaceAfter=10, leading=26)
    cover_subtitle = ParagraphStyle("CoverSub", parent=styles["Normal"], fontName="Helvetica", fontSize=13, textColor=colors.HexColor("#475569"), alignment=1, spaceAfter=20, leading=18)
    cover_meta = ParagraphStyle("CoverMeta", parent=styles["Normal"], fontName="Helvetica", fontSize=10, textColor=colors.HexColor("#334155"), alignment=1, leading=15)
    
    title_style = ParagraphStyle("TitleSt", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=14, textColor=colors.HexColor("#0F172A"), alignment=1, spaceAfter=2)
    sub_style = ParagraphStyle("SubSt", parent=styles["Normal"], fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#475569"), alignment=1, spaceAfter=8, leading=10)
    h2_style = ParagraphStyle("H2St", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=10, textColor=colors.HexColor("#1E3A8A"), spaceBefore=8, spaceAfter=4)
    body_style = ParagraphStyle("BodySt", parent=styles["Normal"], fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#334155"), leading=11, spaceAfter=5)
    cell_style = ParagraphStyle("CellSt", parent=styles["Normal"], fontName="Helvetica", fontSize=7.5, textColor=colors.HexColor("#1E293B"), leading=10)
    cell_bold = ParagraphStyle("CellBSt", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.5, textColor=colors.HexColor("#0F172A"), leading=10)
    card_title = ParagraphStyle("CardT", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, textColor=colors.HexColor("#1E3A8A"), alignment=1)
    card_sub = ParagraphStyle("CardS", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=6.5, textColor=colors.HexColor("#64748B"), alignment=1)

    elements = []

    # ==========================================
    # PÁGINA 1: PORTADA / CARÁTULA INSTITUCIONAL
    # ==========================================
    elements.append(Spacer(1, 100))
    elements.append(Paragraph("PEQUEÑOS DETALLES HANDMADE PERÚ S.A.C.", ParagraphStyle("Company", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, textColor=colors.HexColor("#64748B"), alignment=1, spaceAfter=30)))
    elements.append(Paragraph("REPORTE DE IMPACTO AMBIENTAL Y SOCIAL", cover_title))
    elements.append(Paragraph(f"<b>Proyecto:</b> {proyecto_nom}", cover_subtitle))
    elements.append(Spacer(1, 40))
    
    # Bloque de metadatos de la portada
    elements.append(Paragraph(f"<b>Presentado a:</b> {cliente}", cover_meta))
    if ruc:
        elements.append(Paragraph(f"<b>RUC:</b> {ruc}", cover_meta))
    elements.append(Paragraph(f"<b>Código de Proyecto:</b> {codigo_proy}", cover_meta))
    elements.append(Paragraph(f"<b>Periodo de Ejecución:</b> {fe_inicio} – {fe_fin}", cover_meta))
    
    elements.append(Spacer(1, 120))
    elements.append(Paragraph(f"<b>Fecha de emisión:</b> {fe_fin}", ParagraphStyle("DateSt", parent=cover_meta, fontSize=9, textColor=colors.HexColor("#64748B"))))
    
    # Salto de página para pasar al contenido interno
    elements.append(PageBreak())

    # ==========================================
    # PÁGINA 2 EN ADELANTE: CONTENIDO OFICIAL
    # ==========================================
    elements.append(Paragraph("RESUMEN GENERAL DEL PROYECTO", title_style))
    elements.append(Paragraph(f"Proyecto de transformación de textiles en desuso<br/><b>Cliente:</b> \"{cliente}\" &nbsp;|&nbsp; <b>Fecha:</b> {fe_fin}", sub_style))

    # Tarjetas de Resumen Superior
    cards_data = [
        [Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", card_title), Paragraph(f"<b>{pct_aprovechamiento_total:.2f}%</b>", card_title), Paragraph(f"<b>{co2_neto:.2f} kg</b>", card_title), Paragraph(f"<b>{total_horas_social:.2f} hrs</b>", card_title)],
        [Paragraph("MATERIAL RECIBIDO", card_sub), Paragraph("% APROVECHAMIENTO", card_sub), Paragraph("CO2e NETO EVITADO", card_sub), Paragraph(f"TRABAJO ({total_personas_social} PERS.)", card_sub)],
    ]
    t_cards = Table(cards_data, colWidths=[135, 135, 135, 135])
    t_cards.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    elements.append(t_cards)
    elements.append(Spacer(1, 6))

    # Ficha Técnica
    elements.append(Paragraph("FICHA TÉCNICA DEL PROYECTO", h2_style))
    data_ficha = [
        [Paragraph("Cliente", cell_bold), Paragraph(f"\"{cliente}\" (RUC: {ruc})", cell_style), Paragraph("Empresa ejecutora", cell_bold), Paragraph("Pequeños Detalles Handmade Perú S.A.C.", cell_style)],
        [Paragraph("Tipo de proyecto", cell_bold), Paragraph(proyecto_nom, cell_style), Paragraph("Periodo de ejecución", cell_bold), Paragraph(f"\"{fe_inicio} – {fe_fin}\"", cell_style)],
        [Paragraph("Ubicación", cell_bold), Paragraph("Lima, Perú", cell_style), Paragraph("Material recibido", cell_bold), Paragraph(tipo_material, cell_style)],
        [Paragraph("Cantidad recibida", cell_bold), Paragraph(f"{kg_recibidos:.2f} kg de textiles", cell_style), Paragraph("Área / Responsable", cell_bold), Paragraph(f"{area} / {responsable}", cell_style)],
    ]
    t_ficha = Table(data_ficha, colWidths=[110, 160, 110, 160])
    t_ficha.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F1F5F9")),
        ("PADDING", (0, 0), (-1, -1), 3.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(t_ficha)
    elements.append(Spacer(1, 4))

    # Resumen Ejecutivo
    elements.append(Paragraph("Resumen Ejecutivo", h2_style))
    texto_ejecutivo = (
        f"En el marco de su compromiso con la sostenibilidad, <b>{cliente}</b> implementó un proyecto de economía circular "
        f"mediante la transformación de <b>textiles en desuso</b> provenientes de sus operaciones. Estos materiales fueron recuperados y "
        f"transformados a través de procesos de upcycling, permitiendo extender su vida útil y reincorporarlos a la cadena productiva como nuevos productos. "
        f"Como resultado del proyecto, se transformaron <b>{kg_recibidos:.2f} kg de textiles</b>, se elaboraron <b>{total_prod_unidades} productos</b>, "
        f"y se generaron oportunidades económicas para <b>{total_personas_social} personas</b>, bajo un modelo de producción descentralizada. "
        f"Asimismo, se estimó la evitación de <b>{co2_neto:.2f} kg de CO2 equivalente (CO2e)</b>. "
        f"Este proyecto demuestra cómo la economía circular permite revalorizar materiales en desuso, generando impacto ambiental y social positivo."
    )
    elements.append(Paragraph(texto_ejecutivo, body_style))
    elements.append(Spacer(1, 4))

    # Caracterización del Material
    elements.append(Paragraph("Material Recibido y Caracterización", h2_style))
    elements.append(Paragraph("El proyecto se desarrolló a partir de la recuperación de uniformes corporativos en desuso proporcionados por el cliente. Estos materiales fueron clasificados y acondicionados en función de su tipo, estado y potencial de aprovechamiento.", body_style))
    
    data_prendas_pdf = [[
        Paragraph("Tipo de prenda", cell_bold),
        Paragraph("Cantidad (unidades)", cell_bold),
        Paragraph("Peso estimado (kg)", cell_bold),
    ]]
    for item in lista_items:
        data_prendas_pdf.append([
            Paragraph(item["descripcion"], cell_style),
            Paragraph(str(item["unidades"]), cell_style),
            Paragraph(f"{item['peso_total']:.2f}", cell_style),
        ])
    data_prendas_pdf.append([
        Paragraph("<b>TOTAL</b>", cell_bold),
        Paragraph(f"<b>{total_unidades_ingreso}</b>", cell_bold),
        Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", cell_bold),
    ])
    t_prendas = Table(data_prendas_pdf, colWidths=[240, 150, 150])
    t_prendas.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF6FF")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F8FAFC")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 3.5),
    ]))
    elements.append(t_prendas)
    elements.append(Spacer(1, 6))

    # Indicadores de Impacto
    elements.append(Paragraph("Indicadores de impacto del proyecto", h2_style))
    data_indicadores = [
        [Paragraph("<b>Categoría</b>", cell_bold), Paragraph("<b>Indicador</b>", cell_bold), Paragraph("<b>Valor</b>", cell_bold)],
        [Paragraph("Ambiental", cell_bold), Paragraph("Textiles recibidos (kg)", cell_style), Paragraph(f"{kg_recibidos:.2f} kg", cell_style)],
        [Paragraph("", cell_style), Paragraph("Uniformes transformados (unidades)", cell_style), Paragraph(f"{total_unidades_ingreso}", cell_style)],
        [Paragraph("", cell_style), Paragraph("Emisiones de CO2 evitadas", cell_style), Paragraph(f"{co2_neto:.2f} kg CO2e", cell_style)],
        [Paragraph("", cell_style), Paragraph("Material reincorporado a la cadena productiva (%)", cell_style), Paragraph(f"{pct_aprovechamiento_total:.2f} %", cell_style)],
        [Paragraph("Social", cell_bold), Paragraph("Personas participantes en el proceso productivo", cell_style), Paragraph(f"{total_personas_social}", cell_style)],
        [Paragraph("", cell_style), Paragraph("Horas de trabajo generadas", cell_style), Paragraph(f"{total_horas_social:.2f} h", cell_style)],
        [Paragraph("Circular", cell_bold), Paragraph("Productos elaborados", cell_style), Paragraph(f"{total_prod_unidades}", cell_style)],
    ]
    t_inds = Table(data_indicadores, colWidths=[100, 270, 170])
    t_inds.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF6FF")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 3.5),
    ]))
    elements.append(t_inds)

    elements.append(PageBreak())

    # Impacto Social (Modelo Híbrido)
    elements.append(Paragraph("Impacto Social", h2_style))
    elements.append(Paragraph("El proyecto generó impacto social mediante la participación de personas en el proceso de transformación, bajo un modelo híbrido que combina producción descentralizada (desde casa) con actividades centralizadas en taller y oficina.", body_style))
    
    if lista_confeccion:
        elements.append(Paragraph("<b>Producción descentralizada (trabajo desde casa)</b>", cell_bold))
        data_social_pdf = [[Paragraph("Producto elaborado", cell_bold), Paragraph("Rol", cell_bold), Paragraph("Nombre", cell_bold), Paragraph("Cant.", cell_bold), Paragraph("Horas generadas", cell_bold)]]
        tot_hrs_conf = 0
        for c_item in lista_confeccion:
            tot_hrs_conf += c_item["horas_totales"]
            data_social_pdf.append([
                Paragraph(c_item["producto"], cell_style),
                Paragraph(c_item["rol"], cell_style),
                Paragraph(c_item["persona"], cell_style),
                Paragraph(str(c_item["cantidad"]), cell_style),
                Paragraph(f"{c_item['horas_totales']:.2f} h", cell_style),
            ])
        data_social_pdf.append([Paragraph("<b>TOTAL CONFECCIÓN</b>", cell_bold), "", "", "", Paragraph(f"<b>{tot_hrs_conf:.2f} h</b>", cell_bold)])
        t_soc = Table(data_social_pdf, colWidths=[140, 90, 140, 50, 120])
        t_soc.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF6FF")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F8FAFC")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("SPAN", (0, -1), (3, -1)),
            ("ALIGN", (3, 0), (-1, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 3.5),
        ]))
        elements.append(t_soc)
        elements.append(Spacer(1, 6))

    elements.append(Paragraph("<b>Producción centralizada (taller y oficina)</b>", cell_bold))
    data_ops_pdf = [[Paragraph("Nombre", cell_bold), Paragraph("Área", cell_bold), Paragraph("Días", cell_bold), Paragraph("H/Día", cell_bold), Paragraph("Horas generadas", cell_bold)]]
    tot_hrs_ops = 0
    for op in lista_operaciones_pdf:
        tot_hrs_ops += op["horas_totales"]
        data_ops_pdf.append([
            Paragraph(str(op["nombre"]), cell_style),
            Paragraph(str(op["rol"]), cell_style),
            Paragraph(str(op["dias"]), cell_style),
            Paragraph(f"{op['horas_dia']:.2f}", cell_style),
            Paragraph(f"{op['horas_totales']:.2f} h", cell_style),
        ])
    data_ops_pdf.append([Paragraph("<b>TOTAL TALLER</b>", cell_bold), "", "", "", Paragraph(f"<b>{tot_hrs_ops:.2f} h</b>", cell_bold)])
    t_ops = Table(data_ops_pdf, colWidths=[190, 100, 60, 60, 130])
    t_ops.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF6FF")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F8FAFC")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("SPAN", (0, -1), (3, -1)),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 3.5),
    ]))
    elements.append(t_ops)
    elements.append(Spacer(1, 6))

    # Resumen de Productos
    elements.append(Paragraph("Resumen de productos elaborados", h2_style))
    data_prod_pdf = [[Paragraph("Producto", cell_bold), Paragraph("Cantidad", cell_bold)]]
    for p_item in lista_productos:
        data_prod_pdf.append([
            Paragraph(p_item["producto"], cell_style),
            Paragraph(str(p_item["cantidad"]), cell_style),
        ])
    data_prod_pdf.append([Paragraph("<b>TOTAL</b>", cell_bold), Paragraph(f"<b>{total_prod_unidades}</b>", cell_bold)])
    t_prod = Table(data_prod_pdf, colWidths=[340, 200])
    t_prod.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF6FF")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F8FAFC")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 3.5),
    ]))
    elements.append(t_prod)
    elements.append(Spacer(1, 6))

    # Conclusión
    elements.append(Paragraph("Conclusión", h2_style))
    texto_conclusion = (
        f"El proyecto permitió gestionar de manera eficiente los textiles en desuso de <b>{cliente}</b>, asegurando su aprovechamiento "
        f"mediante un proceso organizado y trazable. Los resultados obtenidos reflejan la capacidad de integrar este tipo de iniciativas "
        f"dentro de la operación de las empresas, generando valor a partir de materiales existentes y cumpliendo con métricas "
        f"ambientales y sociales medibles."
    )
    elements.append(Paragraph(texto_conclusion, body_style))

    doc.build(elements, canvasmaker=ReporteCanvas)
    buffer.seek(0)
    return buffer
# --- ESTADOS DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "pestaña_activa" not in st.session_state:
    st.session_state.pestaña_activa = "➕     Nuevo Reporte PDF"

if "proyecto_editar" not in st.session_state:
    st.session_state.proyecto_editar = {}

if "catalogo_productos" not in st.session_state:
    st.session_state.catalogo_productos = list(PRODUCTOS_CATALOGO_BASE)

try:
    USUARIO_CORRECTO = st.secrets["auth"]["USUARIO"]
    PASSWORD_CORRECTO = st.secrets["auth"]["PASSWORD"]
except KeyError:
    st.error(
        "⚠️ Faltan las credenciales de acceso en `st.secrets`.\n\n"
        "Agrega `USUARIO` y `PASSWORD` dentro de `[auth]` en "
        "`.streamlit/secrets.toml` (local) o en **Settings → Secrets** "
        "(Streamlit Cloud)."
    )
    st.stop()

if not st.session_state.autenticado:
    st.markdown(
        """
        <div style="text-align: center; padding: 40px 10px;">
            <h1 style="color: #1E293B; font-size: 2.2rem; font-weight: 800;">♻️ Pequeños Detalles</h1>
            <p style="color: #64748B; font-size: 1.1rem;">Handmade Perú S.A.C. — Gestión de Sostenibilidad</p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            st.subheader("🔑 Iniciar Sesión")
            usuario_input = st.text_input("Usuario")
            password_input = st.text_input("Contraseña", type="password")

            if st.button(
                "Ingresar al Sistema", use_container_width=True, type="primary"
            ):
                if (
                    usuario_input == USUARIO_CORRECTO
                    and password_input == PASSWORD_CORRECTO
                ):
                    st.session_state.autenticado = True
                    st.success("¡Bienvenido/a!")
                    st.rerun()
                else:
                    st.error("⚠️     Usuario o contraseña incorrectos.")

else:
    proyectos_wip = cargar_proyectos(estado="EN_PROCESO")

    with st.sidebar:
        st.markdown("### ♻️ Pequeños Detalles")
        st.caption("Panel de Control Interno | 2026")
        st.write("---")

        st.markdown(
            '<p class="sidebar-section-title">Navegación</p>',
            unsafe_allow_html=True,
        )

        if st.button(
            "✨     Nuevo Reporte PDF",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.pestaña_activa == "➕     Nuevo Reporte PDF"
                else "secondary"
            ),
        ):
            st.session_state.proyecto_editar = {}
            st.session_state.pestaña_activa = "➕     Nuevo Reporte PDF"
            st.rerun()

        st.markdown(
            '<p class="sidebar-section-title">Proyectos Pendientes</p>',
            unsafe_allow_html=True,
        )

        if proyectos_wip:
            for p in proyectos_wip:
                cli_nombre = p.get("cliente", "Sin Nombre")
                cod_ref = p.get("codigo", "")
                label_btn = f"📁  {cli_nombre}" + (f" ({cod_ref})" if cod_ref else "")

                es_activo = st.session_state.proyecto_editar.get(
                    "id"
                ) == p.get("id") or st.session_state.proyecto_editar.get(
                    "codigo"
                ) == cod_ref

                if st.button(
                    label_btn,
                    key=f"side_proj_{p.get('id', cod_ref)}",
                    use_container_width=True,
                    type="primary" if es_activo else "secondary",
                ):
                    st.session_state.proyecto_editar = p
                    st.session_state.pestaña_activa = "➕     Nuevo Reporte PDF"
                    st.rerun()

            st.write("")
            if st.button("📋  Ver Lista en Proceso", use_container_width=True):
                st.session_state.pestaña_activa = "📋  Proyectos en Proceso"
                st.rerun()
        else:
            st.caption("📂  No hay proyectos en borrador")

        st.markdown(
            '<p class="sidebar-section-title">Analítica e Histórico</p>',
            unsafe_allow_html=True,
        )

        if st.button(
            "📊  Dashboard 2026",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.pestaña_activa == "📊  Dashboard 2026"
                else "secondary"
            ),
        ):
            st.session_state.pestaña_activa = "📊  Dashboard 2026"
            st.rerun()

        if st.button(
            "📜  Historial Completo",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.pestaña_activa == "📜  Historial Completo"
                else "secondary"
            ),
        ):
            st.session_state.pestaña_activa = "📜  Historial Completo"
            st.rerun()

        st.write("---")
        if st.button("🚪  Cerrar Sesión", use_container_width=True):
            st.session_state.autenticado = False
            st.session_state.proyecto_editar = {}
            st.rerun()

    st.markdown(
        f"""
        <div class="hero-header">
            <h1>📄  Sistema de Gestión de Informes Técnicos</h1>
            <p>Sección Activa: <b>{st.session_state.pestaña_activa}</b></p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    if st.session_state.pestaña_activa == "➕     Nuevo Reporte PDF":
        p_edit = st.session_state.proyecto_editar

        if p_edit:
            st.warning(
                "📝  **Modo Edición Activo:** Modificando borrador de"
                f" **{p_edit.get('cliente', '')}** (`{p_edit.get('codigo', '')}`)"
            )
            if st.button("❌     Descartar selección y limpiar formulario"):
                st.session_state.proyecto_editar = {}
                st.rerun()

        with st.container(border=True):
            st.subheader("1. Ficha General del Proyecto")
            c1, c2, c3 = st.columns(3)
            cliente = c1.text_input(
                "Cliente / Empresa", value=p_edit.get("cliente", "")
            )
            ruc = c2.text_input("RUC", value=p_edit.get("ruc", ""))
            codigo_proy = c3.text_input(
                "Código de Proyecto", value=p_edit.get("codigo", "")
            )

            c4, c5, c6 = st.columns(3)
            opciones_tipo_proyecto = [
                "Upcycling",
                "Producción desde cero",
                "Cambio de logo",
                "Mixto",
                "Banner",
            ]
            tipo_actual = p_edit.get("tipo_proyecto", "Upcycling")
            idx_tipo = (
                opciones_tipo_proyecto.index(tipo_actual)
                if tipo_actual in opciones_tipo_proyecto
                else 0
            )

            proyecto_nom = c4.selectbox(
                "Tipo de Proyecto", opciones_tipo_proyecto, index=idx_tipo
            )

            fechas_raw = p_edit.get("fecha", " - ").split(" - ")
            f_ini_val = fechas_raw[0] if len(fechas_raw) > 0 else ""
            f_fin_val = fechas_raw[1] if len(fechas_raw) > 1 else ""

            fe_inicio = c5.text_input("Fecha Inicio", value=f_ini_val)
            fe_fin = c6.text_input("Fecha Término", value=f_fin_val)

            c7, c8, c9 = st.columns(3)
            responsable = c7.text_input(
                "Responsable", value=p_edit.get("responsable", "")
            )
            area = c8.text_input("Área", value=p_edit.get("area", ""))
            guia_remision = c9.text_input(
                "Nº Guía Remisión", value=p_edit.get("guia", "")
            )

            c10, c11 = st.columns(2)
            origen = c10.text_input("Punto Origen", value=p_edit.get("origen", ""))
            destino = c11.text_input("Punto Destino", value=p_edit.get("destino", ""))

        st.write("")

        with st.container(border=True):
            st.subheader("2. Ingreso de Material")
            if "num_items" not in st.session_state:
                st.session_state.num_items = 2

            col_btn1, col_btn2, _ = st.columns([1, 1, 4])
            if col_btn1.button("➕     Agregar Ítem"):
                st.session_state.num_items += 1
                st.rerun()
            if (
                col_btn2.button("➖     Quitar Ítem")
                and st.session_state.num_items > 1
            ):
                st.session_state.num_items -= 1
                st.rerun()

            lista_items = []
            peso_total_recibido = 0.0
            co2_evitado_total = 0.0
            total_piezas_ingresadas = 0
            opciones_prendas = sorted(list(FACTORES_CO2.keys()))

            for i in range(st.session_state.num_items):
                st.markdown(f"**Material {i+1}**")
                col_desc, col_unid, col_peso, col_tot, col_foto = st.columns(
                    [3, 1.5, 1.5, 1.5, 3]
                )

                desc = col_desc.selectbox(
                    "Tipo de Producto / Prenda", opciones_prendas, key=f"desc_{i}"
                )
                unid = col_unid.number_input(
                    "Ingreso (unid.)", min_value=0, value=0, key=f"unid_{i}"
                )
                peso_u = col_peso.number_input(
                    "Peso Unit. (kg)",
                    min_value=0.0,
                    value=0.0,
                    step=0.05,
                    key=f"peso_{i}",
                )
                p_total = unid * peso_u
                col_tot.text_input(
                    "Peso Total", value=f"{p_total:.2f} kg", disabled=True, key=f"tot_{i}"
                )
                foto = col_foto.file_uploader(
                    "Evidencia Foto", type=["jpg", "png", "jpeg"], key=f"foto_{i}"
                )

                if foto is not None:
                    col_foto.image(foto, width=80)

                factor = FACTORES_CO2.get(desc, 6.575)
                co2_item = p_total * factor
                co2_evitado_total += co2_item
                peso_total_recibido += p_total
                total_piezas_ingresadas += unid

                lista_items.append({
                    "descripcion": desc,
                    "unidades": unid,
                    "peso_unitario": peso_u,
                    "peso_total": p_total,
                    "foto": foto,
                    "co2_evitado": co2_item,
                })

            st.info(
                f"⚖️     **Total Material Recibido:** {peso_total_recibido:.2f} kg |"
                " **CO₂ Evitado Calculado:**"
                f" {co2_evitado_total:.2f} kg CO₂e"
            )

        st.write("")

        with st.container(border=True):
            st.subheader("3. Trazabilidad del Proceso en Upcycling")
            etapas_fijas = [
                {
                    "etapa": "Clasificación",
                    "fecha": datetime.date.today(),
                    "resp_defecto": "Evelyn Prada Vizarreta",
                    "peso": "0.00",
                    "tipo": "Registro interno",
                },
                {
                    "etapa": "Lavado",
                    "fecha": datetime.date.today(),
                    "resp_defecto": "Lavandería",
                    "peso": "0.00",
                    "tipo": "Servicio Externo",
                },
                {
                    "etapa": "Corte",
                    "fecha": datetime.date.today(),
                    "resp_defecto": "Taller de corte (5 integrantes)",
                    "peso": "0.00",
                    "tipo": "Pesaje real",
                },
                {
                    "etapa": "Confección",
                    "fecha": datetime.date.today(),
                    "resp_defecto": "Producción descentralizada",
                    "peso": "0.00",
                    "tipo": "Entrega / Recepción",
                },
            ]
            lista_trazabilidad = []
            peso_lavado_auto = 0.0
            peso_corte_auto = 0.0

            for i, item_fijo in enumerate(etapas_fijas):
                st.markdown(f"**Etapa {i+1}**")
                c_etapa, c_fecha, c_resp, c_edit_chk, c_peso, c_tipo, c_foto = (
                    st.columns([1.5, 1.5, 2, 1, 1.2, 1.8, 2])
                )

                e_nom = c_etapa.text_input(
                    "Etapa",
                    value=item_fijo["etapa"],
                    disabled=True,
                    key=f"tr_etapa_{i}",
                )
                e_fec_val = c_fecha.date_input(
                    "Fecha",
                    value=item_fijo["fecha"],
                    format="DD/MM/YYYY",
                    key=f"tr_fecha_{i}",
                )

                permitir_editar = c_edit_chk.checkbox("📝  Editar", key=f"chk_edit_{i}")
                e_res = c_resp.text_input(
                    "Responsable",
                    value=item_fijo["resp_defecto"],
                    disabled=not permitir_editar,
                    key=f"tr_resp_{i}",
                )

                e_pes_str = c_peso.text_input(
                    "Peso (kg)", value=item_fijo["peso"], key=f"tr_peso_{i}"
                )

                try:
                    e_pes_num = float(e_pes_str)
                except ValueError:
                    e_pes_num = 0.0

                if item_fijo["etapa"] == "Lavado":
                    peso_lavado_auto = e_pes_num
                elif item_fijo["etapa"] == "Corte":
                    peso_corte_auto = e_pes_num

                e_tip = c_tipo.text_input(
                    "Tipo Registro",
                    value=item_fijo["tipo"],
                    disabled=True,
                    key=f"tr_tipo_{i}",
                )
                e_fot = c_foto.file_uploader(
                    "Evidencia", type=["jpg", "png", "jpeg"], key=f"tr_foto_{i}"
                )

                if e_fot is not None:
                    c_foto.image(e_fot, width=70)

                lista_trazabilidad.append({
                    "etapa": e_nom,
                    "fecha": e_fec_val.strftime("%d/%m/%Y"),
                    "responsable": e_res,
                    "peso": e_pes_num,
                    "tipo_registro": e_tip,
                    "foto": e_fot,
                })

        st.write("")

        # 4. SALIDA DE PRODUCTOS (CORREGIDO)
        with st.container(border=True):
            st.subheader("4. Salida de Productos")

            if "num_prods" not in st.session_state:
                st.session_state.num_prods = 2

            cp_btn1, cp_btn2, _ = st.columns([1, 1, 4])
            if cp_btn1.button("➕     Agregar Producto"):
                st.session_state.num_prods += 1
                st.rerun()
            if (
                cp_btn2.button("➖     Quitar Producto")
                and st.session_state.num_prods > 1
            ):
                st.session_state.num_prods -= 1
                st.rerun()

            lista_productos = []
            total_prod_unid = 0

            for i in range(st.session_state.num_prods):
                st.markdown(f"**Producto {i+1}**")
                col_psel, col_pnom_nuevo, col_pcant, col_pfoto = st.columns(
                    [3, 2.5, 1.5, 3]
                )

                prod_seleccionado = col_psel.selectbox(
                    "Seleccionar Producto Base",
                    st.session_state.catalogo_productos,
                    key=f"prod_sel_{i}",
                )

                if prod_seleccionado == "➕     Otro (Escribir nuevo producto)":
                    nuevo_nombre = col_pnom_nuevo.text_input(
                        "Escriba el Nuevo Producto", key=f"prod_nuevo_txt_{i}"
                    )
                    nombre_final = (
                        nuevo_nombre.strip()
                        if nuevo_nombre.strip()
                        else f"Producto {i+1}"
                    )

                    if (
                        nuevo_nombre.strip()
                        and nuevo_nombre.strip() not in st.session_state.catalogo_productos
                    ):
                        st.session_state.catalogo_productos.insert(-1, nuevo_nombre.strip())
                else:
                    # CORREGIDO: Ahora muestra correctamente la selección actual del usuario en lugar de un texto estático
                    col_pnom_nuevo.text_input(
                        "Producto",
                        value=prod_seleccionado,
                        disabled=True,
                        key=f"prod_dis_{i}_{prod_seleccionado}",
                    )
                    nombre_final = prod_seleccionado

                p_cant = col_pcant.number_input(
                    "Cantidad (Unid.)", min_value=0, value=0, key=f"prod_cant_{i}"
                )
                p_foto = col_pfoto.file_uploader(
                    "Evidencia Foto", type=["jpg", "png", "jpeg"], key=f"prod_foto_{i}"
                )

                if p_foto is not None:
                    col_pfoto.image(p_foto, width=80)

                total_prod_unid += p_cant
                lista_productos.append(
                    {"producto": nombre_final, "cantidad": p_cant, "foto": p_foto}
                )

            st.success(
                "📦  **Suma Total de Productos Obtenidos:**"
                f" {total_prod_unid} unidades"
            )

        st.write("")

        with st.container(border=True):
            st.subheader("5. Balance de Material")
            st.info(
                f"⚖️     **Material Recibido (calculado automáticamente):** {peso_total_recibido:.2f} kg"
            )

            col_bm1, col_bm2 = st.columns(2)
            mat_transformado = col_bm1.number_input(
                "Material transformado en productos (kg)",
                min_value=0.0,
                value=0.0,
                step=0.1,
            )
            retazos_aprovechables = col_bm2.number_input(
                "Retazos aprovechables (kg)", min_value=0.0, value=0.0, step=0.1
            )

            col_bm3, _ = st.columns([1, 1])
            perdida_no_aprovechable = col_bm3.number_input(
                "Pérdida no aprovechable (kg)", min_value=0.0, value=0.0, step=0.1
            )

            total_procesado = (
                mat_transformado + retazos_aprovechables + perdida_no_aprovechable
            )

            if peso_total_recibido > 0:
                pct_aprovechamiento_total = (
                    (mat_transformado + retazos_aprovechables) / peso_total_recibido
                ) * 100
                pct_perdida = (perdida_no_aprovechable / peso_total_recibido) * 100
            else:
                pct_aprovechamiento_total = 0.0
                pct_perdida = 0.0

            st.markdown("##### Resumen de Indicadores")
            ind1, ind2, ind3 = st.columns(3)
            ind1.metric("Total Procesado", f"{total_procesado:.2f} kg")
            ind2.metric(
                "% Aprovechamiento Total", f"{pct_aprovechamiento_total:.2f}%"
            )
            ind3.metric("% Pérdida", f"{pct_perdida:.2f}%")

        st.write("")

        with st.container(border=True):
            st.subheader("6. Balance de Emisiones (CO₂e)")

            st.markdown("##### 🚚  A. Cálculo de Transporte")
            ct1, ct2, ct3 = st.columns(3)
            vehiculo_sel = ct1.selectbox(
                "Tipo de Vehículo Utilizado", list(FACTORES_TRANSPORTE.keys())
            )
            recorrido_tipo = ct2.selectbox(
                "Tipo de Recorrido", ["Ida y Vuelta (2)", "Ida sola (1)"]
            )
            distancia_km = ct3.number_input(
                "Distancia Recorrida (km)", min_value=0.0, value=0.0, step=0.5
            )

            factor_veh = FACTORES_TRANSPORTE[vehiculo_sel]
            mult_recorrido = 2.0 if "2" in recorrido_tipo else 1.0
            emisiones_transporte = (
                distancia_km
                * mult_recorrido
                * factor_veh["consumo"]
                * factor_veh["factor"]
            )

            st.caption(
                "Emisión de Transporte estimada:"
                f" **{emisiones_transporte:.2f} kg CO₂e**"
            )

            st.markdown(
                "##### ✂️  B. Lavandería y Taller de Corte (Calculado desde Trazabilidad)"
            )
            emisiones_lavado = peso_lavado_auto * 0.30
            emisiones_corte = peso_corte_auto * 0.05

            clav, ccort = st.columns(2)
            clav.info(
                f"**Lavandería ({peso_lavado_auto:.2f} kg):**"
                f" {emisiones_lavado:.2f} kg CO₂e *(Factor: 0.30)*"
            )
            ccort.info(
                f"**Corte ({peso_corte_auto:.2f} kg):** {emisiones_corte:.2f} kg CO₂e"
                " *(Factor: 0.05)*"
            )

            st.markdown("##### 🪡  C. Cálculo de Bordado")
            cb1, cb2 = st.columns(2)
            cant_prendas_bordado = cb1.number_input(
                "Cantidad de prendas que requieren bordado",
                min_value=0,
                value=0,
                step=1,
            )
            tipo_diseno_bordado = cb2.selectbox(
                "Tipo de Diseño / Complejidad", list(FACTORES_BORDADO.keys())
            )

            factor_bordado = FACTORES_BORDADO[tipo_diseno_bordado]
            emisiones_bordado = cant_prendas_bordado * factor_bordado

            st.caption(
                f"Emisión de Bordado estimada: **{emisiones_bordado:.2f} kg CO₂e**"
            )

            emisiones_proceso = (
                emisiones_transporte
                + emisiones_lavado
                + emisiones_corte
                + emisiones_bordado
            )
            co2_neto = co2_evitado_total - emisiones_proceso

            st.warning(
                "🌱  **Total Emisiones del Proceso:**"
                f" {emisiones_proceso:.2f} kg CO₂e | **Impacto Ambiental Neto"
                f" Evitado:** {co2_neto:.2f} kg CO₂e"
            )

        st.write("")

        with st.container(border=True):
            st.subheader("7. Equipo de Trabajo y Generación de Horas")
            st.markdown(
                "**Participación del personal en el proceso de upcycling y horas"
                " trabajadas por actividad**"
            )

            if peso_total_recibido <= 10:
                dias_calc_corte, hdia_calc_corte = 1, 3.0
                dias_calc_log, hdia_calc_log = 1, 2.0
            elif peso_total_recibido <= 30:
                dias_calc_corte, hdia_calc_corte = 1, 6.0
                dias_calc_log, hdia_calc_log = 1, 3.0
            elif peso_total_recibido <= 50:
                dias_calc_corte, hdia_calc_corte = 2, 6.0
                dias_calc_log, hdia_calc_log = 2, 3.0
            else:
                dias_calc_corte = max(2, int(peso_total_recibido / 25))
                hdia_calc_corte = 8.0
                dias_calc_log = max(2, int(peso_total_recibido / 25))
                hdia_calc_log = 4.0

            st.markdown("#### Operaciones – Corte y Logística")

            lista_operaciones = []
            total_horas_ops = 0.0

            h_col1, h_col2, h_col3, h_col4, h_col5, h_col6 = st.columns(
                [1.5, 2.5, 0.8, 1.2, 1.2, 1.2]
            )
            h_col1.markdown("**Rol**")
            h_col2.markdown("**Nombre**")
            h_col3.markdown("**Editar**")
            h_col4.markdown("**Días trabajados**")
            h_col5.markdown("**Hora/día**")
            h_col6.markdown("**Horas totales**")

            st.write("---")

            for idx, p_fijo in enumerate(PERSONAL_FIJO_OPERACIONES):
                c_rol, c_nom, c_chk, c_dias, c_hdia, c_tot = st.columns(
                    [1.5, 2.5, 0.8, 1.2, 1.2, 1.2]
                )

                rol_val = p_fijo["rol"]
                c_rol.text_input(
                    "Rol",
                    value=rol_val,
                    disabled=True,
                    key=f"ops_rol_{idx}",
                    label_visibility="collapsed",
                )

                editar_nom = c_chk.checkbox(
                    "✅", key=f"ops_chk_{idx}", label_visibility="collapsed"
                )
                nom_val = c_nom.text_input(
                    "Nombre",
                    value=p_fijo["nombre"],
                    disabled=not editar_nom,
                    key=f"ops_nom_{idx}",
                    label_visibility="collapsed",
                )

                if rol_val == "Logística":
                    val_dias_defecto = dias_calc_log
                    val_hdia_defecto = hdia_calc_log
                else:
                    val_dias_defecto = dias_calc_corte
                    val_hdia_defecto = hdia_calc_corte

                val_dias = c_dias.number_input(
                    "Días",
                    min_value=0,
                    value=int(val_dias_defecto),
                    step=1,
                    key=f"ops_dias_dyn_{idx}_{val_dias_defecto}",
                    label_visibility="collapsed",
                )
                val_hdia = c_hdia.number_input(
                    "Hrs/Día",
                    min_value=0.0,
                    value=float(val_hdia_defecto),
                    step=0.5,
                    key=f"ops_hdia_dyn_{idx}_{val_hdia_defecto}",
                    label_visibility="collapsed",
                )

                tot_hrs_pers = float(val_dias) * float(val_hdia)

                c_tot.text_input(
                    "Total",
                    value=f"{tot_hrs_pers:.2f}",
                    disabled=True,
                    key=f"ops_tot_{idx}_{val_dias}_{val_hdia}",
                    label_visibility="collapsed",
                )

                total_horas_ops += tot_hrs_pers
                lista_operaciones.append({
                    "rol": rol_val,
                    "nombre": nom_val,
                    "dias": val_dias,
                    "horas_dia": val_hdia,
                    "horas_totales": tot_hrs_pers,
                })

            st.write("---")

            st.markdown("#### Confección y Acabado – Asignación de Personal")
            st.caption(
                "Seleccione el rol correspondiente (Confección o Acabado) para cada persona "
                "y agregue o quite participantes según sea necesario. El acabado se calcula automáticamente al 20% del tiempo de confección."
            )

            lista_confeccion = []
            horas_confeccion_total = 0.0
            personas_confeccion_set = set()

            for idx, prod in enumerate(lista_productos):
                p_nom = prod["producto"]
                p_cant = prod["cantidad"]

                tiempo_base_ia = estimar_tiempo_unidad(p_nom)

                st.markdown(
                    f"**🧵  Producto {idx+1}: {p_nom}** *(Cantidad Total: {p_cant} unid "
                    f"| Base IA Confección: {tiempo_base_ia:.2f} hrs/unid)*"
                )

                key_num_pers = f"num_pers_prod_{idx}"
                if key_num_pers not in st.session_state:
                    st.session_state[key_num_pers] = 1

                col_b1, col_b2, _ = st.columns([1.5, 1.5, 5])
                if col_b1.button("➕  Persona", key=f"add_pers_{idx}"):
                    st.session_state[key_num_pers] += 1
                    st.rerun()
                if (
                    col_b2.button("➖  Quitar", key=f"del_pers_{idx}")
                    and st.session_state[key_num_pers] > 1
                ):
                    st.session_state[key_num_pers] -= 1
                    st.rerun()

                for p_idx in range(st.session_state[key_num_pers]):
                    c_rol, c_persona, c_cant_asig, c_tiempo, c_tot = st.columns(
                        [2, 2.5, 1.5, 2, 2]
                    )

                    rol_sel = c_rol.selectbox(
                        "Rol",
                        ["Confección", "Acabado"],
                        key=f"soc_rol_{idx}_{p_idx}",
                    )
                    persona_nom = c_persona.text_input(
                        "Persona Encargada",
                        placeholder=f"Encargado/a {p_idx+1}",
                        key=f"soc_pers_{idx}_{p_idx}",
                    )

                    cant_sugerida = max(
                        1, int(p_cant / st.session_state[key_num_pers])
                    ) if p_cant > 0 else 0

                    cant_asig = c_cant_asig.number_input(
                        "Unid. Asignadas",
                        min_value=0,
                        max_value=p_cant,
                        value=cant_sugerida,
                        key=f"soc_cant_{idx}_{p_idx}",
                    )

                    if rol_sel == "Acabado":
                        tiempo_unitario = round(tiempo_base_ia * 0.20, 3)
                        c_tiempo.text_input(
                            "Tiempo/Unid (hrs) [Acabado 20%]",
                            value=f"{tiempo_unitario:.3f} hrs",
                            disabled=True,
                            key=f"soc_tunit_calc_{idx}_{p_idx}",
                        )
                    else:
                        tiempo_unitario = c_tiempo.number_input(
                            "Tiempo/Unid (hrs)",
                            min_value=0.0,
                            value=float(tiempo_base_ia),
                            step=0.05,
                            key=f"soc_tunit_{idx}_{p_idx}_{p_nom}",
                        )

                    horas_persona = cant_asig * tiempo_unitario
                    c_tot.metric("Subtotal Horas", f"{horas_persona:.2f} hrs")

                    horas_confeccion_total += horas_persona
                    if persona_nom.strip():
                        personas_confeccion_set.add(persona_nom.strip())

                    lista_confeccion.append({
                        "producto": p_nom,
                        "cantidad": cant_asig,
                        "rol": rol_sel,
                        "persona": (
                            persona_nom.strip() if persona_nom.strip() else "Por asignar"
                        ),
                        "tiempo_unitario": tiempo_unitario,
                        "horas_totales": horas_persona,
                    })

                st.write("---")

            total_horas_social = total_horas_ops + horas_confeccion_total
            total_personas_social = len(PERSONAL_FIJO_OPERACIONES) + len(
                personas_confeccion_set
            )

            ms1, ms2, ms3 = st.columns(3)
            ms1.metric(
                "Horas Corte y Logística",
                f"{total_horas_ops:.2f} hrs",
                f"{len(PERSONAL_FIJO_OPERACIONES)} Personas",
            )
            ms2.metric(
                "Horas Confección y Acabado",
                f"{horas_confeccion_total:.2f} hrs",
                f"{len(personas_confeccion_set)} Artesanas",
            )
            ms3.metric(
                " TOTAL IMPACTO SOCIAL",
                f"{total_horas_social:.2f} hrs",
                f"{total_personas_social} Beneficiarios",
            )
        st.write("")

        def _validar_borrador(cliente_val, codigo_val):
            errores = []
            if not cliente_val.strip() and not codigo_val.strip():
                errores.append(
                    "Ingresa al menos el **Cliente** o el **Código de "
                    "Proyecto** para poder guardar el borrador."
                )
            return errores

        def _validar_informe_final(cliente_val, ruc_val, items_val):
            errores = []
            if not cliente_val.strip():
                errores.append("El campo **Cliente** es obligatorio.")
            if not ruc_val.strip():
                errores.append("El campo **RUC** es obligatorio.")
            if not items_val:
                errores.append(
                    "Debes registrar al menos **un ítem de material "
                    "ingresado** antes de generar el informe."
                )
            return errores

        b_col1, b_col2 = st.columns(2)

        if b_col1.button(
            "💾  Guardar Borrador (En Proceso)", use_container_width=True
        ):
            errores_borrador = _validar_borrador(cliente, codigo_proy)
            if errores_borrador:
                for err in errores_borrador:
                    st.error(err)
            else:
                try:
                    with st.spinner("Guardando borrador..."):
                        supabase.table("proyectos").upsert({
                            "codigo": codigo_proy if codigo_proy else "PROY-PENDIENTE",
                            "cliente": cliente if cliente else "CLIENTE POR DEFINIR",
                            "fecha": f"{fe_inicio} - {fe_fin}",
                            "ruc": ruc,
                            "estado": "EN_PROCESO",
                        }).execute()
                    st.success("✅  ¡Guardado con éxito como Borrador!")
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️  No se pudo guardar el borrador: {e}")

        if b_col2.button(
            "📄  Finalizar y Generar PDF Oficial",
            type="primary",
            use_container_width=True,
        ):
            errores_final = _validar_informe_final(cliente, ruc, lista_items)
            if errores_final:
                st.error(
                    "No se puede generar el informe oficial. Revisa lo "
                    "siguiente:"
                )
                for err in errores_final:
                    st.markdown(f"- {err}")
            else:
                guardado_ok = True
                try:
                    with st.spinner("Actualizando estado del proyecto..."):
                        supabase.table("proyectos").upsert({
                            "codigo": codigo_proy if codigo_proy else "SIN-CODIGO",
                            "cliente": cliente if cliente else "CLIENTE GENERAL",
                            "fecha": f"{fe_inicio} - {fe_fin}",
                            "ruc": ruc,
                            "estado": "COMPLETADO",
                        }).execute()
                except Exception as e:
                    guardado_ok = False
                    st.warning(
                        "⚠️  El informe se generará, pero **no se pudo "
                        "actualizar el estado del proyecto en la base de "
                        f"datos**: {e}"
                    )

                try:
                    with st.spinner("Generando informe PDF..."):
                        pdf_buffer = generar_pdf_oficial(
                            cliente=cliente,
                            ruc=ruc,
                            proyecto_nom=proyecto_nom,
                            codigo_proy=codigo_proy,
                            fe_inicio=fe_inicio,
                            fe_fin=fe_fin,
                            responsable=responsable,
                            area=area,
                            tipo_material="Poliéster / Algodón",
                            valorizacion="Upcycling / Reciclaje Textil",
                            unidad_medida="Kilogramos / Piezas",
                            guia_remision=guia_remision,
                            origen=origen,
                            destino=destino,
                            lista_items=lista_items,
                            lista_trazabilidad=lista_trazabilidad,
                            lista_productos=lista_productos,
                            mat_transformado=mat_transformado,
                            retazos_aprovechables=retazos_aprovechables,
                            perdida_no_aprovechable=perdida_no_aprovechable,
                            total_procesado=total_procesado,
                            pct_aprovechamiento_total=pct_aprovechamiento_total,
                            pct_perdida=pct_perdida,
                            lista_operaciones_pdf=lista_operaciones,
                            lista_confeccion=lista_confeccion,
                            total_horas_social=total_horas_social,
                            total_personas_social=total_personas_social,
                            co2_evitado_total=co2_evitado_total,
                            emisiones_transporte=emisiones_transporte,
                            emisiones_lavado=emisiones_lavado,
                            emisiones_corte=emisiones_corte,
                            emisiones_bordado=emisiones_bordado,
                        )
                except Exception as e:
                    st.error(
                        "⚠️  Ocurrió un error al generar el PDF. No se pudo "
                        "completar el informe."
                    )
                    with st.expander("Detalle técnico del error"):
                        st.exception(e)
                    st.stop()

                if guardado_ok:
                    st.success("✅  ¡Informe Técnico Generado Exitosamente!")
                st.download_button(
                    label="📥     DESCARGAR INFORME TÉCNICO EN PDF",
                    data=pdf_buffer,
                    file_name=(
                        "Informe_Trazabilidad_"
                        f"{codigo_proy if codigo_proy else 'PROYECTO'}.pdf"
                    ),
                    mime="application/pdf",
                    use_container_width=True,
                )

    elif st.session_state.pestaña_activa == "📋  Proyectos en Proceso":
        st.subheader("📋  Proyectos Guardados en Borrador (En Proceso)")
        proyectos_lista = cargar_proyectos(estado="EN_PROCESO")

        if proyectos_lista:
            df = pd.DataFrame(proyectos_lista)
            st.dataframe(df, use_container_width=True)

            st.write("---")
            st.markdown("##### Seleccionar proyecto para continuar editando:")
            col_sel, col_btn = st.columns([3, 1])
            opciones_proy = {
                f"{p.get('cliente', '')} ({p.get('codigo', '')})": p
                for p in proyectos_lista
            }
            seleccionado = col_sel.selectbox(
                "Seleccione un proyecto", list(opciones_proy.keys())
            )

            if col_btn.button(
                "📂  Cargar Borrador", type="primary", use_container_width=True
            ):
                st.session_state.proyecto_editar = opciones_proy[seleccionado]
                st.session_state.pestaña_activa = "➕     Nuevo Reporte PDF"
                st.rerun()
        else:
            st.info("No hay proyectos pendientes o guardados en proceso.")

    elif st.session_state.pestaña_activa == "📊  Dashboard 2026":
        st.subheader("📊  Indicadores Globales de Sostenibilidad 2026")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Material Procesado", "1,245.80 kg", "+15% vs 2025")
        m2.metric("CO₂e Neto Evitado", "8,920.40 kg", "+22%")
        m3.metric("Aprovechamiento Promedio", "89.4%", "1.2%")
        m4.metric("Horas Trabajo Generadas", "3,450 hrs", "+310 hrs")

        st.write("---")
        st.info(
            "📈  Aquí se visualizarán los gráficos acumulados conforme guardes"
            " informes terminados en la base de datos."
        )

    elif st.session_state.pestaña_activa == "📜  Historial Completo":
        st.subheader("📜  Histórico de Proyectos Finalizados")
        proyectos_completados = cargar_proyectos(estado="COMPLETADO")

        if proyectos_completados:
            df_comp = pd.DataFrame(proyectos_completados)
            st.dataframe(df_comp, use_container_width=True)
        else:
            st.info(
                "Aún no se registran proyectos marcados como COMPLETADO en la base de"
                " datos."
            )
