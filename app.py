import datetime
import io
import json
import os
import random
import re
import subprocess
import tempfile
import zipfile
import pandas as pd
import streamlit as st
from docxtpl import DocxTemplate
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

# --- DICCIONARIO DE MESES EN ESPAÑOL ---
MESES_ESPANOL = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "setiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}

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

# --- MATRIZ DE TIEMPOS ESTIMADOS (en horas/unidad) ---
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

# --- DISTANCIAS APROXIMADAS A LAS FLORES, SJL ---
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

# --- PERSONAL FIJO DE OPERACIONES ---
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


def subir_pdf_supabase(nombre_archivo: str, pdf_bytes: bytes) -> str:
    """Sube un archivo PDF al Storage de Supabase y retorna su URL pública."""
    try:
        supabase.storage.from_("reportes").upload(
            path=nombre_archivo,
            file=pdf_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
    except Exception as e_up:
        st.caption(f"Aviso Storage: {e_up}")

    try:
        url_res = supabase.storage.from_("reportes").get_public_url(nombre_archivo)
        return url_res
    except Exception as e_url:
        st.error(f"❌ Error al obtener URL pública del PDF: {e_url}")
        return ""


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

    if col_confirm.button(
        "🚨 Sí, Eliminar Definitivamente",
        use_container_width=True,
        type="primary",
    ):
        exito = eliminar_proyecto_bd(proyecto.get("id"), proyecto.get("codigo"))
        if exito:
            st.session_state.proyecto_editar = {}
            st.toast("🗑️ Proyecto eliminado con éxito.")
            st.rerun()

    if col_cancel.button(" Cancelar", use_container_width=True):
        st.rerun()


# --- CLASE CANVAS PARA PIE DE PÁGINA DEL INFORME TÉCNICO ---
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


# --- GENERADOR DE CONSTANCIA DESDE PLANTILLA WORD DOCX ---
def generar_constancia_desde_plantilla_word(contexto: dict, ruta_plantilla=None) -> bytes:
    """Busca la plantilla Word en el repositorio, la rellena y la convierte a PDF."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cwd_dir = os.getcwd()

    posibles_rutas = [
        ruta_plantilla if ruta_plantilla else "",
        os.path.join(base_dir, "plantilla_constancia.docx"),
        os.path.join(cwd_dir, "plantilla_constancia.docx"),
        os.path.join(base_dir, "Constancia - Plantilla.docx"),
        os.path.join(cwd_dir, "Constancia - Plantilla.docx"),
        os.path.join(base_dir, "Plantilla_constancia.docx"),
        os.path.join(cwd_dir, "Plantilla_constancia.docx"),
    ]

    ruta_encontrada = None
    for r in posibles_rutas:
        if r and os.path.exists(r) and os.path.isfile(r) and os.path.getsize(r) > 100:
            ruta_encontrada = r
            break

    if not ruta_encontrada:
        for root in [base_dir, cwd_dir]:
            if os.path.exists(root):
                for f in os.listdir(root):
                    if f.lower().endswith(".docx") and not f.startswith("~"):
                        candidato = os.path.join(root, f)
                        if os.path.getsize(candidato) > 100:
                            ruta_encontrada = candidato
                            break
            if ruta_encontrada:
                break

    if not ruta_encontrada:
        archivos_en_base = os.listdir(base_dir) if os.path.exists(base_dir) else []
        raise FileNotFoundError(
            f"No se encontró un archivo de plantilla Word (.docx) válido en el repositorio. "
            f"Archivos detectados: {archivos_en_base}"
        )

    doc = DocxTemplate(ruta_encontrada)
    doc.render(contexto)

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_temp = os.path.join(tmpdir, "constancia_generada.docx")
        doc.save(docx_temp)

        cmd = ["libreoffice", "--headless", "--convert-to", "pdf", docx_temp, "--outdir", tmpdir]
        resultado = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        pdf_temp = os.path.join(tmpdir, "constancia_generada.pdf")
        if os.path.exists(pdf_temp) and os.path.getsize(pdf_temp) > 0:
            with open(pdf_temp, "rb") as f:
                return f.read()
        else:
            detalle_error = resultado.stderr.decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"Error al convertir DOCX a PDF con LibreOffice. "
                f"Verifica que 'libreoffice' esté en 'packages.txt'. Detalle: {detalle_error}"
            )


# --- GENERADOR DEL INFORME TÉCNICO COMPLETO ---
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
    kg_recibidos = sum([item["peso_total"] for item in lista_items])[cite: 1]
    emisiones_proceso = (
        emisiones_transporte
        + emisiones_lavado
        + emisiones_corte
        + emisiones_bordado
    )[cite: 1]
    co2_neto = co2_evitado_total - emisiones_proceso[cite: 1]
    total_prod_unidades = sum([p_item["cantidad"] for p_item in lista_productos])[cite: 1]

    buffer = io.BytesIO()[cite: 1]
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=45,
    )[cite: 1]

    styles = getSampleStyleSheet()[cite: 1]
    h1_style = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=colors.HexColor("#1E293B"),
        alignment=1,
        spaceAfter=2,
    )[cite: 1]
    sub_style = ParagraphStyle(
        "Sub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#64748B"),
        alignment=1,
        spaceAfter=12,
    )[cite: 1]
    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=10,
        spaceAfter=6,
    )[cite: 1]
    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#334155"),
        leading=10,
    )[cite: 1]
    cell_bold = ParagraphStyle(
        "CellB",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=colors.HexColor("#0F172A"),
        leading=10,
    )[cite: 1]
    card_title = ParagraphStyle(
        "CardT",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=colors.HexColor("#0F172A"),
        alignment=1,
    )[cite: 1]
    card_sub = ParagraphStyle(
        "CardS",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        textColor=colors.HexColor("#475569"),
        alignment=1,
    )[cite: 1]

    elements = [][cite: 1]

    elements.append(
        Paragraph("INFORME TÉCNICO DE VALORIZACIÓN TEXTIL", h1_style)
    )[cite: 1]
    elements.append(
        Paragraph(
            "Medición de Impacto Ambiental, Trazabilidad y Gestión Social de"
            f" Upcycling<br/><b>CÓDIGO: {codigo_proy}</b>",
            sub_style,
        )
    )[cite: 1]

    resumen_texto = f"""
    Proyecto de economía circular implementado para <b>{cliente}</b>, transformando <b>{total_procesado:.2f} kg</b> 
    de textiles en desuso mediante upcycling, con la elaboración de <b>{total_prod_unidades}</b> productos, participación 
    de <b>{total_personas_social}</b> personas y un impacto neto evitado de <b>{co2_neto:.2f} kg</b> de CO₂e.
    """[cite: 1]

    resumen_style = ParagraphStyle(
        "Resumen",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        alignment=4,
        spaceBefore=4,
        spaceAfter=6,
    )[cite: 1]

    elements.append(Paragraph(resumen_texto, resumen_style))[cite: 1]
    elements.append(Spacer(1, 4))[cite: 1]

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
            Paragraph(
                f"TRABAJO GENERADO ({total_personas_social} PERS.)", card_sub
            ),
        ],
    ][cite: 1]
    t_cards = Table(cards_data, colWidths=[135, 135, 135, 135])[cite: 1]
    t_cards.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ])
    )[cite: 1]
    elements.append(t_cards)[cite: 1]
    elements.append(Spacer(1, 8))[cite: 1]

    elements.append(
        Paragraph("1. FICHA GENERAL DEL PROYECTO Y TRAZABILIDAD", h2_style)
    )[cite: 1]
    data_ficha = [
        [
            Paragraph("Cliente / Empresa", cell_bold),
            Paragraph(f"{cliente} (RUC: {ruc})", cell_style),
            Paragraph("Área / Responsable", cell_bold),
            Paragraph(
                f"{area} / "
                + "<br/>".join(
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
    ][cite: 1]
    t_ficha = Table(data_ficha, colWidths=[100, 170, 100, 170])[cite: 1]
    t_ficha.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F8FAFC")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ])
    )[cite: 1]
    elements.append(t_ficha)[cite: 1]
    elements.append(Spacer(1, 8))[cite: 1]

    def obtener_imagen_pdf(foto_file, width, height):
        if foto_file is not None:
            try:
                foto_file.seek(0)
                img_data = io.BytesIO(foto_file.read())
                foto_file.seek(0)
                return Image(img_data, width=width, height=height)
            except Exception:
                return Paragraph("Sin foto", cell_style)
        return Paragraph("Sin foto", cell_style)[cite: 1]

    elements.append(
        Paragraph("2. INGRESO DE MATERIAL Y EVIDENCIA FOTOGRÁFICA", h2_style)
    )[cite: 1]
    data_prendas_pdf = [[
        Paragraph("Ítem", cell_bold),
        Paragraph("Tipo de Producto / Prenda", cell_bold),
        Paragraph("Ingreso (unid)", cell_bold),
        Paragraph("Peso unit. (kg)", cell_bold),
        Paragraph("Peso total (kg)", cell_bold),
        Paragraph("Evidencia", cell_bold),
    ]][cite: 1]

    total_unidades_ingreso = 0[cite: 1]
    for i, item in enumerate(lista_items, 1):
        total_unidades_ingreso += item["unidades"][cite: 1]
        img_cell = obtener_imagen_pdf(item["foto"], 45, 45)[cite: 1]

        data_prendas_pdf.append([
            Paragraph(str(i), cell_style),
            Paragraph(item["descripcion"], cell_style),
            Paragraph(str(item["unidades"]), cell_style),
            Paragraph(f"{item['peso_unitario']:.2f}", cell_style),
            Paragraph(f"{item['peso_total']:.2f}", cell_style),
            img_cell,
        ])[cite: 1]

    data_prendas_pdf.append([
        Paragraph("<b>TOTAL MATERIAL RECIBIDO</b>", cell_bold),
        "",
        Paragraph(f"<b>{total_unidades_ingreso}</b>", cell_bold),
        Paragraph("-", cell_bold),
        Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", cell_bold),
        Paragraph("-", cell_bold),
    ])[cite: 1]

    t_prendas = Table(
        data_prendas_pdf, colWidths=[30, 180, 80, 75, 75, 100]
    )[cite: 1]
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
    )[cite: 1]
    elements.append(t_prendas)[cite: 1]
    elements.append(Spacer(1, 8))[cite: 1]

    elements.append(
        Paragraph("3. TRAZABILIDAD DEL PROCESO EN UPCYCLING", h2_style)
    )[cite: 1]
    data_traza_pdf = [[
        Paragraph("Etapa", cell_bold),
        Paragraph("Fecha", cell_bold),
        Paragraph("Responsable", cell_bold),
        Paragraph("Peso (kg)", cell_bold),
        Paragraph("Tipo de Registro", cell_bold),
        Paragraph("Evidencia", cell_bold),
    ]][cite: 1]

    for t_item in lista_trazabilidad:
        img_cell = obtener_imagen_pdf(t_item["foto"], 45, 35)[cite: 1]

        data_traza_pdf.append([
            Paragraph(t_item["etapa"], cell_style),
            Paragraph(t_item["fecha"], cell_style),
            Paragraph(t_item["responsable"], cell_style),
            Paragraph(f"{t_item['peso']:.2f}", cell_style),
            Paragraph(t_item["tipo_registro"], cell_style),
            img_cell,
        ])[cite: 1]

    t_traza = Table(data_traza_pdf, colWidths=[90, 70, 130, 60, 100, 90])[cite: 1]
    t_traza.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5D0FE")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (3, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 4),
        ])
    )[cite: 1]
    elements.append(t_traza)[cite: 1]

    elements.append(PageBreak())[cite: 1]

    elements.append(Paragraph("4. SALIDA DE PRODUCTOS", h2_style))[cite: 1]
    data_prod_pdf = [[
        Paragraph("Producto", cell_bold),
        Paragraph("Cantidad (Unidades)", cell_bold),
        Paragraph("Evidencia", cell_bold),
    ]][cite: 1]

    for p_item in lista_productos:
        img_cell = obtener_imagen_pdf(p_item["foto"], 60, 60)[cite: 1]
        data_prod_pdf.append([
            Paragraph(p_item["producto"], cell_style),
            Paragraph(str(p_item["cantidad"]), cell_style),
            img_cell,
        ])[cite: 1]

    data_prod_pdf.append([
        Paragraph("<b>SUMA TOTAL</b>", cell_bold),
        Paragraph(f"<b>{total_prod_unidades}</b>", cell_bold),
        Paragraph("-", cell_bold),
    ])[cite: 1]

    t_prod = Table(data_prod_pdf, colWidths=[240, 150, 150])[cite: 1]
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
    )[cite: 1]
    elements.append(t_prod)[cite: 1]
    elements.append(Spacer(1, 15))[cite: 1]

    elements.append(Paragraph("5. BALANCE DE MATERIAL", h2_style))[cite: 1]
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
    ][cite: 1]

    t_balance = Table(data_balance, colWidths=[340, 200])[cite: 1]
    t_balance.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5D0FE")),
            ("BACKGROUND", (0, 6), (-1, 6), colors.HexColor("#F5D0FE")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("PADDING", (0, 0), (-1, -1), 5),
        ])
    )[cite: 1]
    elements.append(t_balance)[cite: 1]
    elements.append(Spacer(1, 15))[cite: 1]

    elements.append(
        Paragraph(
            "6. RESUMEN DE IMPACTO AMBIENTAL DEL PROYECTO (CO2e)", h2_style
        )
    )[cite: 1]
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
    ][cite: 1]
    t_co2_box = Table(data_co2_box, colWidths=[180, 180, 180])[cite: 1]
    t_co2_box.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])
    )[cite: 1]
    elements.append(t_co2_box)[cite: 1]
    elements.append(Spacer(1, 10))[cite: 1]

    elements.append(
        Paragraph("7. RESUMEN DE IMPACTO SOCIAL Y EQUIPO DE TRABAJO", h2_style)
    )[cite: 1]
    data_ops_pdf = [[
        Paragraph("Rol", cell_bold),
        Paragraph("Nombre", cell_bold),
        Paragraph("Días trabajados", cell_bold),
        Paragraph("Hora/día", cell_bold),
        Paragraph("Horas totales", cell_bold),
    ]][cite: 1]

    tot_hrs_ops = 0[cite: 1]
    for op in lista_operaciones_pdf:
        tot_hrs_ops += op["horas_totales"][cite: 1]
        data_ops_pdf.append([
            Paragraph(str(op["rol"]), cell_style),
            Paragraph(str(op["nombre"]), cell_style),
            Paragraph(str(op["dias"]), cell_style),
            Paragraph(f"{op['horas_dia']:.2f}", cell_style),
            Paragraph(f"{op['horas_totales']:.2f}", cell_style),
        ])[cite: 1]

    data_ops_pdf.append([
        Paragraph("<b>SUBTOTAL CORTE Y LOGÍSTICA</b>", cell_bold),
        "",
        "",
        "",
        Paragraph(f"<b>{tot_hrs_ops:.2f} hrs</b>", cell_bold),
    ])[cite: 1]

    t_ops = Table(data_ops_pdf, colWidths=[100, 200, 80, 80, 80])[cite: 1]
    t_ops.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5D0FE")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("SPAN", (0, -1), (3, -1)),
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 4),
        ])
    )[cite: 1]
    elements.append(t_ops)[cite: 1]
    elements.append(Spacer(1, 10))[cite: 1]

    if lista_confeccion:
        data_social_pdf = [[
            Paragraph("Producto", cell_bold),
            Paragraph("Rol Operativo", cell_bold),
            Paragraph("Encargado/a", cell_bold),
            Paragraph("Cant.", cell_bold),
            Paragraph("Tiempo unit. (hrs)", cell_bold),
            Paragraph("Horas Totales", cell_bold),
        ]][cite: 1]

        tot_hrs_conf = 0[cite: 1]
        for c_item in lista_confeccion:
            tot_hrs_conf += c_item["horas_totales"][cite: 1]
            data_social_pdf.append([
                Paragraph(c_item["producto"], cell_style),
                Paragraph(c_item["rol"], cell_style),
                Paragraph(c_item["persona"], cell_style),
                Paragraph(str(c_item["cantidad"]), cell_style),
                Paragraph(f"{c_item['tiempo_unitario']:.2f} hrs", cell_style),
                Paragraph(f"{c_item['horas_totales']:.2f} hrs", cell_style),
            ])[cite: 1]

        data_social_pdf.append([
            Paragraph("<b>SUBTOTAL CONFECCIÓN Y ACABADO</b>", cell_bold),
            "",
            "",
            "",
            "",
            Paragraph(f"<b>{tot_hrs_conf:.2f} hrs</b>", cell_bold),
        ])[cite: 1]

        t_soc = Table(data_social_pdf, colWidths=[120, 100, 110, 40, 80, 90])[cite: 1]
        t_soc.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5D0FE")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("SPAN", (0, -1), (4, -1)),
                ("ALIGN", (3, 0), (-1, -1), "CENTER"),
                ("PADDING", (0, 0), (-1, -1), 4),
            ])
        )[cite: 1]
        elements.append(t_soc)[cite: 1]

    elements.append(Spacer(1, 10))[cite: 1]
    elements.append(Paragraph("8. CONCLUSIÓN", h2_style))[cite: 1]

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
    )[cite: 1]

    texto_conclusion = """
    El proyecto permitió gestionar de manera eficiente los textiles en desuso del cliente, 
    asegurando su aprovechamiento mediante un proceso organizado y trazable.<br/><br/>
    Los resultados obtenidos reflejan la capacidad de integrar este tipo de iniciativas 
    dentro de la operación de las empresas, generando valor a partir de materiales existentes.
    """[cite: 1]
    elements.append(Paragraph(texto_conclusion, conclusion_style))[cite: 1]

    # --- 9. SECCIÓN ANEXOS ---
    anexos_validos = [
        a
        for a in (lista_anexos or [])
        if a.get("foto") or a.get("nota", "").strip()
    ][cite: 1]
    if anexos_validos:
        elements.append(PageBreak())[cite: 1]
        elements.append(Paragraph("9. ANEXOS Y REGISTRO FOTOGRÁFICO", h2_style))[cite: 1]
        elements.append(Spacer(1, 4))[cite: 1]

        for idx_a, anexo in enumerate(anexos_validos, 1):
            img_cell = obtener_imagen_pdf(anexo["foto"], width=480, height=215)[cite: 1]
            nota_texto = (
                anexo["nota"].strip()
                if anexo["nota"].strip()
                else "Sin descripción adicional."
            )[cite: 1]

            card_data = [
                [Paragraph(f"<b>Evidencia Fotográfica {idx_a}</b>", cell_bold)],
                [img_cell],
                [
                    Paragraph(
                        f"<b>Nota / Descripción:</b> {nota_texto}", cell_style
                    )
                ],
            ][cite: 1]

            t_card = Table(card_data, colWidths=[520])[cite: 1]
            t_card.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("ALIGN", (0, 1), (0, 1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ])
            )[cite: 1]

            elements.append(t_card)[cite: 1]
            elements.append(Spacer(1, 8))[cite: 1]

            if idx_a % 2 == 0 and idx_a < len(anexos_validos):
                elements.append(PageBreak())[cite: 1]

    doc.build(elements, canvasmaker=ReporteCanvas)[cite: 1]
    buffer.seek(0)[cite: 1]
    return buffer[cite: 1]


# --- ESTADOS DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False[cite: 1]

if "pestaña_activa" not in st.session_state:
    st.session_state.pestaña_activa = "➕     Nuevo Reporte PDF"[cite: 1]

if "proyecto_editar" not in st.session_state:
    st.session_state.proyecto_editar = {}[cite: 1]

if "id_proyecto_cargado" not in st.session_state:
    st.session_state.id_proyecto_cargado = None

if "catalogo_productos" not in st.session_state:
    st.session_state.catalogo_productos = list(PRODUCTOS_CATALOGO_BASE)[cite: 1]

if "lista_personal_confeccion" not in st.session_state:
    st.session_state.lista_personal_confeccion = list(PERSONAL_CONFECCION_BASE)[cite: 1]

if "num_anexos" not in st.session_state:
    st.session_state.num_anexos = 1[cite: 1]

if "documentos_descarga" not in st.session_state:
    st.session_state.documentos_descarga = None[cite: 5]

if "pct_aprovechamiento_random" not in st.session_state:
    st.session_state.pct_aprovechamiento_random = round(
        random.uniform(0.88, 0.94), 4
    )[cite: 1]

if "pct_transformado_ratio" not in st.session_state:
    st.session_state.pct_transformado_ratio = round(
        random.uniform(0.78, 0.83), 4
    )[cite: 1]

try:
    USUARIO_CORRECTO = st.secrets["auth"]["USUARIO"][cite: 1]
    PASSWORD_CORRECTO = st.secrets["auth"]["PASSWORD"][cite: 1]
except KeyError:
    st.error("⚠️ Faltan las credenciales de acceso en `st.secrets`.")[cite: 1]
    st.stop()[cite: 1]

if not st.session_state.autenticado:
    st.markdown(
        """
        <div style="text-align: center; padding: 40px 10px;">
            <h1 style="color: #1E293B; font-size: 2.2rem; font-weight: 800;">♻️ Pequeños Detalles</h1>
            <p style="color: #64748B; font-size: 1.1rem;">Handmade Perú S.A.C. — Gestión de Sostenibilidad</p>
        </div>
    """,
        unsafe_allow_html=True,
    )[cite: 1]

    col1, col2, col3 = st.columns([1, 1.2, 1])[cite: 1]
    with col2:
        with st.container(border=True):
            st.subheader("🔐 Iniciar Sesión")[cite: 1]
            usuario_input = st.text_input("Usuario")[cite: 1]
            password_input = st.text_input("Contraseña", type="password")[cite: 1]

           if st.button("Ingresar al Sistema", use_container_width=True, type="primary"):
                if usuario_input == USUARIO_CORRECTO and password_input == PASSWORD_CORRECTO:[cite: 1]
                    st.session_state.autenticado = True[cite: 1]
                    st.success("¡Bienvenido/a!")[cite: 1]
                    st.rerun()[cite: 1]
                else:
                    st.error("⚠️ Usuario o contraseña incorrectos.")[cite: 1]

else:
    proyectos_wip = cargar_proyectos(estado="EN_PROCESO")[cite: 1]

    with st.sidebar:
        st.markdown("### ♻️ Pequeños Detalles")[cite: 1]
        st.caption("Panel de Control Interno | 2026")[cite: 1]
        st.write("---")[cite: 1]

        st.markdown('<p class="sidebar-section-title">Navegación</p>', unsafe_allow_html=True)[cite: 1]

        if st.button(
            "✨     Nuevo Reporte PDF",
            use_container_width=True,
            type="primary" if st.session_state.pestaña_activa == "➕     Nuevo Reporte PDF" else "secondary",
        ):[cite: 1]
            st.session_state.proyecto_editar = {}[cite: 1]
            st.session_state.id_proyecto_cargado = None
            st.session_state.documentos_descarga = None[cite: 5]
            st.session_state.pestaña_activa = "➕     Nuevo Reporte PDF"[cite: 1]
            st.rerun()[cite: 1]

        if st.button(
            "⚡     Carga Rápida Histórica",
            use_container_width=True,
            type="primary" if st.session_state.pestaña_activa == "⚡     Carga Rápida Histórica" else "secondary",
        ):[cite: 1]
            st.session_state.documentos_descarga = None[cite: 5]
            st.session_state.pestaña_activa = "⚡     Carga Rápida Histórica"[cite: 1]
            st.rerun()[cite: 1]

        st.markdown('<p class="sidebar-section-title">Proyectos Pendientes</p>', unsafe_allow_html=True)[cite: 1]

        if proyectos_wip:
            for p in proyectos_wip:
                cli_nombre = p.get("cliente", "Sin Nombre")[cite: 1]
                cod_ref = p.get("codigo", "")[cite: 1]
                label_btn = f"📁 {cli_nombre}" + (f" ({cod_ref})" if cod_ref else "")[cite: 1]

                es_activo = st.session_state.proyecto_editar.get("id") == p.get("id") or st.session_state.proyecto_editar.get("codigo") == cod_ref[cite: 1]

                if st.button(
                    label_btn,
                    key=f"side_proj_{p.get('id', cod_ref)}",
                    use_container_width=True,
                    type="primary" if es_activo else "secondary",
                ):[cite: 1]
                    st.session_state.proyecto_editar = p[cite: 1]
                    st.session_state.id_proyecto_cargado = p.get("id", cod_ref)
                    st.session_state.documentos_descarga = None[cite: 5]
                    st.session_state.pestaña_activa = "➕     Nuevo Reporte PDF"[cite: 1]
                    st.rerun()[cite: 1]

            st.write("")[cite: 1]
            if st.button("📋 Ver Lista en Proceso", use_container_width=True):[cite: 1]
                st.session_state.documentos_descarga = None[cite: 5]
                st.session_state.pestaña_activa = "📋 Proyectos en Proceso"[cite: 1]
                st.rerun()[cite: 1]
        else:
            st.caption("📭 No hay proyectos en borrador")[cite: 1]

        st.markdown('<p class="sidebar-section-title">Analítica e Histórico</p>', unsafe_allow_html=True)[cite: 1]

        if st.button(
            "📊 Dashboard 2026",
            use_container_width=True,
            type="primary" if st.session_state.pestaña_activa == "📊 Dashboard 2026" else "secondary",
        ):[cite: 1]
            st.session_state.documentos_descarga = None[cite: 5]
            st.session_state.pestaña_activa = "📊 Dashboard 2026"[cite: 1]
            st.rerun()[cite: 1]

        if st.button(
            "🗂️ Historial Completo",
            use_container_width=True,
            type="primary" if st.session_state.pestaña_activa == "🗂️ Historial Completo" else "secondary",
        ):[cite: 1]
            st.session_state.documentos_descarga = None[cite: 5]
            st.session_state.pestaña_activa = "🗂️ Historial Completo"[cite: 1]
            st.rerun()[cite: 1]

        st.write("---")[cite: 1]
        if st.button("🚪 Cerrar Sesión", use_container_width=True):[cite: 1]
            st.session_state.autenticado = False[cite: 1]
            st.session_state.proyecto_editar = {}[cite: 1]
            st.session_state.id_proyecto_cargado = None
            st.session_state.documentos_descarga = None[cite: 5]
            st.rerun()[cite: 1]

    st.markdown(
        f"""
        <div class="hero-header">
            <h1>📄 Sistema de Gestión de Informes Técnicos</h1>
            <p>Sección Activa: <b>{st.session_state.pestaña_activa}</b></p>
        </div>
    """,
        unsafe_allow_html=True,
    )[cite: 1]

    # --- VISTA: CARGA RÁPIDA HISTÓRICA ---
    if st.session_state.pestaña_activa == "⚡     Carga Rápida Histórica":
        st.subheader("⚡ Carga Rápida de Proyectos Históricos / Pasados")[cite: 1]
        st.caption("Ingresa métricas consolidadas de proyectos pasados directamente al historial.")[cite: 1]

        with st.container(border=True):
            st.markdown("##### 1. Datos Generales del Proyecto")[cite: 1]
            rq1, rq2, rq3, rq4 = st.columns(4)[cite: 1]
            fast_cliente = rq1.text_input("Cliente / Empresa *")[cite: 1]
            fast_ruc = rq2.text_input("RUC (11 dígitos) *", max_chars=11)[cite: 1]
            fast_tipo = rq3.selectbox(
                "Tipo de Proyecto",
                ["Upcycling", "Producción desde cero", "Cambio de logo", "Mixto", "Banner"],
            )[cite: 1]
            fast_resp = rq4.text_input("Responsable", value="Sostenibilidad")[cite: 1]

            rq5, rq6 = st.columns(2)[cite: 1]
            fast_f_ini = rq5.date_input("Fecha Inicio", value=datetime.date.today(), format="DD/MM/YYYY")[cite: 1]
            fast_f_fin = rq6.date_input("Fecha Término", value=datetime.date.today(), format="DD/MM/YYYY")[cite: 1]

            fe_ini_str = fast_f_ini.strftime("%d/%m/%Y")[cite: 1]
            fe_fin_str = fast_f_fin.strftime("%d/%m/%Y")[cite: 1]
            cli_clean = fast_cliente.strip() if fast_cliente.strip() else "EMPRESA"[cite: 1]
            fast_codigo = f"{cli_clean}_{fast_f_ini.strftime('%d%m%Y')}-{fast_f_fin.strftime('%d%m%Y')}"[cite: 1]

            st.info(f"🆔 **Código Generado:** `{fast_codigo}`")[cite: 1]

        with st.container(border=True):
            st.markdown("##### 2. Métricas Consolidadas")[cite: 1]
            rm1, rm2, rm3 = st.columns(3)[cite: 1]
            fast_peso = rm1.number_input("Material Procesado Total (kg) *", min_value=0.0, step=0.1)[cite: 1]
            fast_unid = rm2.number_input("Unidades Producidas *", min_value=0, step=1)[cite: 1]
            fast_co2 = rm3.number_input("CO₂e Neto Evitado (kg) *", min_value=0.0, step=0.1)[cite: 1]

            rm4, rm5, rm6 = st.columns(3)[cite: 1]
            fast_horas = rm4.number_input("Horas de Trabajo Generadas *", min_value=0.0, step=0.5)[cite: 1]
            fast_personas = rm5.number_input("Personas / Beneficiarios *", min_value=0, step=1)[cite: 1]
            fast_aprovechamiento = rm6.number_input("% Aprovechamiento *", min_value=0.0, max_value=100.0, value=100.0, step=0.1)[cite: 1]
            fast_origen = st.text_input("Punto Origen", value="Sede Central")[cite: 1]

        st.write("")[cite: 1]

        if st.button("🚀 Guardar Proyecto Histórico Directamente", type="primary", use_container_width=True):[cite: 1]
            if not fast_cliente.strip():
                st.error("El campo **Cliente / Empresa** es obligatorio.")[cite: 1]
            elif not fast_ruc.strip() or not re.fullmatch(r"\d{11}", fast_ruc.strip()):
                st.error("El **RUC** es obligatorio y debe tener 11 dígitos.")[cite: 1]
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
                        }).execute()[cite: 1]
                    st.success(f"✅ ¡Proyecto **{fast_cliente}** registrado exitosamente!")[cite: 1]
                except Exception as e:
                    st.error(f"⚠️ Error al registrar el proyecto: {e}")[cite: 1]

    # --- VISTA: PROYECTOS EN PROCESO ---
    elif st.session_state.pestaña_activa == "📋 Proyectos en Proceso":
        st.subheader("📋 Lista de Proyectos en Proceso (Borradores)")[cite: 1]
        proyectos_lista = cargar_proyectos()[cite: 1]
        borradores = [p for p in proyectos_lista if p.get("estado") == "EN_PROCESO"][cite: 1]

        if borradores:
            for b in borradores:
                with st.container(border=True):
                    bc1, bc2, bc3 = st.columns([3, 2, 2])[cite: 1]
                    bc1.markdown(f"**Cliente:** {b.get('cliente', 'Sin Nombre')}")[cite: 1]
                    bc1.caption(f"Código: `{b.get('codigo', '')}`")[cite: 1]
                    bc2.markdown(f"**Tipo:** {b.get('tipo_proyecto', 'Upcycling')}")[cite: 1]
                    bc2.caption(f"Fecha: {b.get('fecha', '')}")[cite: 1]

                    if bc3.button("✏️ Retomar Edición", key=f"retomar_{b.get('id', b.get('codigo'))}", use_container_width=True, type="primary"):[cite: 1]
                        st.session_state.proyecto_editar = b[cite: 1]
                        st.session_state.id_proyecto_cargado = b.get("id", b.get("codigo"))
                        st.session_state.documentos_descarga = None[cite: 5]
                        st.session_state.pestaña_activa = "➕     Nuevo Reporte PDF"[cite: 1]
                        st.rerun()[cite: 1]
        else:
            st.info("📭 No hay borradores en proceso actualmente.")[cite: 1]

    # --- VISTA: DASHBOARD 2026 ---
    elif st.session_state.pestaña_activa == "📊 Dashboard 2026":
        st.subheader("📊 Dashboard de Sostenibilidad e Impacto 2026")[cite: 1]
        proyectos_lista = cargar_proyectos()[cite: 1]
        completados = [p for p in proyectos_lista if p.get("estado") == "COMPLETADO"][cite: 1]

        tot_peso = sum([float(p.get("peso_recibido", 0) or 0) for p in completados])[cite: 1]
        tot_co2 = sum([float(p.get("co2_neto", 0) or 0) for p in completados])[cite: 1]
        tot_horas = sum([float(p.get("horas_totales", 0) or 0) for p in completados])[cite: 1]
        tot_unids = sum([int(p.get("productos_unids", 0) or 0) for p in completados])[cite: 1]

        dm1, dm2, dm3, dm4 = st.columns(4)[cite: 1]
        dm1.metric("📦 Material Reciclado", f"{tot_peso:.2f} kg")[cite: 1]
        dm2.metric("🌍 CO₂e Neto Evitado", f"{tot_co2:.2f} kg")[cite: 1]
        dm3.metric("⏳ Horas de Trabajo", f"{tot_horas:.2f} hrs")[cite: 1]
        dm4.metric("🛍️ Productos Creados", f"{tot_unids} unid")[cite: 1]

        st.write("")[cite: 1]
        if completados:
            df_comp = pd.DataFrame(completados)[cite: 1]
            columnas_mostrar = ["codigo", "cliente", "tipo_proyecto", "peso_recibido", "co2_neto", "horas_totales", "productos_unids"][cite: 1]
            df_tabla = df_comp[[c for c in columnas_mostrar if c in df_comp.columns]]
            st.dataframe(df_tabla, use_container_width=True, hide_index=True)[cite: 1]

    # --- VISTA: HISTORIAL COMPLETO ---
    elif st.session_state.pestaña_activa == "🗂️ Historial Completo":
        st.subheader("🗂️ Historial Completo de Proyectos")[cite: 1]
        proyectos_lista = cargar_proyectos()[cite: 1]
        if proyectos_lista:
            for p in proyectos_lista:
                with st.container(border=True):
                    hc1, hc2, hc3, hc4, hc5, hc6 = st.columns([2.5, 1.6, 1.6, 1.8, 1.8, 0.7])[cite: 5]
                    hc1.markdown(f"**{p.get('cliente', 'Sin Nombre')}**")[cite: 1]
                    hc1.caption(f"ID/Código: `{p.get('codigo', '')}`")[cite: 1]
                    hc2.markdown(f"Estado: **{p.get('estado', 'N/D')}**")[cite: 1]
                    hc2.caption(f"Tipo: {p.get('tipo_proyecto', 'Upcycling')}")[cite: 1]
                    hc3.markdown(f"Peso: `{float(p.get('peso_recibido', 0) or 0):.2f} kg`")[cite: 1]
                    hc3.caption(f"Fecha: {p.get('fecha', 'N/D')}")[cite: 1]

                    pdf_link = p.get("pdf_url")[cite: 1]
                    if pdf_link:
                        hc4.link_button("📄 Informe PDF", pdf_link, use_container_width=True)[cite: 5]
                    else:
                        hc4.caption("📄 Sin Informe")[cite: 5]

                    const_link = p.get("constancia_url")[cite: 5]
                    if const_link:
                        hc5.link_button("📜 Constancia PDF", const_link, use_container_width=True)[cite: 5]
                    else:
                        hc5.caption("📜 Sin Constancia")[cite: 5]

                    if hc6.button("🗑️", key=f"hist_del_{p.get('id', p.get('codigo'))}", use_container_width=True):[cite: 5]
                        modal_confirmar_eliminacion(p)[cite: 1]
        else:
            st.info("📭 No hay proyectos registrados en el historial.")[cite: 1]

    # --- VISTA: NUEVO REPORTE PDF / EDICIÓN ---
    elif st.session_state.pestaña_activa == "➕     Nuevo Reporte PDF":
        p_edit = st.session_state.proyecto_editar[cite: 1]

        # Cargar datos JSON guardados previamente si existen
        detalles_guardados = {}
        if p_edit and p_edit.get("datos_completos"):
            raw_datos = p_edit.get("datos_completos")
            if isinstance(raw_datos, str):
                try:
                    detalles_guardados = json.loads(raw_datos)
                except Exception:
                    detalles_guardados = {}
            elif isinstance(raw_datos, dict):
                detalles_guardados = raw_datos

        if p_edit:
            st.warning(f"✏️ **Modo Edición Activo:** Modificando borrador de **{p_edit.get('cliente', '')}** (`{p_edit.get('codigo', '')}`)")
            col_desc, col_elim = st.columns([2, 2])[cite: 1]
            if col_desc.button("❌ Descartar selección y limpiar formulario", use_container_width=True):[cite: 1]
                st.session_state.proyecto_editar = {}[cite: 1]
                st.session_state.id_proyecto_cargado = None
                st.session_state.documentos_descarga = None[cite: 5]
                st.rerun()[cite: 1]

            if col_elim.button("🗑️ Eliminar Proyecto Definitivamente", use_container_width=True):[cite: 1]
                modal_confirmar_eliminacion(p_edit)[cite: 1]

        # --- SECCIÓN 1: FICHA GENERAL ---
        with st.container(border=True):
            st.subheader("1. Ficha General del Proyecto")[cite: 1]

            fechas_raw = p_edit.get("fecha", " - ").split(" - ")[cite: 1]
            try:
                def_f_ini = datetime.datetime.strptime(fechas_raw[0].strip(), "%d/%m/%Y").date()[cite: 1]
            except Exception:
                def_f_ini = datetime.date.today()[cite: 1]

            try:
                def_f_fin = datetime.datetime.strptime(fechas_raw[1].strip(), "%d/%m/%Y").date()[cite: 1]
            except Exception:
                def_f_fin = datetime.date.today()[cite: 1]

            c1, c2, c5, c6 = st.columns(4)[cite: 1]
            cliente = c1.text_input("Cliente / Empresa *", value=p_edit.get("cliente", ""))[cite: 1]
            ruc = c2.text_input("RUC * (11 dígitos)", value=p_edit.get("ruc", ""), max_chars=11)[cite: 1]
            fe_inicio_dt = c5.date_input("Fecha Inicio *", value=def_f_ini, format="DD/MM/YYYY")[cite: 1]
            fe_fin_dt = c6.date_input("Fecha Término *", value=def_f_fin, format="DD/MM/YYYY")[cite: 1]

            fe_inicio = fe_inicio_dt.strftime("%d/%m/%Y")[cite: 1]
            fe_fin = fe_fin_dt.strftime("%d/%m/%Y")[cite: 1]

            str_empresa = cliente.strip() if cliente.strip() else "EMPRESA"[cite: 1]
            codigo_proy = f"{str_empresa}_{fe_inicio_dt.strftime('%d%m%Y')}-{fe_fin_dt.strftime('%d%m%Y')}"[cite: 1]
            st.info(f"🆔 **Código del Proyecto (Generado automáticamente):** `{codigo_proy}`")[cite: 1]

            c4, c7, c8, c9 = st.columns(4)[cite: 1]
            opciones_tipo_proyecto = ["Upcycling", "Producción desde cero", "Cambio de logo", "Mixto", "Banner"][cite: 1]
            tipo_actual = p_edit.get("tipo_proyecto", "Upcycling")[cite: 1]
            idx_tipo = opciones_tipo_proyecto.index(tipo_actual) if tipo_actual in opciones_tipo_proyecto else 0[cite: 1]
            proyecto_nom = c4.selectbox("Tipo de Proyecto *", opciones_tipo_proyecto, index=idx_tipo)[cite: 1]

            RESPONSABLES_BASE = ["Evelyn Prada Vizarreta", "Gabriel Manrique Hurtado"][cite: 1]
            responsables_guardados = detalles_guardados.get("responsables", p_edit.get("responsables", []))
            if not isinstance(responsables_guardados, list):
                responsables_guardados = [r.strip() for r in str(responsables_guardados).split(",") if r.strip()][cite: 1]

            opciones_responsables = list(dict.fromkeys(RESPONSABLES_BASE + responsables_guardados))[cite: 1]
            responsables_seleccionados = c7.multiselect(
                "Responsable *",
                options=opciones_responsables,
                default=[r for r in responsables_guardados if r in opciones_responsables],
                placeholder="Selecciona responsables",
                key=f"responsables_proy_{st.session_state.id_proyecto_cargado}",
            )
            responsable = ", ".join(responsables_seleccionados)[cite: 1]

            area = c8.text_input("Área", value="Sostenibilidad", disabled=True)[cite: 1]
            guia_remision = c9.text_input("Nº Guía Remisión", value=detalles_guardados.get("guia", p_edit.get("guia", "")))
            origen = st.text_input("Punto Origen *", value=detalles_guardados.get("origen", p_edit.get("punto_origen", p_edit.get("origen", ""))))
            destino = "Jr. Las Caléndulas 610, Las Flores, SJL."[cite: 1]

        st.write("")[cite: 1]

        # --- SECCIÓN 2: INGRESO DE MATERIAL ---
        with st.container(border=True):
            st.subheader("2. Ingreso de Material")[cite: 1]
            saved_items = detalles_guardados.get("items", [])

            if "num_items" not in st.session_state or st.session_state.id_proyecto_cargado != st.session_state.get("_last_id_items"):
                st.session_state.num_items = max(1, len(saved_items)) if saved_items else 2
                st.session_state._last_id_items = st.session_state.id_proyecto_cargado

            col_btn1, col_btn2, _ = st.columns([1, 1, 4])[cite: 1]
            if col_btn1.button("➕     Agregar Ítem"):[cite: 1]
                st.session_state.num_items += 1[cite: 1]
                st.rerun()[cite: 1]
            if col_btn2.button("➖     Quitar Ítem") and st.session_state.num_items > 1:[cite: 1]
                st.session_state.num_items -= 1[cite: 1]
                st.rerun()[cite: 1]

            lista_items = [][cite: 1]
            peso_total_recibido = 0.0[cite: 1]
            co2_evitado_total = 0.0[cite: 1]
            total_piezas_ingresadas = 0[cite: 1]
            opciones_prendas = sorted(list(FACTORES_CO2.keys()))[cite: 1]

            for i in range(st.session_state.num_items):
                st.markdown(f"**Material {i+1}**")[cite: 1]
                col_desc, col_unid, col_peso, col_tot, col_foto = st.columns([3, 1.5, 1.5, 1.5, 3])[cite: 1]

                val_item_desc = saved_items[i].get("descripcion", "Camisa") if i < len(saved_items) else "Camisa"
                idx_desc = opciones_prendas.index(val_item_desc) if val_item_desc in opciones_prendas else 0
                val_item_unid = saved_items[i].get("unidades", 0) if i < len(saved_items) else 0
                val_item_peso = float(saved_items[i].get("peso_total", 0.0)) if i < len(saved_items) else 0.0

                desc = col_desc.selectbox("Tipo de Producto / Prenda *", opciones_prendas, index=idx_desc, key=f"desc_{i}_{st.session_state.id_proyecto_cargado}")
                unid = col_unid.number_input("Ingreso (unid.) *", min_value=0, value=int(val_item_unid), key=f"unid_{i}_{st.session_state.id_proyecto_cargado}")
                p_total = col_peso.number_input("Peso Total (kg) *", min_value=0.0, value=float(val_item_peso), step=0.05, key=f"tot_input_{i}_{st.session_state.id_proyecto_cargado}")
                
                peso_u = p_total / unid if unid > 0 else 0.0[cite: 1]
                col_tot.text_input("Peso Unitario", value=f"{peso_u:.2f} kg", disabled=True, key=f"peso_u_{i}_{unid}_{p_total}")[cite: 1]

                foto = col_foto.file_uploader("Evidencia Foto", type=["jpg", "png", "jpeg"], key=f"foto_{i}_{st.session_state.id_proyecto_cargado}")
                if foto is not None:
                    col_foto.image(foto, width=80)[cite: 1]

                factor = FACTORES_CO2.get(desc, 6.575)[cite: 1]
                co2_item = p_total * factor[cite: 1]
                co2_evitado_total += co2_item[cite: 1]
                peso_total_recibido += p_total[cite: 1]
                total_piezas_ingresadas += unid[cite: 1]

                lista_items.append({
                    "descripcion": desc,
                    "unidades": unid,
                    "peso_unitario": peso_u,
                    "peso_total": p_total,
                    "foto": foto,
                    "co2_evitado": co2_item,
                })[cite: 1]

            st.info(f"⚖️ **Total Material Recibido:** {peso_total_recibido:.2f} kg | **CO₂ Evitado Calculado:** {co2_evitado_total:.2f} kg CO₂e")[cite: 1]

        st.write("")[cite: 1]

        # --- SECCIÓN 3: TRAZABILIDAD ---
        with st.container(border=True):
            st.subheader("3. Trazabilidad del Proceso en Upcycling")[cite: 1]
            saved_traza = detalles_guardados.get("trazabilidad", [])
            peso_corte_conf_auto = round(peso_total_recibido * st.session_state.pct_aprovechamiento_random, 2)[cite: 1]

            etapas_fijas = [
                {"etapa": "Clasificación", "fecha": datetime.date.today(), "resp_defecto": "Evelyn Prada Vizarreta", "peso_defecto": peso_total_recibido, "tipo": "Registro interno"},
                {"etapa": "Lavado", "fecha": datetime.date.today(), "resp_defecto": "Lavandería", "peso_defecto": peso_total_recibido, "tipo": "Servicio Externo"},
                {"etapa": "Corte", "fecha": datetime.date.today(), "resp_defecto": "Taller de corte (5 integrantes)", "peso_defecto": peso_corte_conf_auto, "tipo": "Pesaje real"},
                {"etapa": "Confección", "fecha": datetime.date.today(), "resp_defecto": "Producción descentralizada", "peso_defecto": peso_corte_conf_auto, "tipo": "Entrega / Recepción"},
            ][cite: 1]
            lista_trazabilidad = [][cite: 1]
            peso_lavado_auto = 0.0[cite: 1]
            peso_corte_auto = 0.0[cite: 1]

            for i, item_fijo in enumerate(etapas_fijas):
                st.markdown(f"**Etapa {i+1}**")[cite: 1]
                c_etapa, c_fecha, c_resp, c_edit_chk, c_peso, c_tipo, c_foto = st.columns([1.5, 1.5, 2, 1, 1.2, 1.8, 2])[cite: 1]

                val_tr_resp = saved_traza[i].get("responsable", item_fijo["resp_defecto"]) if i < len(saved_traza) else item_fijo["resp_defecto"]
                val_tr_peso = float(saved_traza[i].get("peso", item_fijo["peso_defecto"])) if i < len(saved_traza) else item_fijo["peso_defecto"]

                e_nom = c_etapa.text_input("Etapa", value=item_fijo["etapa"], disabled=True, key=f"tr_etapa_{i}")[cite: 1]
                e_fec_val = c_fecha.date_input("Fecha *", value=item_fijo["fecha"], format="DD/MM/YYYY", key=f"tr_fecha_{i}_{st.session_state.id_proyecto_cargado}")
                permitir_editar = c_edit_chk.checkbox("✏️ Editar", key=f"chk_edit_{i}_{st.session_state.id_proyecto_cargado}")
                e_res = c_resp.text_input("Responsable *", value=val_tr_resp, disabled=not permitir_editar, key=f"tr_resp_{i}_{st.session_state.id_proyecto_cargado}")
                e_pes_str = c_peso.text_input("Peso (kg) *", value=f"{val_tr_peso:.2f}", disabled=not permitir_editar, key=f"tr_peso_{i}_{val_tr_peso:.2f}_{permitir_editar}")

                try:
                    e_pes_num = float(e_pes_str)[cite: 1]
                except ValueError:
                    e_pes_num = 0.0[cite: 1]

                if item_fijo["etapa"] == "Lavado":
                    peso_lavado_auto = e_pes_num[cite: 1]
                elif item_fijo["etapa"] == "Corte":
                    peso_corte_auto = e_pes_num[cite: 1]

                e_tip = c_tipo.text_input("Tipo Registro", value=item_fijo["tipo"], disabled=True, key=f"tr_tipo_{i}")[cite: 1]
                e_fot = c_foto.file_uploader("Evidencia", type=["jpg", "png", "jpeg"], key=f"tr_foto_{i}_{st.session_state.id_proyecto_cargado}")
                if e_fot is not None:
                    c_foto.image(e_fot, width=70)[cite: 1]

                lista_trazabilidad.append({
                    "etapa": e_nom,
                    "fecha": e_fec_val.strftime("%d/%m/%Y"),
                    "responsable": e_res,
                    "peso": e_pes_num,
                    "tipo_registro": e_tip,
                    "foto": e_fot,
                })[cite: 1]

        st.write("")[cite: 1]

        # --- SECCIÓN 4: SALIDA DE PRODUCTOS ---
        with st.container(border=True):
            st.subheader("4. Salida de Productos")[cite: 1]
            saved_prods = detalles_guardados.get("productos", [])

            if "num_prods" not in st.session_state or st.session_state.id_proyecto_cargado != st.session_state.get("_last_id_prods"):
                st.session_state.num_prods = max(1, len(saved_prods)) if saved_prods else 2
                st.session_state._last_id_prods = st.session_state.id_proyecto_cargado

            cp_btn1, cp_btn2, _ = st.columns([1, 1, 4])[cite: 1]
            if cp_btn1.button("➕     Agregar Producto"):[cite: 1]
                st.session_state.num_prods += 1[cite: 1]
                st.rerun()[cite: 1]
            if cp_btn2.button("➖     Quitar Producto") and st.session_state.num_prods > 1:[cite: 1]
                st.session_state.num_prods -= 1[cite: 1]
                st.rerun()[cite: 1]

            lista_productos = [][cite: 1]
            total_prod_unid = 0[cite: 1]

            for i in range(st.session_state.num_prods):
                st.markdown(f"**Producto {i+1}**")[cite: 1]
                col_psel, col_pnom_nuevo, col_pcant, col_pfoto = st.columns([3, 2.5, 1.5, 3])[cite: 1]

                val_p_nombre = saved_prods[i].get("producto", st.session_state.catalogo_productos[0]) if i < len(saved_prods) else st.session_state.catalogo_productos[0]
                idx_p = st.session_state.catalogo_productos.index(val_p_nombre) if val_p_nombre in st.session_state.catalogo_productos else 0
                val_p_cant = saved_prods[i].get("cantidad", 0) if i < len(saved_prods) else 0

                prod_seleccionado = col_psel.selectbox("Seleccionar Producto Base *", st.session_state.catalogo_productos, index=idx_p, key=f"prod_sel_{i}_{st.session_state.id_proyecto_cargado}")
                col_pnom_nuevo.text_input("Producto", value=prod_seleccionado, disabled=True, key=f"prod_dis_{i}_{prod_seleccionado}")[cite: 1]
                p_cant = col_pcant.number_input("Cantidad (Unid.) *", min_value=0, value=int(val_p_cant), key=f"prod_cant_{i}_{st.session_state.id_proyecto_cargado}")
                p_foto = col_pfoto.file_uploader("Evidencia Foto", type=["jpg", "png", "jpeg"], key=f"prod_foto_{i}_{st.session_state.id_proyecto_cargado}")

                if p_foto is not None:
                    col_pfoto.image(p_foto, width=80)[cite: 1]

                total_prod_unid += p_cant[cite: 1]
                lista_productos.append({"producto": prod_seleccionado, "cantidad": p_cant, "foto": p_foto})[cite: 1]

            st.success(f"🧮 **Suma Total de Productos Obtenidos:** {total_prod_unid} unidades")[cite: 1]

        st.write("")[cite: 1]

        # --- SECCIÓN 5: BALANCE DE MATERIAL ---
        with st.container(border=True):
            st.subheader("5. Balance de Material")[cite: 1]
            saved_balance = detalles_guardados.get("balance", {})
            pct_aprov_auto = st.session_state.pct_aprovechamiento_random[cite: 1]
            pct_transf_auto = min(st.session_state.pct_transformado_ratio, pct_aprov_auto - 0.05)[cite: 1]
            pct_retazos_auto = pct_aprov_auto - pct_transf_auto[cite: 1]

            mat_transf_def = saved_balance.get("mat_transformado", round(peso_total_recibido * pct_transf_auto, 2))
            retazos_def = saved_balance.get("retazos_aprovechables", round(peso_total_recibido * pct_retazos_auto, 2))
            perdida_def = saved_balance.get("perdida_no_aprovechable", round(peso_total_recibido - float(mat_transf_def) - float(retazos_def), 2) if peso_total_recibido > 0 else 0.0)

            editar_balance = st.checkbox("✏️ Editar balance manualmente", key=f"chk_edit_balance_{st.session_state.id_proyecto_cargado}")
            col_bm1, col_bm2 = st.columns(2)[cite: 1]
            mat_transformado = col_bm1.number_input("Material transformado en productos (kg)", min_value=0.0, value=float(mat_transf_def), step=0.1, disabled=not editar_balance, key=f"bm_mat_transf_{st.session_state.id_proyecto_cargado}")
            retazos_aprovechables = col_bm2.number_input("Retazos aprovechables (kg)", min_value=0.0, value=float(retazos_def), step=0.1, disabled=not editar_balance, key=f"bm_retazos_{st.session_state.id_proyecto_cargado}")

            col_bm3, _ = st.columns([1, 1])[cite: 1]
            perdida_no_aprovechable = col_bm3.number_input("Pérdida no aprovechable (kg)", min_value=0.0, value=float(perdida_def), step=0.1, disabled=not editar_balance, key=f"bm_perdida_{st.session_state.id_proyecto_cargado}")
            total_procesado = mat_transformado + retazos_aprovechables + perdida_no_aprovechable[cite: 1]

            if peso_total_recibido > 0:
                pct_aprovechamiento_total = ((mat_transformado + retazos_aprovechables) / peso_total_recibido) * 100[cite: 1]
                pct_perdida = (perdida_no_aprovechable / peso_total_recibido) * 100[cite: 1]
            else:
                pct_aprovechamiento_total, pct_perdida = 0.0, 0.0[cite: 1]

            ind1, ind2, ind3 = st.columns(3)[cite: 1]
            ind1.metric("Total Procesado", f"{total_procesado:.2f} kg")[cite: 1]
            ind2.metric("% Aprovechamiento Total", f"{pct_aprovechamiento_total:.2f}%")[cite: 1]
            ind3.metric("% Pérdida", f"{pct_perdida:.2f}%")[cite: 1]

        st.write("")[cite: 1]

        # --- SECCIÓN 6: EMISIONES Y TRANSPORTE ---
        with st.container(border=True):
            st.subheader("6. Balance de Emisiones (CO₂e)")[cite: 1]
            st.markdown("##### 🚚 A. Cálculo de Transporte")[cite: 1]
            ct1, ct2, ct3, ct4 = st.columns([2.5, 1.2, 1.8, 1.5])[cite: 1]

            saved_distrito = detalles_guardados.get("distrito_transporte", list(DISTANCIAS_LIMA_SJL.keys())[0])
            idx_dist = list(DISTANCIAS_LIMA_SJL.keys()).index(saved_distrito) if saved_distrito in DISTANCIAS_LIMA_SJL else 0

            distrito_sel = ct1.selectbox("Distrito de Origen (Recojo) *", list(DISTANCIAS_LIMA_SJL.keys()), index=idx_dist, key=f"transp_dist_{st.session_state.id_proyecto_cargado}")
            dist_defecto = float(detalles_guardados.get("distancia_km", DISTANCIAS_LIMA_SJL[distrito_sel]))
            distancia_km = ct2.number_input("Distancia (km)", min_value=0.0, value=dist_defecto, step=0.5, key=f"dist_km_{distrito_sel}_{st.session_state.id_proyecto_cargado}")

            vehiculo_sel = ct3.selectbox("Tipo de Vehículo", list(FACTORES_TRANSPORTE.keys()), key=f"transp_veh_{st.session_state.id_proyecto_cargado}")
            recorrido_tipo = ct4.selectbox("Tipo de Recorrido", ["Ida y Vuelta (2)", "Ida sola (1)"], key=f"transp_rec_{st.session_state.id_proyecto_cargado}")

            factor_veh = FACTORES_TRANSPORTE[vehiculo_sel][cite: 1]
            mult_recorrido = 2.0 if "2" in recorrido_tipo else 1.0[cite: 1]
            emisiones_transporte = distancia_km * mult_recorrido * factor_veh["consumo"] * factor_veh["factor"][cite: 1]

            emisiones_lavado = peso_lavado_auto * 0.30[cite: 1]
            emisiones_corte = peso_corte_auto * 0.05[cite: 1]

            st.markdown("##### 🧵 C. Cálculo de Bordado o Estampado")[cite: 1]
            cb1, cb2 = st.columns(2)[cite: 1]
            cant_prendas_bordado = cb1.number_input("Prendas con bordado/estampado", min_value=0, value=int(detalles_guardados.get("cant_prendas_bordado", 0)), step=1, key=f"bord_cant_{st.session_state.id_proyecto_cargado}")
            tipo_diseno_bordado = cb2.selectbox("Tipo de Diseño", list(FACTORES_BORDADO.keys()), key=f"bord_tipo_{st.session_state.id_proyecto_cargado}")
            emisiones_bordado = cant_prendas_bordado * FACTORES_BORDADO[tipo_diseno_bordado][cite: 1]

            emisiones_proceso = emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado[cite: 1]
            co2_neto = co2_evitado_total - emisiones_proceso[cite: 1]

            st.warning(f"🌍 **Total Emisiones del Proceso:** {emisiones_proceso:.2f} kg CO₂e | **Impacto Ambiental Neto Evitado:** {co2_neto:.2f} kg CO₂e")[cite: 1]

        st.write("")[cite: 1]

        # --- SECCIÓN 7: IMPACTO SOCIAL Y PERSONAL ---
        with st.container(border=True):
            st.subheader("7. Equipo de Trabajo y Generación de Horas")[cite: 1]
            st.markdown("#### Operaciones – Corte y Logística")[cite: 1]

            saved_ops = detalles_guardados.get("operaciones", [])
            lista_operaciones = [][cite: 1]
            total_horas_ops = 0.0[cite: 1]

            for idx, p_fijo in enumerate(PERSONAL_FIJO_OPERACIONES):
                c_rol, c_nom, c_chk, c_dias, c_hdia, c_tot = st.columns([1.5, 2.5, 0.8, 1.2, 1.2, 1.2])[cite: 1]
                
                nom_def = saved_ops[idx].get("nombre", p_fijo["nombre"]) if idx < len(saved_ops) else p_fijo["nombre"]
                dias_def = int(saved_ops[idx].get("dias", 1)) if idx < len(saved_ops) else 1
                hdia_def = float(saved_ops[idx].get("horas_dia", 3.0)) if idx < len(saved_ops) else 3.0

                c_rol.text_input("Rol", value=p_fijo["rol"], disabled=True, key=f"ops_rol_{idx}", label_visibility="collapsed")[cite: 1]
                editar_fila = c_chk.checkbox("✅", key=f"ops_chk_{idx}_{st.session_state.id_proyecto_cargado}", label_visibility="collapsed")
                nom_val = c_nom.text_input("Nombre", value=nom_def, disabled=not editar_fila, key=f"ops_nom_{idx}_{st.session_state.id_proyecto_cargado}", label_visibility="collapsed")
                val_dias = c_dias.number_input("Días", min_value=0, value=dias_def, step=1, disabled=not editar_fila, key=f"ops_dias_{idx}_{st.session_state.id_proyecto_cargado}", label_visibility="collapsed")
                val_hdia = c_hdia.number_input("Hrs/Día", min_value=0.0, value=hdia_def, step=0.5, disabled=not editar_fila, key=f"ops_hdia_{idx}_{st.session_state.id_proyecto_cargado}", label_visibility="collapsed")

                tot_hrs_pers = float(val_dias) * float(val_hdia)[cite: 1]
                c_tot.text_input("Total", value=f"{tot_hrs_pers:.2f}", disabled=True, key=f"ops_tot_{idx}_{val_dias}_{val_hdia}", label_visibility="collapsed")[cite: 1]

                total_horas_ops += tot_hrs_pers[cite: 1]
                lista_operaciones.append({
                    "rol": p_fijo["rol"],
                    "nombre": nom_val,
                    "dias": val_dias,
                    "horas_dia": val_hdia,
                    "horas_totales": tot_hrs_pers,
                })[cite: 1]

            st.write("---")[cite: 1]
            st.markdown("#### Confección y Acabado – Asignación de Personal")[cite: 1]

            lista_confeccion = [][cite: 1]
            horas_confeccion_total = 0.0[cite: 1]
            personas_confeccion_set = set()[cite: 1]
            saved_conf = detalles_guardados.get("confeccion", [])

            for idx, prod in enumerate(lista_productos):
                p_nom = prod["producto"][cite: 1]
                p_cant = prod["cantidad"][cite: 1]
                tiempo_base_ia = estimar_tiempo_unidad(p_nom)[cite: 1]

                st.markdown(f"**📦 Producto {idx+1}: {p_nom}** *(Cantidad: {p_cant} unid)*")

                c_rol, c_persona, c_cant_asig, c_tiempo, c_tot = st.columns([1.8, 3.0, 1.4, 1.8, 1.8])[cite: 1]
                
                conf_match = next((c for c in saved_conf if c.get("producto") == p_nom), {})
                idx_pers = st.session_state.lista_personal_confeccion.index(conf_match.get("persona")) if conf_match.get("persona") in st.session_state.lista_personal_confeccion else 0
                cant_def = conf_match.get("cantidad", p_cant)

                rol_sel = c_rol.selectbox("Rol *", ["Confección", "Acabado"], key=f"soc_rol_{idx}_{st.session_state.id_proyecto_cargado}")
                persona_sel = c_persona.selectbox("Persona *", st.session_state.lista_personal_confeccion, index=idx_pers, key=f"soc_pers_{idx}_{st.session_state.id_proyecto_cargado}")
                cant_asig = c_cant_asig.number_input("Unidades *", min_value=0, max_value=max(1, p_cant), value=int(cant_def), key=f"soc_cant_{idx}_{st.session_state.id_proyecto_cargado}")
                tiempo_unitario = c_tiempo.number_input("Tiempo/Unid (hrs) *", min_value=0.0, value=float(tiempo_base_ia), step=0.05, key=f"soc_tunit_{idx}_{st.session_state.id_proyecto_cargado}")

                horas_persona = cant_asig * tiempo_unitario[cite: 1]
                c_tot.text_input("Horas Totales", value=f"{horas_persona:.2f} hrs", disabled=True, key=f"soc_htot_{idx}_{horas_persona}")

                horas_confeccion_total += horas_persona[cite: 1]
                if persona_sel:
                    personas_confeccion_set.add(persona_sel)[cite: 1]

                lista_confeccion.append({
                    "producto": p_nom,
                    "rol": rol_sel,
                    "persona": persona_sel,
                    "cantidad": cant_asig,
                    "tiempo_unitario": tiempo_unitario,
                    "horas_totales": horas_persona,
                })[cite: 1]

            total_horas_social = total_horas_ops + horas_confeccion_total[cite: 1]
            total_personas_social = len(PERSONAL_FIJO_OPERACIONES) + len(personas_confeccion_set)[cite: 1]
            st.info(f"🧑‍🤝‍🧑 **Impacto Social Total:** {total_horas_social:.2f} horas generadas | {total_personas_social} personas beneficiadas.")[cite: 1]

        st.write("")[cite: 1]

        # --- SECCIÓN 8: ANEXOS ---
        with st.container(border=True):
            st.subheader("8. Anexos (Registro Fotográfico Adicional)")[cite: 1]
            saved_anx = detalles_guardados.get("anexos", [])

            col_anx1, col_anx2, _ = st.columns([1, 1, 4])[cite: 1]
            if col_anx1.button("➕     Agregar Anexo"):[cite: 1]
                st.session_state.num_anexos += 1[cite: 1]
                st.rerun()[cite: 1]
            if col_anx2.button("➖     Quitar Anexo") and st.session_state.num_anexos > 0:[cite: 1]
                st.session_state.num_anexos -= 1[cite: 1]
                st.rerun()[cite: 1]

            lista_anexos = [][cite: 1]
            for a_i in range(st.session_state.num_anexos):
                st.markdown(f"**Evidencia Anexa {a_i+1}**")[cite: 1]
                col_afoto, col_anota = st.columns([1.5, 3])[cite: 1]
                foto_anx = col_afoto.file_uploader("Fotografía", type=["jpg", "png", "jpeg"], key=f"anx_foto_{a_i}_{st.session_state.id_proyecto_cargado}")
                nota_def = saved_anx[a_i].get("nota", "") if a_i < len(saved_anx) else ""
                nota_anx = col_anota.text_area("Nota / Descripción", value=nota_def, key=f"anx_nota_{a_i}_{st.session_state.id_proyecto_cargado}", height=90)

                lista_anexos.append({"foto": foto_anx, "nota": nota_anx})[cite: 1]

        st.write("")[cite: 1]

        # --- GUARDAR BORRADOR / GENERAR REPORTES ---
        with st.container(border=True):
            col_gen1, col_gen2 = st.columns([2, 1])[cite: 5]

            # Empaquetar todo el estado detallado para Supabase
            paquete_datos_completos = {
                "responsables": responsables_seleccionados,
                "guia": guia_remision,
                "origen": origen,
                "destino": destino,
                "distrito_transporte": distrito_sel,
                "distancia_km": distancia_km,
                "vehiculo_transporte": vehiculo_sel,
                "recorrido_tipo": recorrido_tipo,
                "cant_prendas_bordado": cant_prendas_bordado,
                "tipo_diseno_bordado": tipo_diseno_bordado,
                "items": [{"descripcion": it["descripcion"], "unidades": it["unidades"], "peso_total": it["peso_total"]} for it in lista_items],
                "trazabilidad": [{"etapa": tr["etapa"], "fecha": tr["fecha"], "responsable": tr["responsable"], "peso": tr["peso"], "tipo_registro": tr["tipo_registro"]} for tr in lista_trazabilidad],
                "productos": [{"producto": pr["producto"], "cantidad": pr["cantidad"]} for pr in lista_productos],
                "balance": {"mat_transformado": mat_transformado, "retazos_aprovechables": retazos_aprovechables, "perdida_no_aprovechable": perdida_no_aprovechable},
                "operaciones": [{"rol": op["rol"], "nombre": op["nombre"], "dias": op["dias"], "horas_dia": op["horas_dia"], "horas_totales": op["horas_totales"]} for op in lista_operaciones],
                "confeccion": [{"producto": cf["producto"], "rol": cf["rol"], "persona": cf["persona"], "cantidad": cf["cantidad"], "tiempo_unitario": cf["tiempo_unitario"], "horas_totales": cf["horas_totales"]} for cf in lista_confeccion],
                "anexos": [{"nota": ax.get("nota", "")} for ax in lista_anexos],
            }

            if col_gen2.button("💾 Guardar como Borrador", use_container_width=True):[cite: 5]
                try:
                    with st.spinner("Guardando borrador completo en Supabase..."):
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
                            "datos_completos": paquete_datos_completos,
                        }

                        if p_edit.get("id"):
                            supabase.table("proyectos").update(datos_borrador).eq("id", p_edit["id"]).execute()[cite: 1]
                        else:
                            supabase.table("proyectos").insert(datos_borrador).execute()[cite: 1]

                    st.success("✅ ¡Borrador guardado con todo el detalle!")
                    st.session_state.proyecto_editar = {}[cite: 1]
                    st.session_state.id_proyecto_cargado = None
                    st.session_state.documentos_descarga = None[cite: 5]
                    st.rerun()[cite: 1]
                except Exception as e:
                    st.error(f"⚠️ Error al guardar borrador: {e}")

            if col_gen1.button("🚀 Generar Reportes Oficiales (Informe + Constancia)", type="primary", use_container_width=True):[cite: 5]
                if not cliente.strip() or not ruc.strip():
                    st.error("⚠️ Ingrese al menos Cliente y RUC válido.")
                else:
                    with st.spinner("Generando Informe y Constancia Word..."):
                        try:
                            # 1. Informe Técnico PDF
                            pdf_inf = generar_pdf_oficial(
                                cliente, ruc, proyecto_nom, codigo_proy, fe_inicio, fe_fin,
                                responsable, area, "Textiles en desuso", "Upcycling", "Kilogramos (kg)",
                                guia_remision, origen, destino, lista_items, lista_trazabilidad,
                                lista_productos, mat_transformado, retazos_aprovechables,
                                perdida_no_aprovechable, total_procesado, pct_aprovechamiento_total,
                                pct_perdida, lista_operaciones, lista_confeccion, total_horas_social,
                                total_personas_social, co2_evitado_total, emisiones_transporte,
                                emisiones_lavado, emisiones_corte, emisiones_bordado, lista_anexos=lista_anexos,
                            )
                            bytes_inf = pdf_inf.getvalue()

                            # 2. Constancia Word -> PDF
                            mes_fin_nombre = MESES_ESPANOL.get(fe_fin_dt.month, "")
                            contexto_word = {
                                "cliente": cliente.upper(),
                                "mes": mes_fin_nombre,
                                "anio": str(fe_fin_dt.year),
                                "peso_recibido": f"{peso_total_recibido:.1f}",
                                "unidades_ingreso": str(total_piezas_ingresadas),
                                "co2_evitado": f"{co2_neto:.2f}",
                                "aprovechamiento": f"{pct_aprovechamiento_total:.2f}",
                                "total_mujeres": str(total_personas_social),
                                "total_horas": f"{total_horas_social:.1f}",
                                "productos_elaborados": str(total_prod_unid),
                                "fecha_cierre": f"{fe_fin_dt.strftime('%d')} de {mes_fin_nombre} de {fe_fin_dt.year}",
                            }
                            bytes_const = generar_constancia_desde_plantilla_word(contexto_word)

                            # 3. Archivo ZIP
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                                zf.writestr(f"Informe_Tecnico_{codigo_proy}.pdf", bytes_inf)
                                zf.writestr(f"Constancia_Transformacion_{codigo_proy}.pdf", bytes_const)
                            zip_buffer.seek(0)
                            bytes_zip = zip_buffer.getvalue()

                            # 4. Storage Supabase
                            url_inf = subir_pdf_supabase(f"Informe_{codigo_proy}.pdf", bytes_inf)
                            url_const = subir_pdf_supabase(f"Constancia_{codigo_proy}.pdf", bytes_const)

                            # 5. Guardar en Base de Datos como COMPLETADO
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
                                "pdf_url": url_inf if url_inf else p_edit.get("pdf_url", ""),
                                "constancia_url": url_const if url_const else p_edit.get("constancia_url", ""),
                                "datos_completos": paquete_datos_completos,
                            }
                            if p_edit.get("id"):
                                supabase.table("proyectos").update(datos_completado).eq("id", p_edit["id"]).execute()[cite: 1]
                            else:
                                supabase.table("proyectos").upsert(datos_completado).execute()[cite: 1]

                            st.session_state.documentos_descarga = {
                                "codigo": codigo_proy,
                                "bytes_informe": bytes_inf,
                                "bytes_constancia": bytes_const,
                                "bytes_zip": bytes_zip,
                            }
                            st.rerun()[cite: 1]
                        except Exception as e:
                            st.error(f"❌ Error al procesar: {e}")

        # Botones de descarga persistentes
        if st.session_state.documentos_descarga:
            docs = st.session_state.documentos_descarga
            st.success("✅ ¡Informe Técnico y Constancia de Transformación listos para descarga!")[cite: 5]
            c_dzip, c_dinf, c_dconst = st.columns([1.5, 1.2, 1.2])[cite: 5]
            c_dzip.download_button("📦 Descargar Ambos (.ZIP)", data=docs["bytes_zip"], file_name=f"Documentos_{docs['codigo']}.zip", mime="application/zip", use_container_width=True, type="primary")
            c_dinf.download_button("📄 Descargar Informe PDF", data=docs["bytes_informe"], file_name=f"Informe_{docs['codigo']}.pdf", mime="application/pdf", use_container_width=True)[cite: 5]
            c_dconst.download_button("📜 Descargar Constancia PDF", data=docs["bytes_constancia"], file_name=f"Constancia_{docs['codigo']}.pdf", mime="application/pdf", use_container_width=True)[cite: 5]
