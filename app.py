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
    "Estrellas",
    "Cartuchera",
    "Cúbica",
    "Bolso",
    "Mochila",
    "Llavero",
    "Monedero",
    "Canguro",
    "Tote bag",
    "Neceser",
    "Portalaptop",
    "Portacepillos",
    "Pelota",
    "Portacubierto",
    "Juguete",
    "Cubo",
    "Corazones",
    "Peluche",
    "Morral",
    "Portaútiles",
    "Portabotella",
    "Cama perrito",
    "Colets",
    "Rombo",
    "Mandiles",
    "Lonchera",
    "➕ Otro (Escribir nuevo producto)",
]

# --- MATRIZ DE TIEMPOS ESTIMADOS SEGÚN TIPO Y COMPLEJIDAD DEL PRODUCTO (en horas/unidad) ---
TIEMPOS_ESTIMADOS_PRODUCTO = {
    "Mochila": 2.50,
    "Bolso": 1.50,
    "Tote bag": 0.80,
    "Portalaptop": 1.20,
    "Canguro": 1.10,
    "Neceser": 0.70,
    "Lonchera": 1.00,
    "Cartuchera": 0.50,
    "Morral": 1.20,
    "Mandiles": 0.60,
    "Cama perrito": 1.80,
    "Peluche": 1.50,
    "Pelota": 0.80,
    "Estrellas": 0.35,
    "Corazones": 0.35,
    "Rombo": 0.35,
    "Cúbica": 0.60,
    "Cubo": 0.50,
    "Llavero": 0.20,
    "Monedero": 0.30,
    "Portacepillos": 0.25,
    "Portacubierto": 0.25,
    "Portaútiles": 0.40,
    "Portabotella": 0.45,
    "Colets": 0.15,
    "Juguete": 0.75,
}


def estimar_tiempo_unidad(nombre_producto: str) -> float:
    """Retorna el tiempo estimado (horas/unidad) según el tipo de producto."""
    for prod_key, tiempo in TIEMPOS_ESTIMADOS_PRODUCTO.items():
        if prod_key.lower() in nombre_producto.lower():
            return tiempo
    return 0.75


# --- FACTORES DE EMISIÓN DE MATERIALES ---
FACTORES_CO2 = {
    "Banner": 9.5,
    "Bata de laboratorio": 6.575,
    "Bolsas": 8.0,
    "Camisa": 6.575,
    "Camisa algodón": 5.0,
    "Camisa drill": 5.9,
    "Camisa ignífuga": 5.35,
    "Camisa jean / denim": 5.0,
    "Camisaco": 5.0,
    "Camisaco drill": 5.9,
    "Camisaco drill con cinta": 6.25,
    "Casaca": 6.575,
    "Casaca drill": 5.9,
    "Casaca polar": 6.0,
    "Casaca polar con cinta reflectiva": 6.3,
    "Casaca térmica": 6.1,
    "Chaleco": 6.575,
    "Chaleco con cinta": 6.925,
    "Chaleco de seguridad": 9.75,
    "Chaleco Fluorescente": 9.625,
    "Chaleco polar": 6.0,
    "Chaleco reversible": 9.5,
    "Chompa": 7.1,
    "Chompa con cinta reflectiva": 7.45,
    "Chompa Jorge Chavez": 6.0,
    "Chompa Jorge Chavez con cinta reflectiva": 6.3,
    "Chompa polar": 6.0,
    "Enterizo": 6.575,
    "Gorro": 7.925,
    "Impermeable": 9.425,
    "Mameluco": 6.575,
    "Mameluco acolchado": 5.825,
    "Mameluco drill": 5.9,
    "Mameluco jean reflectivo": 5.35,
    "Merma": 6.575,
    "Overol": 6.575,
    "Pantalón": 6.575,
    "Pantalón algodón": 5.0,
    "Pantalón drill": 5.9,
    "Pantalón drill con cinta": 6.25,
    "Pantalón ignífugo": 5.35,
    "Pantalón jean": 5.0,
    "Pantalón jean / drill": 5.675,
    "Pantalón jean con cinta reflectiva": 5.35,
    "Pantalón polar": 6.0,
    "Pantalón térmico": 6.0,
    "Polera": 5.0,
    "Polera polar": 6.0,
    "Polo": 6.8,
    "Polo algodón": 5.0,
    "Polo con cinta reflectiva": 6.925,
    "Polo manga corta": 6.8,
    "Polo manga larga": 6.8,
    "Polo manga larga con cinta reflectiva": 6.7,
    "Polo piqué": 5.0,
    "Short": 6.575,
    "Toalla": 5.0,
    "Otro": 6.575,
}

# --- FACTORES DE TRANSPORTE ---
FACTORES_TRANSPORTE = {
    "Auto": {"consumo": 0.10, "factor": 2.31},
    "Minivan": {"consumo": 0.12, "factor": 2.00},
    "Mototaxi": {"consumo": 0.04, "factor": 2.31},
    "Moto": {"consumo": 0.03, "factor": 2.31},
    "Camión mediano": {"consumo": 0.30, "factor": 2.68},
    "Camión grande": {"consumo": 0.40, "factor": 2.68},
}

# --- FACTORES DE BORDADO ---
FACTORES_BORDADO = {
    "Sin bordado / Ninguno": 0.0,
    "Simple (5 min/pieza)": 0.020,
    "Medio (9 min/pieza)": 0.037,
    "Complejo (10 min/pieza)": 0.041,
}

# --- PERSONAL FIJO DE OPERACIONES (CORTE Y LOGÍSTICA) ---
PERSONAL_FIJO_OPERACIONES = [
    {"rol": "Corte", "nombre": "Maria Isabel Estrada Sandoval"},
    {"rol": "Corte", "nombre": "Genaro Jara García"},
    {"rol": "Corte", "nombre": "Luciana Jara estrada"},
    {"rol": "Corte", "nombre": "Felicita Sandoval vilchez"},
    {"rol": "Corte", "nombre": "Nicolle Estrada"},
    {"rol": "Logística", "nombre": "Evelyn Prada Vizarreta"},
]

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Pequeños Detalles - Sistema de Trazabilidad",
    page_icon="✂️",
    layout="wide",
)

# --- ESTILOS CSS ---
st.markdown(
    """
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
    </style>
""",
    unsafe_allow_html=True,
)


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
        self.drawString(
            36,
            20,
            "Pequeños Detalles Handmade Perú S.A.C. - Trazabilidad y Sostenibilidad Textil",
        )
        self.drawRightString(576, 20, f"Página {self._pageNumber}")
        self.restoreState()


# --- GENERADOR DEL PDF OFICIAL ---
def generar_pdf_oficial(
    cliente,
    ruc,
    proyecto_nom,
    codigo_proy,
    fe_inicio,
    fe_fin,
    responsable,
    area,
    tipo_material,
    valorizacion,
    unidad_medida,
    guia_remision,
    origen,
    destino,
    lista_items,
    lista_trazabilidad,
    lista_productos,
    mat_transformado,
    retazos_aprovechables,
    perdida_no_aprovechable,
    total_procesado,
    pct_aprovechamiento_total,
    pct_perdida,
    lista_operaciones_pdf,
    lista_confeccion,
    total_horas_social,
    total_personas_social,
    co2_evitado_total,
    emisiones_transporte,
    emisiones_lavado,
    emisiones_corte,
    emisiones_bordado,
):
    kg_recibidos = sum([item["peso_total"] for item in lista_items])
    emisiones_proceso = (
        emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado
    )
    co2_neto = co2_evitado_total - emisiones_proceso

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    h1_style = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=colors.HexColor("#1E293B"),
        alignment=1,
        spaceAfter=2,
    )
    sub_style = ParagraphStyle(
        "Sub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#64748B"),
        alignment=1,
        spaceAfter=12,
    )
    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=10,
        spaceAfter=6,
    )
    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#334155"),
        leading=10,
    )
    cell_bold = ParagraphStyle(
        "CellB",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=colors.HexColor("#0F172A"),
        leading=10,
    )
    card_title = ParagraphStyle(
        "CardT",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=colors.HexColor("#0F172A"),
        alignment=1,
    )
    card_sub = ParagraphStyle(
        "CardS",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        textColor=colors.HexColor("#475569"),
        alignment=1,
    )

    elements = []

    # Encabezado PDF
    elements.append(Paragraph("INFORME TÉCNICO DE VALORIZACIÓN TEXTIL", h1_style))
    elements.append(
        Paragraph(
            "Medición de Impacto Ambiental, Trazabilidad y Gestión Social de"
            f" Upcycling<br/><b>CÓDIGO: {codigo_proy}</b>",
            sub_style,
        )
    )

    # Tarjetas Métricas PDF
    cards_data = [
        [
            Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", card_title),
            Paragraph(f"<b>{pct_aprovechamiento_total:.2f}%</b>", card_title),
            Paragraph(f"<b>{co2_neto:.2f} kg</b>", card_title),
            Paragraph(f"<b>{total_horas_social:.2f} hrs</b>", card_title),
        ],
        [
            Paragraph("MATERIAL RECIBIDO", card_sub),
            Paragraph("% APROVECHAMIENTO", card_sub),
            Paragraph("CO₂e NETO EVITADO", card_sub),
            Paragraph(f"TRABAJO GENERADO ({total_personas_social} PERS.)", card_sub),
        ],
    ]
    t_cards = Table(cards_data, colWidths=[135, 135, 135, 135])
    t_cards.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ])
    )
    elements.append(t_cards)
    elements.append(Spacer(1, 8))

    # 1. Ficha General
    elements.append(Paragraph("1. FICHA GENERAL DEL PROYECTO Y TRAZABILIDAD", h2_style))
    data_ficha = [
        [
            Paragraph("Cliente / Empresa", cell_bold),
            Paragraph(f"{cliente} (RUC: {ruc})", cell_style),
            Paragraph("Área / Responsable", cell_bold),
            Paragraph(f"{area} / {responsable}", cell_style),
        ],
        [
            Paragraph("Tipo de Proyecto", cell_bold),
            Paragraph(proyecto_nom, cell_style),
            Paragraph("Periodo de Ejecución", cell_bold),
            Paragraph(f"{fe_inicio} al {fe_fin}", cell_style),
        ],
        [
            Paragraph("Tipo de Material", cell_bold),
            Paragraph(tipo_material, cell_style),
            Paragraph("Tipo de Valorización", cell_bold),
            Paragraph(valorizacion, cell_style),
        ],
        [
            Paragraph("Guía de Remisión", cell_bold),
            Paragraph(guia_remision, cell_style),
            Paragraph("Unidad de Medida", cell_bold),
            Paragraph(unidad_medida, cell_style),
        ],
        [
            Paragraph("Punto de Origen", cell_bold),
            Paragraph(origen, cell_style),
            Paragraph("Punto de Destino", cell_bold),
            Paragraph(destino, cell_style),
        ],
    ]
    t_ficha = Table(data_ficha, colWidths=[100, 170, 100, 170])
    t_ficha.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F8FAFC")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ])
    )
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
    elements.append(
        Paragraph("2. INGRESO DE MATERIAL Y EVIDENCIA FOTOGRÁFICA", h2_style)
    )
    data_prendas_pdf = [[
        Paragraph("Ítem", cell_bold),
        Paragraph("Tipo de Producto / Prenda", cell_bold),
        Paragraph("Ingreso (unid)", cell_bold),
        Paragraph("Peso unit. (kg)", cell_bold),
        Paragraph("Peso total (kg)", cell_bold),
        Paragraph("Evidencia", cell_bold),
    ]]

    total_unidades_ingreso = 0
    for i, item in enumerate(lista_items, 1):
        total_unidades_ingreso += item["unidades"]
        img_cell = obtener_imagen_pdf(item["foto"], 45, 45)

        data_prendas_pdf.append([
            Paragraph(str(i), cell_style),
            Paragraph(item["descripcion"], cell_style),
            Paragraph(str(item["unidades"]), cell_style),
            Paragraph(f"{item['peso_unitario']:.2f}", cell_style),
            Paragraph(f"{item['peso_total']:.2f}", cell_style),
            img_cell,
        ])

    data_prendas_pdf.append([
        Paragraph("<b>TOTAL MATERIAL RECIBIDO</b>", cell_bold),
        "",
        Paragraph(f"<b>{total_unidades_ingreso}</b>", cell_bold),
        Paragraph("-", cell_bold),
        Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", cell_bold),
        Paragraph("-", cell_bold),
    ])

    t_prendas = Table(data_prendas_pdf, colWidths=[30, 180, 80, 75, 75, 100])
    t_prendas.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5D0FE")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("SPAN", (0, -1), (1, -1)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (2, 0), (4, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elements.append(t_prendas)
    elements.append(Spacer(1, 8))

    # 3. Trazabilidad
    elements.append(Paragraph("3. TRAZABILIDAD DEL PROCESO EN UPCYCLING", h2_style))
    data_traza_pdf = [[
        Paragraph("Etapa", cell_bold),
        Paragraph("Fecha", cell_bold),
        Paragraph("Responsable", cell_bold),
        Paragraph("Peso (kg)", cell_bold),
        Paragraph("Tipo de Registro", cell_bold),
        Paragraph("Evidencia", cell_bold),
    ]]

    for t_item in lista_trazabilidad:
        img_cell = obtener_imagen_pdf(t_item["foto"], 45, 35)

        data_traza_pdf.append([
            Paragraph(t_item["etapa"], cell_style),
            Paragraph(t_item["fecha"], cell_style),
            Paragraph(t_item["responsable"], cell_style),
            Paragraph(f"{t_item['peso']:.2f}", cell_style),
            Paragraph(t_item["tipo_registro"], cell_style),
            img_cell,
        ])

    t_traza = Table(data_traza_pdf, colWidths=[90, 70, 130, 60, 100, 90])
    t_traza.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5D0FE")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (3, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elements.append(t_traza)

    elements.append(PageBreak())

    # 4. SALIDA DE PRODUCTOS
    elements.append(Paragraph("4. SALIDA DE PRODUCTOS", h2_style))
    elements.append(
        Paragraph(
            "Registro de productos obtenidos a partir del proceso de upcycling",
            sub_style,
        )
    )

    data_prod_pdf = [[
        Paragraph("Producto", cell_bold),
        Paragraph("Cantidad (Unidades)", cell_bold),
        Paragraph("Evidencia", cell_bold),
    ]]

    total_prod_unidades = 0
    for p_item in lista_productos:
        total_prod_unidades += p_item["cantidad"]
        img_cell = obtener_imagen_pdf(p_item["foto"], 60, 60)

        data_prod_pdf.append([
            Paragraph(p_item["producto"], cell_style),
            Paragraph(str(p_item["cantidad"]), cell_style),
            img_cell,
        ])

    data_prod_pdf.append([
        Paragraph("<b>SUMA TOTAL</b>", cell_bold),
        Paragraph(f"<b>{total_prod_unidades}</b>", cell_bold),
        Paragraph("-", cell_bold),
    ])

    t_prod = Table(data_prod_pdf, colWidths=[240, 150, 150])
    t_prod.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5D0FE")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 5),
        ])
    )
    elements.append(t_prod)
    elements.append(Spacer(1, 15))

    # 5. BALANCE DE MATERIAL
    elements.append(Paragraph("5. BALANCE DE MATERIAL", h2_style))
    elements.append(
        Paragraph(
            "Resumen del flujo y aprovechamiento del material procesado",
            sub_style,
        )
    )

    data_balance = [
        [
            Paragraph("<b>Concepto</b>", cell_bold),
            Paragraph("<b>Cantidad (kg)</b>", cell_bold),
        ],
        [
            Paragraph("Material recibido", cell_style),
            Paragraph(f"{kg_recibidos:.2f}", cell_style),
        ],
        [
            Paragraph("Material transformado en productos", cell_style),
            Paragraph(f"{mat_transformado:.2f}", cell_style),
        ],
        [
            Paragraph("Retazos aprovechables", cell_style),
            Paragraph(f"{retazos_aprovechables:.2f}", cell_style),
        ],
        [
            Paragraph("Pérdida no aprovechable", cell_style),
            Paragraph(f"{perdida_no_aprovechable:.2f}", cell_style),
        ],
        [
            Paragraph("<b>Total procesado</b>", cell_bold),
            Paragraph(f"<b>{total_procesado:.2f}</b>", cell_bold),
        ],
        [
            Paragraph("<b>Indicador</b>", cell_bold),
            Paragraph("<b>Valor</b>", cell_bold),
        ],
        [
            Paragraph("% aprovechamiento total", cell_style),
            Paragraph(f"{pct_aprovechamiento_total:.2f}%", cell_style),
        ],
        [
            Paragraph("% pérdida", cell_style),
            Paragraph(f"{pct_perdida:.2f}%", cell_style),
        ],
    ]

    t_balance = Table(data_balance, colWidths=[340, 200])
    t_balance.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5D0FE")),
            ("BACKGROUND", (0, 6), (-1, 6), colors.HexColor("#F5D0FE")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("PADDING", (0, 0), (-1, -1), 5),
        ])
    )
    elements.append(t_balance)
    elements.append(Spacer(1, 15))

    # 6. BALANCE DE IMPACTO AMBIENTAL
    elements.append(
        Paragraph("6. RESUMEN DE IMPACTO AMBIENTAL DEL PROYECTO (CO₂e)", h2_style)
    )
    data_co2_box = [
        [
            Paragraph("<b>(+) CO₂ Evitado por Upcycling</b>", card_sub),
            Paragraph("<b>(-) Emisiones del Proceso</b>", card_sub),
            Paragraph("<b>(=) Impacto Ambiental Neto</b>", card_sub),
        ],
        [
            Paragraph(f"<b>{co2_evitado_total:.2f} kg CO₂e</b>", card_title),
            Paragraph(f"<b>{emisiones_proceso:.2f} kg CO₂e</b>", card_title),
            Paragraph(f"<b>{co2_neto:.2f} kg CO₂e</b>", card_title),
        ],
    ]
    t_co2_box = Table(data_co2_box, colWidths=[180, 180, 180])
    t_co2_box.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])
    )
    elements.append(t_co2_box)
    elements.append(Spacer(1, 10))

    # 7. IMPACTO SOCIAL
    elements.append(
        Paragraph("7. RESUMEN DE IMPACTO SOCIAL Y EQUIPO DE TRABAJO", h2_style)
    )
    elements.append(
        Paragraph(
            "Participación del personal en el proceso de upcycling e integración"
            f" social (Total Horas Generadas: <b>{total_horas_social:.2f}"
            " hrs</b>).",
            cell_style,
        )
    )
    elements.append(Spacer(1, 6))

    elements.append(Paragraph("<b>Operaciones – Corte y Logística</b>", cell_bold))
    data_ops_pdf = [[
        Paragraph("Rol", cell_bold),
        Paragraph("Nombre", cell_bold),
        Paragraph("Días trabajados", cell_bold),
        Paragraph("Hora/día", cell_bold),
        Paragraph("Horas totales", cell_bold),
    ]]

    tot_hrs_ops = 0
    for op in lista_operaciones_pdf:
        tot_hrs_ops += op["horas_totales"]
        data_ops_pdf.append([
            Paragraph(str(op["rol"]), cell_style),
            Paragraph(str(op["nombre"]), cell_style),
            Paragraph(str(op["dias"]), cell_style),
            Paragraph(f"{op['horas_dia']:.2f}", cell_style),
            Paragraph(f"{op['horas_totales']:.2f}", cell_style),
        ])

    data_ops_pdf.append([
        Paragraph("<b>SUBTOTAL CORTE Y LOGÍSTICA</b>", cell_bold),
        "",
        "",
        "",
        Paragraph(f"<b>{tot_hrs_ops:.2f} hrs</b>", cell_bold),
    ])

    t_ops = Table(data_ops_pdf, colWidths=[100, 200, 80, 80, 80])
    t_ops.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5D0FE")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("SPAN", (0, -1), (3, -1)),
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elements.append(t_ops)
    elements.append(Spacer(1, 10))

    # CONFECCIÓN Y ACABADO
    if lista_confeccion:
        elements.append(
            Paragraph(
                "<b>Desglose del Personal de Confección y Acabado</b>", cell_bold
            )
        )
        data_social_pdf = [[
            Paragraph("Producto", cell_bold),
            Paragraph("Rol Operativo", cell_bold),
            Paragraph("Encargado/a", cell_bold),
            Paragraph("Cant.", cell_bold),
            Paragraph("Tiempo unit. (hrs)", cell_bold),
            Paragraph("Horas Totales", cell_bold),
        ]]

        tot_hrs_conf = 0
        for c_item in lista_confeccion:
            tot_hrs_conf += c_item["horas_totales"]
            data_social_pdf.append([
                Paragraph(c_item["producto"], cell_style),
                Paragraph(c_item["rol"], cell_style),
                Paragraph(c_item["persona"], cell_style),
                Paragraph(str(c_item["cantidad"]), cell_style),
                Paragraph(f"{c_item['tiempo_unitario']:.2f} hrs", cell_style),
                Paragraph(f"{c_item['horas_totales']:.2f} hrs", cell_style),
            ])

        data_social_pdf.append([
            Paragraph("<b>SUBTOTAL CONFECCIÓN Y ACABADO</b>", cell_bold),
            "",
            "",
            "",
            "",
            Paragraph(f"<b>{tot_hrs_conf:.2f} hrs</b>", cell_bold),
        ])

        t_soc = Table(data_social_pdf, colWidths=[120, 100, 110, 40, 80, 90])
        t_soc.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5D0FE")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("SPAN", (0, -1), (4, -1)),
                ("ALIGN", (3, 0), (-1, -1), "CENTER"),
                ("PADDING", (0, 0), (-1, -1), 4),
            ])
        )
        elements.append(t_soc)

    doc.build(elements, canvasmaker=ReporteCanvas)
    buffer.seek(0)
    return buffer


# --- ESTADOS DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "pestaña_activa" not in st.session_state:
    st.session_state.pestaña_activa = "➕   Nuevo Reporte PDF"

if "proyecto_editar" not in st.session_state:
    st.session_state.proyecto_editar = {}

if "catalogo_productos" not in st.session_state:
    st.session_state.catalogo_productos = list(PRODUCTOS_CATALOGO_BASE)

# --- LOGIN ---
USUARIO_CORRECTO = "admin"
PASSWORD_CORRECTO = "pequenos2026"

if not st.session_state.autenticado:
    st.markdown(
        """
        <div style="text-align: center; padding: 40px 10px;">
            <h1 style="color: #1E293B; font-size: 2.2rem; font-weight: 800;">✂️   Pequeños Detalles</h1>
            <p style="color: #64748B; font-size: 1.1rem;">Handmade Perú S.A.C. — Gestión de Sostenibilidad</p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            st.subheader("🔑   Iniciar Sesión")
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
                    st.error("⚠️   Usuario o contraseña incorrectos.")

else:
    proyectos_wip = cargar_proyectos(estado="EN_PROCESO")

    # --- BARRA LATERAL ---
    with st.sidebar:
        st.markdown("### ✂️   Pequeños Detalles")
        st.caption("Panel de Control Interno | 2026")
        st.write("---")

        st.markdown(
            '<p class="sidebar-section-title">Navegación</p>',
            unsafe_allow_html=True,
        )

        if st.button(
            "✨   Nuevo Reporte PDF",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.pestaña_activa == "➕   Nuevo Reporte PDF"
                else "secondary"
            ),
        ):
            st.session_state.proyecto_editar = {}
            st.session_state.pestaña_activa = "➕   Nuevo Reporte PDF"
            st.rerun()

        st.markdown(
            '<p class="sidebar-section-title">Proyectos Pendientes</p>',
            unsafe_allow_html=True,
        )

        if proyectos_wip:
            for p in proyectos_wip:
                cli_nombre = p.get("cliente", "Sin Nombre")
                cod_ref = p.get("codigo", "")
                label_btn = f"📁   {cli_nombre}" + (f" ({cod_ref})" if cod_ref else "")

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
                    st.session_state.pestaña_activa = "➕   Nuevo Reporte PDF"
                    st.rerun()

            st.write("")
            if st.button("📋   Ver Lista en Proceso", use_container_width=True):
                st.session_state.pestaña_activa = "📄   Proyectos en Proceso"
                st.rerun()
        else:
            st.caption("📂   No hay proyectos en borrador")

        st.markdown(
            '<p class="sidebar-section-title">Analítica e Histórico</p>',
            unsafe_allow_html=True,
        )

        if st.button(
            "📊   Dashboard 2026",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.pestaña_activa == "📊   Dashboard 2026"
                else "secondary"
            ),
        ):
            st.session_state.pestaña_activa = "📊   Dashboard 2026"
            st.rerun()

        if st.button(
            "🗂️   Historial Completo",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.pestaña_activa == "🗂️   Historial Completo"
                else "secondary"
            ),
        ):
            st.session_state.pestaña_activa = "🗂️   Historial Completo"
            st.rerun()

        st.write("---")
        if st.button("🚪   Cerrar Sesión", use_container_width=True):
            st.session_state.autenticado = False
            st.session_state.proyecto_editar = {}
            st.rerun()

    # --- HEADER VÍVIDO ---
    st.markdown(
        f"""
        <div class="hero-header">
            <h1>✂️   Sistema de Gestión de Informes Técnicos</h1>
            <p>Sección Activa: <b>{st.session_state.pestaña_activa}</b></p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # --- PESTAÑA: NUEVO / EDITAR REPORTE ---
    if st.session_state.pestaña_activa == "➕   Nuevo Reporte PDF":
        p_edit = st.session_state.proyecto_editar

        if p_edit:
            st.warning(
                "✏️   **Modo Edición Activo:** Modificando borrador de"
                f" **{p_edit.get('cliente', '')}** (`{p_edit.get('codigo', '')}`)"
            )
            if st.button("❌   Descartar selección y limpiar formulario"):
                st.session_state.proyecto_editar = {}
                st.rerun()

        # 1. FICHA
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

        # 2. INGRESO DE MATERIAL
        with st.container(border=True):
            st.subheader("2. Ingreso de Material")
            if "num_items" not in st.session_state:
                st.session_state.num_items = 2

            col_btn1, col_btn2, _ = st.columns([1, 1, 4])
            if col_btn1.button("➕   Agregar Ítem"):
                st.session_state.num_items += 1
                st.rerun()
            if (
                col_btn2.button("➖   Quitar Ítem")
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
                f"⚖️   **Total Material Recibido:** {peso_total_recibido:.2f} kg |"
                " **CO₂ Evitado Calculado:**"
                f" {co2_evitado_total:.2f} kg CO₂e"
            )

        st.write("")

        # 3. TRAZABILIDAD
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

                permitir_editar = c_edit_chk.checkbox("✏️   Editar", key=f"chk_edit_{i}")
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

        # 4. SALIDA DE PRODUCTOS
        with st.container(border=True):
            st.subheader("4. Salida de Productos")

            if "num_prods" not in st.session_state:
                st.session_state.num_prods = 2

            cp_btn1, cp_btn2, _ = st.columns([1, 1, 4])
            if cp_btn1.button("➕   Agregar Producto"):
                st.session_state.num_prods += 1
                st.rerun()
            if (
                cp_btn2.button("➖   Quitar Producto")
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

                if prod_seleccionado == "➕   Otro (Escribir nuevo producto)":
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
                    col_pnom_nuevo.text_input(
                        "Producto",
                        value=prod_seleccionado,
                        disabled=True,
                        key=f"prod_dis_{i}",
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
                "📦   **Suma Total de Productos Obtenidos:**"
                f" {total_prod_unid} unidades"
            )

        st.write("")

        # 5. BALANCE DE MATERIAL
        with st.container(border=True):
            st.subheader("5. Balance de Material")
            st.info(
                "⚖️   **Material Recibido (calculado automáticamente):**"
                f" {peso_total_recibido:.2f} kg"
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

        # 6. CÁLCULO DE EMISIONES
        with st.container(border=True):
            st.subheader("6. Balance de Emisiones (CO₂e)")

            st.markdown("##### 🚚   A. Cálculo de Transporte")
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
                "##### 🧺   B. Lavandería y Taller de Corte (Calculado desde"
                " Trazabilidad)"
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

            st.markdown("##### 🧵   C. Cálculo de Bordado")
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
                "🌱   **Total Emisiones del Proceso:**"
                f" {emisiones_proceso:.2f} kg CO₂e | **Impacto Ambiental Neto"
                f" Evitado:** {co2_neto:.2f} kg CO₂e"
            )

        st.write("")

# 7. EQUIPO DE TRABAJO Y GENERACIÓN DE HORAS
        with st.container(border=True):
            st.subheader("7. Equipo de Trabajo y Generación de Horas")
            st.markdown(
                "**Participación del personal en el proceso de upcycling y horas"
                " trabajadas por actividad**"
            )

            # CÁLCULO DINÁMICO REAJUSTADO A TIEMPOS REALES DE UPCYCLING
                if peso_total_recibido <= 10:
                    dias_calc_corte = 1
                    hdia_calc_corte = 3.0  # 3 hrs totales por persona
                elif peso_total_recibido <= 30:
                    dias_calc_corte = 1
                    hdia_calc_corte = 6.0  # 6 hrs totales por persona
                elif peso_total_recibido <= 50:
                    dias_calc_corte = 2
                    hdia_calc_corte = 6.0  # 12 hrs totales por persona
                else:
                    dias_calc_corte = max(2, int(peso_total_recibido / 25))
                    hdia_calc_corte = 8.0

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
                    "✏️", key=f"ops_chk_{idx}", label_visibility="collapsed"
                )
                nom_val = c_nom.text_input(
                    "Nombre",
                    value=p_fijo["nombre"],
                    disabled=not editar_nom,
                    key=f"ops_nom_{idx}",
                    label_visibility="collapsed",
                )

                # ASIGNACIÓN DINÁMICA DE DÍAS Y HORAS SEGÚN EL MATERIAL RECIBIDO
                val_dias_defecto = 3 if rol_val == "Logística" else dias_calc_corte
                val_hdia_defecto = 3.0 if rol_val == "Logística" else hdia_calc_corte

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

                # MULTIPLICACIÓN DIRECTA Y CORRECCIÓN DE MOSTRADO
                tot_hrs_pers = float(val_dias) * float(val_hdia)
                
                c_tot.text_input(
                    "Total",
                    value=f"{tot_hrs_pers:.2f}",
                    disabled=True,
                    key=f"ops_tot_{idx}_{val_dias}_{val_hdia}",  # <--- KEY DINÁMICA PARA FORZAR RE-RENDERIZADO
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

            # --- CONFECCIÓN Y ACABADO ---
            st.markdown("#### Confección y Acabado – Artesanas y Taller")
            st.caption(
                "El tiempo unitario se estima automáticamente según el tipo de"
                " producto. Puede asignar varias personas por cada producto para"
                " Confección o Acabado."
            )

            lista_confeccion = []
            horas_confeccion_total = 0.0
            personas_confeccion_set = set()

            for idx, prod in enumerate(lista_productos):
                p_nom = prod["producto"]
                p_cant = prod["cantidad"]

                tiempo_sugerido_ia = estimar_tiempo_unidad(p_nom)

                st.markdown(
                    f"**🏷️  Producto {idx+1}: {p_nom}** *(Cantidad Total: {p_cant} unid"
                    f" | Estimación IA: {tiempo_sugerido_ia:.2f} hrs/unid)*"
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
                        "Rol Operativo",
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

                    tiempo_unitario = c_tiempo.number_input(
                        "Tiempo/Unid (hrs)",
                        min_value=0.0,
                        value=float(tiempo_sugerido_ia),
                        step=0.05,
                        key=f"soc_tunit_{idx}_{p_idx}",
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
                "👥   TOTAL IMPACTO SOCIAL",
                f"{total_horas_social:.2f} hrs",
                f"{total_personas_social} Beneficiarios",
            )
        st.write("")

        # BOTONES DE ACCIÓN Y GENERACIÓN
        b_col1, b_col2 = st.columns(2)

        if b_col1.button(
            "💾   Guardar Borrador (En Proceso)", use_container_width=True
        ):
            try:
                supabase.table("proyectos").upsert({
                    "codigo": codigo_proy if codigo_proy else "PROY-PENDIENTE",
                    "cliente": cliente if cliente else "CLIENTE POR DEFINIR",
                    "fecha": f"{fe_inicio} - {fe_fin}",
                    "ruc": ruc,
                    "estado": "EN_PROCESO",
                }).execute()
                st.success("💾   ¡Guardado con éxito como Borrador!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

        if b_col2.button(
            "📄   Finalizar y Generar PDF Oficial",
            type="primary",
            use_container_width=True,
        ):
            try:
                supabase.table("proyectos").upsert({
                    "codigo": codigo_proy if codigo_proy else "SIN-CODIGO",
                    "cliente": cliente if cliente else "CLIENTE GENERAL",
                    "fecha": f"{fe_inicio} - {fe_fin}",
                    "ruc": ruc,
                    "estado": "COMPLETADO",
                }).execute()
            except Exception:
                pass

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

            st.success("✅   ¡Informe Técnico Generado Exitosamente!")
            st.download_button(
                label="📥   DESCARGAR INFORME TÉCNICO EN PDF",
                data=pdf_buffer,
                file_name=(
                    "Informe_Trazabilidad_"
                    f"{codigo_proy if codigo_proy else 'PROYECTO'}.pdf"
                ),
                mime="application/pdf",
                use_container_width=True,
            )

    # --- PESTAÑA: PROYECTOS EN PROCESO ---
    elif st.session_state.pestaña_activa == "📄   Proyectos en Proceso":
        st.subheader("📋   Proyectos Guardados en Borrador (En Proceso)")
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
                "✏️   Cargar Borrador", type="primary", use_container_width=True
            ):
                st.session_state.proyecto_editar = opciones_proy[seleccionado]
                st.session_state.pestaña_activa = "➕   Nuevo Reporte PDF"
                st.rerun()
        else:
            st.info("No hay proyectos pendientes o guardados en proceso.")

    # --- PESTAÑA: DASHBOARD 2026 ---
    elif st.session_state.pestaña_activa == "📊   Dashboard 2026":
        st.subheader("📊   Indicadores Globales de Sostenibilidad 2026")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Material Procesado", "1,245.80 kg", "+15% vs 2025")
        m2.metric("CO₂e Neto Evitado", "8,920.40 kg", "+22%")
        m3.metric("Aprovechamiento Promedio", "89.4%", "1.2%")
        m4.metric("Horas Trabajo Generadas", "3,450 hrs", "+310 hrs")

        st.write("---")
        st.info(
            "📈   Aquí se visualizarán los gráficos acumulados conforme guardes"
            " informes terminados en la base de datos."
        )

    # --- PESTAÑA: HISTORIAL COMPLETO ---
    elif st.session_state.pestaña_activa == "🗂️   Historial Completo":
        st.subheader("🗂️   Histórico de Proyectos Finalizados")
        proyectos_completados = cargar_proyectos(estado="COMPLETADO")

        if proyectos_completados:
            df_comp = pd.DataFrame(proyectos_completados)
            st.dataframe(df_comp, use_container_width=True)
        else:
            st.info(
                "Aún no se registran proyectos marcados como COMPLETADO en la base de"
                " datos."
            )
