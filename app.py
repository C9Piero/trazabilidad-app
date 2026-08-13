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

# --- EQUIPO HABITUAL CORTE Y LOGÍSTICA ---
EQUIPO_CORTE_LOGISTICA_PREDETERMINADO = [
    {"rol": "Corte", "nombre": "Maria Isabel Estrada Sandoval", "dias": 2, "horas_dia": 8.5},
    {"rol": "Corte", "nombre": "Genaro Jara García", "dias": 2, "horas_dia": 8.5},
    {"rol": "Corte", "nombre": "Luciana Jara estrada", "dias": 2, "horas_dia": 8.5},
    {"rol": "Corte", "nombre": "Felicita Sandoval vilchez", "dias": 2, "horas_dia": 8.5},
    {"rol": "Corte", "nombre": "Nicolle Estrada", "dias": 2, "horas_dia": 8.5},
    {"rol": "Logística", "nombre": "Evelyn Prada Vizarreta", "dias": 3, "horas_dia": 3.0},
]

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Pequeños Detalles - Sistema de Trazabilidad",
    page_icon="🧵",
    layout="wide"
)

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    div[data-testid="stNumberInput"] button { display: none !important; }
    div[data-testid="stNumberInput"] input { text-align: left; }
    
    .hero-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 50%, #2563EB 100%);
        color: white;
        padding: 24px 30px;
        border-radius: 16px;
        box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.3);
        margin-bottom: 25px;
    }
    .hero-header h1 { color: #ffffff !important; font-weight: 800; font-size: 1.8rem; margin: 0; }
    .hero-header p { color: #93C5FD !important; margin: 4px 0 0 0; font-size: 0.95rem; }

    div[data-testid="stSidebar"] { background-color: #F8FAFC; border-right: 1px solid #E2E8F0; }
    .sidebar-section-title { color: #475569; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 15px; margin-bottom: 8px; }
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

# --- CANVAS REPORTLAB ---
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
    lista_corte_logistica, lista_confeccion, total_horas_corte_log, total_horas_conf, total_horas_social, total_personas_social,
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

    elements.append(Paragraph("INFORME TÉCNICO DE VALORIZACIÓN TEXTIL", h1_style))
    elements.append(Paragraph(f"Medición de Impacto Ambiental, Trazabilidad y Gestión Social de Upcycling<br/><b>CÓDIGO: {codigo_proy}</b>", sub_style))

    cards_data = [
        [
            Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", card_title),
            Paragraph(f"<b>{pct_aprovechamiento_total:.2f}%</b>", card_title),
            Paragraph(f"<b>{co2_neto:.2f} kg</b>", card_title),
            Paragraph(f"<b>{total_horas_social:.1f} hrs</b>", card_title)
        ],
        [
            Paragraph("MATERIAL RECIBIDO", card_sub),
            Paragraph("% APROVECHAMIENTO", card_sub),
            Paragraph("CO₂e NETO EVITADO", card_sub),
            Paragraph(f"TRABAJO GENERADO ({total_personas_social} PERS.)", card_sub)
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

    elements.append(Paragraph("4. SALIDA DE PRODUCTOS", h2_style))
    data_prod_pdf = [[Paragraph("Producto", cell_bold), Paragraph("Cantidad (Unidades)", cell_bold), Paragraph("Evidencia", cell_bold)]]
    total_prod_unidades = 0
    for p_item in lista_productos:
        total_prod_unidades += p_item["cantidad"]
        img_cell = obtener_imagen_pdf(p_item["foto"], 50, 50)
        data_prod_pdf.append([Paragraph(p_item["producto"], cell_style), Paragraph(str(p_item["cantidad"]), cell_style), img_cell])

    data_prod_pdf.append([Paragraph("<b>SUMA TOTAL</b>", cell_bold), Paragraph(f"<b>{total_prod_unidades}</b>", cell_bold), Paragraph("-", cell_bold)])
    t_prod = Table(data_prod_pdf, colWidths=[240, 150, 150])
    t_prod.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F1F5F9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_prod)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("5. BALANCE DE MATERIAL", h2_style))
    data_balance = [
        [Paragraph("<b>Concepto</b>", cell_bold), Paragraph("<b>Cantidad (kg)</b>", cell_bold)],
        [Paragraph("Material recibido", cell_style), Paragraph(f"{kg_recibidos:.2f}", cell_style)],
        [Paragraph("Material transformado en productos", cell_style), Paragraph(f"{mat_transformado:.2f}", cell_style)],
        [Paragraph("Retazos aprovechables", cell_style), Paragraph(f"{retazos_aprovechables:.2f}", cell_style)],
        [Paragraph("Pérdida no aprovechable", cell_style), Paragraph(f"{perdida_no_aprovechable:.2f}", cell_style)],
        [Paragraph("<b>Total procesado</b>", cell_bold), Paragraph(f"<b>{total_procesado:.2f}</b>", cell_bold)],
        [Paragraph("<b>Indicador</b>", cell_bold), Paragraph("<b>Valor</b>", cell_bold)],
        [Paragraph("% aprovechamiento total", cell_style), Paragraph(f"{pct_aprovechamiento_total:.2f}%", cell_style)],
        [Paragraph("% pérdida", cell_style), Paragraph(f"{pct_perdida:.2f}%", cell_style)],
    ]
    t_balance = Table(data_balance, colWidths=[340, 200])
    t_balance.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
        ('BACKGROUND', (0,6), (-1,6), colors.HexColor('#F5D0FE')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_balance)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("6. RESUMEN DE IMPACTO AMBIENTAL (CO₂e)", h2_style))
    data_co2_box = [
        [Paragraph("<b>(+) CO₂ Evitado por Upcycling</b>", card_sub), Paragraph("<b>(-) Emisiones del Proceso</b>", card_sub), Paragraph("<b>(=) Impacto Ambiental Neto</b>", card_sub)],
        [Paragraph(f"<b>{co2_evitado_total:.2f} kg CO₂e</b>", card_title), Paragraph(f"<b>{emisiones_proceso:.2f} kg CO₂e</b>", card_title), Paragraph(f"<b>{co2_neto:.2f} kg CO₂e</b>", card_title)]
    ]
    t_co2_box = Table(data_co2_box, colWidths=[180, 180, 180])
    t_co2_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t_co2_box)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("7. IMPACTO SOCIAL Y EMPLEO GENERADO", h2_style))
    
    elements.append(Paragraph("<b>Operaciones – Corte y Logística</b>", cell_bold))
    data_corte_pdf = [[Paragraph("Rol", cell_bold), Paragraph("Nombre", cell_bold), Paragraph("Días trabajados", cell_bold), Paragraph("Hora/día", cell_bold), Paragraph("Horas totales", cell_bold)]]
    for row in lista_corte_logistica:
        data_corte_pdf.append([Paragraph(row["rol"], cell_style), Paragraph(row["nombre"], cell_style), Paragraph(str(row["dias"]), cell_style), Paragraph(f"{row['horas_dia']:.1f}", cell_style), Paragraph(f"{row['horas_totales']:.1f}", cell_style)])
    data_corte_pdf.append([Paragraph("<b>Subtotal Corte y Logística</b>", cell_bold), "", "", "", Paragraph(f"<b>{total_horas_corte_log:.1f} hrs</b>", cell_bold)])
    
    t_corte = Table(data_corte_pdf, colWidths=[100, 200, 80, 80, 80])
    t_corte.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F1F5F9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('SPAN', (0, -1), (3, -1)),
        ('ALIGN', (2,0), (-1,-1), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_corte)
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("<b>Producción – Confección y Acabado</b>", cell_bold))
    data_conf_pdf = [[Paragraph("Rol", cell_bold), Paragraph("Producto", cell_bold), Paragraph("Nombre", cell_bold), Paragraph("Cantidad", cell_bold), Paragraph("Tiempo por unidad (h)", cell_bold), Paragraph("Horas generadas", cell_bold)]]
    for row in lista_confeccion:
        data_conf_pdf.append([Paragraph(row["rol"], cell_style), Paragraph(row["producto"], cell_style), Paragraph(row["nombre"], cell_style), Paragraph(str(row["cantidad"]), cell_style), Paragraph(f"{row['tiempo_unitario']:.2f}", cell_style), Paragraph(f"{row['horas_generadas']:.1f}", cell_style)])
    data_conf_pdf.append([Paragraph("<b>Subtotal Confección y Acabado</b>", cell_bold), "", "", "", "", Paragraph(f"<b>{total_horas_conf:.1f} hrs</b>", cell_bold)])
    
    t_conf = Table(data_conf_pdf, colWidths=[70, 130, 140, 50, 75, 75])
    t_conf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F1F5F9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('SPAN', (0, -1), (4, -1)),
        ('ALIGN', (3,0), (-1,-1), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_conf)

    doc.build(elements, canvasmaker=ReporteCanvas)
    buffer.seek(0)
    return buffer

# --- ESTADOS DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "pestaña_activa" not in st.session_state:
    st.session_state.pestaña_activa = "➕ Nuevo Reporte PDF"

if "proyecto_editar" not in st.session_state:
    st.session_state.proyecto_editar = {}

USUARIO_CORRECTO = "admin"
PASSWORD_CORRECTO = "pequenos2026"

if not st.session_state.autenticado:
    st.markdown("""
        <div style="text-align: center; padding: 40px 10px;">
            <h1 style="color: #1E293B; font-size: 2.2rem; font-weight: 800;">🧵 Pequeños Detalles</h1>
            <p style="color: #64748B; font-size: 1.1rem;">Handmade Perú S.A.C. — Gestión de Sostenibilidad</p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            st.subheader("🔑 Iniciar Sesión")
            usuario_input = st.text_input("Usuario")
            password_input = st.text_input("Contraseña", type="password")
            
            if st.button("Ingresar al Sistema", use_container_width=True, type="primary"):
                if usuario_input == USUARIO_CORRECTO and password_input == PASSWORD_CORRECTO:
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("⚠️ Usuario o contraseña incorrectos.")

else:
    proyectos_wip = cargar_proyectos(estado="EN_PROCESO")

    with st.sidebar:
        st.markdown("### 🧵 Pequeños Detalles")
        st.caption("Panel de Control Interno | 2026")
        st.write("---")

        if st.button("✨ Nuevo Reporte PDF", use_container_width=True, type="primary" if st.session_state.pestaña_activa == "➕ Nuevo Reporte PDF" else "secondary"):
            st.session_state.proyecto_editar = {}
            st.session_state.pestaña_activa = "➕ Nuevo Reporte PDF"
            st.rerun()

        st.markdown('<p class="sidebar-section-title">Proyectos Pendientes</p>', unsafe_allow_html=True)
        if proyectos_wip:
            for p in proyectos_wip:
                cli_nombre = p.get('cliente', 'Sin Nombre')
                cod_ref = p.get('codigo', '')
                label_btn = f"🔸 {cli_nombre}" + (f" ({cod_ref})" if cod_ref else "")
                es_activo = st.session_state.proyecto_editar.get('id') == p.get('id')
                if st.button(label_btn, key=f"side_proj_{p.get('id', cod_ref)}", use_container_width=True, type="primary" if es_activo else "secondary"):
                    st.session_state.proyecto_editar = p
                    st.session_state.pestaña_activa = "➕ Nuevo Reporte PDF"
                    st.rerun()
        else:
            st.caption("🟢 No hay proyectos en borrador")

        st.write("---")
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.autenticado = False
            st.session_state.proyecto_editar = {}
            st.rerun()

    st.markdown(f"""
        <div class="hero-header">
            <h1>🧵 Sistema de Gestión de Informes Técnicos</h1>
            <p>Sección Activa: <b>{st.session_state.pestaña_activa}</b></p>
        </div>
    """, unsafe_allow_html=True)

    if st.session_state.pestaña_activa == "➕ Nuevo Reporte PDF":
        p_edit = st.session_state.proyecto_editar

        # 1. FICHA GENERAL
        with st.container(border=True):
            st.subheader("1. Ficha General del Proyecto")
            c1, c2, c3 = st.columns(3)
            cliente = c1.text_input("Cliente / Empresa", value=p_edit.get("cliente", ""))
            ruc = c2.text_input("RUC", value=p_edit.get("ruc", ""))
            codigo_proy = c3.text_input("Código de Proyecto", value=p_edit.get("codigo", ""))

            c4, c5, c6 = st.columns(3)
            proyecto_nom = c4.text_input("Nombre del Proyecto", value=p_edit.get("nombre", f"Upcycling {cliente}"))
            fe_inicio = c5.text_input("Fecha Inicio", value="")
            fe_fin = c6.text_input("Fecha Término", value="")

            c7, c8, c9 = st.columns(3)
            responsable = c7.text_input("Responsable", value="")
            area = c8.text_input("Área", value="")
            guia_remision = c9.text_input("Nº Guía Remisión", value="")

            c10, c11 = st.columns(2)
            origen = c10.text_input("Punto Origen", value="")
            destino = c11.text_input("Punto Destino", value="")

        # 2. INGRESO MATERIAL
        with st.container(border=True):
            st.subheader("2. Ingreso de Material")
            if "num_items" not in st.session_state:
                st.session_state.num_items = 2

            col_btn1, col_btn2, _ = st.columns([1, 1, 4])
            if col_btn1.button("➕ Agregar Ítem"):
                st.session_state.num_items += 1
                st.rerun()
            if col_btn2.button("➖ Quitar Ítem") and st.session_state.num_items > 1:
                st.session_state.num_items -= 1
                st.rerun()

            lista_items = []
            peso_total_recibido = 0.0
            co2_evitado_total = 0.0
            opciones_prendas = sorted(list(FACTORES_CO2.keys()))

            for i in range(st.session_state.num_items):
                col_desc, col_unid, col_peso, col_tot, col_foto = st.columns([3, 1.5, 1.5, 1.5, 3])
                desc = col_desc.selectbox("Tipo de Producto / Prenda", opciones_prendas, key=f"desc_{i}")
                unid = col_unid.number_input("Ingreso (unid.)", min_value=0, value=0, key=f"unid_{i}")
                peso_u = col_peso.number_input("Peso Unit. (kg)", min_value=0.0, value=0.0, step=0.05, key=f"peso_{i}")
                p_total = unid * peso_u
                col_tot.text_input("Peso Total", value=f"{p_total:.2f} kg", disabled=True, key=f"tot_{i}")
                foto = col_foto.file_uploader("Evidencia Foto", type=["jpg", "png", "jpeg"], key=f"foto_{i}")

                factor = FACTORES_CO2.get(desc, 6.575)
                co2_item = p_total * factor
                co2_evitado_total += co2_item
                peso_total_recibido += p_total

                lista_items.append({"descripcion": desc, "unidades": unid, "peso_unitario": peso_u, "peso_total": p_total, "foto": foto, "co2_evitado": co2_item})

        # 3. TRAZABILIDAD
        with st.container(border=True):
            st.subheader("3. Trazabilidad del Proceso en Upcycling")
            etapas_fijas = [
                {"etapa": "Clasificación", "resp": "Área de Logística", "tipo": "Registro interno"},
                {"etapa": "Lavado", "resp": "Lavandería", "tipo": "Servicio Externo"},
                {"etapa": "Corte", "resp": "Taller de corte", "tipo": "Pesaje real"},
                {"etapa": "Confección", "resp": "Producción descentralizada", "tipo": "Entrega / Recepción"},
            ]
            lista_trazabilidad = []
            peso_lavado_auto = 0.0
            peso_corte_auto = 0.0

            for i, item_fijo in enumerate(etapas_fijas):
                c_etapa, c_fecha, c_resp, c_peso, c_tipo, c_foto = st.columns([2, 1.8, 2, 1.5, 2, 2.5])
                e_nom = c_etapa.text_input("Etapa", value=item_fijo["etapa"], disabled=True, key=f"tr_etapa_{i}")
                e_fec_val = c_fecha.date_input("Fecha", value=datetime.date.today(), format="DD/MM/YYYY", key=f"tr_fecha_{i}")
                e_res = c_resp.text_input("Responsable", value=item_fijo["resp"], disabled=True, key=f"tr_resp_{i}")
                e_pes_str = c_peso.text_input("Peso (kg)", value="0.00", key=f"tr_peso_{i}")
                
                try:
                    e_pes_num = float(e_pes_str)
                except ValueError:
                    e_pes_num = 0.0

                if item_fijo["etapa"] == "Lavado": peso_lavado_auto = e_pes_num
                elif item_fijo["etapa"] == "Corte": peso_corte_auto = e_pes_num

                e_tip = c_tipo.text_input("Tipo Registro", value=item_fijo["tipo"], disabled=True, key=f"tr_tipo_{i}")
                e_fot = c_foto.file_uploader("Evidencia", type=["jpg", "png", "jpeg"], key=f"tr_foto_{i}")

                lista_trazabilidad.append({"etapa": e_nom, "fecha": e_fec_val.strftime("%d/%m/%Y"), "responsable": e_res, "peso": e_pes_num, "tipo_registro": e_tip, "foto": e_fot})

        # 4. SALIDA DE PRODUCTOS
        with st.container(border=True):
            st.subheader("4. Salida de Productos")
            if "num_prods" not in st.session_state:
                st.session_state.num_prods = 2

            cp_btn1, cp_btn2, _ = st.columns([1, 1, 4])
            if cp_btn1.button("➕ Agregar Producto Salida"):
                st.session_state.num_prods += 1
                st.rerun()
            if cp_btn2.button("➖ Quitar Producto Salida") and st.session_state.num_prods > 1:
                st.session_state.num_prods -= 1
                st.rerun()

            lista_productos = []
            for i in range(st.session_state.num_prods):
                col_pnom, col_pcant, col_pfoto = st.columns([4, 2, 4])
                p_nombre = col_pnom.text_input("Producto", value="", key=f"prod_nom_{i}")
                p_cant = col_pcant.number_input("Cantidad (Unidades)", min_value=0, value=0, key=f"prod_cant_{i}")
                p_foto = col_pfoto.file_uploader("Evidencia Foto", type=["jpg", "png", "jpeg"], key=f"prod_foto_{i}")

                p_final_nom = p_nombre.strip() if p_nombre.strip() else f"Producto {i+1}"
                lista_productos.append({"producto": p_final_nom, "cantidad": p_cant, "foto": p_foto})

        # 5. BALANCE MATERIAL
        with st.container(border=True):
            st.subheader("5. Balance de Material")
            col_bm1, col_bm2, col_bm3 = st.columns(3)
            mat_transformado = col_bm1.number_input("Material transformado (kg)", min_value=0.0, value=0.0, step=0.1)
            retazos_aprovechables = col_bm2.number_input("Retazos aprovechables (kg)", min_value=0.0, value=0.0, step=0.1)
            perdida_no_aprovechable = col_bm3.number_input("Pérdida no aprovechable (kg)", min_value=0.0, value=0.0, step=0.1)

            total_procesado = mat_transformado + retazos_aprovechables + perdida_no_aprovechable
            pct_aprovechamiento_total = ((mat_transformado + retazos_aprovechables) / peso_total_recibido * 100) if peso_total_recibido > 0 else 0.0
            pct_perdida = (perdida_no_aprovechable / peso_total_recibido * 100) if peso_total_recibido > 0 else 0.0

        # 6. EMISIONES
        with st.container(border=True):
            st.subheader("6. Balance de Emisiones (CO₂e)")
            ct1, ct2, ct3 = st.columns(3)
            vehiculo_sel = ct1.selectbox("Tipo de Vehículo", list(FACTORES_TRANSPORTE.keys()))
            recorrido_tipo = ct2.selectbox("Tipo de Recorrido", ["Ida y Vuelta (2)", "Ida sola (1)"])
            distancia_km = ct3.number_input("Distancia Recorrida (km)", min_value=0.0, value=0.0)

            mult_recorrido = 2.0 if "2" in recorrido_tipo else 1.0
            factor_veh = FACTORES_TRANSPORTE[vehiculo_sel]
            emisiones_transporte = distancia_km * mult_recorrido * factor_veh["consumo"] * factor_veh["factor"]
            emisiones_lavado = peso_lavado_auto * 0.30
            emisiones_corte = peso_corte_auto * 0.05

            cb1, cb2 = st.columns(2)
            cant_prendas_bordado = cb1.number_input("Prendas con bordado", min_value=0, value=0)
            tipo_diseno_bordado = cb2.selectbox("Diseño Bordado", list(FACTORES_BORDADO.keys()))
            emisiones_bordado = cant_prendas_bordado * FACTORES_BORDADO[tipo_diseno_bordado]

            emisiones_proceso = emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado

        # 7. IMPACTO SOCIAL Y EMPLEO
        with st.container(border=True):
            st.subheader("7. Impacto Social y Empleo Generado")

            # TABLA 1: CORTE Y LOGÍSTICA
            st.markdown("##### 📦 Operaciones – Corte y Logística")
            st.caption("Personal recurrente/fijo de operaciones.")

            if "num_corte_log" not in st.session_state:
                st.session_state.num_corte_log = len(EQUIPO_CORTE_LOGISTICA_PREDETERMINADO)

            btn_cl1, btn_cl2, _ = st.columns([1, 1, 4])
            if btn_cl1.button("➕ Agregar Persona Operaciones"):
                st.session_state.num_corte_log += 1
                st.rerun()
            if btn_cl2.button("➖ Quitar Persona Operaciones") and st.session_state.num_corte_log > 1:
                st.session_state.num_corte_log -= 1
                st.rerun()

            lista_corte_logistica = []
            total_horas_corte_log = 0.0

            for idx in range(st.session_state.num_corte_log):
                val_pred = EQUIPO_CORTE_LOGISTICA_PREDETERMINADO[idx] if idx < len(EQUIPO_CORTE_LOGISTICA_PREDETERMINADO) else {"rol": "Corte", "nombre": "", "dias": 1, "horas_dia": 8.0}

                c_rol, c_nom, c_dias, c_hdia, c_htot = st.columns([1.5, 3.5, 1.5, 1.5, 1.5])
                rol_op = c_rol.selectbox("Rol", ["Corte", "Logística"], index=0 if val_pred["rol"]=="Corte" else 1, key=f"cl_rol_{idx}")
                nom_op = c_nom.text_input("Nombre", value=val_pred["nombre"], key=f"cl_nom_{idx}")
                dias_op = c_dias.number_input("Días trabajados", min_value=0, value=val_pred["dias"], key=f"cl_dias_{idx}")
                hdia_op = c_hdia.number_input("Hora/día", min_value=0.0, value=float(val_pred["horas_dia"]), step=0.5, key=f"cl_hdia_{idx}")
                
                htot_op = dias_op * hdia_op
                c_htot.metric("Horas totales", f"{htot_op:.1f}")
                
                total_horas_corte_log += htot_op
                lista_corte_logistica.append({"rol": rol_op, "nombre": nom_op, "dias": dias_op, "horas_dia": hdia_op, "horas_totales": htot_op})

            st.write("---")

            # TABLA 2: CONFECCIÓN Y ACABADO
            st.markdown("##### 🧵 Producción – Confección y Acabado")
            st.caption("Detalle de prendas producidas por personal específico.")

            if "num_rows_conf" not in st.session_state:
                st.session_state.num_rows_conf = 3

            btn_cf1, btn_cf2, _ = st.columns([1, 1, 4])
            if btn_cf1.button("➕ Agregar Fila Confección"):
                st.session_state.num_rows_conf += 1
                st.rerun()
            if btn_cf2.button("➖ Quitar Fila Confección") and st.session_state.num_rows_conf > 1:
                st.session_state.num_rows_conf -= 1
                st.rerun()

            nombres_productos = [p["producto"] for p in lista_productos if p["producto"]]
            if not nombres_productos:
                nombres_productos = ["Estuche Voyager", "Monederos", "Monedero Circular", "Camita Perro S", "Camita Perro XL", "Lonchera Rectangular"]

            lista_confeccion = []
            total_horas_conf = 0.0

            for idx in range(st.session_state.num_rows_conf):
                col_rol, col_prod, col_nom, col_cant, col_tunit, col_htot = st.columns([1.5, 2.5, 2.5, 1.2, 1.5, 1.5])
                
                rol_c = col_rol.selectbox("Rol", ["Confección", "Acabado"], key=f"cf_rol_{idx}")
                prod_c = col_prod.selectbox("Producto", nombres_productos, key=f"cf_prod_{idx}")
                nom_c = col_nom.text_input("Nombre", value="", placeholder="Ej: Lucia", key=f"cf_nom_{idx}")
                cant_c = col_cant.number_input("Cantidad", min_value=0, value=100, key=f"cf_cant_{idx}")
                tunit_c = col_tunit.number_input("Tiempo / unid (h)", min_value=0.0, value=0.15, step=0.01, format="%.2f", key=f"cf_tunit_{idx}")
                
                hgen_c = cant_c * tunit_c
                col_htot.metric("Horas gen.", f"{hgen_c:.1f}")

                total_horas_conf += hgen_c
                lista_confeccion.append({"rol": rol_c, "producto": prod_c, "nombre": nom_c, "cantidad": cant_c, "tiempo_unitario": tunit_c, "horas_generadas": hgen_c})

            # CONSOLIDADO SOCIAL
            personas_unicas = set(
                [x["nombre"].strip() for x in lista_corte_logistica if x["nombre"].strip()] +
                [x["nombre"].strip() for x in lista_confeccion if x["nombre"].strip()]
            )
            total_personas_social = len(personas_unicas)
            total_horas_social = total_horas_corte_log + total_horas_conf

            st.write("---")
            m1, m2, m3 = st.columns(3)
            m1.metric("Horas Operaciones (Corte/Logística)", f"{total_horas_corte_log:.1f} h")
            m2.metric("Horas Producción (Confección/Acabado)", f"{total_horas_conf:.1f} h")
            m3.metric("Total Horas Sociales Generadas", f"{total_horas_social:.1f} h", delta=f"{total_personas_social} personas")

        # GENERACIÓN DEL REPORTE
        st.write("---")
        if st.button("📄 Generar Informe Técnico PDF", type="primary", use_container_width=True):
            pdf_bytes = generar_pdf_oficial(
                cliente, ruc, proyecto_nom, codigo_proy, fe_inicio, fe_fin, responsable, area,
                "Prendas de vestir / Textiles", "Upcycling (Reciclaje Textil)", "Piezas / Kilogramos", guia_remision, origen, destino,
                lista_items, lista_trazabilidad, lista_productos,
                mat_transformado, retazos_aprovechables, perdida_no_aprovechable, total_procesado,
                pct_aprovechamiento_total, pct_perdida,
                lista_corte_logistica, lista_confeccion, total_horas_corte_log, total_horas_conf, total_horas_social, total_personas_social,
                co2_evitado_total, emisiones_transporte, emisiones_lavado, emisiones_corte, emisiones_bordado
            )
            st.success("✅ Informe PDF generado correctamente.")
            st.download_button(
                label="📥 Descargar Reporte en PDF",
                data=pdf_bytes,
                file_name=f"Informe_Tecnico_{codigo_proy or 'PD'}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
