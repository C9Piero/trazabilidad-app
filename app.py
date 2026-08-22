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
import plotly.express as px
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
        if "drive_oauth" not in st.secrets: return None
        creds_data = st.secrets["drive_oauth"]
        credentials = Credentials(token=None, refresh_token=creds_data["refresh_token"], client_id=creds_data["client_id"], client_secret=creds_data["client_secret"], token_uri="https://oauth2.googleapis.com/token")
        service = build('drive', 'v3', credentials=credentials)
        root_folder_id = creds_data["folder_id"]

        nombre_carpeta_anio = str(fecha_fin_dt.year)
        query_anio = f"name='{nombre_carpeta_anio}' and mimeType='application/vnd.google-apps.folder' and '{root_folder_id}' in parents and trashed=false"
        res_anio = service.files().list(q=query_anio, fields='files(id)').execute()
        id_anio = res_anio.get('files')[0].get('id') if res_anio.get('files', []) else service.files().create(body={'name': nombre_carpeta_anio, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [root_folder_id]}, fields='id').execute().get('id')

        nombre_carpeta_mes = MESES_ESPANOL.get(fecha_fin_dt.month, 'MES').upper()
        query_mes = f"name='{nombre_carpeta_mes}' and mimeType='application/vnd.google-apps.folder' and '{id_anio}' in parents and trashed=false"
        res_mes = service.files().list(q=query_mes, fields='files(id)').execute()
        id_mes = res_mes.get('files')[0].get('id') if res_mes.get('files', []) else service.files().create(body={'name': nombre_carpeta_mes, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [id_anio]}, fields='id').execute().get('id')

        nombre_cliente = cliente.strip().upper().replace("'", "")
        query_cli = f"name='{nombre_cliente}' and mimeType='application/vnd.google-apps.folder' and '{id_mes}' in parents and trashed=false"
        res_cli = service.files().list(q=query_cli, fields='files(id)').execute()
        id_cli = res_cli.get('files')[0].get('id') if res_cli.get('files', []) else service.files().create(body={'name': nombre_cliente, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [id_mes]}, fields='id').execute().get('id')

        query_proy = f"name='{nombre_subcarpeta}' and mimeType='application/vnd.google-apps.folder' and '{id_cli}' in parents and trashed=false"
        res_proy = service.files().list(q=query_proy, fields='files(id)').execute()
        return res_proy.get('files')[0].get('id') if res_proy.get('files', []) else service.files().create(body={'name': nombre_subcarpeta, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [id_cli]}, fields='id').execute().get('id')
    except Exception as e: st.caption(f"Aviso Carpetas Drive: {e}"); return None

def subir_a_drive(nombre_archivo: str, file_bytes: bytes, mime_type="application/pdf", custom_folder_id=None):
    try:
        if "drive_oauth" not in st.secrets: return None 
        creds_data = st.secrets["drive_oauth"]
        credentials = Credentials(token=None, refresh_token=creds_data["refresh_token"], client_id=creds_data["client_id"], client_secret=creds_data["client_secret"], token_uri="https://oauth2.googleapis.com/token")
        service = build('drive', 'v3', credentials=credentials)
        return service.files().create(body={'name': nombre_archivo, 'parents': [custom_folder_id if custom_folder_id else creds_data["folder_id"]]}, media_body=MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True), fields='id').execute().get('id')
    except Exception as e: st.caption(f"Aviso Drive: No se pudo respaldar {nombre_archivo} - {e}"); return None

# --- CONSTANTES ---
MESES_ESPANOL = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio", 7: "julio", 8: "agosto", 9: "setiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"}
MESES_ORDEN = [m.capitalize() for m in MESES_ESPANOL.values()]
PRODUCTOS_CATALOGO_BASE = ["Estrellas", "Cartuchera", "Cúbica", "Bolso", "Mochila", "Llavero", "Monedero", "Canguro", "Tote bag", "Neceser", "Portalaptop", "Portacepillos", "Pelota", "Portacubierto", "Juguete", "Cubo", "Corazones", "Peluche", "Morral", "Portaútiles", "Portabotella", "Cama perrito", "Colets", "Rombo", "Mandiles", "Lonchera", "➕ Otro (Escribir nuevo producto)"]
PERSONAL_CONFECCION_BASE = ["Celinda Gutierrez Delgado", "Guadalupe Guerra Cespedes", "Isabel Estrada Sandoval", "Carmen Cespedes Borda", "Mavela Espinoza", "Juana Padilla Ruiz", "Felicita Sandoval Vilchez", "Luciana Jara Estrada", "Genaro Jara Garcia", "Yovana Davila", "Katherine Hilario Vilca", "Rody Jara Rucana", "Lucila Campos", "Tiffany Landa Rios", "Sara Mallqui Herrada", "Erlith Paima", "Sonia Panduro Torres", "Cintya Rincon", "Dixie Hidalgo Martel", "Janeth Mescco Bautista", "Judith Cueva Vargas", "Linfa Tauche", "Maricela Nieto", "Sofia Moya Reyes", "Carmen Vizarreta Lozada", "Genoveva Vizarreta Lozada", "Gathy Perez Ortiz", "Omar Prada", "Yovana Davila Ramirez", "Rosario Evelin Blas Alcala", "Esmeralda Tandazo Briceño", "Jhoel Angel Dominguez Rementeria", "Pedro Estrada Ramos", "Victor Auccapuri San Miguel", "Gabriel Manrique Hurtado", "Evelyn Prada Vizarreta", "Eugenia Almanza Huere", "Nicolle Estrada Yabe", "Oswaldo Jara Garcia", "Noelia Gonzales Lopez"]
TIEMPOS_CONFECCION_PURO = {"mochila": 0.60, "bolso": 0.45, "tote bag": 0.30, "portalaptop": 0.75, "canguro": 0.50, "neceser": 0.35, "lonchera": 0.50, "cartuchera": 0.25, "morral": 0.50, "mandiles": 0.30, "cama perrito": 0.80, "cama": 0.80, "casa": 0.80, "peluche": 0.60, "pelota": 0.30, "estrellas": 0.15, "corazones": 0.15, "rombo": 0.15, "cúbica": 0.25, "cubo": 0.25, "llavero": 0.10, "monedero": 0.15, "portacepillos": 0.12, "portacubierto": 0.12, "portaútiles": 0.20, "portabotella": 0.20, "colets": 0.08, "juguete": 0.40}

def estimar_tiempo_unidad(nombre_producto: str) -> float:
    if not nombre_producto: return 0.35
    nombre_lower = nombre_producto.lower().strip()
    tiempo_costura = next((tiempo for prod_key, tiempo in TIEMPOS_CONFECCION_PURO.items() if prod_key in nombre_lower), None)
    if tiempo_costura is None:
        if any(w in nombre_lower for w in ["casa", "cama", "colchón", "almohadón", "organizador"]): tiempo_costura = 0.80
        elif any(w in nombre_lower for w in ["mochila", "morral", "maletín", "set", "conjunto"]): tiempo_costura = 0.70
        elif any(w in nombre_lower for w in ["bolso", "tote", "lonchera", "funda", "delantal"]): tiempo_costura = 0.45
        elif any(w in nombre_lower for w in ["cartuchera", "neceser", "monedero", "estuche"]): tiempo_costura = 0.30
        else: tiempo_costura = 0.35
    if any(w in nombre_lower for w in ["gran", "grande", "maxi", "complejo", "completo", "xl", "pesado"]): tiempo_costura += 0.25
    elif any(w in nombre_lower for w in ["mini", "pequeño", "simple", "corto", "sencillo"]): tiempo_costura = max(0.10, tiempo_costura - 0.15)
    return round(max(0.10, tiempo_costura), 2)

FACTORES_CO2 = {"Banner": 9.5, "Bolsas": 8.0, "Camisa algodón": 5.0, "Camisa drill": 5.9, "Casaca drill": 5.9, "Casaca polar": 6.0, "Chaleco": 6.575, "Pantalón jean": 5.0, "Polo algodón": 5.0, "Otro": 6.575}
FACTORES_TRANSPORTE = {"Auto": {"consumo": 0.10, "factor": 2.31}, "Minivan": {"consumo": 0.12, "factor": 2.00}, "Mototaxi": {"consumo": 0.04, "factor": 2.31}, "Moto": {"consumo": 0.03, "factor": 2.31}, "Camión mediano": {"consumo": 0.30, "factor": 2.68}, "Camión grande": {"consumo": 0.40, "factor": 2.68}}
DISTANCIAS_LIMA_SJL = {"San Juan de Lurigancho (Local)": 4.0, "Ate": 14.0, "Barranco": 18.5, "Callao (Cercado)": 18.0, "Comas": 18.0, "El Agustino": 6.0, "Independencia": 12.0, "Jesús María": 12.0, "La Molina": 15.0, "La Victoria": 9.5, "Lima (Cercado de Lima)": 9.0, "Lince": 12.5, "Los Olivos": 15.0, "Miraflores": 16.0, "Pueblo Libre": 13.5, "Rímac": 7.5, "San Borja": 12.0, "San Isidro": 13.5, "San Miguel": 15.5, "Santiago de Surco": 17.0, "Villa El Salvador": 28.0, "➕ Otro / Fuera de Lima (Ingreso manual)": 0.0}
FACTORES_BORDADO = {"Sin bordado / Ninguno": 0.0, "Estampado DTF": 0.020, "Simple (5 min/pieza)": 0.020, "Medio (9 min/pieza)": 0.037, "Complejo (10 min/pieza)": 0.041}
PERSONAL_FIJO_OPERACIONES = [{"rol": "Corte", "nombre": "Maria Isabel Estrada Sandoval"}, {"rol": "Corte", "nombre": "Genaro Jara García"}, {"rol": "Corte", "nombre": "Luciana Jara estrada"}, {"rol": "Corte", "nombre": "Felicita Sandoval vilchez"}, {"rol": "Corte", "nombre": "Nicolle Estrada"}, {"rol": "Logística", "nombre": "Evelyn Prada Vizarreta"}]

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Pequeños Detalles - Sistema de Trazabilidad", page_icon="♻️", layout="wide")

st.markdown("""<style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');:root { --brand-900: #0F172A; --brand-700: #1E3A8A; --brand-500: #2563EB; --ink-muted: #64748B; --border: #E2E8F0; --surface: #F8FAFC; --radius: 14px; }html, body, [class*="css"] { font-family: 'Inter', sans-serif; }div[data-testid="stNumberInput"] button { display: none !important; }div[data-testid="stNumberInput"] input { text-align: left; }.hero-header { background: linear-gradient(135deg, var(--brand-900) 0%, var(--brand-700) 50%, var(--brand-500) 100%); color: white; padding: 24px 30px; border-radius: var(--radius); box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.3); margin-bottom: 25px; }.hero-header h1 { color: #ffffff !important; font-weight: 800; font-size: 1.8rem; margin: 0; }.hero-header p { color: #93C5FD !important; margin: 4px 0 0 0; font-size: 0.95rem; }div[data-testid="stSidebar"] { background-color: var(--surface); border-right: 1px solid var(--border); }.sidebar-section-title { color: var(--ink-muted); font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 15px; margin-bottom: 8px; }div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: var(--radius) !important; border: 1px solid var(--border) !important; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06); transition: box-shadow 0.2s ease; }div[data-testid="stVerticalBlockBorderWrapper"]:hover { box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08); }div[data-testid="stButton"] button { border-radius: 10px; font-weight: 600; border: 1px solid var(--border); }div[data-testid="stButton"] button[kind="primary"] { background: linear-gradient(135deg, var(--brand-700) 0%, var(--brand-500) 100%); border: none; }div[data-testid="stMetric"] { background-color: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; }</style>""", unsafe_allow_html=True)

@st.cache_resource
def init_supabase() -> Client: return create_client(st.secrets["supabase"]["SUPABASE_URL"], st.secrets["supabase"]["SUPABASE_KEY"])

try: supabase = init_supabase()
except Exception as e: st.error(f"⚠️ Error Supabase: {e}"); st.stop()

def subir_pdf_supabase(nombre_archivo: str, pdf_bytes: bytes) -> str:
    try: supabase.storage.from_("reportes").upload(path=nombre_archivo, file=pdf_bytes, file_options={"content-type": "application/pdf", "upsert": "true"}); return supabase.storage.from_("reportes").get_public_url(nombre_archivo)
    except: return ""

def subir_imagen_supabase(nombre_archivo: str, img_bytes: bytes) -> str:
    try: supabase.storage.from_("reportes").upload(path=nombre_archivo, file=img_bytes, file_options={"content-type": "image/jpeg", "upsert": "true"}); return supabase.storage.from_("reportes").get_public_url(nombre_archivo)
    except: return ""

def cargar_proyectos(estado=None):
    try: query = supabase.table("proyectos").select("*"); return (query.eq("estado", estado) if estado else query).execute().data
    except: return []

def eliminar_proyecto_bd(proyecto_id, codigo_proy):
    try: supabase.table("proyectos").delete().eq("id" if proyecto_id else "codigo", proyecto_id or codigo_proy).execute(); return True
    except: return False

@st.dialog("⚠️ Confirmar Eliminación Permanente")
def modal_confirmar_eliminacion(proyecto):
    st.warning(f"¿Eliminar permanentemente **{proyecto.get('cliente', 'Sin Nombre')}**?")
    c_y, c_n = st.columns(2)
    if c_y.button("🚨 Eliminar", use_container_width=True, type="primary"):
        if eliminar_proyecto_bd(proyecto.get("id"), proyecto.get("codigo")): st.session_state.proyecto_editar = {}; st.toast("🗑️ Eliminado."); st.rerun()
    if c_n.button("Cancelar", use_container_width=True): st.rerun()

@st.dialog("⚠️ Confirmar Eliminación Masiva")
def modal_confirmar_eliminacion_masiva(proyectos_a_borrar):
    st.warning(f"¿Eliminar **{len(proyectos_a_borrar)}** proyectos permanentemente?")
    c_y, c_n = st.columns(2)
    if c_y.button("🚨 Eliminar Todos", use_container_width=True, type="primary"):
        for p in proyectos_a_borrar: eliminar_proyecto_bd(p.get("id"), p.get("codigo"))
        st.session_state.proyecto_editar = {}; st.toast(f"🗑️ {len(proyectos_a_borrar)} eliminados.")
        for p in proyectos_a_borrar: st.session_state.pop(f"bulk_del_{p.get('id', p.get('codigo'))}", None)
        st.rerun()
    if c_n.button("Cancelar", use_container_width=True): st.rerun()

class ReporteCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs): super().__init__(*args, **kwargs); self.pages = []
    def showPage(self): self.pages.append(dict(self.__dict__)); self._startPage()
    def save(self):
        for page in self.pages: self.__dict__.update(page); self.draw_footer(); super().showPage()
        super().save()
    def draw_footer(self):
        self.saveState(); self.setFont("Helvetica", 7); self.setFillColor(colors.HexColor("#94A3B8"))
        self.drawCentredString(612 / 2.0, 22, "Promoviendo el desarrollo sostenible a través de la economía circular y el empoderamiento de mujeres")
        self.drawCentredString(612 / 2.0, 12, "emprendedoras"); self.restoreState()

def generar_constancia_desde_plantilla_word(contexto: dict) -> bytes:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ruta = next((os.path.join(base_dir, f) for f in os.listdir(base_dir) if f.lower().endswith(".docx") and not f.startswith("~")), None)
    if not ruta: raise FileNotFoundError("No se encontró plantilla Word (.docx)")
    doc = DocxTemplate(ruta); doc.render(contexto)
    with tempfile.TemporaryDirectory() as tmpdir:
        doc.save(os.path.join(tmpdir, "temp.docx"))
        subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", os.path.join(tmpdir, "temp.docx"), "--outdir", tmpdir], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with open(os.path.join(tmpdir, "temp.pdf"), "rb") as f: return f.read()

def generar_pdf_oficial(cliente, ruc, proyecto_nom, codigo_proy, fe_inicio, fe_fin, responsable, area, tipo_material, valorizacion, unidad_medida, guia_remision, origen, destino, lista_items, lista_trazabilidad, lista_productos, mat_transformado, retazos_aprovechables, perdida_no_aprovechable, total_procesado, pct_aprovechamiento_total, pct_perdida, lista_operaciones_pdf, lista_confeccion, total_horas_social, total_personas_social, co2_evitado_total, emisiones_transporte, emisiones_lavado, emisiones_corte, emisiones_bordado, lista_anexos=None):
    kg_recibidos = sum([item["peso_total"] for item in lista_items]); co2_neto = co2_evitado_total - (emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado)
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=45)
    st_n = getSampleStyleSheet()["Normal"]; h1 = ParagraphStyle("H1", parent=getSampleStyleSheet()["Heading1"], fontName="Helvetica-Bold", fontSize=14, textColor=colors.HexColor("#1E293B"), alignment=1, spaceAfter=2); sub = ParagraphStyle("Sub", parent=st_n, fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#64748B"), alignment=1, spaceAfter=12); h2 = ParagraphStyle("H2", parent=getSampleStyleSheet()["Heading2"], fontName="Helvetica-Bold", fontSize=10, textColor=colors.HexColor("#0F172A"), spaceBefore=10, spaceAfter=6); c_st = ParagraphStyle("C", parent=st_n, fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#334155"), leading=10); c_b = ParagraphStyle("CB", parent=st_n, fontName="Helvetica-Bold", fontSize=8, textColor=colors.HexColor("#0F172A"), leading=10); c_t = ParagraphStyle("CT", parent=st_n, fontName="Helvetica-Bold", fontSize=12, textColor=colors.HexColor("#0F172A"), alignment=1); c_s = ParagraphStyle("CS", parent=st_n, fontName="Helvetica", fontSize=7, textColor=colors.HexColor("#475569"), alignment=1)

    elements = [
        Paragraph("INFORME TÉCNICO DE VALORIZACIÓN TEXTIL", h1), Paragraph(f"Medición de Impacto Ambiental, Trazabilidad y Gestión Social de Upcycling<br/><b>CÓDIGO: {codigo_proy}</b>", sub),
        Paragraph(f"Proyecto implementado para <b>{cliente}</b>, transformando <b>{total_procesado:.2f} kg</b> de textiles mediante upcycling, con la elaboración de <b>{sum([p['cantidad'] for p in lista_productos])}</b> productos, participación de <b>{total_personas_social}</b> personas y un impacto neto evitado de <b>{co2_neto:.2f} kg</b> de CO₂e.", ParagraphStyle("R", parent=st_n, fontSize=8.5, leading=12, alignment=4, spaceAfter=6)), Spacer(1, 4),
        Table([[Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", c_t), Paragraph(f"<b>{pct_aprovechamiento_total:.2f}%</b>", c_t), Paragraph(f"<b>{co2_neto:.2f} kg</b>", c_t), Paragraph(f"<b>{total_horas_social:.2f} hrs</b>", c_t)], [Paragraph("MATERIAL", c_s), Paragraph("% APROVECH.", c_s), Paragraph("CO2e NETO EVITADO", c_s), Paragraph(f"TRABAJO GENERADO", c_s)]], colWidths=[135]*4, style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("PADDING", (0, 0), (-1, -1), 6), ("ALIGN", (0, 0), (-1, -1), "CENTER")])),
        Spacer(1, 8), Paragraph("1. FICHA GENERAL", h2),
        Table([[Paragraph("Cliente / Empresa", c_b), Paragraph(f"{cliente} (RUC: {ruc})", c_st), Paragraph("Responsable", c_b), Paragraph(responsable, c_st)], [Paragraph("Tipo", c_b), Paragraph(proyecto_nom, c_st), Paragraph("Periodo", c_b), Paragraph(f"{fe_inicio} al {fe_fin}", c_st)], [Paragraph("Origen", c_b), Paragraph(origen, c_st), Paragraph("Guía", c_b), Paragraph(guia_remision, c_st)]], colWidths=[100, 170, 100, 170], style=TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")), ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F8FAFC")), ("PADDING", (0, 0), (-1, -1), 4)])),
        Spacer(1, 8), Paragraph("2. MATERIAL", h2)
    ]
    t_pren = [[Paragraph("Ítem", c_b), Paragraph("Tipo", c_b), Paragraph("Unid", c_b), Paragraph("Total kg", c_b)]] + [[Paragraph(str(i), c_st), Paragraph(it["descripcion"], c_st), Paragraph(str(it["unidades"]), c_st), Paragraph(f"{it['peso_total']:.2f}", c_st)] for i, it in enumerate(lista_items, 1)]
    elements.extend([Table(t_pren, colWidths=[40, 240, 130, 130], style=TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5D0FE")), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("PADDING", (0, 0), (-1, -1), 4)])), PageBreak(), Paragraph("3. PRODUCTOS", h2)])
    t_pro = [[Paragraph("Producto", c_b), Paragraph("Cantidad", c_b)]] + [[Paragraph(pr["producto"], c_st), Paragraph(str(pr["cantidad"]), c_st)] for pr in lista_productos]
    elements.extend([Table(t_pro, colWidths=[350, 190], style=TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5D0FE")), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("PADDING", (0, 0), (-1, -1), 4)])), Spacer(1, 15), Paragraph("4. BALANCE Y EMISIONES", h2)])
    elements.extend([Table([[Paragraph("Material recibido", c_st), Paragraph(f"{kg_recibidos:.2f} kg", c_st)], [Paragraph("Aprovechamiento", c_st), Paragraph(f"{pct_aprovechamiento_total:.2f}%", c_st)], [Paragraph("CO2 Neto", c_b), Paragraph(f"{co2_neto:.2f} kg", c_b)]], colWidths=[350, 190], style=TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#F1F5F9")), ("PADDING", (0, 0), (-1, -1), 5)])), Spacer(1, 15), Paragraph("5. IMPACTO SOCIAL", h2)])
    elements.extend([Table([[Paragraph("Horas Generadas", c_b), Paragraph(f"{total_horas_social:.2f} hrs", c_st)], [Paragraph("Beneficiadas", c_b), Paragraph(str(total_personas_social), c_st)]], colWidths=[350, 190], style=TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("PADDING", (0, 0), (-1, -1), 5)])), Spacer(1, 10)])
    doc.build(elements, canvasmaker=ReporteCanvas); buffer.seek(0)
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
except KeyError: st.error("⚠️ Faltan credenciales."); st.stop()

# --- LOGIN ---
if not st.session_state.autenticado:
    st.markdown('<div style="text-align: center; padding: 40px 10px;"><h1 style="color: #1E293B; font-weight: 800;">♻️ Pequeños Detalles</h1><p style="color: #64748B;">Gestión de Sostenibilidad</p></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2.container(border=True):
        u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True, type="primary"):
            if u == USUARIO_CORRECTO and p == PASSWORD_CORRECTO: st.session_state.autenticado = True; st.rerun()
            else: st.error("⚠️ Error.")
else:
    proyectos_wip = cargar_proyectos("EN_PROCESO")

    with st.sidebar:
        st.markdown("### ♻️ Pequeños Detalles\nPanel de Control"); st.write("---")
        st.markdown('<p class="sidebar-section-title">Navegación</p>', unsafe_allow_html=True)
        if st.button("✨     Nuevo Reporte", use_container_width=True, type="primary" if st.session_state.pestaña_activa == "➕     Nuevo Reporte PDF" else "secondary"):
            st.session_state.proyecto_editar = {}; st.session_state.documentos_descarga = None; st.session_state.pestaña_activa = "➕     Nuevo Reporte PDF"; st.session_state.uid_proyecto = str(random.randint(1000, 9999)); st.rerun()
        if st.button("⚡     Carga Histórica", use_container_width=True, type="primary" if st.session_state.pestaña_activa == "⚡     Carga Rápida Histórica" else "secondary"):
            st.session_state.pestaña_activa = "⚡     Carga Rápida Histórica"; st.rerun()

        st.markdown('<p class="sidebar-section-title">Borradores</p>', unsafe_allow_html=True)
        if proyectos_wip:
            for p in proyectos_wip:
                if st.button(f"📁 {p.get('cliente', 'Sin Nombre')}", key=f"s_{p.get('id')}", use_container_width=True, type="primary" if st.session_state.proyecto_editar.get("id") == p.get("id") else "secondary"):
                    st.session_state.proyecto_editar = p; st.session_state.pestaña_activa = "➕     Nuevo Reporte PDF"; st.rerun()
        else: st.caption("📭 No hay borradores")

        st.markdown('<p class="sidebar-section-title">Analítica</p>', unsafe_allow_html=True)
        if st.button("📊 Dashboard Analítico", use_container_width=True, type="primary" if st.session_state.pestaña_activa == "📊 Dashboard Analítico" else "secondary"):
            st.session_state.pestaña_activa = "📊 Dashboard Analítico"; st.rerun()
        if st.button("🗂️ Historial", use_container_width=True, type="primary" if st.session_state.pestaña_activa == "🗂️ Historial Completo" else "secondary"):
            st.session_state.pestaña_activa = "🗂️ Historial Completo"; st.rerun()
        st.write("---")
        if st.button("🚪 Salir", use_container_width=True): st.session_state.autenticado = False; st.rerun()

    st.markdown(f'<div class="hero-header"><h1>📄 Sistema de Gestión de Informes Técnicos</h1><p>Sección Activa: <b>{st.session_state.pestaña_activa}</b></p></div>', unsafe_allow_html=True)

    # --- VISTA: CARGA RÁPIDA E IMPORTACIÓN MASIVA ---
    if st.session_state.pestaña_activa == "⚡     Carga Rápida Histórica":
        st.subheader("⚡ Carga Histórica")
        t_man, t_mas = st.tabs(["✍️ Manual", "📂 Masiva (CSV/Excel)"])

        with t_man:
            with st.container(border=True):
                r1, r2, r3, r4 = st.columns([2.5, 1.5, 1, 1.5])
                f_cli = r1.text_input("Cliente *")
                f_mes = r2.selectbox("Mes *", MESES_ORDEN, index=datetime.date.today().month - 1)
                f_anio = r3.selectbox("Año", [2024, 2025, 2026, 2027], index=2)
                f_tip = r4.selectbox("Tipo", ["UPCYCLING", "PRODUCCIÓN DESDE CERO", "CAMBIO DE LOGO", "MIXTO", "BANNER"])
                
                m_num = MESES_ORDEN.index(f_mes) + 1
                f_cod = f"HIST_{f_cli.strip()[:8]}_{m_num:02d}{f_anio}-{random.randint(1000, 9999)}"

            with st.container(border=True):
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                f_pes = m1.number_input("Kg *", min_value=0.0, step=0.1)
                f_ure = m2.number_input("U. Rec", min_value=0, step=1)
                f_uni = m3.number_input("Prods *", min_value=0, step=1)
                f_co2 = m4.number_input("CO₂ *", min_value=0.0, step=0.1)
                f_hrs = m5.number_input("Hrs *", min_value=0.0, step=0.5)
                f_per = m6.number_input("Pers *", min_value=0, step=1)

            if st.button("🚀 Guardar", type="primary", use_container_width=True):
                if not f_cli.strip(): st.error("Falta Cliente.")
                else:
                    supabase.table("proyectos").upsert({"codigo": f_cod, "cliente": f_cli, "ruc": "00000000000", "tipo_proyecto": f_tip, "responsable": "Histórico", "fecha": f"01/{m_num:02d}/{f_anio} - 28/{m_num:02d}/{f_anio}", "estado": "COMPLETADO", "peso_recibido": f_pes, "peso_transformado": f_pes, "aprovechamiento": 100.0, "co2_neto": f_co2, "horas_totales": f_hrs, "productos_unids": f_uni, "punto_origen": "Histórico", "datos_completos": {"participantes": f_per, "unidades_recibidas": f_ure}}).execute()
                    st.success("✅ Guardado"); st.rerun()

        with t_mas:
            with st.container(border=True):
                st.markdown("##### 📂 Carga Masiva Automática")
                st.markdown("El sistema lee CSV (recomendado) o Excel automáticamente.")
                arc = st.file_uploader("Sube CSV/Excel", type=["csv", "xlsx"])
                a_mas = st.selectbox("Año a aplicar", [2024, 2025, 2026, 2027], index=2)

                if arc:
                    df_sub = None
                    if arc.name.endswith('.csv'):
                        try: df_sub = pd.read_csv(arc, encoding='utf-8', sep=None, engine='python')
                        except: arc.seek(0); df_sub = pd.read_csv(arc, encoding='latin1', sep=None, engine='python')
                    else:
                        try: df_sub = pd.read_excel(arc)
                        except: st.error("⚠️ Falta openpyxl. Usa CSV.")
                    
                    if df_sub is not None:
                        st.write("Vista previa:", df_sub.head(3))
                        if st.button("🚀 Importar Todos", type="primary", use_container_width=True):
                            with st.spinner("Importando..."):
                                map_m = {m.lower(): i for i, m in MESES_ESPANOL.items()}
                                c_cl = next((c for c in df_sub.columns if "cliente" in str(c).lower()), "Cliente")
                                c_ms = next((c for c in df_sub.columns if "mes" in str(c).lower()), "Mes")
                                c_ur = next((c for c in df_sub.columns if "unid" in str(c).lower()), "Unidades recibidas")
                                c_kg = next((c for c in df_sub.columns if "kg" in str(c).lower() or "peso" in str(c).lower()), "Kg recibidos")
                                c_co = next((c for c in df_sub.columns if "co2" in str(c).lower() or "evit" in str(c).lower()), "CO2 evitado")
                                c_hr = next((c for c in df_sub.columns if "hora" in str(c).lower()), "Horas")
                                c_pr = next((c for c in df_sub.columns if "prod" in str(c).lower()), "Productos")
                                c_pa = next((c for c in df_sub.columns if "partic" in str(c).lower()), "Participantes")
                                c_ti = next((c for c in df_sub.columns if "tipo" in str(c).lower()), "TIPO DE PROYECTO")

                                def sf(v): return float(v) if pd.notna(v) else 0.0
                                def si(v): return int(float(v)) if pd.notna(v) else 0

                                ex = 0
                                for i, r in df_sub.iterrows():
                                    cl = str(r.get(c_cl)).strip()
                                    if pd.isna(r.get(c_cl)) or cl.upper() == "NAN" or not cl: continue
                                    mn = map_m.get(str(r.get(c_ms, "enero")).strip().lower(), 1)
                                    supabase.table("proyectos").upsert({
                                        "codigo": f"MAS_{cl[:6].replace(' ','')}_{mn:02d}{a_mas}-{i}-{random.randint(10000,99999)}",
                                        "cliente": cl, "ruc": "00000000000", "tipo_proyecto": str(r.get(c_ti, "UPCYCLING")).upper(),
                                        "responsable": "Histórico", "fecha": f"01/{mn:02d}/{a_mas} - 28/{mn:02d}/{a_mas}", "estado": "COMPLETADO",
                                        "peso_recibido": sf(r.get(c_kg)), "peso_transformado": sf(r.get(c_kg)), "aprovechamiento": 100.0,
                                        "co2_neto": sf(r.get(c_co)), "horas_totales": sf(r.get(c_hr)), "productos_unids": si(r.get(c_pr)),
                                        "punto_origen": "Masivo", "datos_completos": {"participantes": si(r.get(c_pa)), "unidades_recibidas": si(r.get(c_ur))}
                                    }).execute()
                                    ex += 1
                                st.success(f"🎉 ¡{ex} importados!"); st.balloons()

    # --- VISTA: DASHBOARD DINÁMICO ---
    elif st.session_state.pestaña_activa == "📊 Dashboard Analítico":
        st.subheader("📊 Dashboard Dinámico de Sostenibilidad")
        completados = cargar_proyectos("COMPLETADO")
        
        if not completados: st.info("📭 Aún no hay proyectos.")
        else:
            t_dat = []
            for p in completados:
                dc = p.get("datos_completos") or {}
                m_txt, a_txt = "N/D", "2026"
                if p.get("fecha") and "-" in p.get("fecha"):
                    try:
                        f_p = p.get("fecha").split("-")[1].strip().split("/")
                        m_txt, a_txt = MESES_ESPANOL.get(int(f_p[1]), "N/D").capitalize(), str(f_p[2])
                    except: pass

                t_dat.append({
                    "Cliente": p.get("cliente", "Sin Nombre"), "Año": a_txt, "Mes": m_txt, 
                    "U. Rec": sum([int(i.get("unidades",0)) for i in dc.get("items",[])]) if "items" in dc else int(dc.get("unidades_recibidas",0)),
                    "Kg": float(p.get("peso_recibido") or 0), "CO₂e": float(p.get("co2_neto") or 0),
                    "Hrs": float(p.get("horas_totales") or 0), "Prods": int(p.get("productos_unids") or 0),
                    "Pers": (6+len(set([c.get("persona","").strip() for c in dc.get("confeccion",[]) if c.get("persona","").strip()]))) if "items" in dc else int(dc.get("participantes",0)),
                    "Tipo": p.get("tipo_proyecto", "UPCYCLING")
                })
            df = pd.DataFrame(t_dat)

            st.markdown("### 🎛️ Filtros")
            f0, f1, f2, f3 = st.columns(4)
            a_dsp = ["Todos"] + sorted(list(df["Año"].unique()), reverse=True)
            m_dsp = ["Todos"] + [m for m in MESES_ORDEN if m in df["Mes"].unique()]
            c_dsp = ["Todos"] + sorted([str(x) for x in df["Cliente"].unique() if x != "N/D"])
            t_dsp = ["Todos"] + sorted([str(x) for x in df["Tipo"].unique() if x != "N/D"])

            s_a = f0.selectbox("🗓️ Año", a_dsp)
            s_m = f1.selectbox("📅 Mes", m_dsp)
            s_c = f2.selectbox("🏢 Cliente", c_dsp)
            s_t = f3.selectbox("♻️ Tipo", t_dsp)

            df_f = df.copy()
            if s_a != "Todos": df_f = df_f[df_f["Año"] == s_a]
            if s_m != "Todos": df_f = df_f[df_f["Mes"] == s_m]
            if s_c != "Todos": df_f = df_f[df_f["Cliente"] == s_c]
            if s_t != "Todos": df_f = df_f[df_f["Tipo"] == s_t]

            dm1, dm2, dm3, dm4, dm5 = st.columns(5)
            dm1.metric("📦 U. Recibidas", f"{int(df_f['U. Rec'].sum())}")
            dm2.metric("⚖️ Kg Procesados", f"{df_f['Kg'].sum():.1f} kg")
            dm3.metric("🌍 CO₂e Evitado", f"{df_f['CO₂e'].sum():.1f} kg")
            dm4.metric("⏳ Hrs Trabajo", f"{df_f['Hrs'].sum():.1f} h")
            dm5.metric("🛍️ Prods Creados", f"{int(df_f['Prods'].sum())}")
            st.write("---")

            cg1, cg2 = st.columns([2, 1.2])
            with cg1:
                st.markdown("##### 📈 Evolución CO₂e Mensual")
                if not df_f.empty:
                    df_mg = df_f.groupby("Mes")["CO₂e"].sum().reset_index()
                    df_mg["M_cat"] = pd.Categorical(df_mg["Mes"], categories=MESES_ORDEN, ordered=True)
                    fig1 = px.bar(df_mg.sort_values("M_cat"), x="Mes", y="CO₂e", text_auto='.0f', color_discrete_sequence=["#2563EB"])
                    fig1.update_traces(textposition="outside"); fig1.update_layout(margin=dict(l=0, r=0, t=30, b=0), xaxis_title="")
                    st.plotly_chart(fig1, use_container_width=True)
            with cg2:
                st.markdown("##### 🍩 Tipos de Servicio (por Kg)")
                if not df_f.empty:
                    fig2 = px.pie(df_f.groupby("Tipo")["Kg"].sum().reset_index(), values="Kg", names="Tipo", hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig2.update_traces(textposition='inside', textinfo='percent'); fig2.update_layout(margin=dict(l=0, r=0, t=30, b=0), showlegend=True, legend=dict(orientation="h", y=-0.2))
                    st.plotly_chart(fig2, use_container_width=True)

            cr1, cr2 = st.columns([1.5, 2.5])
            with cr1:
                st.markdown("##### 🥇 Top 5 Clientes (CO₂e)")
                if not df_f.empty:
                    t5 = df_f.groupby("Cliente")["CO₂e"].sum().reset_index().sort_values(by="CO₂e", ascending=False).head(5)
                    t5.insert(0, "Rank", ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][:len(t5)])
                    st.dataframe(t5, use_container_width=True, hide_index=True)
            with cr2:
                st.markdown("##### 📋 Proyectos (Filtrados)")
                st.dataframe(df_f, use_container_width=True, hide_index=True, height=230, column_config={"Kg": st.column_config.ProgressColumn("Kg", min_value=0, max_value=float(df_f["Kg"].max() or 100), format="%.1f"), "CO₂e": st.column_config.ProgressColumn("CO₂e", min_value=0, max_value=float(df_f["CO₂e"].max() or 100), format="%.1f")})

    # --- VISTA: HISTORIAL COMPLETO ---
    elif st.session_state.pestaña_activa == "🗂️ Historial Completo":
        st.subheader("🗂️ Historial Completo de Proyectos")
        proyectos_lista = cargar_proyectos()
        if proyectos_lista:
            sel_b = [p for p in proyectos_lista if st.session_state.get(f"bulk_del_{p.get('id', p.get('codigo'))}", False)]
            c_top1, c_top2 = st.columns([4, 2])
            if c_top2.button(f"🗑️ Eliminar ({len(sel_b)})", disabled=not sel_b, type="primary", use_container_width=True): modal_confirmar_eliminacion_masiva(sel_b)
            st.write("---")

            for p in proyectos_lista:
                with st.container(border=True):
                    cc, hc1, hc2, hc3, hc4, hc5, hc6 = st.columns([0.4, 2.5, 1.6, 1.6, 1.8, 1.8, 0.7])
                    cc.write(""); cc.checkbox(" ", key=f"bulk_del_{p.get('id', p.get('codigo'))}", label_visibility="collapsed")
                    hc1.markdown(f"**{p.get('cliente', 'Sin Nombre')}**\n\n`{p.get('codigo', '')}`")
                    hc2.markdown(f"**{p.get('estado', 'N/D')}**\n\n{p.get('tipo_proyecto', 'Upcycling')}")
                    hc3.markdown(f"`{float(p.get('peso_recibido', 0) or 0):.2f} kg`\n\n{p.get('fecha', 'N/D')}")
                    if p.get("pdf_url"): hc4.link_button("📄 PDF", p.get("pdf_url"), use_container_width=True)
                    else: hc4.caption("Sin Informe")
                    if p.get("constancia_url"): hc5.link_button("📜 Const.", p.get("constancia_url"), use_container_width=True)
                    else: hc5.caption("Sin Constancia")
                    if hc6.button("🗑️", key=f"hd_{p.get('id')}", use_container_width=True): modal_confirmar_eliminacion(p)
        else: st.info("📭 No hay proyectos.")

    # --- VISTA: NUEVO REPORTE ---
    elif st.session_state.pestaña_activa == "➕     Nuevo Reporte PDF":
        pe = st.session_state.proyecto_editar
        tid = pe.get("id") or pe.get("codigo") or "__nuevo__"
        if st.session_state.get("_loaded_project_id") != tid:
            st.session_state._loaded_project_id = tid
            di = pe.get("datos_completos") or pe.get("datos_formulario") or {}
            st.session_state.num_items, st.session_state.num_prods, st.session_state.num_anexos = di.get("num_items", max(2, len(di.get("items", [])))), di.get("num_prods", max(2, len(di.get("productos", [])))), di.get("num_anexos", max(1, len(di.get("anexos", []))))
            for k, v in di.get("confeccion_num_pers", {}).items(): st.session_state[k] = v
            [st.session_state.pop(k) for k in list(st.session_state.keys()) if any(k.startswith(px) for px in ["desc_", "unid_", "tot_input_", "peso_u_", "foto_", "prod_sel_", "prod_cant_", "prod_nuevo_txt_", "prod_dis_", "prod_foto_", "tr_etapa_", "tr_fecha_", "tr_resp_", "chk_edit_", "chk_no_aplica_", "tr_peso_", "tr_tipo_", "tr_foto_", "soc_rol_", "soc_pers_sel_", "soc_pers_txt_custom_", "soc_cant_", "soc_tunit_", "soc_tunit_calc_", "soc_htot_", "anx_foto_", "anx_nota_", "ops_chk_", "ops_nom_", "ops_dias_", "ops_hdia_", "ops_tot_", "transporte_distrito_origen", "dist_km_manual", "dist_km_auto_", "chk_edit_balance", "bm_mat_transf_", "bm_retazos_", "bm_perdida_", "responsables_proyecto", "nuevo_responsable_proyecto"])]
        
        dc = pe.get("datos_completos") or pe.get("datos_formulario") or {}
        if pe:
            st.warning(f"✏️ Editando: {pe.get('cliente', '')}")
            cd, ce = st.columns(2)
            if cd.button("❌ Descartar", use_container_width=True): st.session_state.proyecto_editar = {}; st.rerun()
            if ce.button("🗑️ Eliminar", use_container_width=True): modal_confirmar_eliminacion(pe)

        with st.container(border=True):
            st.subheader("1. Ficha General")
            try: f_ini, f_fin = datetime.datetime.strptime(pe.get("fecha", " - ").split(" - ")[0].strip(), "%d/%m/%Y").date(), datetime.datetime.strptime(pe.get("fecha", " - ").split(" - ")[1].strip(), "%d/%m/%Y").date()
            except: f_ini, f_fin = datetime.date.today(), datetime.date.today()

            c1, c2, c5, c6 = st.columns(4)
            cliente = c1.text_input("Cliente *", value=pe.get("cliente", ""))
            ruc = c2.text_input("RUC *", value=pe.get("ruc", ""), max_chars=11)
            fe_inicio_dt, fe_fin_dt = c5.date_input("Inicio *", value=f_ini, format="DD/MM/YYYY"), c6.date_input("Término *", value=f_fin, format="DD/MM/YYYY")
            fe_inicio, fe_fin = fe_inicio_dt.strftime("%d/%m/%Y"), fe_fin_dt.strftime("%d/%m/%Y")
            codigo_proy = pe.get("codigo") or f"{cliente.strip() or 'EMPRESA'}_{fe_inicio_dt.strftime('%d%m%Y')}-{fe_fin_dt.strftime('%d%m%Y')}-{st.session_state.uid_proyecto}"
            st.info(f"🆔 **Código:** `{codigo_proy}`")

            c4, c7, c8, c9 = st.columns(4)
            proyecto_nom = c4.selectbox("Tipo *", ["Upcycling", "Producción desde cero", "Cambio de logo", "Mixto", "Banner"], index=0)
            rg = pe.get("responsables", [x.strip() for x in str(pe.get("responsable", "")).split(",") if x.strip()]) if not pe.get("responsables") else pe["responsables"]
            opc_r = list(dict.fromkeys(["Evelyn Prada Vizarreta", "Gabriel Manrique Hurtado"] + (rg if isinstance(rg, list) else [])))
            resp_sel = c7.multiselect("Resp *", opc_r, default=[r for r in rg if r in opc_r])
            n_resp = c7.text_input("➕ Otro resp", key="nr")
            if n_resp.strip() and n_resp.strip() not in resp_sel: resp_sel.append(n_resp.strip())
            responsable = ", ".join(resp_sel)
            area = c8.text_input("Área", value="Sostenibilidad", disabled=True)
            guia_remision = c9.text_input("Guía", value=pe.get("guia", "") or dc.get("guia_remision", ""))
            origen = st.text_input("Origen *", value=pe.get("origen", pe.get("punto_origen", dc.get("origen", ""))))
            destino = "Jr. Las Caléndulas 610, Las Flores, SJL."

        with st.container(border=True):
            st.subheader("2. Material")
            cb1, cb2, _ = st.columns([1, 1, 4])
            if cb1.button("➕ Ítem"): st.session_state.num_items += 1; st.rerun()
            if cb2.button("➖ Ítem") and st.session_state.num_items > 1: st.session_state.num_items -= 1; st.rerun()

            lista_items, peso_tot, co2_tot, unid_tot, op_p, s_it = [], 0.0, 0.0, 0, sorted(list(FACTORES_CO2.keys())), dc.get("items", [])
            for i in range(st.session_state.num_items):
                cd, cu, cp, ct, cf = st.columns([3, 1.5, 1.5, 1.5, 3])
                ip = s_it[i] if i < len(s_it) else {}
                desc = cd.selectbox(f"Prenda {i+1} *", op_p, index=op_p.index(ip.get("descripcion", op_p[0])) if ip.get("descripcion") in op_p else 0, key=f"d_{i}")
                unid = cu.number_input("Unid *", min_value=0, value=int(ip.get("unidades", 0)), key=f"u_{i}")
                p_t = cp.number_input("Kg *", min_value=0.0, value=float(ip.get("peso_total", 0.0)), step=0.05, key=f"pt_{i}")
                ct.text_input("Kg/U", value=f"{p_t/unid if unid>0 else 0:.2f}", disabled=True, key=f"pu_{i}")
                fot = cf.file_uploader("Foto", type=["jpg", "png"], key=f"f_{i}")
                if fot: cf.image(fot, width=80)
                elif ip.get("foto_url"): cf.image(ip.get("foto_url"), width=80)
                
                co2_i = p_t * FACTORES_CO2.get(desc, 6.575); peso_tot += p_t; co2_tot += co2_i; unid_tot += unid
                lista_items.append({"descripcion": desc, "unidades": unid, "peso_unitario": p_t/unid if unid>0 else 0, "peso_total": p_t, "foto_up": fot, "foto_url": ip.get("foto_url", ""), "co2_evitado": co2_i})

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

        with st.container(border=True):
            st.subheader("4. Productos")
            c1, c2, _ = st.columns([1,1,4])
            if c1.button("➕ Prod"): st.session_state.num_prods += 1; st.rerun()
            if c2.button("➖ Prod") and st.session_state.num_prods > 1: st.session_state.num_prods -= 1; st.rerun()

            lista_productos, t_pu, s_pr = [], 0, dc.get("productos", [])
            for i in range(st.session_state.num_prods):
                cp1, cp2, cp3, cp4 = st.columns([3, 2.5, 1.5, 3])
                pr = s_pr[i] if i < len(s_pr) else {}; nm = pr.get("producto", "")
                if nm and nm not in st.session_state.catalogo_productos: st.session_state.catalogo_productos.insert(-1, nm)
                
                sel = cp1.selectbox(f"Base {i+1}", st.session_state.catalogo_productos, index=st.session_state.catalogo_productos.index(nm) if nm in st.session_state.catalogo_productos else 0, key=f"ps_{i}")
                fnm = cp2.text_input("Nuevo", key=f"pn_{i}") if "Otro" in sel else sel
                c_u = cp3.number_input("Unid", min_value=0, value=int(pr.get("cantidad", 0)), key=f"pc_{i}")
                pf = cp4.file_uploader("Foto", type=["jpg", "png"], key=f"pf_{i}")
                if pf: cp4.image(pf, width=80)
                elif pr.get("foto_url"): cp4.image(pr.get("foto_url"), width=80)
                
                t_pu += c_u
                lista_productos.append({"producto": fnm, "cantidad": c_u, "foto_up": pf, "foto_url": pr.get("foto_url", "")})

        with st.container(border=True):
            st.subheader("5. Balance")
            ed_b = st.checkbox("✏️ Editar manual", value=dc.get("balance", {}).get("editar_manual", False))
            c1, c2, c3 = st.columns(3)
            mtr = c1.number_input("Transf (kg)", value=float(dc.get("balance", {}).get("mat_transformado", peso_tot * 0.8)), disabled=not ed_b)
            mre = c2.number_input("Retazos (kg)", value=float(dc.get("balance", {}).get("retazos_aprovechables", peso_tot * 0.1)), disabled=not ed_b)
            mpe = c3.number_input("Pérdida (kg)", value=float(dc.get("balance", {}).get("perdida_no_aprovechable", peso_tot * 0.1)), disabled=not ed_b)
            p_apr = ((mtr + mre)/peso_tot)*100 if peso_tot>0 else 0

        with st.container(border=True):
            st.subheader("6. Emisiones")
            c1, c2, c3, c4 = st.columns([2.5, 1.2, 1.8, 1.5])
            do = c1.selectbox("Origen", list(DISTANCIAS_LIMA_SJL.keys()))
            dk = c2.number_input("Km", value=float(dc.get("transporte", {}).get("distancia", DISTANCIAS_LIMA_SJL.get(do, 0))))
            tv = c3.selectbox("Vehículo", list(FACTORES_TRANSPORTE.keys()))
            tr = c4.selectbox("Viaje", ["Ida y Vuelta (2)", "Ida sola (1)"])
            
            emi_t = dk * (2 if "2" in tr else 1) * FACTORES_TRANSPORTE[tv]["consumo"] * FACTORES_TRANSPORTE[tv]["factor"]
            cb1, cb2 = st.columns(2)
            c_bord = cb1.number_input("Unid. Bordadas", min_value=0, value=int(dc.get("bordado", {}).get("cantidad", 0)))
            t_bord = cb2.selectbox("Tipo Bordado", list(FACTORES_BORDADO.keys()))
            emi_b = c_bord * FACTORES_BORDADO[t_bord]
            
            emi_tot = emi_t + (p_lav * 0.3) + (p_cor * 0.05) + emi_b; co2_neto = co2_tot - emi_tot

        with st.container(border=True):
            st.subheader("7. Horas Sociales")
            lista_op, t_h_op = [], 0.0
            for i, o in enumerate(PERSONAL_FIJO_OPERACIONES):
                c1, c2, c3, c4, c5 = st.columns([1.5, 2.5, 1, 1, 1])
                c1.markdown(f"**{o['rol']}**"); c2.markdown(o['nombre'])
                d = c3.number_input("Días", value=1, key=f"od_{i}"); h = c4.number_input("Hrs/D", value=4.0, key=f"oh_{i}")
                c5.text_input("Tot", value=f"{d*h}", disabled=True, key=f"ot_{i}")
                t_h_op += d*h; lista_op.append({"rol": o["rol"], "nombre": o["nombre"], "dias": d, "horas_dia": h, "horas_totales": d*h})
                
            lista_conf, t_h_cf, pers_u = [], 0.0, set()
            for i, pr in enumerate(lista_productos):
                st.markdown(f"📦 **{pr['producto']}** (Unid: {pr['cantidad']})")
                c1, c2, c3, c4, c5 = st.columns([1.8, 3, 1.4, 1.8, 1.8])
                sel_p = c2.selectbox("Resp.", st.session_state.lista_personal_confeccion, key=f"cr_{i}")
                unid = c3.number_input("U.", max_value=pr['cantidad'], value=pr['cantidad'], key=f"cu_{i}")
                t_u = c4.number_input("H.", value=estimar_tiempo_unidad(pr['producto']), step=0.05, key=f"ch_{i}")
                c5.text_input("T.", value=f"{unid*t_u:.2f}", disabled=True, key=f"ct_{i}")
                t_h_cf += unid*t_u; pers_u.add(sel_p)
                lista_conf.append({"producto": pr["producto"], "rol": "Confección", "persona": sel_p, "cantidad": unid, "tiempo_unitario": t_u, "horas_totales": unid*t_u})

        with st.container(border=True):
            st.subheader("8. Anexos")
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
                        buf = generar_pdf_oficial(cliente, ruc, proyecto_nom, codigo_proy, fe_inicio, fe_fin, responsable, area, "Textiles", "Upcycling", "kg", guia_remision, origen, destino, lista_items, lista_trazabilidad, lista_productos, mtr, mre, mpe, mtr+mre+mpe, p_apr, (mpe/peso_tot)*100 if peso_tot>0 else 0, lista_op, lista_conf, t_h_op+t_h_cf, len(PERSONAL_FIJO_OPERACIONES)+len(pers_u), co2_tot, emi_t, p_lav*0.3, p_cor*0.05, emi_b, lista_anexos)
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
