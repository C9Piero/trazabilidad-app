import datetime
import io
import os
import random
import re
import subprocess
import tempfile
import zipfile
import pandas as pd
import streamlit as st
import plotly.express as px  # <-- LIBRERÍA NUEVA PARA GRÁFICOS INTERACTIVOS
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

# --- LIBRERÍAS DE GOOGLE DRIVE (OAUTH) ---
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

def obtener_carpeta_destino_drive(cliente: str, fecha_fin_dt, nombre_subcarpeta: str):
    """Crea o busca la estructura de carpetas: AÑO / MES / CLIENTE / SUBCARPETA en Google Drive"""
    try:
        if "drive_oauth" not in st.secrets:
            return None
        creds_data = st.secrets["drive_oauth"]
        credentials = Credentials(
            token=None,
            refresh_token=creds_data["refresh_token"],
            client_id=creds_data["client_id"],
            client_secret=creds_data["client_secret"],
            token_uri="https://oauth2.googleapis.com/token"
        )
        service = build('drive', 'v3', credentials=credentials)
        root_folder_id = creds_data["folder_id"]

        nombre_carpeta_anio = str(fecha_fin_dt.year)
        query_anio = f"name='{nombre_carpeta_anio}' and mimeType='application/vnd.google-apps.folder' and '{root_folder_id}' in parents and trashed=false"
        res_anio = service.files().list(q=query_anio, fields='files(id)').execute()
        
        if not res_anio.get('files', []):
            carpeta_anio = service.files().create(
                body={'name': nombre_carpeta_anio, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [root_folder_id]}, 
                fields='id'
            ).execute()
            id_anio = carpeta_anio.get('id')
        else:
            id_anio = res_anio.get('files')[0].get('id')

        meses = {1:"ENERO", 2:"FEBRERO", 3:"MARZO", 4:"ABRIL", 5:"MAYO", 6:"JUNIO", 
                 7:"JULIO", 8:"AGOSTO", 9:"SETIEMBRE", 10:"OCTUBRE", 11:"NOVIEMBRE", 12:"DICIEMBRE"}
        nombre_carpeta_mes = meses.get(fecha_fin_dt.month, 'MES')
        query_mes = f"name='{nombre_carpeta_mes}' and mimeType='application/vnd.google-apps.folder' and '{id_anio}' in parents and trashed=false"
        res_mes = service.files().list(q=query_mes, fields='files(id)').execute()
        
        if not res_mes.get('files', []):
            carpeta_mes = service.files().create(
                body={'name': nombre_carpeta_mes, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [id_anio]}, 
                fields='id'
            ).execute()
            id_mes = carpeta_mes.get('id')
        else:
            id_mes = res_mes.get('files')[0].get('id')

        nombre_cliente = cliente.strip().upper().replace("'", "")
        query_cli = f"name='{nombre_cliente}' and mimeType='application/vnd.google-apps.folder' and '{id_mes}' in parents and trashed=false"
        res_cli = service.files().list(q=query_cli, fields='files(id)').execute()
        
        if not res_cli.get('files', []):
            carpeta_cli = service.files().create(
                body={'name': nombre_cliente, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [id_mes]}, 
                fields='id'
            ).execute()
            id_cli = carpeta_cli.get('id')
        else:
            id_cli = res_cli.get('files')[0].get('id')

        query_proy = f"name='{nombre_subcarpeta}' and mimeType='application/vnd.google-apps.folder' and '{id_cli}' in parents and trashed=false"
        res_proy = service.files().list(q=query_proy, fields='files(id)').execute()
        
        if not res_proy.get('files', []):
            carpeta_proy = service.files().create(
                body={'name': nombre_subcarpeta, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [id_cli]}, 
                fields='id'
            ).execute()
            id_proy = carpeta_proy.get('id')
        else:
            id_proy = res_proy.get('files')[0].get('id')

        return id_proy
    except Exception as e:
        st.caption(f"Aviso Carpetas Drive: {e}")
        return None

def subir_a_drive(nombre_archivo: str, file_bytes: bytes, mime_type="application/pdf", custom_folder_id=None):
    """Sube un archivo a Google Drive usando las credenciales del usuario (OAuth)."""
    try:
        if "drive_oauth" not in st.secrets:
            return None 
        creds_data = st.secrets["drive_oauth"]
        credentials = Credentials(
            token=None,
            refresh_token=creds_data["refresh_token"],
            client_id=creds_data["client_id"],
            client_secret=creds_data["client_secret"],
            token_uri="https://oauth2.googleapis.com/token"
        )
        service = build('drive', 'v3', credentials=credentials)
        folder_id = custom_folder_id if custom_folder_id else creds_data["folder_id"]
        
        file_metadata = {'name': nombre_archivo, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        
        archivo_subido = service.files().create(
            body=file_metadata, media_body=media, fields='id'
        ).execute()
        return archivo_subido.get('id')
    except Exception as e:
        st.caption(f"Aviso Drive: No se pudo respaldar el archivo {nombre_archivo} - {e}")
        return None

# --- DICCIONARIO DE MESES EN ESPAÑOL ---
MESES_ESPANOL = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "setiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}
MESES_ORDEN = [m.capitalize() for m in MESES_ESPANOL.values()]

# --- CATÁLOGO BASE DE PRODUCTOS HISTÓRICOS ---
PRODUCTOS_CATALOGO_BASE = [
    "Estrellas", "Cartuchera", "Cúbica", "Bolso", "Mochila", "Llavero",
    "Monedero", "Canguro", "Tote bag", "Neceser", "Portalaptop",
    "Portacepillos", "Pelota", "Portacubierto", "Juguete", "Cubo",
    "Corazones", "Peluche", "Morral", "Portaútiles", "Portabotella",
    "Cama perrito", "Colets", "Rombo", "Mandiles", "Lonchera",
    "➕ Otro (Escribir nuevo producto)",
]

# --- PERSONAL BASE DE CONFECCIÓN Y ACABADO ---
PERSONAL_CONFECCION_BASE = [
    "Celinda Gutierrez Delgado", "Guadalupe Guerra Cespedes", "Isabel Estrada Sandoval",
    "Carmen Cespedes Borda", "Mavela Espinoza", "Juana Padilla Ruiz", "Felicita Sandoval Vilchez",
    "Luciana Jara Estrada", "Genaro Jara Garcia", "Yovana Davila", "Katherine Hilario Vilca",
    "Rody Jara Rucana", "Lucila Campos", "Tiffany Landa Rios", "Sara Mallqui Herrada",
    "Erlith Paima", "Sonia Panduro Torres", "Cintya Rincon", "Dixie Hidalgo Martel",
    "Janeth Mescco Bautista", "Judith Cueva Vargas", "Linfa Tauche", "Maricela Nieto",
    "Sofia Moya Reyes", "Carmen Vizarreta Lozada", "Genoveva Vizarreta Lozada",
    "Gathy Perez Ortiz", "Omar Prada", "Yovana Davila Ramirez", "Rosario Evelin Blas Alcala",
    "Esmeralda Tandazo Briceño", "Jhoel Angel Dominguez Rementeria", "Pedro Estrada Ramos",
    "Victor Auccapuri San Miguel", "Gabriel Manrique Hurtado", "Evelyn Prada Vizarreta",
    "Eugenia Almanza Huere", "Nicolle Estrada Yabe", "Oswaldo Jara Garcia", "Noelia Gonzales Lopez",
]

# --- MATRIZ DE TIEMPOS DE CONFECCIÓN PURA (en horas) ---
TIEMPOS_CONFECCION_PURO = {
    "mochila": 0.60, "bolso": 0.45, "tote bag": 0.30, "portalaptop": 0.75,
    "canguro": 0.50, "neceser": 0.35, "lonchera": 0.50, "cartuchera": 0.25,
    "morral": 0.50, "mandiles": 0.30, "cama perrito": 0.80, "cama": 0.80, 
    "casa": 0.80, "peluche": 0.60, "pelota": 0.30, "estrellas": 0.15, 
    "corazones": 0.15, "rombo": 0.15, "cúbica": 0.25, "cubo": 0.25, 
    "llavero": 0.10, "monedero": 0.15, "portacepillos": 0.12, 
    "portacubierto": 0.12, "portaútiles": 0.20, "portabotella": 0.20, 
    "colets": 0.08, "juguete": 0.40,
}

def estimar_tiempo_unidad(nombre_producto: str) -> float:
    if not nombre_producto: return 0.35
    nombre_lower = nombre_producto.lower().strip()
    tiempo_costura = 0.40
    encontrado = False
    
    for prod_key, tiempo in TIEMPOS_CONFECCION_PURO.items():
        if prod_key in nombre_lower:
            tiempo_costura = tiempo
            encontrado = True
            break
            
    if not encontrado:
        if any(w in nombre_lower for w in ["casa", "cama", "colchón", "almohadón", "organizador"]): tiempo_costura = 0.80
        elif any(w in nombre_lower for w in ["mochila", "morral", "maletín", "set", "conjunto"]): tiempo_costura = 0.70
        elif any(w in nombre_lower for w in ["bolso", "tote", "lonchera", "funda", "delantal"]): tiempo_costura = 0.45
        elif any(w in nombre_lower for w in ["cartuchera", "neceser", "monedero", "estuche"]): tiempo_costura = 0.30
        else: tiempo_costura = 0.35

    if any(w in nombre_lower for w in ["gran", "grande", "maxi", "complejo", "completo", "xl", "pesado"]):
        tiempo_costura += 0.25
    elif any(w in nombre_lower for w in ["mini", "pequeño", "simple", "corto", "sencillo"]):
        tiempo_costura = max(0.10, tiempo_costura - 0.15)
        
    return round(max(0.10, tiempo_costura), 2)

# --- FACTORES DE EMISIÓN Y TRANSPORTE ---
FACTORES_CO2 = {"Banner": 9.5, "Bolsas": 8.0, "Camisa algodón": 5.0, "Camisa drill": 5.9, "Casaca drill": 5.9, "Casaca polar": 6.0, "Chaleco": 6.575, "Pantalón jean": 5.0, "Polo algodón": 5.0, "Otro": 6.575}
FACTORES_TRANSPORTE = {"Auto": {"consumo": 0.10, "factor": 2.31}, "Minivan": {"consumo": 0.12, "factor": 2.00}, "Mototaxi": {"consumo": 0.04, "factor": 2.31}, "Moto": {"consumo": 0.03, "factor": 2.31}, "Camión mediano": {"consumo": 0.30, "factor": 2.68}, "Camión grande": {"consumo": 0.40, "factor": 2.68}}
DISTANCIAS_LIMA_SJL = {"San Juan de Lurigancho (Local)": 4.0, "Ate": 14.0, "Barranco": 18.5, "Callao (Cercado)": 18.0, "Comas": 18.0, "El Agustino": 6.0, "Independencia": 12.0, "Jesús María": 12.0, "La Molina": 15.0, "La Victoria": 9.5, "Lima (Cercado de Lima)": 9.0, "Lince": 12.5, "Los Olivos": 15.0, "Miraflores": 16.0, "Pueblo Libre": 13.5, "Rímac": 7.5, "San Borja": 12.0, "San Isidro": 13.5, "San Miguel": 15.5, "Santiago de Surco": 17.0, "Villa El Salvador": 28.0, "➕ Otro / Fuera de Lima (Ingreso manual)": 0.0}
FACTORES_BORDADO = {"Sin bordado / Ninguno": 0.0, "Estampado DTF": 0.020, "Simple (5 min/pieza)": 0.020, "Medio (9 min/pieza)": 0.037, "Complejo (10 min/pieza)": 0.041}
PERSONAL_FIJO_OPERACIONES = [{"rol": "Corte", "nombre": "Maria Isabel Estrada Sandoval"}, {"rol": "Corte", "nombre": "Genaro Jara García"}, {"rol": "Corte", "nombre": "Luciana Jara estrada"}, {"rol": "Corte", "nombre": "Felicita Sandoval vilchez"}, {"rol": "Corte", "nombre": "Nicolle Estrada"}, {"rol": "Logística", "nombre": "Evelyn Prada Vizarreta"}]

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Pequeños Detalles - Sistema de Trazabilidad", page_icon="♻️", layout="wide")

# --- ESTILOS CSS ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    :root { --brand-900: #0F172A; --brand-700: #1E3A8A; --brand-500: #2563EB; --ink-muted: #64748B; --border: #E2E8F0; --surface: #F8FAFC; --radius: 14px; }
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    div[data-testid="stNumberInput"] button { display: none !important; }
    div[data-testid="stNumberInput"] input { text-align: left; }
    .hero-header { background: linear-gradient(135deg, var(--brand-900) 0%, var(--brand-700) 50%, var(--brand-500) 100%); color: white; padding: 24px 30px; border-radius: var(--radius); box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.3); margin-bottom: 25px; }
    .hero-header h1 { color: #ffffff !important; font-weight: 800; font-size: 1.8rem; margin: 0; }
    .hero-header p { color: #93C5FD !important; margin: 4px 0 0 0; font-size: 0.95rem; }
    div[data-testid="stSidebar"] { background-color: var(--surface); border-right: 1px solid var(--border); }
    .sidebar-section-title { color: var(--ink-muted); font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 15px; margin-bottom: 8px; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: var(--radius) !important; border: 1px solid var(--border) !important; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06); transition: box-shadow 0.2s ease; }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover { box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08); }
    div[data-testid="stButton"] button { border-radius: 10px; font-weight: 600; border: 1px solid var(--border); }
    div[data-testid="stButton"] button[kind="primary"] { background: linear-gradient(135deg, var(--brand-700) 0%, var(--brand-500) 100%); border: none; }
    div[data-testid="stMetric"] { background-color: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["supabase"]["SUPABASE_URL"], st.secrets["supabase"]["SUPABASE_KEY"])

try: supabase = init_supabase()
except Exception as e: st.error(f"⚠️ No se pudo conectar con Supabase: {e}"); st.stop()

def subir_pdf_supabase(nombre_archivo: str, pdf_bytes: bytes) -> str:
    try:
        supabase.storage.from_("reportes").upload(path=nombre_archivo, file=pdf_bytes, file_options={"content-type": "application/pdf", "upsert": "true"})
        return supabase.storage.from_("reportes").get_public_url(nombre_archivo)
    except Exception: return ""

def subir_imagen_supabase(nombre_archivo: str, img_bytes: bytes) -> str:
    try:
        supabase.storage.from_("reportes").upload(path=nombre_archivo, file=img_bytes, file_options={"content-type": "image/jpeg", "upsert": "true"})
        return supabase.storage.from_("reportes").get_public_url(nombre_archivo)
    except Exception: return ""

def cargar_proyectos(estado=None):
    try:
        query = supabase.table("proyectos").select("*")
        if estado: query = query.eq("estado", estado)
        return query.execute().data
    except Exception: return []

def eliminar_proyecto_bd(proyecto_id, codigo_proy):
    try:
        if proyecto_id: supabase.table("proyectos").delete().eq("id", proyecto_id).execute()
        elif codigo_proy: supabase.table("proyectos").delete().eq("codigo", codigo_proy).execute()
        return True
    except Exception: return False

@st.dialog("⚠️ Confirmar Eliminación Permanente")
def modal_confirmar_eliminacion(proyecto):
    st.warning(f"¿Deseas eliminar permanentemente el proyecto **{proyecto.get('cliente', 'Sin Nombre')}**?")
    col_confirm, col_cancel = st.columns(2)
    if col_confirm.button("🚨 Eliminar", use_container_width=True, type="primary"):
        if eliminar_proyecto_bd(proyecto.get("id"), proyecto.get("codigo")):
            st.session_state.proyecto_editar = {}; st.toast("🗑️ Proyecto eliminado."); st.rerun()
    if col_cancel.button("Cancelar", use_container_width=True): st.rerun()

@st.dialog("⚠️ Confirmar Eliminación Masiva")
def modal_confirmar_eliminacion_masiva(proyectos_a_borrar):
    st.warning(f"¿Deseas eliminar permanentemente **{len(proyectos_a_borrar)}** proyectos seleccionados?")
    col_confirm, col_cancel = st.columns(2)
    if col_confirm.button("🚨 Eliminar Todos", use_container_width=True, type="primary"):
        for p in proyectos_a_borrar: eliminar_proyecto_bd(p.get("id"), p.get("codigo"))
        st.session_state.proyecto_editar = {}; st.toast(f"🗑️ {len(proyectos_a_borrar)} eliminados.")
        for p in proyectos_a_borrar:
            if f"bulk_del_{p.get('id', p.get('codigo'))}" in st.session_state: del st.session_state[f"bulk_del_{p.get('id', p.get('codigo'))}"]
        st.rerun()
    if col_cancel.button("Cancelar", use_container_width=True): st.rerun()

class ReporteCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.pages = []
    def showPage(self): self.pages.append(dict(self.__dict__)); self._startPage()
    def save(self):
        for page in self.pages:
            self.__dict__.update(page); self.draw_footer(); super().showPage()
        super().save()
    def draw_footer(self):
        self.saveState(); self.setFont("Helvetica", 7); self.setFillColor(colors.HexColor("#94A3B8"))
        self.drawCentredString(612 / 2.0, 22, "Promoviendo el desarrollo sostenible a través de la economía circular y el empoderamiento de mujeres")
        self.drawCentredString(612 / 2.0, 12, "emprendedoras"); self.restoreState()

def generar_constancia_desde_plantilla_word(contexto: dict) -> bytes:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ruta_encontrada = next((os.path.join(base_dir, f) for f in os.listdir(base_dir) if f.lower().endswith(".docx") and not f.startswith("~")), None)
    if not ruta_encontrada: raise FileNotFoundError("No se encontró plantilla Word (.docx)")
    doc = DocxTemplate(ruta_encontrada)
    doc.render(contexto)
    with tempfile.TemporaryDirectory() as tmpdir:
        docx_temp = os.path.join(tmpdir, "temp.docx")
        doc.save(docx_temp)
        subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", docx_temp, "--outdir", tmpdir], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with open(os.path.join(tmpdir, "temp.pdf"), "rb") as f: return f.read()

def generar_pdf_oficial(cliente, ruc, proyecto_nom, codigo_proy, fe_inicio, fe_fin, responsable, area, tipo_material, valorizacion, unidad_medida, guia_remision, origen, destino, lista_items, lista_trazabilidad, lista_productos, mat_transformado, retazos_aprovechables, perdida_no_aprovechable, total_procesado, pct_aprovechamiento_total, pct_perdida, lista_operaciones_pdf, lista_confeccion, total_horas_social, total_personas_social, co2_evitado_total, emisiones_transporte, emisiones_lavado, emisiones_corte, emisiones_bordado, lista_anexos=None):
    kg_recibidos = sum([item["peso_total"] for item in lista_items])
    co2_neto = co2_evitado_total - (emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=45)
    styles = getSampleStyleSheet()
    h1_style = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=14, textColor=colors.HexColor("#1E293B"), alignment=1, spaceAfter=2)
    sub_style = ParagraphStyle("Sub", parent=styles["Normal"], fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#64748B"), alignment=1, spaceAfter=12)
    h2_style = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=10, textColor=colors.HexColor("#0F172A"), spaceBefore=10, spaceAfter=6)
    cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#334155"), leading=10)
    cell_bold = ParagraphStyle("CellB", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, textColor=colors.HexColor("#0F172A"), leading=10)
    card_title = ParagraphStyle("CardT", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=12, textColor=colors.HexColor("#0F172A"), alignment=1)
    card_sub = ParagraphStyle("CardS", parent=styles["Normal"], fontName="Helvetica", fontSize=7, textColor=colors.HexColor("#475569"), alignment=1)

    elements = [
        Paragraph("INFORME TÉCNICO DE VALORIZACIÓN TEXTIL", h1_style),
        Paragraph(f"Medición de Impacto Ambiental, Trazabilidad y Gestión Social de Upcycling<br/><b>CÓDIGO: {codigo_proy}</b>", sub_style),
        Paragraph(f"Proyecto de economía circular implementado para <b>{cliente}</b>, transformando <b>{total_procesado:.2f} kg</b> de textiles en desuso mediante upcycling, con la elaboración de <b>{sum([p['cantidad'] for p in lista_productos])}</b> productos, participación de <b>{total_personas_social}</b> personas y un impacto neto evitado de <b>{co2_neto:.2f} kg</b> de CO₂e.", ParagraphStyle("Res", parent=styles["Normal"], fontSize=8.5, leading=12, alignment=4, spaceAfter=6)),
        Spacer(1, 4)
    ]

    t_cards = Table([
        [Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", card_title), Paragraph(f"<b>{pct_aprovechamiento_total:.2f}%</b>", card_title), Paragraph(f"<b>{co2_neto:.2f} kg</b>", card_title), Paragraph(f"<b>{total_horas_social:.2f} hrs</b>", card_title)],
        [Paragraph("MATERIAL RECIBIDO", card_sub), Paragraph("% APROVECHAMIENTO", card_sub), Paragraph("CO2e NETO EVITADO", card_sub), Paragraph(f"TRABAJO GENERADO", card_sub)]
    ], colWidths=[135, 135, 135, 135])
    t_cards.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("PADDING", (0, 0), (-1, -1), 6), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    elements.extend([t_cards, Spacer(1, 8), Paragraph("1. FICHA GENERAL DEL PROYECTO", h2_style)])

    t_ficha = Table([
        [Paragraph("Cliente / Empresa", cell_bold), Paragraph(f"{cliente} (RUC: {ruc})", cell_style), Paragraph("Área / Responsable", cell_bold), Paragraph(f"{area} / {responsable}", cell_style)],
        [Paragraph("Tipo de Proyecto", cell_bold), Paragraph(proyecto_nom, cell_style), Paragraph("Periodo", cell_bold), Paragraph(f"{fe_inicio} al {fe_fin}", cell_style)],
        [Paragraph("Origen", cell_bold), Paragraph(origen, cell_style), Paragraph("Guía", cell_bold), Paragraph(guia_remision, cell_style)]
    ], colWidths=[100, 170, 100, 170])
    t_ficha.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")), ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F8FAFC")), ("PADDING", (0, 0), (-1, -1), 4)]))
    elements.extend([t_ficha, Spacer(1, 8), Paragraph("2. INGRESO DE MATERIAL", h2_style)])

    data_prendas = [[Paragraph("Ítem", cell_bold), Paragraph("Tipo Producto", cell_bold), Paragraph("Unid", cell_bold), Paragraph("Peso U.", cell_bold), Paragraph("Total kg", cell_bold)]]
    for i, it in enumerate(lista_items, 1): data_prendas.append([Paragraph(str(i), cell_style), Paragraph(it["descripcion"], cell_style), Paragraph(str(it["unidades"]), cell_style), Paragraph(f"{it['peso_unitario']:.2f}", cell_style), Paragraph(f"{it['peso_total']:.2f}", cell_style)])
    t_prendas = Table(data_prendas, colWidths=[40, 200, 100, 100, 100])
    t_prendas.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5D0FE")), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("PADDING", (0, 0), (-1, -1), 4)]))
    elements.extend([t_prendas, PageBreak(), Paragraph("3. SALIDA DE PRODUCTOS", h2_style)])

    data_prod = [[Paragraph("Producto", cell_bold), Paragraph("Cantidad", cell_bold)]]
    for pr in lista_productos: data_prod.append([Paragraph(pr["producto"], cell_style), Paragraph(str(pr["cantidad"]), cell_style)])
    t_prod = Table(data_prod, colWidths=[300, 150])
    t_prod.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5D0FE")), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("PADDING", (0, 0), (-1, -1), 4)]))
    elements.extend([t_prod, Spacer(1, 15), Paragraph("4. BALANCE DE MATERIAL Y EMISIONES", h2_style)])

    t_bal = Table([
        [Paragraph("Material recibido", cell_style), Paragraph(f"{kg_recibidos:.2f} kg", cell_style)],
        [Paragraph("Aprovechamiento Total", cell_style), Paragraph(f"{pct_aprovechamiento_total:.2f}%", cell_style)],
        [Paragraph("CO2 Neto Evitado", cell_bold), Paragraph(f"{co2_neto:.2f} kg", cell_bold)]
    ], colWidths=[300, 150])
    t_bal.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#F1F5F9")), ("PADDING", (0, 0), (-1, -1), 5)]))
    elements.extend([t_bal, Spacer(1, 15), Paragraph("5. IMPACTO SOCIAL", h2_style)])
    
    t_soc = Table([[Paragraph("Horas Totales Generadas", cell_bold), Paragraph(f"{total_horas_social:.2f} hrs", cell_style)], [Paragraph("Personas Beneficiadas", cell_bold), Paragraph(str(total_personas_social), cell_style)]], colWidths=[300, 150])
    t_soc.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("PADDING", (0, 0), (-1, -1), 5)]))
    elements.extend([t_soc, Spacer(1, 10), Paragraph("CONCLUSIÓN: Proyecto ejecutado con éxito garantizando trazabilidad y economía circular.", cell_style)])

    doc.build(elements, canvasmaker=ReporteCanvas)
    buffer.seek(0)
    return buffer

# --- ESTADOS DE SESIÓN ---
for key in ["autenticado", "pestaña_activa", "proyecto_editar", "documentos_descarga"]:
    if key not in st.session_state: st.session_state[key] = False if key == "autenticado" else ({} if key == "proyecto_editar" else ("➕     Nuevo Reporte PDF" if key == "pestaña_activa" else None))
if "catalogo_productos" not in st.session_state: st.session_state.catalogo_productos = list(PRODUCTOS_CATALOGO_BASE)
if "lista_personal_confeccion" not in st.session_state: st.session_state.lista_personal_confeccion = list(PERSONAL_CONFECCION_BASE)
if "pct_aprovechamiento_random" not in st.session_state: st.session_state.pct_aprovechamiento_random = round(random.uniform(0.88, 0.94), 4)
if "pct_transformado_ratio" not in st.session_state: st.session_state.pct_transformado_ratio = round(random.uniform(0.78, 0.83), 4)
if "uid_proyecto" not in st.session_state: st.session_state.uid_proyecto = str(random.randint(1000, 9999))

try: USUARIO_CORRECTO, PASSWORD_CORRECTO = st.secrets["auth"]["USUARIO"], st.secrets["auth"]["PASSWORD"]
except KeyError: st.error("⚠️ Faltan credenciales en `st.secrets`."); st.stop()

# --- LOGIN ---
if not st.session_state.autenticado:
    st.markdown('<div style="text-align: center; padding: 40px 10px;"><h1 style="color: #1E293B; font-weight: 800;">♻️ Pequeños Detalles</h1><p style="color: #64748B;">Gestión de Sostenibilidad</p></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2.container(border=True):
        u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar al Sistema", use_container_width=True, type="primary"):
            if u == USUARIO_CORRECTO and p == PASSWORD_CORRECTO: st.session_state.autenticado = True; st.rerun()
            else: st.error("⚠️ Credenciales incorrectas.")
else:
    proyectos_wip = cargar_proyectos(estado="EN_PROCESO")

    # --- BARRA LATERAL ---
    with st.sidebar:
        st.markdown("### ♻️ Pequeños Detalles")
        st.caption("Panel de Control Interno | 2026"); st.write("---")
        st.markdown('<p class="sidebar-section-title">Navegación</p>', unsafe_allow_html=True)

        if st.button("✨     Nuevo Reporte PDF", use_container_width=True, type="primary" if st.session_state.pestaña_activa == "➕     Nuevo Reporte PDF" else "secondary"):
            st.session_state.proyecto_editar = {}; st.session_state.documentos_descarga = None; st.session_state.pestaña_activa = "➕     Nuevo Reporte PDF"; st.session_state.uid_proyecto = str(random.randint(1000, 9999)); st.rerun()
        if st.button("⚡     Carga Rápida Histórica", use_container_width=True, type="primary" if st.session_state.pestaña_activa == "⚡     Carga Rápida Histórica" else "secondary"):
            st.session_state.documentos_descarga = None; st.session_state.pestaña_activa = "⚡     Carga Rápida Histórica"; st.rerun()

        st.markdown('<p class="sidebar-section-title">Borradores</p>', unsafe_allow_html=True)
        if proyectos_wip:
            for p in proyectos_wip:
                es_activo = st.session_state.proyecto_editar.get("id") == p.get("id")
                if st.button(f"📁 {p.get('cliente', 'Sin Nombre')}", key=f"side_{p.get('id')}", use_container_width=True, type="primary" if es_activo else "secondary"):
                    st.session_state.proyecto_editar = p; st.session_state.pestaña_activa = "➕     Nuevo Reporte PDF"; st.rerun()
            st.write(""); 
            if st.button("📋 Ver Lista en Proceso", use_container_width=True): st.session_state.pestaña_activa = "📋 Proyectos en Proceso"; st.rerun()
        else: st.caption("📭 No hay borradores")

        st.markdown('<p class="sidebar-section-title">Analítica</p>', unsafe_allow_html=True)
        if st.button("📊 Dashboard Dinámico", use_container_width=True, type="primary" if st.session_state.pestaña_activa == "📊 Dashboard 2026" else "secondary"):
            st.session_state.pestaña_activa = "📊 Dashboard 2026"; st.rerun()
        if st.button("🗂️ Historial Completo", use_container_width=True, type="primary" if st.session_state.pestaña_activa == "🗂️ Historial Completo" else "secondary"):
            st.session_state.pestaña_activa = "🗂️ Historial Completo"; st.rerun()

        st.write("---")
        if st.button("🚪 Cerrar Sesión", use_container_width=True): st.session_state.autenticado = False; st.rerun()

    st.markdown(f'<div class="hero-header"><h1>📄 Sistema de Gestión de Informes Técnicos</h1><p>Sección Activa: <b>{st.session_state.pestaña_activa.replace("2026","")}</b></p></div>', unsafe_allow_html=True)

    # --- VISTA: CARGA RÁPIDA E IMPORTACIÓN MASIVA ---
    if st.session_state.pestaña_activa == "⚡     Carga Rápida Histórica":
        st.subheader("⚡ Carga Rápida de Proyectos Históricos")
        st.caption("Registra proyectos individuales o sube tu tabla completa en segundos.")

        tab_manual, tab_masiva = st.tabs(["✍️ Carga Manual Individual", "📂 Carga Masiva Inteligente (CSV)"])

        with tab_manual:
            with st.container(border=True):
                st.markdown("##### 1. Datos Generales")
                rq1, rq2, rq3, rq4 = st.columns([2.5, 1.5, 1, 1.5])
                fast_cliente = rq1.text_input("Cliente / Razón Social *")
                fast_mes = rq2.selectbox("Mes del pedido *", MESES_ORDEN, index=datetime.date.today().month - 1)
                fast_anio = rq3.selectbox("Año", [2024, 2025, 2026, 2027], index=2)
                fast_tipo = rq4.selectbox("Tipo de Proyecto", ["UPCYCLING", "PRODUCCIÓN DESDE CERO", "CAMBIO DE LOGO", "MIXTO", "BANNER"])
                
                mes_num = MESES_ORDEN.index(fast_mes) + 1
                fast_codigo = f"HIST_{fast_cliente.strip()[:8]}_{mes_num:02d}{fast_anio}-{random.randint(1000, 9999)}"

            with st.container(border=True):
                st.markdown("##### 2. Métricas para el Dashboard")
                rm1, rm2, rm3, rm4, rm5, rm6 = st.columns(6)
                fast_peso = rm1.number_input("Kg Recibidos *", min_value=0.0, step=0.1)
                fast_unid_recibidas = rm2.number_input("Unid Recibidas", min_value=0, step=1)
                fast_unid = rm3.number_input("Productos *", min_value=0, step=1)
                fast_co2 = rm4.number_input("CO₂ Evitado *", min_value=0.0, step=0.1)
                fast_horas = rm5.number_input("Horas *", min_value=0.0, step=0.5)
                fast_personas = rm6.number_input("Participantes *", min_value=0, step=1)

            st.write("")
            if st.button("🚀 Guardar Proyecto Histórico", type="primary", use_container_width=True):
                if not fast_cliente.strip(): st.error("El campo **Cliente** es obligatorio.")
                else:
                    with st.spinner("Registrando..."):
                        supabase.table("proyectos").upsert({
                            "codigo": fast_codigo, "cliente": fast_cliente, "ruc": "00000000000", "tipo_proyecto": fast_tipo,
                            "responsable": "Histórico", "fecha": f"01/{mes_num:02d}/{fast_anio} - 28/{mes_num:02d}/{fast_anio}", "estado": "COMPLETADO",
                            "peso_recibido": fast_peso, "peso_transformado": fast_peso, "aprovechamiento": 100.0, "co2_neto": fast_co2,
                            "horas_totales": fast_horas, "productos_unids": fast_unid, "punto_origen": "Histórico",
                            "datos_completos": {"participantes": fast_personas, "unidades_recibidas": fast_unid_recibidas}
                        }).execute()
                    st.success("✅ ¡Registrado con éxito!"); st.rerun()

        with tab_masiva:
            with st.container(border=True):
                st.markdown("##### 📂 Carga Masiva con Detector Automático")
                st.markdown("Sube tu archivo **CSV** desde Excel. El sistema corregirá codificaciones (`latin1`, `utf-8`) y separadores (`;`, `,`) automáticamente.")
                archivo_cargado = st.file_uploader("Selecciona tu archivo CSV", type=["csv", "xlsx"])
                anio_masivo = st.selectbox("Año aplicable", [2024, 2025, 2026, 2027], index=2)

                if archivo_cargado:
                    df_subido = None
                    if archivo_cargado.name.endswith('.csv'):
                        try: df_subido = pd.read_csv(archivo_cargado, encoding='utf-8', sep=None, engine='python')
                        except: 
                            archivo_cargado.seek(0)
                            try: df_subido = pd.read_csv(archivo_cargado, encoding='latin1', sep=None, engine='python')
                            except Exception as e: st.error(f"Error leyendo CSV: {e}")
                    else:
                        try: df_subido = pd.read_excel(archivo_cargado)
                        except: st.error("⚠️ Para archivos Excel necesitas 'openpyxl'. Guarda tu archivo como CSV y súbelo.")

                    if df_subido is not None:
                        st.write("Vista previa inteligente:", df_subido.head(3))
                        if st.button("🚀 Importar Todos los Proyectos", type="primary", use_container_width=True):
                            with st.spinner("Importando masivamente..."):
                                m_map = {m.lower(): i for i, m in MESES_ESPANOL.items()}
                                cols = df_subido.columns
                                cli_col = next((c for c in cols if "cliente" in str(c).lower() or "razón" in str(c).lower()), "Cliente")
                                mes_col = next((c for c in cols if "mes" in str(c).lower()), "Mes")
                                unid_col = next((c for c in cols if "unid" in str(c).lower()), "Unidades recibidas")
                                kg_col = next((c for c in cols if "kg" in str(c).lower() or "peso" in str(c).lower()), "Kg recibidos")
                                co2_col = next((c for c in cols if "co2" in str(c).lower() or "evit" in str(c).lower()), "CO2 evitado")
                                hr_col = next((c for c in cols if "hora" in str(c).lower()), "Horas")
                                prod_col = next((c for c in cols if "prod" in str(c).lower()), "Productos")
                                part_col = next((c for c in cols if "partic" in str(c).lower()), "Participantes")
                                tipo_col = next((c for c in cols if "tipo" in str(c).lower()), "TIPO DE PROYECTO")

                                def s_float(v): return float(v) if pd.notna(v) else 0.0
                                def s_int(v): return int(float(v)) if pd.notna(v) else 0

                                exito = 0
                                for idx, r in df_subido.iterrows():
                                    cli = str(r.get(cli_col)).strip()
                                    if pd.isna(r.get(cli_col)) or cli.upper() == "NAN" or not cli: continue
                                    m_n = m_map.get(str(r.get(mes_col, "enero")).strip().lower(), 1)
                                    
                                    supabase.table("proyectos").upsert({
                                        "codigo": f"MAS_{cli[:6].replace(' ','')}_{m_n:02d}{anio_masivo}-{idx}-{random.randint(10000,99999)}",
                                        "cliente": cli, "ruc": "00000000000", "tipo_proyecto": str(r.get(tipo_col, "UPCYCLING")).upper(),
                                        "responsable": "Histórico", "fecha": f"01/{m_n:02d}/{anio_masivo} - 28/{m_n:02d}/{anio_masivo}", "estado": "COMPLETADO",
                                        "peso_recibido": s_float(r.get(kg_col)), "peso_transformado": s_float(r.get(kg_col)),
                                        "aprovechamiento": 100.0, "co2_neto": s_float(r.get(co2_col)),
                                        "horas_totales": s_float(r.get(hr_col)), "productos_unids": s_int(r.get(prod_col)),
                                        "punto_origen": "Masivo", "datos_completos": {"participantes": s_int(r.get(part_col)), "unidades_recibidas": s_int(r.get(unid_col))}
                                    }).execute()
                                    exito += 1
                                st.success(f"🎉 ¡{exito} proyectos importados al Dashboard!"); st.balloons()

    # --- VISTA: PROYECTOS EN PROCESO ---
    elif st.session_state.pestaña_activa == "📋 Proyectos en Proceso":
        st.subheader("📋 Lista de Proyectos en Proceso")
        borradores = [p for p in cargar_proyectos() if p.get("estado") == "EN_PROCESO"]
        if borradores:
            for b in borradores:
                with st.container(border=True):
                    bc1, bc2, bc3 = st.columns([3, 2, 2])
                    bc1.markdown(f"**Cliente:** {b.get('cliente', 'Sin Nombre')}\n\n`{b.get('codigo', '')}`")
                    bc2.markdown(f"**Tipo:** {b.get('tipo_proyecto', 'Upcycling')}\n\n{b.get('fecha', '')}")
                    if bc3.button("✏️ Retomar Edición", key=f"ret_{b.get('id')}", use_container_width=True, type="primary"):
                        st.session_state.proyecto_editar = b; st.session_state.pestaña_activa = "➕     Nuevo Reporte PDF"; st.rerun()
        else: st.info("📭 No hay borradores pendientes.")

    # --- VISTA: DASHBOARD SÚPER DINÁMICO (PLOTLY) ---
    elif st.session_state.pestaña_activa == "📊 Dashboard 2026":
        st.subheader("📊 Panel de Control y Analítica Avanzada")
        st.caption("Filtra, analiza y visualiza el impacto histórico generado por tus proyectos.")

        completados = [p for p in cargar_proyectos() if p.get("estado") == "COMPLETADO"]
        
        if not completados:
            st.info("📭 Aún no hay proyectos completados para mostrar en las métricas.")
        else:
            # 1. CONSTRUIR DATAFRAME BASE
            tabla_data = []
            for p in completados:
                dc = p.get("datos_completos") or {}
                unid_rec = sum([int(it.get("unidades", 0)) for it in dc.get("items", [])]) if "items" in dc else int(dc.get("unidades_recibidas", 0))
                partic = (6 + len(set([c.get("persona", "").strip() for c in dc.get("confeccion", []) if c.get("persona", "").strip()]))) if "items" in dc else int(dc.get("participantes", 0))
                
                mes_txt = "N/D"
                if p.get("fecha") and "-" in p.get("fecha"):
                    try: mes_txt = MESES_ESPANOL.get(int(p.get("fecha").split("-")[1].split("/")[1]), "N/D").capitalize()
                    except: pass

                tabla_data.append({
                    "Cliente": p.get("cliente", "Sin Nombre"), "Mes": mes_txt, "Unidades recibidas": unid_rec,
                    "Kg recibidos": float(p.get("peso_recibido") or 0), "CO₂ evitado": float(p.get("co2_neto") or 0),
                    "Horas": float(p.get("horas_totales") or 0), "Productos": int(p.get("productos_unids") or 0),
                    "Participantes": partic, "TIPO DE PROYECTO": p.get("tipo_proyecto", "UPCYCLING")
                })
            df = pd.DataFrame(tabla_data)

            # 2. FILTROS DINÁMICOS SUPERIORES
            st.markdown("### 🎛️ Filtros de Análisis")
            f1, f2, f3 = st.columns(3)
            
            # Forzar el orden correcto de los meses en el filtro
            meses_presentes = [m for m in MESES_ORDEN if m in df["Mes"].unique()]
            cli_disp = ["Todos"] + sorted([str(x) for x in df["Cliente"].unique() if x != "N/D"])
            tipo_disp = ["Todos"] + sorted([str(x) for x in df["TIPO DE PROYECTO"].unique() if x != "N/D"])

            sel_mes = f1.selectbox("📅 Filtrar por Mes", ["Todos"] + meses_presentes)
            sel_cli = f2.selectbox("🏢 Filtrar por Cliente", cli_disp)
            sel_tipo = f3.selectbox("♻️ Filtrar por Tipo de Servicio", tipo_disp)

            # APLICAR FILTROS
            df_fil = df.copy()
            if sel_mes != "Todos": df_fil = df_fil[df_fil["Mes"] == sel_mes]
            if sel_cli != "Todos": df_fil = df_fil[df_fil["Cliente"] == sel_cli]
            if sel_tipo != "Todos": df_fil = df_fil[df_fil["TIPO DE PROYECTO"] == sel_tipo]

            # 3. TARJETAS DE IMPACTO (Dinámicas)
            st.markdown("### 🏆 Impacto Acumulado")
            dm1, dm2, dm3, dm4, dm5 = st.columns(5)
            dm1.metric("📦 Unid. Recibidas", f"{int(df_fil['Unidades recibidas'].sum())} unid")
            dm2.metric("⚖️ Peso Procesado", f"{df_fil['Kg recibidos'].sum():.2f} kg")
            dm3.metric("🌍 CO₂e Evitado", f"{df_fil['CO₂ evitado'].sum():.2f} kg")
            dm4.metric("⏳ Horas Trabajo", f"{df_fil['Horas'].sum():.2f} hrs")
            dm5.metric("🛍️ Productos", f"{int(df_fil['Productos'].sum())} unid")

            st.write("---")

            # 4. GRÁFICOS INTERACTIVOS (Plotly Express)
            cg1, cg2 = st.columns([2, 1.2])
            with cg1:
                st.markdown("##### 📈 Evolución de CO₂ Evitado Mensual")
                if not df_fil.empty:
                    df_mes_graf = df_fil.groupby("Mes")["CO₂ evitado"].sum().reset_index()
                    # Ordenar meses cronológicamente
                    df_mes_graf["Mes_cat"] = pd.Categorical(df_mes_graf["Mes"], categories=MESES_ORDEN, ordered=True)
                    df_mes_graf = df_mes_graf.sort_values("Mes_cat")
                    
                    fig1 = px.bar(df_mes_graf, x="Mes", y="CO₂ evitado", text_auto='.0f', color_discrete_sequence=["#2563EB"])
                    fig1.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                    fig1.update_layout(margin=dict(l=0, r=0, t=30, b=0), yaxis_title="Kg CO₂e", xaxis_title="")
                    st.plotly_chart(fig1, use_container_width=True)
                else: st.caption("No hay datos para graficar con estos filtros.")

            with cg2:
                st.markdown("##### 🍩 Tipos de Servicio (por Kg procesados)")
                if not df_fil.empty:
                    df_tipo = df_fil.groupby("TIPO DE PROYECTO")["Kg recibidos"].sum().reset_index()
                    fig2 = px.pie(df_tipo, values="Kg recibidos", names="TIPO DE PROYECTO", hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig2.update_traces(textposition='inside', textinfo='percent')
                    fig2.update_layout(margin=dict(l=0, r=0, t=30, b=0), showlegend=True, legend=dict(orientation="h", y=-0.2))
                    st.plotly_chart(fig2, use_container_width=True)
                else: st.caption("No hay datos para graficar con estos filtros.")

            # 5. RANKING Y DATA
            cr1, cr2 = st.columns([1.5, 2.5])
            with cr1:
                st.markdown("##### 🥇 Top 5 Clientes (CO₂e)")
                if not df_fil.empty:
                    top5 = df_fil.groupby("Cliente")["CO₂ evitado"].sum().reset_index().sort_values(by="CO₂ evitado", ascending=False).head(5)
                    top5["Medalla"] = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][:len(top5)]
                    top5 = top5[["Medalla", "Cliente", "CO₂ evitado"]]
                    st.dataframe(top5, use_container_width=True, hide_index=True)

            with cr2:
                st.markdown("##### 📋 Detalle de Proyectos (Filtrado)")
                max_k = float(df_fil["Kg recibidos"].max()) if not df_fil.empty else 100.0
                max_c = float(df_fil["CO₂ evitado"].max()) if not df_fil.empty else 100.0
                st.dataframe(
                    df_fil, use_container_width=True, hide_index=True, height=230,
                    column_config={
                        "Kg recibidos": st.column_config.ProgressColumn("Kg Recibidos", min_value=0, max_value=max_k, format="%.1f"),
                        "CO₂ evitado": st.column_config.ProgressColumn("CO₂ Evitado", min_value=0, max_value=max_c, format="%.1f")
                    }
                )

    # --- VISTA: HISTORIAL COMPLETO ---
    elif st.session_state.pestaña_activa == "🗂️ Historial Completo":
        st.subheader("🗂️ Historial Completo de Proyectos")
        st.caption("Gestiona todos tus reportes. Selecciona casillas para borrado masivo.")

        proyectos_lista = cargar_proyectos()
        if proyectos_lista:
            sel_borrar = [p for p in proyectos_lista if st.session_state.get(f"bulk_del_{p.get('id', p.get('codigo'))}", False)]
            c_top1, c_top2 = st.columns([4, 2])
            if c_top2.button(f"🗑️ Eliminar Seleccionados ({len(sel_borrar)})", disabled=not sel_borrar, type="primary", use_container_width=True):
                modal_confirmar_eliminacion_masiva(sel_borrar)
            st.write("---")

            for p in proyectos_lista:
                with st.container(border=True):
                    c_chk, hc1, hc2, hc3, hc4, hc5, hc6 = st.columns([0.4, 2.5, 1.6, 1.6, 1.8, 1.8, 0.7])
                    c_chk.write(""); c_chk.checkbox(" ", key=f"bulk_del_{p.get('id', p.get('codigo'))}", label_visibility="collapsed")
                    
                    hc1.markdown(f"**{p.get('cliente', 'Sin Nombre')}**\n\n`{p.get('codigo', '')}`")
                    hc2.markdown(f"**{p.get('estado', 'N/D')}**\n\n{p.get('tipo_proyecto', 'Upcycling')}")
                    hc3.markdown(f"`{float(p.get('peso_recibido', 0) or 0):.2f} kg`\n\n{p.get('fecha', 'N/D')}")

                    if p.get("pdf_url"): hc4.link_button("📄 Informe PDF", p.get("pdf_url"), use_container_width=True)
                    else: hc4.caption("📄 Sin Informe")

                    if p.get("constancia_url"): hc5.link_button("📜 Constancia PDF", p.get("constancia_url"), use_container_width=True)
                    else: hc5.caption("📜 Sin Constancia")

                    if hc6.button("🗑️", key=f"hist_del_{p.get('id', p.get('codigo'))}", use_container_width=True): modal_confirmar_eliminacion(p)
        else: st.info("📭 No hay proyectos registrados en el historial.")

    # --- VISTA: NUEVO REPORTE PDF ---
    elif st.session_state.pestaña_activa == "➕     Nuevo Reporte PDF":
        p_edit = st.session_state.proyecto_editar
        if st.session_state.get("_loaded_project_id") != (p_edit.get("id") or p_edit.get("codigo") or "__nuevo__"):
            st.session_state._loaded_project_id = p_edit.get("id") or p_edit.get("codigo") or "__nuevo__"
            dc_init = p_edit.get("datos_completos") or p_edit.get("datos_formulario") or {}
            st.session_state.num_items, st.session_state.num_prods, st.session_state.num_anexos = dc_init.get("num_items", max(2, len(dc_init.get("items", [])))), dc_init.get("num_prods", max(2, len(dc_init.get("productos", [])))), dc_init.get("num_anexos", max(1, len(dc_init.get("anexos", []))))
            for k_np, v_np in dc_init.get("confeccion_num_pers", {}).items(): st.session_state[k_np] = v_np
            [st.session_state.pop(k) for k in list(st.session_state.keys()) if any(k.startswith(px) for px in ["desc_", "unid_", "tot_input_", "peso_u_", "foto_", "prod_sel_", "prod_cant_", "prod_nuevo_txt_", "prod_dis_", "prod_foto_", "tr_etapa_", "tr_fecha_", "tr_resp_", "chk_edit_", "chk_no_aplica_", "tr_peso_", "tr_tipo_", "tr_foto_", "soc_rol_", "soc_pers_sel_", "soc_pers_txt_custom_", "soc_cant_", "soc_tunit_", "soc_tunit_calc_", "soc_htot_", "anx_foto_", "anx_nota_", "ops_chk_", "ops_nom_", "ops_dias_", "ops_hdia_", "ops_tot_", "transporte_distrito_origen", "dist_km_manual", "dist_km_auto_", "chk_edit_balance", "bm_mat_transf_", "bm_retazos_", "bm_perdida_", "responsables_proyecto", "nuevo_responsable_proyecto"])]
        
        dc = p_edit.get("datos_completos") or p_edit.get("datos_formulario") or {}

        if p_edit:
            st.warning(f"✏️ **Modo Edición:** {p_edit.get('cliente', '')} (`{p_edit.get('codigo', '')}`)")
            cd, ce = st.columns(2)
            if cd.button("❌ Descartar", use_container_width=True): st.session_state.proyecto_editar = {}; st.rerun()
            if ce.button("🗑️ Eliminar", use_container_width=True): modal_confirmar_eliminacion(p_edit)

        with st.container(border=True):
            st.subheader("1. Ficha General del Proyecto")
            f_raw = p_edit.get("fecha", " - ").split(" - ")
            try: f_ini, f_fin = datetime.datetime.strptime(f_raw[0].strip(), "%d/%m/%Y").date(), datetime.datetime.strptime(f_raw[1].strip(), "%d/%m/%Y").date()
            except: f_ini, f_fin = datetime.date.today(), datetime.date.today()

            c1, c2, c5, c6 = st.columns(4)
            cliente = c1.text_input("Cliente *", value=p_edit.get("cliente", ""))
            ruc = c2.text_input("RUC *", value=p_edit.get("ruc", ""), max_chars=11)
            fe_inicio_dt = c5.date_input("Inicio *", value=f_ini, format="DD/MM/YYYY")
            fe_fin_dt = c6.date_input("Término *", value=f_fin, format="DD/MM/YYYY")

            codigo_proy = p_edit.get("codigo") or f"{cliente.strip() or 'EMPRESA'}_{fe_inicio_dt.strftime('%d%m%Y')}-{fe_fin_dt.strftime('%d%m%Y')}-{st.session_state.uid_proyecto}"
            st.info(f"🆔 **Código:** `{codigo_proy}`")

            c4, c7, c8, c9 = st.columns(4)
            opc_t = ["Upcycling", "Producción desde cero", "Cambio de logo", "Mixto", "Banner"]
            proyecto_nom = c4.selectbox("Tipo *", opc_t, index=opc_t.index(p_edit.get("tipo_proyecto", "Upcycling")) if p_edit.get("tipo_proyecto", "Upcycling") in opc_t else 0)

            resp_g = p_edit.get("responsables", [x.strip() for x in str(p_edit.get("responsable", "")).split(",") if x.strip()]) if not p_edit.get("responsables") else p_edit["responsables"]
            if not resp_g: resp_g = dc.get("responsables_seleccionados", [])
            opc_r = list(dict.fromkeys(["Evelyn Prada Vizarreta", "Gabriel Manrique Hurtado"] + (resp_g if isinstance(resp_g, list) else [])))
            
            resp_sel = c7.multiselect("Responsable *", opc_r, default=[r for r in resp_g if r in opc_r])
            n_resp = c7.text_input("➕ Agregar otro", key="n_resp")
            if n_resp.strip() and n_resp.strip() not in resp_sel: resp_sel.append(n_resp.strip())
            
            responsable = ", ".join(resp_sel)
            area = c8.text_input("Área", value="Sostenibilidad", disabled=True)
            guia_remision = c9.text_input("Guía Remisión", value=p_edit.get("guia", "") or dc.get("guia_remision", ""))
            origen = st.text_input("Punto Origen *", value=p_edit.get("origen", p_edit.get("punto_origen", dc.get("origen", ""))))
            destino = "Jr. Las Caléndulas 610, Las Flores, SJL."

        st.write("")

        with st.container(border=True):
            st.subheader("2. Ingreso de Material")
            cb1, cb2, _ = st.columns([1, 1, 4])
            if cb1.button("➕ Agregar Ítem"): st.session_state.num_items += 1; st.rerun()
            if cb2.button("➖ Quitar Ítem") and st.session_state.num_items > 1: st.session_state.num_items -= 1; st.rerun()

            lista_items, peso_tot, co2_tot, unid_tot, opc_p, s_it = [], 0.0, 0.0, 0, sorted(list(FACTORES_CO2.keys())), dc.get("items", [])
            for i in range(st.session_state.num_items):
                cd, cu, cp, ct, cf = st.columns([3, 1.5, 1.5, 1.5, 3])
                ip = s_it[i] if i < len(s_it) else {}
                desc = cd.selectbox(f"Prenda {i+1} *", opc_p, index=opc_p.index(ip.get("descripcion", opc_p[0])) if ip.get("descripcion") in opc_p else 0, key=f"d_{i}")
                unid = cu.number_input("Unid *", min_value=0, value=int(ip.get("unidades", 0)), key=f"u_{i}")
                p_t = cp.number_input("Kg Totales *", min_value=0.0, value=float(ip.get("peso_total", 0.0)), step=0.05, key=f"pt_{i}")
                ct.text_input("Kg/U", value=f"{p_t/unid if unid>0 else 0:.2f}", disabled=True, key=f"pu_{i}")
                fot = cf.file_uploader("Foto", type=["jpg", "png"], key=f"f_{i}")
                if fot: cf.image(fot, width=80)
                elif ip.get("foto_url"): cf.image(ip.get("foto_url"), width=80)
                
                co2_i = p_t * FACTORES_CO2.get(desc, 6.575)
                peso_tot += p_t; co2_tot += co2_i; unid_tot += unid
                lista_items.append({"descripcion": desc, "unidades": unid, "peso_unitario": p_t/unid if unid>0 else 0, "peso_total": p_t, "foto_up": fot, "foto_url": ip.get("foto_url", ""), "co2_evitado": co2_i})

            st.info(f"⚖️ **Recibido:** {peso_tot:.2f} kg | **CO₂ Evitado:** {co2_tot:.2f} kg")

        st.write("")

        with st.container(border=True):
            st.subheader("3. Trazabilidad")
            lista_trazabilidad, p_lav, p_cor, s_tr = [], 0.0, 0.0, dc.get("trazabilidad", [])
            for i, f in enumerate([{"e": "Clasificación", "r": "Evelyn Prada", "t": "Interno"}, {"e": "Lavado", "r": "Lavandería", "t": "Externo"}, {"e": "Corte", "r": "Taller", "t": "Pesaje"}, {"e": "Confección", "r": "Taller", "t": "Recepción"}]):
                ce, cf, cr, cx, cp, ct, cimg = st.columns([1.5, 1.5, 2, 1, 1.2, 1.6, 2])
                tp = s_tr[i] if i < len(s_tr) else {}
                try: fd = datetime.datetime.strptime(tp.get("fecha"), "%d/%m/%Y").date() if tp.get("fecha") else fe_inicio_dt
                except: fd = fe_inicio_dt
                
                na = cx.checkbox("N/A", value=bool(tp.get("no_aplica")), key=f"na_{i}") if f["e"] == "Lavado" else False
                ed = cx.checkbox("Edit", value=bool(tp.get("editado")), key=f"ed_{i}") if f["e"] != "Lavado" else not na
                
                ce.text_input("Etapa", value=f["e"], disabled=True, key=f"te_{i}")
                fv = cf.date_input("Fecha", value=fd, disabled=na or f["e"]=="Clasificación", key=f"tf_{i}")
                rv = cr.text_input("Resp.", value="N/A" if na else tp.get("responsable", f["r"]), disabled=not ed, key=f"tr_{i}")
                pv = cp.number_input("Kg", value=0.0 if na else float(tp.get("peso", peso_tot if f["e"]=="Clasificación" else (peso_tot*st.session_state.pct_aprovechamiento_random))), disabled=not ed, key=f"tp_{i}")
                tv = ct.text_input("Tipo", value="N/A" if na else tp.get("tipo_registro", f["t"]), disabled=True, key=f"tt_{i}")
                
                if f["e"] == "Lavado": p_lav = 0.0 if na else pv
                if f["e"] == "Corte": p_cor = pv
                
                img = cimg.file_uploader("Evid.", type=["jpg", "png"], key=f"ti_{i}") if not na else None
                if img: cimg.image(img, width=70)
                elif not na and tp.get("foto_url"): cimg.image(tp.get("foto_url"), width=70)
                
                lista_trazabilidad.append({"etapa": f["e"], "fecha": fv.strftime("%d/%m/%Y"), "responsable": rv, "peso": pv, "tipo_registro": tv, "no_aplica": na, "foto_up": img, "foto_url": "" if na else tp.get("foto_url", "")})

        st.write("")

        with st.container(border=True):
            st.subheader("4. Productos Salientes")
            with st.expander("⚙️ Catálogo"):
                t1, t2, t3 = st.tabs(["➕", "✏️", "🗑️"])
                with t1:
                    n = st.text_input("Nuevo:", key="np")
                    if st.button("Guardar", key="bp1") and n.strip() not in st.session_state.catalogo_productos: st.session_state.catalogo_productos.insert(-1, n.strip()); st.rerun()
                with t2:
                    m = st.selectbox("Modificar:", [x for x in st.session_state.catalogo_productos if "Otro" not in x], key="mp")
                    nn = st.text_input("Corrección:", value=m, key="nnp")
                    if st.button("Actualizar", key="bp2") and nn.strip(): st.session_state.catalogo_productos[st.session_state.catalogo_productos.index(m)] = nn.strip(); st.rerun()
                with t3:
                    d = st.selectbox("Borrar:", [x for x in st.session_state.catalogo_productos if "Otro" not in x], key="dp")
                    if st.button("Eliminar", key="bp3"): st.session_state.catalogo_productos.remove(d); st.rerun()

            c1, c2, _ = st.columns([1,1,4])
            if c1.button("➕ Prod"): st.session_state.num_prods += 1; st.rerun()
            if c2.button("➖ Prod") and st.session_state.num_prods > 1: st.session_state.num_prods -= 1; st.rerun()

            lista_productos, t_pu, s_pr = [], 0, dc.get("productos", [])
            for i in range(st.session_state.num_prods):
                cp1, cp2, cp3, cp4 = st.columns([3, 2.5, 1.5, 3])
                pr = s_pr[i] if i < len(s_pr) else {}
                nm = pr.get("producto", "")
                if nm and nm not in st.session_state.catalogo_productos: st.session_state.catalogo_productos.insert(-1, nm)
                
                sel = cp1.selectbox(f"Base {i+1}", st.session_state.catalogo_productos, index=st.session_state.catalogo_productos.index(nm) if nm in st.session_state.catalogo_productos else 0, key=f"ps_{i}")
                fnm = cp2.text_input("Nuevo", key=f"pn_{i}") if "Otro" in sel else sel
                if "Otro" in sel and fnm.strip() and fnm.strip() not in st.session_state.catalogo_productos: st.session_state.catalogo_productos.insert(-1, fnm.strip())
                
                c_u = cp3.number_input("Unid", min_value=0, value=int(pr.get("cantidad", 0)), key=f"pc_{i}")
                pf = cp4.file_uploader("Foto", type=["jpg", "png"], key=f"pf_{i}")
                if pf: cp4.image(pf, width=80)
                elif pr.get("foto_url"): cp4.image(pr.get("foto_url"), width=80)
                
                t_pu += c_u
                lista_productos.append({"producto": fnm, "cantidad": c_u, "foto_up": pf, "foto_url": pr.get("foto_url", "")})
            st.success(f"🧮 **Productos:** {t_pu} unidades")

        st.write("")

        with st.container(border=True):
            st.subheader("5. Balance de Material")
            ed_b = st.checkbox("✏️ Editar manual", value=dc.get("balance", {}).get("editar_manual", False))
            c1, c2, c3 = st.columns(3)
            
            mtr = c1.number_input("Transformado (kg)", value=float(dc.get("balance", {}).get("mat_transformado", peso_tot * 0.8)), disabled=not ed_b)
            mre = c2.number_input("Retazos (kg)", value=float(dc.get("balance", {}).get("retazos_aprovechables", peso_tot * 0.1)), disabled=not ed_b)
            mpe = c3.number_input("Pérdida (kg)", value=float(dc.get("balance", {}).get("perdida_no_aprovechable", peso_tot * 0.1)), disabled=not ed_b)
            
            tot_p = mtr + mre + mpe
            p_apr = ((mtr + mre)/peso_tot)*100 if peso_tot>0 else 0
            p_per = (mpe/peso_tot)*100 if peso_tot>0 else 0
            
            i1, i2, i3 = st.columns(3)
            i1.metric("Procesado", f"{tot_p:.2f} kg"); i2.metric("% Aprovech", f"{p_apr:.2f}%"); i3.metric("% Pérdida", f"{p_per:.2f}%")

        st.write("")

        with st.container(border=True):
            st.subheader("6. Emisiones del Proceso")
            c1, c2, c3, c4 = st.columns([2.5, 1.2, 1.8, 1.5])
            do = c1.selectbox("Origen", list(DISTANCIAS_LIMA_SJL.keys()), index=list(DISTANCIAS_LIMA_SJL.keys()).index(dc.get("transporte", {}).get("distrito", "San Juan de Lurigancho (Local)")))
            dk = c2.number_input("Km", value=float(dc.get("transporte", {}).get("distancia", DISTANCIAS_LIMA_SJL.get(do, 0))))
            tv = c3.selectbox("Vehículo", list(FACTORES_TRANSPORTE.keys()))
            tr = c4.selectbox("Viaje", ["Ida y Vuelta (2)", "Ida sola (1)"])
            
            emi_t = dk * (2 if "2" in tr else 1) * FACTORES_TRANSPORTE[tv]["consumo"] * FACTORES_TRANSPORTE[tv]["factor"]
            cb1, cb2 = st.columns(2)
            c_bord = cb1.number_input("Unid. Bordadas", min_value=0, value=int(dc.get("bordado", {}).get("cantidad", 0)))
            t_bord = cb2.selectbox("Tipo Bordado", list(FACTORES_BORDADO.keys()))
            emi_b = c_bord * FACTORES_BORDADO[t_bord]
            
            emi_tot = emi_t + (p_lav * 0.3) + (p_cor * 0.05) + emi_b
            co2_neto = co2_tot - emi_tot
            st.warning(f"🌍 **Emisiones:** {emi_tot:.2f} kg CO₂e | **Neto Evitado:** {co2_neto:.2f} kg CO₂e")

        st.write("")

        with st.container(border=True):
            st.subheader("7. Horas e Impacto Social")
            lista_op, t_h_op = [], 0.0
            for i, o in enumerate(PERSONAL_FIJO_OPERACIONES):
                c1, c2, c3, c4, c5 = st.columns([1.5, 2.5, 1, 1, 1])
                c1.markdown(f"**{o['rol']}**")
                c2.markdown(o['nombre'])
                d = c3.number_input("Días", value=1, key=f"od_{i}")
                h = c4.number_input("Hrs/D", value=4.0, key=f"oh_{i}")
                c5.text_input("Tot", value=f"{d*h}", disabled=True, key=f"ot_{i}")
                t_h_op += d*h
                lista_op.append({"rol": o["rol"], "nombre": o["nombre"], "dias": d, "horas_dia": h, "horas_totales": d*h})
                
            st.write("---")
            lista_conf, t_h_cf, pers_u = [], 0.0, set()
            for i, pr in enumerate(lista_productos):
                st.markdown(f"📦 **{pr['producto']}** (Unid: {pr['cantidad']})")
                c1, c2, c3, c4, c5 = st.columns([1.8, 3, 1.4, 1.8, 1.8])
                c1.markdown("**Rol**"); c2.markdown("**Persona**"); c3.markdown("**Unid**"); c4.markdown("**Hrs/U**"); c5.markdown("**Total**")
                
                sel_p = c2.selectbox("Resp.", st.session_state.lista_personal_confeccion, key=f"cr_{i}")
                unid = c3.number_input("U.", max_value=pr['cantidad'], value=pr['cantidad'], key=f"cu_{i}")
                t_u = c4.number_input("H.", value=estimar_tiempo_unidad(pr['producto']), step=0.05, key=f"ch_{i}")
                c5.text_input("T.", value=f"{unid*t_u:.2f}", disabled=True, key=f"ct_{i}")
                t_h_cf += unid*t_u
                pers_u.add(sel_p)
                lista_conf.append({"producto": pr["producto"], "rol": "Confección", "persona": sel_p, "cantidad": unid, "tiempo_unitario": t_u, "horas_totales": unid*t_u})

            st.info(f"🧑‍🤝‍🧑 **Impacto:** {t_h_op + t_h_cf:.2f} hrs | {len(PERSONAL_FIJO_OPERACIONES) + len(pers_u)} personas.")

        st.write("")

        with st.container(border=True):
            st.subheader("8. Anexos Fotográficos")
            c1, c2, _ = st.columns([1,1,4])
            if c1.button("➕ Anexo"): st.session_state.num_anexos += 1; st.rerun()
            if c2.button("➖ Anexo") and st.session_state.num_anexos > 0: st.session_state.num_anexos -= 1; st.rerun()
            lista_anexos, sa = [], dc.get("anexos", [])
            for i in range(st.session_state.num_anexos):
                c_f, c_n = st.columns([1.5, 3])
                f = c_f.file_uploader("Foto", type=["jpg", "png"], key=f"af_{i}")
                url = sa[i].get("foto_url", "") if i < len(sa) else ""
                if f: c_f.image(f, width=100)
                elif url: c_f.image(url, width=100)
                n = c_n.text_area("Nota", value=sa[i].get("nota", "") if i<len(sa) else "", key=f"an_{i}")
                lista_anexos.append({"foto_up": f, "foto_url": url, "nota": n})

        st.write("")

        with st.container(border=True):
            col_b1, col_b2 = st.columns([2, 1])
            if col_b2.button("💾 Guardar Borrador", use_container_width=True):
                with st.spinner("Guardando..."):
                    ts = int(datetime.datetime.now().timestamp())
                    det = {
                        "items": [{"descripcion": i["descripcion"], "unidades": i["unidades"], "peso_unitario": i["peso_unitario"], "peso_total": i["peso_total"], "foto_url": subir_imagen_supabase(f"fotos/{codigo_proy}/i_{x}_{ts}.jpg", i["foto_up"].read()) if i["foto_up"] else i["foto_url"]} for x, i in enumerate(lista_items)],
                        "trazabilidad": [{"etapa": t["etapa"], "fecha": t["fecha"], "responsable": t["responsable"], "peso": t["peso"], "tipo_registro": t["tipo_registro"], "no_aplica": t["no_aplica"], "foto_url": subir_imagen_supabase(f"fotos/{codigo_proy}/t_{x}_{ts}.jpg", t["foto_up"].read()) if t["foto_up"] else t["foto_url"]} for x, t in enumerate(lista_trazabilidad)],
                        "productos": [{"producto": p["producto"], "cantidad": p["cantidad"], "foto_url": subir_imagen_supabase(f"fotos/{codigo_proy}/p_{x}_{ts}.jpg", p["foto_up"].read()) if p["foto_up"] else p["foto_url"]} for x, p in enumerate(lista_productos)],
                        "operaciones": lista_op, "confeccion": lista_conf, "balance": {"editar_manual": ed_b, "mat_transformado": mtr, "retazos_aprovechables": mre, "perdida_no_aprovechable": mpe},
                        "transporte": {"distrito": do, "distancia": dk, "vehiculo": tv, "recorrido": tr}, "bordado": {"cantidad": c_bord, "tipo": t_bord},
                        "anexos": [{"nota": a["nota"], "foto_url": subir_imagen_supabase(f"fotos/{codigo_proy}/a_{x}_{ts}.jpg", a["foto_up"].read()) if a["foto_up"] else a["foto_url"]} for x, a in enumerate(lista_anexos)]
                    }
                    supabase.table("proyectos").upsert({"codigo": codigo_proy, "cliente": cliente, "ruc": ruc, "tipo_proyecto": proyecto_nom, "responsable": responsable, "fecha": f"{fe_inicio} - {fe_fin}", "estado": "EN_PROCESO", "peso_recibido": peso_tot, "peso_transformado": mtr, "aprovechamiento": p_apr, "co2_neto": co2_neto, "horas_totales": t_h_op+t_h_cf, "productos_unids": t_pu, "punto_origen": origen, "datos_completos": det}).execute()
                st.success("✅ Borrador guardado."); st.session_state.proyecto_editar = {}; st.rerun()

            if col_b1.button("🚀 Generar Reportes", type="primary", use_container_width=True):
                if not cliente.strip() or not ruc.strip(): st.error("Faltan datos en la Ficha General.")
                else:
                    with st.spinner("Generando..."):
                        buf = generar_pdf_oficial(cliente, ruc, proyecto_nom, codigo_proy, fe_inicio, fe_fin, responsable, area, "Textiles", "Upcycling", "kg", guia_remision, origen, destino, lista_items, lista_trazabilidad, lista_productos, mtr, mre, mpe, tot_p, p_apr, p_per, lista_op, lista_conf, t_h_op+t_h_cf, len(PERSONAL_FIJO_OPERACIONES)+len(pers_u), co2_tot, emi_t, p_lav*0.3, p_cor*0.05, emi_b, lista_anexos)
                        b_inf = buf.getvalue()
                        b_con = generar_constancia_desde_plantilla_word({"cliente": cliente.upper(), "mes": MESES_ESPANOL.get(fe_fin_dt.month, ""), "anio": str(fe_fin_dt.year), "peso_recibido": f"{peso_tot:.1f}", "unidades_ingreso": str(unid_tot), "co2_evitado": f"{co2_neto:.2f}", "aprovechamiento": f"{p_apr:.2f}", "total_mujeres": str(len(PERSONAL_FIJO_OPERACIONES)+len(pers_u)), "total_horas": f"{t_h_op+t_h_cf:.1f}", "productos_elaborados": str(t_pu), "fecha_cierre": f"{fe_fin_dt.strftime('%d')} de {MESES_ESPANOL.get(fe_fin_dt.month, '')} de {fe_fin_dt.year}"})
                        c_lim = cliente.strip().replace("/", "-")
                        u_inf = subir_pdf_supabase(f"Informe_{codigo_proy}.pdf", b_inf)
                        u_con = subir_pdf_supabase(f"Constancia_{codigo_proy}.pdf", b_con)
                        
                        try:
                            cid = obtener_carpeta_destino_drive(cliente, fe_fin_dt, f"Pedido {fe_fin_dt.strftime('%d-%m-%Y')}")
                            subir_a_drive(f"Informe_{c_lim}.pdf", b_inf, "application/pdf", cid)
                            subir_a_drive(f"Constancia_{c_lim}.pdf", b_con, "application/pdf", cid)
                        except: pass

                        ts = int(datetime.datetime.now().timestamp())
                        det = {
                            "items": [{"descripcion": i["descripcion"], "unidades": i["unidades"], "peso_unitario": i["peso_unitario"], "peso_total": i["peso_total"], "foto_url": subir_imagen_supabase(f"fotos/{codigo_proy}/i_{x}_{ts}.jpg", i["foto_up"].read()) if i["foto_up"] else i["foto_url"]} for x, i in enumerate(lista_items)],
                            "trazabilidad": [{"etapa": t["etapa"], "fecha": t["fecha"], "responsable": t["responsable"], "peso": t["peso"], "tipo_registro": t["tipo_registro"], "no_aplica": t["no_aplica"], "foto_url": subir_imagen_supabase(f"fotos/{codigo_proy}/t_{x}_{ts}.jpg", t["foto_up"].read()) if t["foto_up"] else t["foto_url"]} for x, t in enumerate(lista_trazabilidad)],
                            "productos": [{"producto": p["producto"], "cantidad": p["cantidad"], "foto_url": subir_imagen_supabase(f"fotos/{codigo_proy}/p_{x}_{ts}.jpg", p["foto_up"].read()) if p["foto_up"] else p["foto_url"]} for x, p in enumerate(lista_productos)],
                            "operaciones": lista_op, "confeccion": lista_conf, "balance": {"editar_manual": ed_b, "mat_transformado": mtr, "retazos_aprovechables": mre, "perdida_no_aprovechable": mpe},
                            "transporte": {"distrito": do, "distancia": dk, "vehiculo": tv, "recorrido": tr}, "bordado": {"cantidad": c_bord, "tipo": t_bord},
                            "anexos": [{"nota": a["nota"], "foto_url": subir_imagen_supabase(f"fotos/{codigo_proy}/a_{x}_{ts}.jpg", a["foto_up"].read()) if a["foto_up"] else a["foto_url"]} for x, a in enumerate(lista_anexos)]
                        }
                        supabase.table("proyectos").upsert({"codigo": codigo_proy, "cliente": cliente, "ruc": ruc, "tipo_proyecto": proyecto_nom, "responsable": responsable, "fecha": f"{fe_inicio} - {fe_fin}", "estado": "COMPLETADO", "peso_recibido": peso_tot, "peso_transformado": mtr, "aprovechamiento": p_apr, "co2_neto": co2_neto, "horas_totales": t_h_op+t_h_cf, "productos_unids": t_pu, "punto_origen": origen, "pdf_url": u_inf, "constancia_url": u_con, "datos_completos": det}).execute()
                        
                        st.session_state.documentos_descarga = {"cliente_limpio": c_lim, "bytes_informe": b_inf, "bytes_constancia": b_con, "bytes_zip": io.BytesIO().getvalue()}
                        st.session_state.proyecto_editar = {}; st.rerun()

        if st.session_state.documentos_descarga:
            d = st.session_state.documentos_descarga
            st.success("✅ Generado con éxito.")
            c1, c2 = st.columns(2)
            c1.download_button("📄 Descargar Informe", d["bytes_informe"], f"Informe_{d['cliente_limpio']}.pdf", "application/pdf", use_container_width=True)
            c2.download_button("📜 Descargar Constancia", d["bytes_constancia"], f"Constancia_{d['cliente_limpio']}.pdf", "application/pdf", use_container_width=True)
