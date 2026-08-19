import datetime
import io
import re
import random
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

# --- PERSONAL BASE DE CONFECCIÓN Y ACABADO ---
PERSONAL_CONFECCION_BASE = [
    "Celinda Gutierrez Delgado",
    "Guadalupe Guerra Cespedes",
    "Isabel Estrada Sandoval",
    "Carmen Cespedes Borda",
    "Mavela Espinoza",
    "Juana Padilla Ruiz",
    "Felicita Sandoval Vilchez",
    "Luciana Jara Estrada",
    "Genaro Jara Garcia",
    "Yovana Davila",
    "Katherine Hilario Vilca",
    "Rody Jara Rucana",
    "Lucila Campos",
    "Tiffany Landa Rios",
    "Sara Mallqui Herrada",
    "Erlith Paima",
    "Sonia Panduro Torres",
    "Cintya Rincon",
    "Dixie Hidalgo Martel",
    "Janeth Mescco Bautista",
    "Judith Cueva Vargas",
    "Linfa Tauche",
    "Maricela Nieto",
    "Sofia Moya Reyes",
    "Carmen Vizarreta Lozada",
    "Genoveva Vizarreta Lozada",
    "Gathy Perez Ortiz",
    "Omar Prada",
    "Yovana Davila Ramirez",
    "Rosario Evelin Blas Alcala",
    "Esmeralda Tandazo Briceño",
    "Jhoel Angel Dominguez Rementeria",
    "Pedro Estrada Ramos",
    "Victor Auccapuri San Miguel",
    "Gabriel Manrique Hurtado",
    "Evelyn Prada Vizarreta",
    "Eugenia Almanza Huere",
    "Nicolle Estrada Yabe",
    "Oswaldo Jara Garcia",
    "Noelia Gonzales Lopez",
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
    if not nombre_producto:
        return 0.35
    for prod_key, tiempo in TIEMPOS_ESTIMADOS_PRODUCTO.items():
        if prod_key.lower() in nombre_producto.lower():
            return tiempo
    return 0.35


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

# --- DISTANCIAS APROXIMADAS (KM) A LAS FLORES, SAN JUAN DE LURIGANCHO ---
DISTANCIAS_LIMA_SJL = {
    "San Juan de Lurigancho (Local)": 4.0,
    "Ancón": 48.0,
    "Ate": 14.0,
    "Barranco": 18.5,
    "Bellavista (Callao)": 17.0,
    "Breña": 10.5,
    "Callao (Cercado)": 18.0,
    "Carabayllo": 25.0,
    "Carmen de la Legua Reynoso (Callao)": 15.0,
    "Chaclacayo": 28.0,
    "Chorrillos": 22.0,
    "Cieneguilla": 32.0,
    "Comas": 18.0,
    "El Agustino": 6.0,
    "Independencia": 12.0,
    "Jesús María": 12.0,
    "La Molina": 15.0,
    "La Perla (Callao)": 18.0,
    "La Punta (Callao)": 21.0,
    "La Victoria": 9.5,
    "Lima (Cercado de Lima)": 9.0,
    "Lince": 12.5,
    "Los Olivos": 15.0,
    "Lurigancho-Chosica": 36.0,
    "Lurín": 36.0,
    "Magdalena del Mar": 15.0,
    "Mi Perú (Callao)": 32.0,
    "Miraflores": 16.0,
    "Pachacámac": 34.0,
    "Pucusana": 72.0,
    "Pueblo Libre": 13.5,
    "Puente Piedra": 28.0,
    "Punta Hermosa": 52.0,
    "Punta Negra": 56.0,
    "Rímac": 7.5,
    "San Bartolo": 60.0,
    "San Borja": 12.0,
    "San Isidro": 13.5,
    "San Juan de Miraflores": 20.0,
    "San Luis": 10.0,
    "San Martín de Porres": 13.0,
    "San Miguel": 15.5,
    "Santa Anita": 8.0,
    "Santa María del Mar": 63.0,
    "Santa Rosa": 42.0,
    "Santiago de Surco": 17.0,
    "Surquillo": 14.5,
    "Ventanilla (Callao)": 30.0,
    "Villa El Salvador": 28.0,
    "Villa María del Triunfo": 24.0,
    "➕ Otro / Fuera de Lima (Ingreso manual)": 0.0,
}

# --- FACTORES DE BORDADO O ESTAMPADO ---
FACTORES_BORDADO = {
    "Sin bordado / Ninguno": 0.0,
    "Estampado DTF": 0.020,
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
    page_icon="♻️",
    layout="wide",
)

# --- ESTILOS CSS ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        --brand-900: #0F172A;
        --brand-700: #1E3A8A;
        --brand-500: #2563EB;
        --brand-100: #DBEAFE;
        --ink: #1E293B;
        --ink-muted: #64748B;
        --border: #E2E8F0;
        --surface: #F8FAFC;
        --radius: 14px;
    }

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    div[data-testid="stNumberInput"] button { display: none !important; }
    div[data-testid="stNumberInput"] input { text-align: left; }

    .hero-header {
        background: linear-gradient(135deg, var(--brand-900) 0%, var(--brand-700) 50%, var(--brand-500) 100%);
        color: white;
        padding: 24px 30px;
        border-radius: var(--radius);
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
        background-color: var(--surface);
        border-right: 1px solid var(--border);
    }

    .sidebar-section-title {
        color: var(--ink-muted);
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 15px;
        margin-bottom: 8px;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: var(--radius) !important;
        border: 1px solid var(--border) !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
        transition: box-shadow 0.2s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
    }

    div[data-testid="stButton"] button, div[data-testid="stDownloadButton"] button {
        border-radius: 10px;
        font-weight: 600;
        transition: transform 0.12s ease, box-shadow 0.12s ease;
        border: 1px solid var(--border);
    }
    div[data-testid="stButton"] button:hover, div[data-testid="stDownloadButton"] button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 10px rgba(15, 23, 42, 0.10);
    }
    div[data-testid="stButton"] button[kind="primary"] {
        background: linear-gradient(135deg, var(--brand-700) 0%, var(--brand-500) 100%);
        border: none;
    }

    div[data-testid="stMetric"] {
        background-color: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 14px 16px;
    }
    div[data-testid="stMetricLabel"] { color: var(--ink-muted); }

    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] {
        border-radius: 8px !important;
    }

    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 8px; }
    ::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
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
except KeyError:
    st.error(
        "⚠️ No se encontraron las credenciales de Supabase en `st.secrets`.\n\n"
        "Configura `SUPABASE_URL` y `SUPABASE_KEY` dentro de `[supabase]` en "
        "`.streamlit/secrets.toml` (local) o en **Settings → Secrets** "
        "(Streamlit Cloud)."
    )
    st.stop()
except Exception as e:
    st.error(f"⚠️ No se pudo conectar con Supabase: {e}")
    st.stop()


def cargar_proyectos(estado=None):
    """Carga proyectos desde Supabase."""
    try:
        query = supabase.table("proyectos").select("*")
        if estado:
            query = query.eq("estado", estado)
        response = query.execute()
        return response.data
    except Exception as e:
        st.warning(f"⚠️ No se pudieron cargar los proyectos: {e}")
        return []


def eliminar_proyecto_bd(proyecto_id, codigo_proy):
    """Elimina definitivamente un proyecto de la base de datos."""
    try:
        if proyecto_id:
            supabase.table("proyectos").delete().eq("id", proyecto_id).execute()
        elif codigo_proy:
            supabase.table("proyectos").delete().eq("codigo", codigo_proy).execute()
        return True
    except Exception as e:
        st.error(f"❌ Error al eliminar el proyecto: {e}")
        return False


# --- DIÁLOGO MODAL DE CONFIRMACIÓN DE ELIMINACIÓN ---
@st.dialog("⚠️ Confirmar Eliminación Permanente")
def modal_confirmar_eliminacion(proyecto):
    st.warning(
        f"¿Estás seguro de que deseas eliminar permanentemente el proyecto **{proyecto.get('cliente', 'Sin Nombre')}** (`{proyecto.get('codigo', '')}`)?\n\n"
        "Esta acción **no se puede deshacer** y borrará todos los datos asociados de la base de datos."
    )
    col_confirm, col_cancel = st.columns(2)
    
    if col_confirm.button("🚨 Sí, Eliminar Definitivamente", use_container_width=True, type="primary"):
        exito = eliminar_proyecto_bd(proyecto.get("id"), proyecto.get("codigo"))
        if exito:
            st.session_state.proyecto_editar = {}
            st.toast("🗑️ Proyecto eliminado con éxito.")
            st.rerun()

    if col_cancel.button(" Cancelar", use_container_width=True):
        st.rerun()


# --- CLASE CANVAS PERSONALIZADA PARA EL PIE DE PÁGINA ---
class ReporteCanvas(canvas.Canvas):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            self.draw_footer()
            super().showPage()
        super().save()

    def draw_footer(self):
        self.saveState()
        self.setFont("Helvetica", 7)
        self.setFillColor(colors.HexColor("#94A3B8"))

        linea_1 = "Promoviendo el desarrollo sostenible a través de la economía circular y el empoderamiento de mujeres"
        linea_2 = "emprendedoras"

        self.drawCentredString(612 / 2.0, 22, linea_1)
        self.drawCentredString(612 / 2.0, 12, linea_2)
        self.restoreState()


# --- GENERADOR DEL PDF OFICIAL COMPLETO ---
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
    lista_anexos=None,
):
    kg_recibidos = sum([item["peso_total"] for item in lista_items])
    emisiones_proceso = (
        emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado
    )
    co2_neto = co2_evitado_total - emisiones_proceso
    total_prod_unidades = sum([p_item["cantidad"] for p_item in lista_productos])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=45,
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

    elements.append(Paragraph("INFORME TÉCNICO DE VALORIZACIÓN TEXTIL", h1_style))
    elements.append(
        Paragraph(
            "Medición de Impacto Ambiental, Trazabilidad y Gestión Social de"
            f" Upcycling<br/><b>CÓDIGO: {codigo_proy}</b>",
            sub_style,
        )
    )

    resumen_texto = f"""
    Proyecto de economía circular implementado para <b>{cliente}</b>, transformando <b>{total_procesado:.2f} kg</b> 
    de textiles en desuso mediante upcycling, con la elaboración de <b>{total_prod_unidades}</b> productos, participación 
    de <b>{total_personas_social}</b> personas y un impacto neto evitado de <b>{co2_neto:.2f} kg</b> de CO₂e.
    """

    resumen_style = ParagraphStyle(
        "Resumen",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        alignment=4,
        spaceBefore=4,
        spaceAfter=6,
    )

    elements.append(Paragraph(resumen_texto, resumen_style))
    elements.append(Spacer(1, 4))

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
            Paragraph("CO2e NETO EVITADO", card_sub),
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

    elements.append(Paragraph("1. FICHA GENERAL DEL PROYECTO Y TRAZABILIDAD", h2_style))
    elements.append(
        Paragraph(
            "Datos generales que identifican al cliente, el tipo de proyecto y el "
            "flujo logístico del material, desde el punto de origen hasta su "
            "destino final en el taller.",
            sub_style,
        )
    )
    data_ficha = [
        [
            Paragraph("Cliente / Empresa", cell_bold),
            Paragraph(f"{cliente} (RUC: {ruc})", cell_style),
            Paragraph("Área / Responsable", cell_bold),
            Paragraph(
                f"{area} / " + "<br/>".join(
                    f"• {r}" for r in responsable.split(", ") if r.strip()
                ),
                cell_style,
            ),
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

    elements.append(
        Paragraph("2. INGRESO DE MATERIAL Y EVIDENCIA FOTOGRÁFICA", h2_style)
    )
    elements.append(
        Paragraph(
            "Detalle de cada tipo de prenda o producto recibido del cliente, con su "
            "peso registrado al ingreso y la evidencia fotográfica correspondiente, "
            "como respaldo del material que da inicio al proceso de upcycling.",
            sub_style,
        )
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

    elements.append(Paragraph("3. TRAZABILIDAD DEL PROCESO EN UPCYCLING", h2_style))
    elements.append(
        Paragraph(
            "Seguimiento del material a través de cada etapa del proceso "
            "(clasificación, lavado, corte, confección, entrega), registrando "
            "fecha, responsable y peso en cada punto de control para garantizar "
            "transparencia frente al cliente.",
            sub_style,
        )
    )
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

    for p_item in lista_productos:
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

    elements.append(
        Paragraph("6. RESUMEN DE IMPACTO AMBIENTAL DEL PROYECTO (CO2e)", h2_style)
    )
    elements.append(
        Paragraph(
            "Balance de emisiones de CO2 equivalente: el CO2 evitado al no fabricar "
            "prendas nuevas, menos las emisiones propias generadas por el proceso "
            "de transporte, lavado, corte y bordado o estampado, da como resultado el impacto "
            "ambiental neto del proyecto.",
            sub_style,
        )
    )
    data_co2_box = [
        [
            Paragraph("<b>(+) CO2 Evitado por Upcycling</b>", card_sub),
            Paragraph("<b>(-) Emisiones del Proceso</b>", card_sub),
            Paragraph("<b>(=) Impacto Ambiental Neto</b>", card_sub),
        ],
        [
            Paragraph(f"<b>{co2_evitado_total:.2f} kg CO2e</b>", card_title),
            Paragraph(f"<b>{emisiones_proceso:.2f} kg CO2e</b>", card_title),
            Paragraph(f"<b>{co2_neto:.2f} kg CO2e</b>", card_title),
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
    elements.append(
        Paragraph(
            "Personal a cargo de las actividades centralizadas de corte de tela y "
            "logística, con los días y horas dedicados a cada proyecto.",
            sub_style,
        )
    )
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

    if lista_confeccion:
        elements.append(
            Paragraph(
                "<b>Desglose del Personal de Confección y Acabado</b>", cell_bold
            )
        )
        elements.append(
            Paragraph(
                "Personal encargado de la elaboración de cada producto bajo modalidad "
                "descentralizada, con el tiempo dedicado por unidad y el total de "
                "horas generadas.",
                sub_style,
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

    elements.append(Spacer(1, 10))
    elements.append(Paragraph("8. CONCLUSIÓN", h2_style))

    conclusion_style = ParagraphStyle(
        "ConclusionText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=13,
        alignment=4,
        textColor=colors.HexColor("#334155"),
        spaceBefore=4,
        spaceAfter=10,
    )

    texto_conclusion = """
    El proyecto permitió gestionar de manera eficiente los textiles en desuso del cliente, 
    asegurando su aprovechamiento mediante un proceso organizado y trazable.<br/><br/>
    Los resultados obtenidos reflejan la capacidad de integrar este tipo de iniciativas 
    dentro de la operación de las empresas, generando valor a partir de materiales existentes.<br/><br/>
    Este tipo de iniciativas permite a las empresas gestionar sus materiales en desuso de 
    manera trazable, generando beneficios ambientales y sociales medibles, e integrando 
    principios de economía circular dentro de su operación.
    """

    elements.append(Paragraph(texto_conclusion, conclusion_style))

    # --- 9. SECCIÓN ANEXOS ---
    anexos_validos = [a for a in (lista_anexos or []) if a.get("foto") or a.get("nota", "").strip()]
    if anexos_validos:
        elements.append(PageBreak())
        elements.append(Paragraph("9. ANEXOS Y REGISTRO FOTOGRÁFICO", h2_style))
        elements.append(
            Paragraph(
                "Evidencias visuales complementarias del proceso: fotos en taller, colaboradoras, "
                "acabados y detalles del proyecto.",
                sub_style,
            )
        )
        elements.append(Spacer(1, 4))

        for idx_a, anexo in enumerate(anexos_validos, 1):
            img_cell = obtener_imagen_pdf(anexo["foto"], width=480, height=215)
            nota_texto = anexo["nota"].strip() if anexo["nota"].strip() else "Sin descripción adicional."

            card_data = [
                [Paragraph(f"<b>Evidencia Fotográfica {idx_a}</b>", cell_bold)],
                [img_cell],
                [Paragraph(f"<b>Nota / Descripción:</b> {nota_texto}", cell_style)],
            ]

            t_card = Table(card_data, colWidths=[520])
            t_card.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("ALIGN", (0, 1), (0, 1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ])
            )

            elements.append(t_card)
            elements.append(Spacer(1, 8))

            if idx_a % 2 == 0 and idx_a < len(anexos_validos):
                elements.append(PageBreak())

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

if "lista_personal_confeccion" not in st.session_state:
    st.session_state.lista_personal_confeccion = list(PERSONAL_CONFECCION_BASE)

if "num_anexos" not in st.session_state:
    st.session_state.num_anexos = 1

if "pct_aprovechamiento_random" not in st.session_state:
    st.session_state.pct_aprovechamiento_random = round(random.uniform(0.88, 0.94), 4)

if "pct_transformado_ratio" not in st.session_state:
    st.session_state.pct_transformado_ratio = round(random.uniform(0.78, 0.83), 4)

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
            st.subheader("🔐 Iniciar Sesión")
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

        if st.button(
            "⚡     Carga Rápida Histórica",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.pestaña_activa == "⚡     Carga Rápida Histórica"
                else "secondary"
            ),
        ):
            st.session_state.pestaña_activa = "⚡     Carga Rápida Histórica"
            st.rerun()

        st.markdown(
            '<p class="sidebar-section-title">Proyectos Pendientes</p>',
            unsafe_allow_html=True,
        )

        if proyectos_wip:
            for p in proyectos_wip:
                cli_nombre = p.get("cliente", "Sin Nombre")
                cod_ref = p.get("codigo", "")
                label_btn = f"📁 {cli_nombre}" + (f" ({cod_ref})" if cod_ref else "")

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
            if st.button("📋 Ver Lista en Proceso", use_container_width=True):
                st.session_state.pestaña_activa = "📋 Proyectos en Proceso"
                st.rerun()
        else:
            st.caption("📭 No hay proyectos en borrador")

        st.markdown(
            '<p class="sidebar-section-title">Analítica e Histórico</p>',
            unsafe_allow_html=True,
        )

        if st.button(
            "📊 Dashboard 2026",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.pestaña_activa == "📊 Dashboard 2026"
                else "secondary"
            ),
        ):
            st.session_state.pestaña_activa = "📊 Dashboard 2026"
            st.rerun()

        if st.button(
            "🗂️ Historial Completo",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.pestaña_activa == "🗂️ Historial Completo"
                else "secondary"
            ),
        ):
            st.session_state.pestaña_activa = "🗂️ Historial Completo"
            st.rerun()

        st.write("---")
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.autenticado = False
            st.session_state.proyecto_editar = {}
            st.rerun()

    st.markdown(
        f"""
        <div class="hero-header">
            <h1>📄 Sistema de Gestión de Informes Técnicos</h1>
            <p>Sección Activa: <b>{st.session_state.pestaña_activa}</b></p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # --- VISTA: CARGA RÁPIDA HISTÓRICA ---
    if st.session_state.pestaña_activa == "⚡     Carga Rápida Histórica":
        st.subheader("⚡ Carga Rápida de Proyectos Históricos / Pasados")
        st.caption(
            "Utiliza este formulario simplificado para ingresar rápidamente métricas "
            "consolidadas de proyectos pasados directamente al historial y métricas generales."
        )

        with st.container(border=True):
            st.markdown("##### 1. Datos Generales del Proyecto")
            rq1, rq2, rq3, rq4 = st.columns(4)
            fast_cliente = rq1.text_input("Cliente / Empresa *")
            fast_ruc = rq2.text_input("RUC (11 dígitos) *", max_chars=11)
            fast_tipo = rq3.selectbox(
                "Tipo de Proyecto",
                ["Upcycling", "Producción desde cero", "Cambio de logo", "Mixto", "Banner"],
            )
            fast_resp = rq4.text_input("Responsable", value="Sostenibilidad")

            rq5, rq6 = st.columns(2)
            fast_f_ini = rq5.date_input("Fecha Inicio", value=datetime.date.today(), format="DD/MM/YYYY")
            fast_f_fin = rq6.date_input("Fecha Término", value=datetime.date.today(), format="DD/MM/YYYY")

            fe_ini_str = fast_f_ini.strftime("%d/%m/%Y")
            fe_fin_str = fast_f_fin.strftime("%d/%m/%Y")
            cli_clean = fast_cliente.strip() if fast_cliente.strip() else "EMPRESA"
            fast_codigo = f"{cli_clean}_{fast_f_ini.strftime('%d%m%Y')}-{fast_f_fin.strftime('%d%m%Y')}"

            st.info(f"🆔 **Código Generado:** `{fast_codigo}`")

        with st.container(border=True):
            st.markdown("##### 2. Métricas Consolidadas")
            rm1, rm2, rm3 = st.columns(3)
            fast_peso = rm1.number_input("Material Procesado Total (kg) *", min_value=0.0, step=0.1)
            fast_unid = rm2.number_input("Unidades Producidas *", min_value=0, step=1)
            fast_co2 = rm3.number_input("CO₂e Neto Evitado (kg) *", min_value=0.0, step=0.1)

            rm4, rm5, rm6 = st.columns(3)
            fast_horas = rm4.number_input("Horas de Trabajo Generadas *", min_value=0.0, step=0.5)
            fast_personas = rm5.number_input("Personas / Beneficiarios *", min_value=0, step=1)
            fast_aprovechamiento = rm6.number_input("% Aprovechamiento *", min_value=0.0, max_value=100.0, value=100.0, step=0.1)

            fast_origen = st.text_input("Punto Origen", value="Sede Central")

        st.write("")

        if st.button("🚀 Guardar Proyecto Histórico Directamente", type="primary", use_container_width=True):
            if not fast_cliente.strip():
                st.error("El campo **Cliente / Empresa** es obligatorio.")
            elif not fast_ruc.strip() or not re.fullmatch(r"\d{11}", fast_ruc.strip()):
                st.error("El **RUC** es obligatorio y debe tener 11 dígitos.")
            else:
                try:
                    with st.spinner("Registrando proyecto histórico..."):
                        supabase.table("proyectos").upsert({
                            "codigo": fast_codigo,
                            "cliente": fast_cliente,
                            "ruc": fast_ruc,
                            "tipo_proyecto": fast_tipo,
                            "responsable": fast_resp,
                            "fecha": f"{fe_ini_str} - {fe_fin_str}",
                            "estado": "COMPLETADO",
                            "peso_recibido": fast_peso,
                            "peso_transformado": fast_peso,
                            "aprovechamiento": fast_aprovechamiento,
                            "co2_neto": fast_co2,
                            "horas_totales": fast_horas,
                            "productos_unids": fast_unid,
                            "punto_origen": fast_origen,
                        }).execute()
                    st.success(f"✅ ¡Proyecto **{fast_cliente}** registrado exitosamente en el Histórico!")
                    st.toast("⚡ Guardado rápido completado")
                except Exception as e:
                    st.error(f"⚠️ Error al registrar el proyecto: {e}")

    # --- VISTA: PROYECTOS EN PROCESO ---
    elif st.session_state.pestaña_activa == "📋 Proyectos en Proceso":
        st.subheader("📋 Lista de Proyectos en Proceso (Borradores)")
        st.caption("Proyectos guardados pendientes de culminación o emisión definitiva.")
        
        proyectos_lista = cargar_proyectos()
        borradores = [p for p in proyectos_lista if p.get("estado") == "EN_PROCESO"]

        if borradores:
            for b in borradores:
                with st.container(border=True):
                    bc1, bc2, bc3 = st.columns([3, 2, 2])
                    bc1.markdown(f"**Cliente:** {b.get('cliente', 'Sin Nombre')}")
                    bc1.caption(f"Código: `{b.get('codigo', '')}`")
                    bc2.markdown(f"**Tipo:** {b.get('tipo_proyecto', 'Upcycling')}")
                    bc2.caption(f"Fecha: {b.get('fecha', '')}")
                    
                    if bc3.button("✏️ Retomar Edición", key=f"retomar_{b.get('id', b.get('codigo'))}", use_container_width=True, type="primary"):
                        st.session_state.proyecto_editar = b
                        st.session_state.pestaña_activa = "➕     Nuevo Reporte PDF"
                        st.rerun()
        else:
            st.info("📭 No hay borradores en proceso actualmente.")

    # --- VISTA: DASHBOARD 2026 ---
    elif st.session_state.pestaña_activa == "📊 Dashboard 2026":
        st.subheader("📊 Dashboard de Sostenibilidad e Impacto 2026")
        st.caption("Métricas consolidadas de todos los proyectos completados en el sistema.")

        proyectos_lista = cargar_proyectos()
        completados = [p for p in proyectos_lista if p.get("estado") == "COMPLETADO"]

        tot_peso = sum([float(p.get("peso_recibido", 0) or 0) for p in completados])
        tot_co2 = sum([float(p.get("co2_neto", 0) or 0) for p in completados])
        tot_horas = sum([float(p.get("horas_totales", 0) or 0) for p in completados])
        tot_unids = sum([int(p.get("productos_unids", 0) or 0) for p in completados])

        dm1, dm2, dm3, dm4 = st.columns(4)
        dm1.metric("📦 Material Reciclado", f"{tot_peso:.2f} kg")
        dm2.metric("🌍 CO₂e Neto Evitado", f"{tot_co2:.2f} kg")
        dm3.metric("⏳ Horas de Trabajo", f"{tot_horas:.2f} hrs")
        dm4.metric("🛍️ Productos Creados", f"{tot_unids} unid")

        st.write("")
        st.markdown("##### 📋 Resumen General de Proyectos Registrados")
        if completados:
            df_comp = pd.DataFrame(completados)
            columnas_mostrar = ["codigo", "cliente", "tipo_proyecto", "peso_recibido", "co2_neto", "horas_totales", "productos_unids"]
            nombres_cols = {
                "codigo": "Código",
                "cliente": "Cliente",
                "tipo_proyecto": "Tipo",
                "peso_recibido": "Peso (kg)",
                "co2_neto": "CO₂e Evitado (kg)",
                "horas_totales": "Horas",
                "productos_unids": "Unidades",
            }
            df_tabla = df_comp[[c for c in columnas_mostrar if c in df_comp.columns]].rename(columns=nombres_cols)
            st.dataframe(df_tabla, use_container_width=True, hide_index=True)
        else:
            st.info("📭 Aún no hay proyectos completados para mostrar en las métricas.")

    # --- VISTA: HISTORIAL COMPLETO ---
    elif st.session_state.pestaña_activa == "🗂️ Historial Completo":
        st.subheader("🗂️ Historial Completo de Proyectos")
        st.caption("Listado general de todos los proyectos registrados en la base de datos.")

        proyectos_lista = cargar_proyectos()
        if proyectos_lista:
            for p in proyectos_lista:
                with st.container(border=True):
                    hc1, hc2, hc3, hc4 = st.columns([3, 2, 2, 1.5])
                    hc1.markdown(f"**{p.get('cliente', 'Sin Nombre')}**")
                    hc1.caption(f"ID/Código: `{p.get('codigo', '')}`")
                    hc2.markdown(f"Estado: **{p.get('estado', 'N/D')}**")
                    hc2.caption(f"Tipo: {p.get('tipo_proyecto', 'Upcycling')}")
                    hc3.markdown(f"Peso: `{float(p.get('peso_recibido', 0) or 0):.2f} kg`")
                    hc3.caption(f"Fecha: {p.get('fecha', 'N/D')}")

                    if hc4.button("🗑️ Eliminar", key=f"hist_del_{p.get('id', p.get('codigo'))}", use_container_width=True):
                        modal_confirmar_eliminacion(p)
        else:
            st.info("📭 No hay proyectos registrados en el historial.")

    # --- VISTA: NUEVO REPORTE PDF ---
    elif st.session_state.pestaña_activa == "➕     Nuevo Reporte PDF":
        p_edit = st.session_state.proyecto_editar

        if p_edit:
            st.warning(
                "✏️ **Modo Edición Activo:** Modificando borrador de"
                f" **{p_edit.get('cliente', '')}** (`{p_edit.get('codigo', '')}`)"
            )
            col_desc, col_elim = st.columns([2, 2])
            if col_desc.button("❌ Descartar selección y limpiar formulario", use_container_width=True):
                st.session_state.proyecto_editar = {}
                st.rerun()
            
            if col_elim.button("🗑️ Eliminar Proyecto Definitivamente", use_container_width=True):
                modal_confirmar_eliminacion(p_edit)

        with st.container(border=True):
            st.subheader("1. Ficha General del Proyecto")

            fechas_raw = p_edit.get("fecha", " - ").split(" - ")
            try:
                def_f_ini = datetime.datetime.strptime(
                    fechas_raw[0].strip(), "%d/%m/%Y"
                ).date()
            except Exception:
                def_f_ini = datetime.date.today()

            try:
                def_f_fin = datetime.datetime.strptime(
                    fechas_raw[1].strip(), "%d/%m/%Y"
                ).date()
            except Exception:
                def_f_fin = datetime.date.today()

            c1, c2, c5, c6 = st.columns(4)
            cliente = c1.text_input(
                "Cliente / Empresa *", value=p_edit.get("cliente", "")
            )

            ruc = c2.text_input(
                "RUC * (11 dígitos)", value=p_edit.get("ruc", ""), max_chars=11
            )

            fe_inicio_dt = c5.date_input(
                "Fecha Inicio *", value=def_f_ini, format="DD/MM/YYYY"
            )
            fe_fin_dt = c6.date_input(
                "Fecha Término *", value=def_f_fin, format="DD/MM/YYYY"
            )

            fe_inicio = fe_inicio_dt.strftime("%d/%m/%Y")
            fe_fin = fe_fin_dt.strftime("%d/%m/%Y")

            str_empresa = cliente.strip() if cliente.strip() else "EMPRESA"
            codigo_proy = f"{str_empresa}_{fe_inicio_dt.strftime('%d%m%Y')}-{fe_fin_dt.strftime('%d%m%Y')}"

            st.info(
                f"🆔 **Código del Proyecto (Generado automáticamente):** `{codigo_proy}`"
            )

            c4, c7, c8, c9 = st.columns(4)
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
                "Tipo de Proyecto *", opciones_tipo_proyecto, index=idx_tipo
            )

            RESPONSABLES_BASE = [
                "Evelyn Prada Vizarreta",
                "Gabriel Manrique Hurtado",
            ]

            responsables_guardados = p_edit.get("responsables", [])
            if not isinstance(responsables_guardados, list):
                responsables_guardados = [
                    r.strip() for r in str(responsables_guardados).split(",") if r.strip()
                ]

            responsable_anterior = p_edit.get("responsable", "")
            if responsable_anterior and not responsables_guardados:
                responsables_guardados = [
                    r.strip() for r in str(responsable_anterior).split(",") if r.strip()
                ]

            opciones_responsables = list(dict.fromkeys(
                RESPONSABLES_BASE + responsables_guardados
            ))

            responsables_seleccionados = c7.multiselect(
                "Responsable *",
                options=opciones_responsables,
                default=[
                    r for r in responsables_guardados
                    if r in opciones_responsables
                ],
                placeholder="Selecciona uno o más responsables",
                key="responsables_proyecto",
            )

            nuevo_responsable = c7.text_input(
                "➕ Agregar otro responsable",
                placeholder="Escribe el nombre completo",
                key="nuevo_responsable_proyecto",
            )

            if nuevo_responsable.strip():
                nuevo_nombre = nuevo_responsable.strip()
                if nuevo_nombre not in responsables_seleccionados:
                    responsables_seleccionados.append(nuevo_nombre)

            responsable = ", ".join(responsables_seleccionados)

            area = c8.text_input("Área", value="Sostenibilidad", disabled=True)
            guia_remision = c9.text_input(
                "Nº Guía Remisión", value=p_edit.get("guia", "")
            )

            origen = st.text_input("Punto Origen *", value=p_edit.get("origen", ""))
            destino = "Jr. Las Caléndulas 610, Las Flores, SJL."

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
                    "Tipo de Producto / Prenda *", opciones_prendas, key=f"desc_{i}"
                )
                unid = col_unid.number_input(
                    "Ingreso (unid.) *", min_value=0, value=0, key=f"unid_{i}"
                )
                
                p_total = col_peso.number_input(
                    "Peso Total (kg) *",
                    min_value=0.0,
                    value=0.0,
                    step=0.05,
                    key=f"tot_input_{i}",
                )
                peso_u = p_total / unid if unid > 0 else 0.0
                
                col_tot.text_input(
                    "Peso Unitario",
                    value=f"{peso_u:.2f} kg",
                    disabled=True,
                    key=f"peso_u_{i}_{unid}_{p_total}",
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
            
            peso_corte_conf_auto = round(peso_total_recibido * st.session_state.pct_aprovechamiento_random, 2)

            etapas_fijas = [
                {
                    "etapa": "Clasificación",
                    "fecha": datetime.date.today(),
                    "resp_defecto": "Evelyn Prada Vizarreta",
                    "peso_defecto": peso_total_recibido,
                    "tipo": "Registro interno",
                },
                {
                    "etapa": "Lavado",
                    "fecha": datetime.date.today(),
                    "resp_defecto": "Lavandería",
                    "peso_defecto": peso_total_recibido,
                    "tipo": "Servicio Externo",
                },
                {
                    "etapa": "Corte",
                    "fecha": datetime.date.today(),
                    "resp_defecto": "Taller de corte (5 integrantes)",
                    "peso_defecto": peso_corte_conf_auto,
                    "tipo": "Pesaje real",
                },
                {
                    "etapa": "Confección",
                    "fecha": datetime.date.today(),
                    "resp_defecto": "Producción descentralizada",
                    "peso_defecto": peso_corte_conf_auto,
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
                    "Fecha *",
                    value=item_fijo["fecha"],
                    format="DD/MM/YYYY",
                    key=f"tr_fecha_{i}",
                )

                permitir_editar = c_edit_chk.checkbox("✏️ Editar", key=f"chk_edit_{i}")
                e_res = c_resp.text_input(
                    "Responsable *",
                    value=item_fijo["resp_defecto"],
                    disabled=not permitir_editar,
                    key=f"tr_resp_{i}",
                )

                val_peso_etapa = float(item_fijo["peso_defecto"])
                e_pes_str = c_peso.text_input(
                    "Peso (kg) *",
                    value=f"{val_peso_etapa:.2f}",
                    disabled=not permitir_editar,
                    key=f"tr_peso_{i}_{val_peso_etapa:.2f}_{permitir_editar}",
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
                    "Seleccionar Producto Base *",
                    st.session_state.catalogo_productos,
                    key=f"prod_sel_{i}",
                )

                if prod_seleccionado == "➕ Otro (Escribir nuevo producto)":
                    nuevo_nombre = col_pnom_nuevo.text_input(
                        "Escriba el Nuevo Producto *", key=f"prod_nuevo_txt_{i}"
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
                        key=f"prod_dis_{i}_{prod_seleccionado}",
                    )
                    nombre_final = prod_seleccionado

                p_cant = col_pcant.number_input(
                    "Cantidad (Unid.) *", min_value=0, value=0, key=f"prod_cant_{i}"
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
                "🧮 **Suma Total de Productos Obtenidos:**"
                f" {total_prod_unid} unidades"
            )

        st.write("")

        with st.container(border=True):
            st.subheader("5. Balance de Material")
            st.info(
                f"⚖️     **Material Recibido (calculado automáticamente):** {peso_total_recibido:.2f} kg"
            )

            pct_aprov_auto = st.session_state.pct_aprovechamiento_random
            pct_transf_auto = min(st.session_state.pct_transformado_ratio, pct_aprov_auto - 0.05)
            pct_retazos_auto = pct_aprov_auto - pct_transf_auto

            mat_transf_def = round(peso_total_recibido * pct_transf_auto, 2)
            retazos_def = round(peso_total_recibido * pct_retazos_auto, 2)
            perdida_def = round(peso_total_recibido - mat_transf_def - retazos_def, 2) if peso_total_recibido > 0 else 0.0

            editar_balance = st.checkbox("✏️ Editar balance manualmente", key="chk_edit_balance")

            col_bm1, col_bm2 = st.columns(2)
            mat_transformado = col_bm1.number_input(
                "Material transformado en productos (kg)",
                min_value=0.0,
                value=float(mat_transf_def),
                step=0.1,
                disabled=not editar_balance,
                key=f"bm_mat_transf_{peso_total_recibido:.2f}_{editar_balance}",
            )
            retazos_aprovechables = col_bm2.number_input(
                "Retazos aprovechables (kg)",
                min_value=0.0,
                value=float(retazos_def),
                step=0.1,
                disabled=not editar_balance,
                key=f"bm_retazos_{peso_total_recibido:.2f}_{editar_balance}",
            )

            col_bm3, _ = st.columns([1, 1])
            perdida_no_aprovechable = col_bm3.number_input(
                "Pérdida no aprovechable (kg)",
                min_value=0.0,
                value=float(perdida_def),
                step=0.1,
                disabled=not editar_balance,
                key=f"bm_perdida_{peso_total_recibido:.2f}_{editar_balance}",
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

            st.markdown("##### 🚚 A. Cálculo de Transporte")
            st.caption("Destino Fijo: **Taller Las Flores, San Juan de Lurigancho (SJL)**")
            
            ct1, ct2, ct3, ct4 = st.columns([2.5, 1.2, 1.8, 1.5])
            
            distrito_sel = ct1.selectbox(
                "Distrito de Origen (Recojo de Material) *",
                list(DISTANCIAS_LIMA_SJL.keys()),
                index=0,
                key="transporte_distrito_origen",
            )

            dist_defecto = float(DISTANCIAS_LIMA_SJL[distrito_sel])

            if distrito_sel == "➕ Otro / Fuera de Lima (Ingreso manual)":
                distancia_km = ct2.number_input(
                    "Distancia (km) *",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    key="dist_km_manual",
                )
            else:
                distancia_km = ct2.number_input(
                    "Distancia (km)",
                    min_value=0.0,
                    value=dist_defecto,
                    step=0.5,
                    key=f"dist_km_auto_{distrito_sel}",
                )

            vehiculo_sel = ct3.selectbox(
                "Tipo de Vehículo Utilizado", list(FACTORES_TRANSPORTE.keys())
            )
            recorrido_tipo = ct4.selectbox(
                "Tipo de Recorrido", ["Ida y Vuelta (2)", "Ida sola (1)"]
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
                f"Distancia considerada: **{distancia_km:.1f} km** ({recorrido_tipo}) | "
                f"Emisión de Transporte estimada: **{emisiones_transporte:.2f} kg CO₂e**"
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

            st.markdown("##### 🧵 C. Cálculo de Bordado o Estampado")
            cb1, cb2 = st.columns(2)
            cant_prendas_bordado = cb1.number_input(
                "Cantidad de prendas que requieren bordado o estampado",
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
                f"Emisión estimada (Bordado/Estampado): **{emisiones_bordado:.2f} kg CO₂e**"
            )

            emisiones_proceso = (
                emisiones_transporte
                + emisiones_lavado
                + emisiones_corte
                + emisiones_bordado
            )
            co2_neto = co2_evitado_total - emisiones_proceso

            st.warning(
                "🌍 **Total Emisiones del Proceso:**"
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

                editar_fila = c_chk.checkbox(
                    "✅", key=f"ops_chk_{idx}", label_visibility="collapsed"
                )
                nom_val = c_nom.text_input(
                    "Nombre",
                    value=p_fijo["nombre"],
                    disabled=not editar_fila,
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
                    disabled=not editar_fila,
                    key=f"ops_dias_dyn_{idx}_{val_dias_defecto}_{editar_fila}",
                    label_visibility="collapsed",
                )
                val_hdia = c_hdia.number_input(
                    "Hrs/Día",
                    min_value=0.0,
                    value=float(val_hdia_defecto),
                    step=0.5,
                    disabled=not editar_fila,
                    key=f"ops_hdia_dyn_{idx}_{val_hdia_defecto}_{editar_fila}",
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

            # Panel de Administración de Catálogo de Personal
            with st.expander("⚙️ Administrar Catálogo de Personal (Agregar, Modificar o Eliminar)"):
                tab_add, tab_edit, tab_del = st.tabs(["➕ Agregar Personal", "✏️ Modificar Nombre", "🗑️ Eliminar de la Lista"])
                
                with tab_add:
                    c_a1, c_a2 = st.columns([3, 1])
                    nuevo_integrante = c_a1.text_input(
                        "Nombre completo de la nueva persona:",
                        placeholder="Ej. Rosa María Quispe",
                        key="adm_input_add",
                    )
                    if c_a2.button("Guardar en Lista", use_container_width=True):
                        n_limpio = nuevo_integrante.strip()
                        if n_limpio and n_limpio not in st.session_state.lista_personal_confeccion:
                            st.session_state.lista_personal_confeccion.append(n_limpio)
                            st.session_state.lista_personal_confeccion.sort()
                            st.toast(f"✅ Agregado/a: {n_limpio}")
                            st.rerun()
                        elif n_limpio in st.session_state.lista_personal_confeccion:
                            st.warning("⚠️ Esta persona ya se encuentra en la lista.")

                with tab_edit:
                    c_e1, c_e2, c_e3 = st.columns([2, 2, 1])
                    pers_a_mod = c_e1.selectbox(
                        "Persona a modificar:",
                        st.session_state.lista_personal_confeccion,
                        key="adm_sel_mod",
                    )
                    nombre_modificado = c_e2.text_input(
                        "Nombre corregido:",
                        value=pers_a_mod,
                        key=f"adm_txt_mod_{pers_a_mod}",
                    )
                    if c_e3.button("Actualizar", use_container_width=True):
                        if nombre_modificado.strip() and pers_a_mod in st.session_state.lista_personal_confeccion:
                            idx_mod = st.session_state.lista_personal_confeccion.index(pers_a_mod)
                            st.session_state.lista_personal_confeccion[idx_mod] = nombre_modificado.strip()
                            st.session_state.lista_personal_confeccion.sort()
                            st.toast(f"✅ Actualizado: {nombre_modificado.strip()}")
                            st.rerun()

                with tab_del:
                    c_d1, c_d2 = st.columns([3, 1])
                    pers_a_borrar = c_d1.selectbox(
                        "Persona a eliminar del catálogo:",
                        st.session_state.lista_personal_confeccion,
                        key="adm_sel_del",
                    )
                    if c_d2.button("Eliminar", use_container_width=True):
                        if pers_a_borrar in st.session_state.lista_personal_confeccion:
                            st.session_state.lista_personal_confeccion.remove(pers_a_borrar)
                            st.toast(f"🗑️ Eliminado/a: {pers_a_borrar}")
                            st.rerun()

            lista_confeccion = []
            horas_confeccion_total = 0.0
            personas_confeccion_set = set()

            for idx, prod in enumerate(lista_productos):
                p_nom = prod["producto"]
                p_cant = prod["cantidad"]

                tiempo_base_ia = estimar_tiempo_unidad(p_nom)

                st.markdown(
                    f"**📦 Producto {idx+1}: {p_nom}** *(Cantidad Total: {p_cant} unid "
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
                        [1.8, 3.0, 1.4, 1.8, 1.8]
                    )

                    rol_sel = c_rol.selectbox(
                        "Rol *",
                        ["Confección", "Acabado"],
                        key=f"soc_rol_{idx}_{p_idx}",
                    )

                    opciones_personas = list(st.session_state.lista_personal_confeccion)
                    opcion_otro = "➕ Otro (Escribir nuevo nombre)"
                    if opcion_otro not in opciones_personas:
                        opciones_personas.append(opcion_otro)

                    persona_sel = c_persona.selectbox(
                        "Persona Encargada *",
                        opciones_personas,
                        key=f"soc_pers_sel_{idx}_{p_idx}",
                    )

                    if persona_sel == opcion_otro:
                        nuevo_nombre_escrito = c_persona.text_input(
                            "Escribe el nombre *",
                            placeholder="Nombre y Apellido",
                            key=f"soc_pers_txt_custom_{idx}_{p_idx}",
                        )
                        persona_nom = nuevo_nombre_escrito.strip() if nuevo_nombre_escrito.strip() else f"Persona {p_idx+1}"
                        if (
                            nuevo_nombre_escrito.strip()
                            and nuevo_nombre_escrito.strip() not in st.session_state.lista_personal_confeccion
                        ):
                            st.session_state.lista_personal_confeccion.append(nuevo_nombre_escrito.strip())
                            st.session_state.lista_personal_confeccion.sort()
                    else:
                        persona_nom = persona_sel

                    cant_sugerida = max(
                        1, int(p_cant / st.session_state[key_num_pers])
                    ) if p_cant > 0 else 0

                    cant_asig = c_cant_asig.number_input(
                        "Unid. Asignadas *",
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
                            "Tiempo/Unid (hrs) *",
                            min_value=0.0,
                            value=float(tiempo_base_ia),
                            step=0.05,
                            key=f"soc_tunit_{idx}_{p_idx}_{p_nom}",
                        )

                    horas_persona = cant_asig * tiempo_unitario

                    c_tot.text_input(
                        "Horas Totales",
                        value=f"{horas_persona:.2f} hrs",
                        disabled=True,
                        key=f"soc_htot_{idx}_{p_idx}",
                    )

                    horas_confeccion_total += horas_persona
                    if persona_nom.strip():
                        personas_confeccion_set.add(persona_nom.strip())

                    lista_confeccion.append({
                        "producto": p_nom,
                        "rol": rol_sel,
                        "persona": persona_nom,
                        "cantidad": cant_asig,
                        "tiempo_unitario": tiempo_unitario,
                        "horas_totales": horas_persona,
                    })

            total_horas_social = total_horas_ops + horas_confeccion_total
            total_personas_social = len(PERSONAL_FIJO_OPERACIONES) + len(
                personas_confeccion_set
            )

            st.info(
                "🧑‍🤝‍🧑 **Impacto Social Total:**"
                f" {total_horas_social:.2f} horas generadas |"
                f" {total_personas_social} personas beneficiadas."
            )

        st.write("")

        # --- SECCIÓN 8: ANEXOS (REGISTRO FOTOGRÁFICO EXTRA) ---
        with st.container(border=True):
            st.subheader("8. Anexos (Registro Fotográfico Adicional)")
            st.caption(
                "Agrega fotografías adicionales de colaboradoras con sus productos, procesos en taller, "
                "talleres de corte o evidencia de recepción/entrega con su respectiva nota descriptiva."
            )

            col_anx1, col_anx2, _ = st.columns([1, 1, 4])
            if col_anx1.button("➕     Agregar Anexo"):
                st.session_state.num_anexos += 1
                st.rerun()
            if col_anx2.button("➖     Quitar Anexo") and st.session_state.num_anexos > 0:
                st.session_state.num_anexos -= 1
                st.rerun()

            lista_anexos = []
            for a_i in range(st.session_state.num_anexos):
                st.markdown(f"**Evidencia Anexa {a_i+1}**")
                col_afoto, col_anota = st.columns([1.5, 3])

                foto_anx = col_afoto.file_uploader(
                    "Fotografía de Evidencia",
                    type=["jpg", "png", "jpeg"],
                    key=f"anx_foto_{a_i}",
                )

                if foto_anx is not None:
                    col_afoto.image(foto_anx, width=110)

                nota_anx = col_anota.text_area(
                    "Nota / Descripción de la evidencia",
                    placeholder="Ej. Colaboradora Juana Padilla elaborando productos en taller descentralizado...",
                    key=f"anx_nota_{a_i}",
                    height=90,
                )

                lista_anexos.append({
                    "foto": foto_anx,
                    "nota": nota_anx,
                })

        st.write("")

        def _validar_informe_final(cliente_val, ruc_val, responsable_val, origen_val, items_val):
            errores = []
            if not cliente_val.strip():
                errores.append("Falta 'Cliente / Empresa' en Ficha General.")
            if not ruc_val.strip() or not re.fullmatch(r"\d{11}", ruc_val.strip()):
                errores.append("El 'RUC' debe tener 11 dígitos numéricos.")
            if not responsable_val.strip():
                errores.append("Falta 'Responsable' en Ficha General.")
            if not origen_val.strip():
                errores.append("Falta 'Punto Origen' en Ficha General.")
            for i_item, v_item in enumerate(items_val, 1):
                if v_item["unidades"] <= 0 or v_item["peso_total"] <= 0:
                    errores.append(
                        f"En Ingreso de Material (Ítem {i_item}), las unidades y el "
                        "peso total deben ser mayores a 0."
                    )
            return errores

        with st.container(border=True):
            col_gen1, col_gen2, col_gen3 = st.columns([1, 1, 1])

            if col_gen2.button(
                "💾 Guardar como Borrador", use_container_width=True
            ):
                try:
                    with st.spinner("Guardando en la base de datos..."):
                        datos_borrador = {
                            "codigo": codigo_proy,
                            "cliente": cliente,
                            "ruc": ruc,
                            "tipo_proyecto": proyecto_nom,
                            "fecha": f"{fe_inicio} - {fe_fin}",
                            "estado": "EN_PROCESO",
                            "peso_recibido": peso_total_recibido,
                            "peso_transformado": mat_transformado,
                            "aprovechamiento": pct_aprovechamiento_total,
                            "co2_neto": co2_neto,
                            "horas_totales": total_horas_social,
                            "productos_unids": total_prod_unid,
                            "punto_origen": origen,
                        }

                        if p_edit.get("id"):
                            supabase.table("proyectos").update(datos_borrador).eq("id", p_edit["id"]).execute()
                        else:
                            supabase.table("proyectos").insert(datos_borrador).execute()

                    st.success("✅ Borrador guardado exitosamente.")
                    st.session_state.proyecto_editar = {}
                    st.rerun()

                except Exception as e:
                    st.error(f"⚠️ Error al guardar el borrador: {e}")

            if col_gen1.button(
                "📄 Generar y Descargar PDF",
                type="primary",
                use_container_width=True,
            ):
                errores_final = _validar_informe_final(
                    cliente, ruc, responsable, origen, lista_items
                )
                if errores_final:
                    st.error("⚠️  Por favor, corrige los siguientes errores antes de generar el PDF:")
                    for err in errores_final:
                        st.markdown(f"- {err}")
                else:
                    with st.spinner("Generando Informe Técnico PDF..."):
                        try:
                            pdf_buffer = generar_pdf_oficial(
                                cliente,
                                ruc,
                                proyecto_nom,
                                codigo_proy,
                                fe_inicio,
                                fe_fin,
                                responsable,
                                area,
                                "Textiles en desuso",
                                "Upcycling",
                                "Kilogramos (kg)",
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
                                lista_operaciones,
                                lista_confeccion,
                                total_horas_social,
                                total_personas_social,
                                co2_evitado_total,
                                emisiones_transporte,
                                emisiones_lavado,
                                emisiones_corte,
                                emisiones_bordado,
                                lista_anexos=lista_anexos,
                            )
                            st.success("✅  ¡PDF generado exitosamente!")
                            st.download_button(
                                label="📥 Descargar Informe Técnico",
                                data=pdf_buffer,
                                file_name=f"Informe_Tecnico_{codigo_proy}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                type="primary",
                            )

                            try:
                                datos_completado = {
                                    "codigo": codigo_proy,
                                    "cliente": cliente,
                                    "ruc": ruc,
                                    "tipo_proyecto": proyecto_nom,
                                    "fecha": f"{fe_inicio} - {fe_fin}",
                                    "estado": "COMPLETADO",
                                    "peso_recibido": peso_total_recibido,
                                    "peso_transformado": mat_transformado,
                                    "aprovechamiento": pct_aprovechamiento_total,
                                    "co2_neto": co2_neto,
                                    "horas_totales": total_horas_social,
                                    "productos_unids": total_prod_unid,
                                    "punto_origen": origen,
                                }
                                if p_edit.get("id"):
                                    supabase.table("proyectos").update(datos_completado).eq("id", p_edit["id"]).execute()
                                else:
                                    supabase.table("proyectos").upsert(datos_completado).execute()
                            except Exception as e_bd:
                                st.warning(f"⚠️ El PDF se generó, pero hubo un error al actualizar el estado en la BD: {e_bd}")

                        except Exception as e:
                            st.error(f"❌ Error al generar el PDF: {e}")
