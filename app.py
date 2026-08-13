import io
import datetime
import streamlit as st
import pandas as pd
from supabase import create_client, Client

# Importaciones para ReportLab
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# --- FACTORES DE EMISIÓN DE MATERIALES ---
FACTORES_CO2 = {
    "Banner": 9.5, "Bata de laboratorio": 6.575, "Bolsas": 8.0, "Camisa": 6.575,
    "Camisa algodón": 5.0, "Camisa drill": 5.9, "Camisa ignífuga": 5.35, "Camisa jean / denim": 5.0,
    "Camisaco": 5.0, "Camisaco drill": 5.9, "Camisaco drill con cinta": 6.25, "Casaca": 6.575,
    "Casaca drill": 5.9, "Casaca polar": 6.0, "Casaca polar con cinta reflectiva": 6.3,
    "Casaca térmica": 6.1, "Chaleco": 6.575, "Chaleco con cinta": 6.925, "Chaleco de seguridad": 9.75,
    "Chaleco Fluorescente": 9.625, "Chaleco polar": 6.0, "Chaleco reversible": 9.5, "Chompa": 7.1,
    "Chompa con cinta reflectiva": 7.45, "Chompa Jorge Chavez": 6.0,
    "Chompa Jorge Chavez con cinta reflectiva": 6.3, "Chompa polar": 6.0, "Enterizo": 6.575,
    "Gorro": 7.925, "Impermeable": 9.425, "Mameluco": 6.575, "Mameluco acolchado": 5.825,
    "Mameluco drill": 5.9, "Mameluco jean reflectivo": 5.35, "Merma": 6.575, "Overol": 6.575,
    "Pantalón": 6.575, "Pantalón algodón": 5.0, "Pantalón drill": 5.9, "Pantalón drill con cinta": 6.25,
    "Pantalón ignífugo": 5.35, "Pantalón jean": 5.0, "Pantalón jean / drill": 5.675,
    "Pantalón jean con cinta reflectiva": 5.35, "Pantalón polar": 6.0, "Pantalón térmico": 6.0,
    "Polera": 5.0, "Polera polar": 6.0, "Polo": 6.8, "Polo algodón": 5.0,
    "Polo con cinta reflectiva": 6.925, "Polo manga corta": 6.8, "Polo manga larga": 6.8,
    "Polo manga larga con cinta reflectiva": 6.7, "Polo piqué": 5.0, "Short": 6.575,
    "Toalla": 5.0, "Otro": 6.575
}

# --- FACTORES DE TRANSPORTE ---
FACTORES_TRANSPORTE = {
    "Auto": {"consumo": 0.10, "factor": 2.31},
    "Minivan": {"consumo": 0.12, "factor": 2.00},
    "Mototaxi": {"consumo": 0.04, "factor": 2.31},
    "Moto": {"consumo": 0.03, "factor": 2.31},
    "Camión mediano": {"consumo": 0.30, "factor": 2.68},
    "Camión grande": {"consumo": 0.40, "factor": 2.68}
}

# --- FACTORES DE BORDADO ---
FACTORES_BORDADO = {
    "Sin bordado / Ninguno": 0.0,
    "Simple (5 min/pieza)": 0.020,
    "Medio (9 min/pieza)": 0.037,
    "Complejo (10 min/pieza)": 0.041
}

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Pequeños Detalles - Sistema de Trazabilidad",
    page_icon="🧵",
    layout="wide"
)

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    /* Ocultar flechas numéricas */
    div[data-testid="stNumberInput"] button { display: none !important; }
    div[data-testid="stNumberInput"] input { text-align: left; }
    
    /* Header principal moderno */
    .hero-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 50%, #2563EB 100%);
        color: white;
        padding: 24px 30px;
        border-radius: 16px;
        box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.3);
        margin-bottom: 25px;
    }
    .hero-header h1 {
        color: #ffffff !important;
        font-weight: 800;
        font-size: 1.8rem;
        margin: 0;
    }
    .hero-header p {
        color: #93C5FD !important;
        margin: 4px 0 0 0;
        font-size: 0.95rem;
    }

    /* Badges de estado */
    .badge-wip {
        background-color: #FEF3C7;
        color: #D97706;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.8rem;
        border: 1px solid #FCD34D;
    }

    /* Estilos para el sidebar */
    div[data-testid="stSidebar"] {
        background-color: #F8FAFC;
        border-right: 1px solid #E2E8F0;
    }
    
    .sidebar-section-title {
        color: #475569;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 15px;
        margin-bottom: 8px;
    }

    /* Aumentar tamaño y peso del título dentro del sidebar */
    div[data-testid="stSidebar"] .stMarkdown h1,
    div[data-testid="stSidebar"] .stMarkdown h2,
    div[data-testid="stSidebar"] .stMarkdown h3,
    div[data-testid="stSidebar"] .stMarkdown > div p {
        font-size: 18px !important;   /* ajusta el tamaño a tu gusto */
        font-weight: 800 !important;
        margin: 0;
        color: #0F172A !important;
    }

    /* Subtítulo / texto pequeño bajo el título */
    div[data-testid="stSidebar"] .stCaption,
    div[data-testid="stSidebar"] .stMarkdown .small-subtitle {
        font-size: 12px !important;
        color: #64748B !important;
        margin-top: 2px;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["SUPABASE_URL"]
    key = st.secrets["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception:
    st.error("Error al conectar con Supabase. Revisa las credenciales en Secrets.")

def cargar_proyectos(estado=None):
    try:
        query = supabase.table("proyectos").select("*")
        if estado:
            query = query.eq("estado", estado)
        response = query.execute()
        return response.data
    except Exception:
        return []

# --- CANVAS PARA PIE DE PÁGINA Y HEADER EN EL PDF ---
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
        self.drawString(36, 20, "Pequeños Detalles Handmade Perú S.A.C. - Trazabilidad y Sostenibilidad Textil")
        self.drawRightString(576, 20, f"Página {self._pageNumber}")
        self.restoreState()

# --- GENERADOR DEL PDF OFICIAL ---
def generar_pdf_oficial(
    cliente, ruc, proyecto_nom, codigo_proy, fe_inicio, fe_fin, responsable, area,
    tipo_material, valorizacion, unidad_medida, guia_remision, origen, destino,
    lista_items, lista_trazabilidad, lista_productos,
    mat_transformado, retazos_aprovechables, perdida_no_aprovechable, total_procesado,
    pct_aprovechamiento_total, pct_perdida,
    horas_totales, cant_personas,
    co2_evitado_total, emisiones_transporte, emisiones_lavado, emisiones_corte, emisiones_bordado
):
    kg_recibidos = sum([item["peso_total"] for item in lista_items])
    emisiones_proceso = emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado
    co2_neto = co2_evitado_total - emisiones_proceso

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)

    styles = getSampleStyleSheet()
    h1_style = ParagraphStyle('H1', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=14, textColor=colors.HexColor('#1E293B'), alignment=1, spaceAfter=2)
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#64748B'), alignment=1, spaceAfter=12)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#0F172A'), spaceBefore=10, spaceAfter=6)
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#334155'), leading=10)
    cell_bold = ParagraphStyle('CellB', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#0F172A'), leading=10)
    card_title = ParagraphStyle('CardT', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor('#0F172A'), alignment=1)
    card_sub = ParagraphStyle('CardS', parent=styles['Normal'], fontName='Helvetica', fontSize=7, textColor=colors.HexColor('#475569'), alignment=1)

    elements = []

    # Encabezado PDF
    elements.append(Paragraph("INFORME TÉCNICO DE VALORIZACIÓN TEXTIL", h1_style))
    elements.append(Paragraph(f"Medición de Impacto Ambiental, Trazabilidad y Gestión Social de Upcycling<br/><b>CÓDIGO: {codigo_proy}</b>", sub_style))

    # Tarjetas Métricas PDF
    cards_data = [
        [
            Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", card_title),
            Paragraph(f"<b>{pct_aprovechamiento_total:.2f}%</b>", card_title),
            Paragraph(f"<b>{co2_neto:.2f} kg</b>", card_title),
            Paragraph(f"<b>{horas_totales:.2f} hrs</b>", card_title)
        ],
        [
            Paragraph("MATERIAL RECIBIDO", card_sub),
            Paragraph("% APROVECHAMIENTO", card_sub),
            Paragraph("CO₂e NETO EVITADO", card_sub),
            Paragraph(f"TRABAJO GENERADO ({cant_personas} PERS.)", card_sub)
        ]
    ]
    t_cards = Table(cards_data, colWidths=[135, 135, 135, 135])
    t_cards.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    elements.append(t_cards)
    elements.append(Spacer(1, 8))

    # 1. Ficha General
    elements.append(Paragraph("1. FICHA GENERAL DEL PROYECTO Y TRAZABILIDAD", h2_style))
    data_ficha = [
        [Paragraph("Cliente / Empresa", cell_bold), Paragraph(f"{cliente} (RUC: {ruc})", cell_style), Paragraph("Área / Responsable", cell_bold), Paragraph(f"{area} / {responsable}", cell_style)],
        [Paragraph("Nombre del Proyecto", cell_bold), Paragraph(proyecto_nom, cell_style), Paragraph("Periodo de Ejecución", cell_bold), Paragraph(f"{fe_inicio} al {fe_fin}", cell_style)],
        [Paragraph("Tipo de Material", cell_bold), Paragraph(tipo_material, cell_style), Paragraph("Tipo de Valorización", cell_bold), Paragraph(valorizacion, cell_style)],
        [Paragraph("Guía de Remisión", cell_bold), Paragraph(guia_remision, cell_style), Paragraph("Unidad de Medida", cell_bold), Paragraph(unidad_medida, cell_style)],
        [Paragraph("Punto de Origen", cell_bold), Paragraph(origen, cell_style), Paragraph("Punto de Destino", cell_bold), Paragraph(destino, cell_style)],
    ]
    t_ficha = Table(data_ficha, colWidths=[100, 170, 100, 170])
    t_ficha.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#F8FAFC')),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_ficha)
    elements.append(Spacer(1, 8))

    def obtener_imagen_pdf(foto_file, width, height):
        if foto_file is not None:
            try:
                foto_file.seek(0)
                img_data = io.BytesIO(foto_file.read())
                foto_file.seek(0)
                return Image(img_data, width=width, height=height)
            except Exception:
                return Paragraph("Sin foto", cell_style)
        return Paragraph("Sin foto", cell_style)

    # 2. Ingreso de Material
    elements.append(Paragraph("2. INGRESO DE MATERIAL Y EVIDENCIA FOTOGRÁFICA", h2_style))
    data_prendas_pdf = [[
        Paragraph("Ítem", cell_bold), Paragraph("Tipo de Producto / Prenda", cell_bold),
        Paragraph("Ingreso (unid)", cell_bold), Paragraph("Peso unit. (kg)", cell_bold),
        Paragraph("Peso total (kg)", cell_bold), Paragraph("Evidencia", cell_bold)
    ]]

    total_unidades_ingreso = 0
    for i, item in enumerate(lista_items, 1):
        total_unidades_ingreso += item["unidades"]
        img_cell = obtener_imagen_pdf(item["foto"], 45, 45)

        data_prendas_pdf.append([
            Paragraph(str(i), cell_style), Paragraph(item["descripcion"], cell_style),
            Paragraph(str(item["unidades"]), cell_style), Paragraph(f"{item['peso_unitario']:.2f}", cell_style),
            Paragraph(f"{item['peso_total']:.2f}", cell_style), img_cell
        ])

    data_prendas_pdf.append([
        Paragraph("<b>TOTAL MATERIAL RECIBIDO</b>", cell_bold), "",
        Paragraph(f"<b>{total_unidades_ingreso}</b>", cell_bold), Paragraph("-", cell_bold),
        Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", cell_bold), Paragraph("-", cell_bold)
    ])

    t_prendas = Table(data_prendas_pdf, colWidths=[30, 180, 80, 75, 75, 100])
    t_prendas.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F1F5F9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('SPAN', (0, -1), (1, -1)),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (2,0), (4,-1), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_prendas)
    elements.append(Spacer(1, 8))

    # 3. Trazabilidad
    elements.append(Paragraph("3. TRAZABILIDAD DEL PROCESO EN UPCYCLING", h2_style))
    data_traza_pdf = [[
        Paragraph("Etapa", cell_bold), Paragraph("Fecha", cell_bold),
        Paragraph("Responsable", cell_bold), Paragraph("Peso (kg)", cell_bold),
        Paragraph("Tipo de Registro", cell_bold), Paragraph("Evidencia", cell_bold)
    ]]

    for t_item in lista_trazabilidad:
        img_cell = obtener_imagen_pdf(t_item["foto"], 45, 35)

        data_traza_pdf.append([
            Paragraph(t_item["etapa"], cell_style), Paragraph(t_item["fecha"], cell_style),
            Paragraph(t_item["responsable"], cell_style), Paragraph(f"{t_item['peso']:.2f}", cell_style),
            Paragraph(t_item["tipo_registro"], cell_style), img_cell
        ])

    t_traza = Table(data_traza_pdf, colWidths=[90, 70, 130, 60, 100, 90])
    t_traza.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (3,-1), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_traza)

    elements.append(PageBreak())

    # 4. SALIDA DE PRODUCTOS
    elements.append(Paragraph("4. SALIDA DE PRODUCTOS", h2_style))
    elements.append(Paragraph("Registro de productos obtenidos a partir del proceso de upcycling", sub_style))

    data_prod_pdf = [[
        Paragraph("Producto", cell_bold),
        Paragraph("Cantidad (Unidades)", cell_bold),
        Paragraph("Evidencia", cell_bold)
    ]]

    total_prod_unidades = 0
    for p_item in lista_productos:
        total_prod_unidades += p_item["cantidad"]
        img_cell = obtener_imagen_pdf(p_item["foto"], 60, 60)

        data_prod_pdf.append([
            Paragraph(p_item["producto"], cell_style),
            Paragraph(str(p_item["cantidad"]), cell_style),
            img_cell
        ])

    data_prod_pdf.append([
        Paragraph("<b>SUMA TOTAL</b>", cell_bold),
        Paragraph(f"<b>{total_prod_unidades}</b>", cell_bold),
        Paragraph("-", cell_bold)
    ])

    t_prod = Table(data_prod_pdf, colWidths=[240, 150, 150])
    t_prod.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F1F5F9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('ALIGN', (2,0), (2,-1), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t_prod)
    elements.append(Spacer(1, 15))

    # 5. BALANCE DE MATERIAL
    elements.append(Paragraph("5. BALANCE DE MATERIAL", h2_style))
    elements.append(Paragraph("Resumen del flujo y aprovechamiento del material procesado", sub_style))

    data_balance = [
        [Paragraph("<b>Concepto</b>", cell_bold), Paragraph("<b>Cantidad (kg)</b>", cell_bold)],
        [Paragraph("Material recibido", cell_style), Paragraph(f"{kg_recibidos:.2f}", cell_style)],
        [Paragraph("Material transformado en productos", cell_style), Paragraph(f"{mat_transformado:.2f}", cell_style)],
        [Paragraph("Retazos aprovechables", cell_style), Paragraph(f"{retazos_aprovechables:.2f}", cell_style)],
        [Paragraph("Pérdida no aprovechable", cell_style), Paragraph(f"{perdida_no_aprovechable:.2f}", cell_style)],
        [Paragraph("Total procesado", cell_style), Paragraph(f"{total_procesado:.2f}", cell_style)],
        [Paragraph("% Aprovechamiento", cell_style), Paragraph(f"{pct_aprovechamiento_total:.2f} %", cell_style)],
        [Paragraph("% Pérdida", cell_style), Paragraph(f"{pct_perdida:.2f} %", cell_style)],
    ]

    t_balance = Table(data_balance, colWidths=[300, 200])
    t_balance.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F8FAFC')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_balance)
    elements.append(Spacer(1, 12))

    # 6. EMISIONES
    elements.append(Paragraph("6. EMISIONES (kg CO2e)", h2_style))
    data_emisiones = [
        [Paragraph("Concepto", cell_bold), Paragraph("CO2e (kg)", cell_bold)],
        [Paragraph("Emisiones transporte", cell_style), Paragraph(f"{emisiones_transporte:.2f}", cell_style)],
        [Paragraph("Emisiones lavado", cell_style), Paragraph(f"{emisiones_lavado:.2f}", cell_style)],
        [Paragraph("Emisiones corte", cell_style), Paragraph(f"{emisiones_corte:.2f}", cell_style)],
        [Paragraph("Emisiones bordado", cell_style), Paragraph(f"{emisiones_bordado:.2f}", cell_style)],
        [Paragraph("CO2e evitado (total)", cell_bold), Paragraph(f"{co2_evitado_total:.2f}", cell_bold)],
        [Paragraph("CO2e neto", cell_bold), Paragraph(f"{co2_neto:.2f}", cell_bold)],
    ]

    t_emisiones = Table(data_emisiones, colWidths=[300, 200])
    t_emisiones.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_emisiones)
    elements.append(Spacer(1, 12))

    # Pie / Firma
    elements.append(Paragraph("Documento generado por Pequeños Detalles", cell_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"Fecha de generación: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", cell_style))

    # Construir PDF
    try:
        doc.build(elements, canvasmaker=ReporteCanvas)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        # En caso de error al generar PDF, devolver None para manejarlo fuera
        return None
