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
    KeepTogether,
)
from supabase import Client, create_client

# --- LIBRERÍAS DE GOOGLE DRIVE (OAUTH - CUENTA PERSONAL) ---
# Nota: se usa OAuth (no Cuenta de Servicio) porque las Cuentas de Servicio
# no tienen espacio de almacenamiento propio y no pueden subir archivos
# a un Google Drive personal (@gmail.com). Con OAuth, la app sube los
# archivos actuando como el usuario real dueño del Drive.
from google.oauth2.credentials import Credentials as UserCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- LIBRERÍAS DE GOOGLE DRIVE (OAUTH) ---
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

def _drive_service():
    """
    Crea y devuelve el servicio autenticado de Google Drive usando OAuth 2.0,
    leyendo el client_id, client_secret y refresh_token desde st.secrets.
    """
    if "drive_oauth" not in st.secrets or "folder_id" not in st.secrets:
        return None, None
        
    creds_data = st.secrets["drive_oauth"]
    credentials = Credentials(
        token=None,
        refresh_token=creds_data["refresh_token"],
        client_id=creds_data["client_id"],
        client_secret=creds_data["client_secret"],
        token_uri="https://oauth2.googleapis.com/token"
    )
    
    service = build('drive', 'v3', credentials=credentials)
    root_folder_id = st.secrets["folder_id"]
    return service, root_folder_id

def obtener_carpeta_destino_drive(cliente: str, fecha_fin_dt, nombre_subcarpeta: str):
    try:
        service, root_folder_id = _drive_service()
        if service is None:
            return None

        # --- 1. CARPETA MAESTRA: PEQUEÑOS DETALLES ---
        query_master = f"name='PEQUEÑOS DETALLES' and mimeType='application/vnd.google-apps.folder' and '{root_folder_id}' in parents and trashed=false"
        res_master = service.files().list(q=query_master, fields='files(id)').execute()
        
        if not res_master.get('files', []):
            carpeta_master = service.files().create(body={'name': 'PEQUEÑOS DETALLES', 'mimeType': 'application/vnd.google-apps.folder', 'parents': [root_folder_id]}, fields='id').execute()
            id_master = carpeta_master.get('id')
        else:
            id_master = res_master.get('files')[0].get('id')

        # --- 2. CARPETA DEL AÑO (Dentro de la maestra) ---
        nombre_carpeta_anio = str(fecha_fin_dt.year)
        query_anio = f"name='{nombre_carpeta_anio}' and mimeType='application/vnd.google-apps.folder' and '{id_master}' in parents and trashed=false"
        res_anio = service.files().list(q=query_anio, fields='files(id)').execute()
        
        if not res_anio.get('files', []):
            carpeta_anio = service.files().create(body={'name': nombre_carpeta_anio, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [id_master]}, fields='id').execute()
            id_anio = carpeta_anio.get('id')
        else:
            id_anio = res_anio.get('files')[0].get('id')

        # --- 3. CARPETA DEL MES ---
        meses = {1:"ENERO", 2:"FEBRERO", 3:"MARZO", 4:"ABRIL", 5:"MAYO", 6:"JUNIO", 7:"JULIO", 8:"AGOSTO", 9:"SETIEMBRE", 10:"OCTUBRE", 11:"NOVIEMBRE", 12:"DICIEMBRE"}
        nombre_carpeta_mes = meses.get(fecha_fin_dt.month, 'MES')
        query_mes = f"name='{nombre_carpeta_mes}' and mimeType='application/vnd.google-apps.folder' and '{id_anio}' in parents and trashed=false"
        res_mes = service.files().list(q=query_mes, fields='files(id)').execute()
        
        if not res_mes.get('files', []):
            carpeta_mes = service.files().create(body={'name': nombre_carpeta_mes, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [id_anio]}, fields='id').execute()
            id_mes = carpeta_mes.get('id')
        else:
            id_mes = res_mes.get('files')[0].get('id')

        # --- 4. CARPETA DEL CLIENTE ---
        nombre_cliente = cliente.strip().upper().replace("'", "")
        query_cli = f"name='{nombre_cliente}' and mimeType='application/vnd.google-apps.folder' and '{id_mes}' in parents and trashed=false"
        res_cli = service.files().list(q=query_cli, fields='files(id)').execute()
        
        if not res_cli.get('files', []):
            carpeta_cli = service.files().create(body={'name': nombre_cliente, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [id_mes]}, fields='id').execute()
            id_cli = carpeta_cli.get('id')
        else:
            id_cli = res_cli.get('files')[0].get('id')

        # --- 5. SUBCARPETA DEL PROYECTO ---
        query_proy = f"name='{nombre_subcarpeta}' and mimeType='application/vnd.google-apps.folder' and '{id_cli}' in parents and trashed=false"
        res_proy = service.files().list(q=query_proy, fields='files(id)').execute()
        
        if not res_proy.get('files', []):
            carpeta_proy = service.files().create(body={'name': nombre_subcarpeta, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [id_cli]}, fields='id').execute()
            id_proy = carpeta_proy.get('id')
        else:
            id_proy = res_proy.get('files')[0].get('id')

        return id_proy
    except Exception as e:
        st.session_state["_drive_last_error"] = f"Carpetas Drive: {e}"
        return None

def subir_a_drive(nombre_archivo: str, file_bytes: bytes, mime_type="application/pdf", custom_folder_id=None):
    try:
        service, root_folder_id = _drive_service()
        if service is None:
            st.session_state["_drive_last_error"] = (
                "Faltan credenciales de Drive en Secrets (google_credentials / folder_id)."
            )
            return None
        folder_id = custom_folder_id if custom_folder_id else root_folder_id
        
        file_metadata = {'name': nombre_archivo, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        
        archivo_subido = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return archivo_subido.get('id')
    except Exception as e:
        st.session_state["_drive_last_error"] = f"No se pudo subir '{nombre_archivo}': {e}"
        return None

# --- CONSTANTES GLOBALES ---
MESES_ESPANOL = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio", 7: "julio", 8: "agosto", 9: "setiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"}
MESES_ORDEN = [m.capitalize() for m in MESES_ESPANOL.values()]

PRODUCTOS_CATALOGO_BASE = [
    "Estrellas", "Cartuchera", "Cúbica", "Bolso", "Mochila", "Llavero", "Monedero", "Canguro", "Tote bag", "Neceser", 
    "Portalaptop", "Portacepillos", "Pelota", "Portacubierto", "Juguete", "Cubo", "Corazones", "Peluche", "Morral", 
    "Portaútiles", "Portabotella", "Cama perrito", "Colets", "Rombo", "Mandiles", "Lonchera", "Otro (Escribir nuevo producto)"
]

PERSONAL_CONFECCION_BASE = [
    "Celinda Gutierrez Delgado", "Guadalupe Guerra Cespedes", "Isabel Estrada Sandoval", "Carmen Cespedes Borda", 
    "Mavela Espinoza", "Juana Padilla Ruiz", "Felicita Sandoval Vilchez", "Luciana Jara Estrada", "Genaro Jara Garcia", 
    "Yovana Davila", "Katherine Hilario Vilca", "Rody Jara Rucana", "Lucila Campos", "Tiffany Landa Rios", "Sara Mallqui Herrada",
    "Erlith Paima", "Sonia Panduro Torres", "Cintya Rincon", "Dixie Hidalgo Martel", "Janeth Mescco Bautista", 
    "Judith Cueva Vargas", "Linfa Tauche", "Maricela Nieto", "Sofia Moya Reyes", "Carmen Vizarreta Lozada", 
    "Genoveva Vizarreta Lozada", "Gathy Perez Ortiz", "Omar Prada", "Yovana Davila Ramirez", "Rosario Evelin Blas Alcala",
    "Esmeralda Tandazo Briceño", "Jhoel Angel Dominguez Rementeria", "Pedro Estrada Ramos", "Victor Auccapuri San Miguel", 
    "Gabriel Manrique Hurtado", "Evelyn Prada Vizarreta", "Eugenia Almanza Huere", "Nicolle Estrada Yabe", 
    "Oswaldo Jara Garcia", "Noelia Gonzales Lopez"
]

TIEMPOS_CONFECCION_PURO = {
    "mochila": 0.60, "bolso": 0.45, "tote bag": 0.30, "portalaptop": 0.75, "canguro": 0.50, "neceser": 0.35, 
    "lonchera": 0.50, "cartuchera": 0.25, "morral": 0.50, "mandiles": 0.30, "cama perrito": 0.80, "cama": 0.80, 
    "casa": 0.80, "peluche": 0.60, "pelota": 0.30, "estrellas": 0.15, "corazones": 0.15, "rombo": 0.15, 
    "cúbica": 0.25, "cubo": 0.25, "llavero": 0.10, "monedero": 0.15, "portacepillos": 0.12, "portacubierto": 0.12, 
    "portaútiles": 0.20, "portabotella": 0.20, "colets": 0.08, "juguete": 0.40
}

def estimar_tiempo_unidad(nombre_producto: str) -> float:
    if not nombre_producto: return 0.35
    nombre_lower = nombre_producto.lower().strip()
    tiempo_costura = 0.40
    encontrado = False
    
    for prod_key, tiempo in TIEMPOS_CONFECCION_PURO.items():
        if prod_key in nombre_lower:
            tiempo_costura = tiempo; encontrado = True; break
            
    if not encontrado:
        if any(w in nombre_lower for w in ["casa", "cama", "colchón", "almohadón", "organizador"]): tiempo_costura = 0.80
        elif any(w in nombre_lower for w in ["mochila", "morral", "maletín", "set", "conjunto"]): tiempo_costura = 0.70
        elif any(w in nombre_lower for w in ["bolso", "tote", "lonchera", "funda", "delantal"]): tiempo_costura = 0.45
        elif any(w in nombre_lower for w in ["cartuchera", "neceser", "monedero", "estuche"]): tiempo_costura = 0.30
        else: tiempo_costura = 0.35

    if any(w in nombre_lower for w in ["gran", "grande", "maxi", "complejo", "completo", "xl", "pesado"]): tiempo_costura += 0.25
    elif any(w in nombre_lower for w in ["mini", "pequeño", "simple", "corto", "sencillo"]): tiempo_costura = max(0.10, tiempo_costura - 0.15)
        
    return round(max(0.10, tiempo_costura), 2)

FACTORES_CO2_BASE = {
    "Banner": 9.5, "Bata de laboratorio": 6.575, "Bolsas": 8.0, "Camisa": 6.575, "Camisa algodón": 5.0, "Camisa drill": 5.9, 
    "Camisa ignífuga": 5.35, "Camisa jean / denim": 5.0, "Camisaco": 5.0, "Camisaco drill": 5.9, "Camisaco drill con cinta": 6.25, 
    "Casaca": 6.575, "Casaca drill": 5.9, "Casaca polar": 6.0, "Casaca polar con cinta reflectiva": 6.3, "Casaca térmica": 6.1, 
    "Chaleco": 6.575, "Chaleco con cinta": 6.925, "Chaleco de seguridad": 9.75, "Chaleco Fluorescente": 9.625, "Chaleco polar": 6.0, 
    "Chaleco reversible": 9.5, "Chompa": 7.1, "Chompa con cinta reflectiva": 7.45, "Chompa Jorge Chavez": 6.0, 
    "Chompa Jorge Chavez con cinta reflectiva": 6.3, "Chompa polar": 6.0, "Enterizo": 6.575, "Gorro": 7.925, "Impermeable": 9.425, 
    "Mameluco": 6.575, "Mameluco acolchado": 5.825, "Mameluco drill": 5.9, "Mameluco jean reflectivo": 5.35, 
    "Merma de Acrílico / Dralon": 6.0, "Merma de Alfombra / Tapiz": 8.5, "Merma de Algodón": 5.0, "Merma de Cuerina (PU/PVC)": 7.5, 
    "Merma de Denim / Jean": 5.0, "Merma de Drill": 5.9, "Merma de Elastano / Spandex": 9.0, "Merma de Lana": 13.0, 
    "Merma de Lino": 6.5, "Merma de Nylon / Poliamida": 8.0, "Merma de Polar": 6.0, "Merma de Poliéster": 9.5, 
    "Merma de Seda": 14.0, "Merma de Viscosa / Rayón": 4.0,
    "Overol": 6.575, "Pantalón": 6.575, "Pantalón algodón": 5.0, "Pantalón drill": 5.9, "Pantalón drill con cinta": 6.25, 
    "Pantalón ignífugo": 5.35, "Pantalón jean": 5.0, "Pantalón jean / drill": 5.675, "Pantalón jean con cinta reflectiva": 5.35, 
    "Pantalón polar": 6.0, "Pantalón térmico": 6.0, "Polera": 5.0, "Polera polar": 6.0, "Polo": 6.8, "Polo algodón": 5.0, 
    "Polo con cinta reflectiva": 6.925, "Polo manga corta": 6.8, "Polo manga larga": 6.8, "Polo manga larga con cinta reflectiva": 6.7, 
    "Polo piqué": 5.0, "Short": 6.575, "Toalla": 5.0, "Otro": 6.575,
}

FACTORES_TRANSPORTE = {
    "Auto": {"consumo": 0.10, "factor": 2.31}, "Minivan": {"consumo": 0.12, "factor": 2.00}, "Mototaxi": {"consumo": 0.04, "factor": 2.31},
    "Moto": {"consumo": 0.03, "factor": 2.31}, "Camión mediano": {"consumo": 0.30, "factor": 2.68}, "Camión grande": {"consumo": 0.40, "factor": 2.68},
}

DISTANCIAS_LIMA_SJL = {
    "San Juan de Lurigancho (Local)": 4.0, "Ancón": 48.0, "Ate": 14.0, "Barranco": 18.5, "Bellavista (Callao)": 17.0, "Breña": 10.5, 
    "Callao (Cercado)": 18.0, "Carabayllo": 25.0, "Carmen de la Legua Reynoso (Callao)": 15.0, "Chaclacayo": 28.0, "Chorrillos": 22.0, 
    "Cieneguilla": 32.0, "Comas": 18.0, "El Agustino": 6.0, "Independencia": 12.0, "Jesús María": 12.0, "La Molina": 15.0, 
    "La Perla (Callao)": 18.0, "La Punta (Callao)": 21.0, "La Victoria": 9.5, "Lima (Cercado de Lima)": 9.0, "Lince": 12.5, 
    "Los Olivos": 15.0, "Lurigancho-Chosica": 36.0, "Lurín": 36.0, "Magdalena del Mar": 15.0, "Mi Perú (Callao)": 32.0, 
    "Miraflores": 16.0, "Pachacámac": 34.0, "Pucusana": 72.0, "Pueblo Libre": 13.5, "Puente Piedra": 28.0, "Punta Hermosa": 52.0, 
    "Punta Negra": 56.0, "Rímac": 7.5, "San Bartolo": 60.0, "San Borja": 12.0, "San Isidro": 13.5, "San Juan de Miraflores": 20.0, 
    "San Luis": 10.0, "San Martín de Porres": 13.0, "San Miguel": 15.5, "Santa Anita": 8.0, "Santa María del Mar": 63.0, 
    "Santa Rosa": 42.0, "Santiago de Surco": 17.0, "Surquillo": 14.5, "Ventanilla (Callao)": 30.0, "Villa El Salvador": 28.0, 
    "Villa María del Triunfo": 24.0, "Otro / Fuera de Lima (Ingreso manual)": 0.0,
}

FACTORES_BORDADO = {"Sin bordado / Ninguno": 0.0, "Estampado DTF": 0.020, "Simple (5 min/pieza)": 0.020, "Medio (9 min/pieza)": 0.037, "Complejo (10 min/pieza)": 0.041}

PERSONAL_FIJO_OPERACIONES = [
    {"rol": "Corte", "nombre": "Maria Isabel Estrada Sandoval"}, {"rol": "Corte", "nombre": "Genaro Jara García"},
    {"rol": "Corte", "nombre": "Luciana Jara estrada"}, {"rol": "Corte", "nombre": "Felicita Sandoval vilchez"},
    {"rol": "Corte", "nombre": "Nicolle Estrada"}, {"rol": "Logística", "nombre": "Evelyn Prada Vizarreta"},
]

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Pequeños Detalles - Sistema de Trazabilidad", page_icon="♻️", layout="wide")

# --- PALETA DINÁMICA SEGÚN EL ENTORNO ACTIVO ---
# "textil" (Pequeños Detalles) usa la paleta rosa; "circular" (ONG Mujer Power) usa la paleta morada.

PALETA_ROSA = {
    "BG_MAIN": "#FAF7F8",
    "ACCENT": "#D88C9A",
    "ACCENT_STRONG": "#C2185B",
    "ACCENT_STRONG_HOVER": "#A01249",
    "ACCENT_SOFT_BG": "#FCEEF1",
    "BG_SIDEBAR": "#FBF3F5",
    "BORDER_SOFT": "#EFE4E7",
    "APP_GRADIENT_START": "#F7EEF1",
    "HERO_GRADIENT_END": "#FDF4F6",
    "ACCENT_STRONG_2": "#A8134F",
    "SHADOW_RGB": "194, 24, 91",
    "FOCUS_RGB": "216, 140, 154",
}

PALETA_MORADA = {
    "BG_MAIN": "#F9F7FC",
    "ACCENT": "#A78BFA",
    "ACCENT_STRONG": "#7C3AED",
    "ACCENT_STRONG_HOVER": "#5B21B6",
    "ACCENT_SOFT_BG": "#F3EEFE",
    "BG_SIDEBAR": "#F5F1FC",
    "BORDER_SOFT": "#E6DFF7",
    "APP_GRADIENT_START": "#EFE6FB",
    "HERO_GRADIENT_END": "#F5F0FE",
    "ACCENT_STRONG_2": "#6D28D9",
    "SHADOW_RGB": "124, 58, 237",
    "FOCUS_RGB": "167, 139, 250",
}

_espacio_actual = st.session_state.get("espacio", "textil")
_autenticado_actual = st.session_state.get("autenticado", False)
_paleta_activa = PALETA_MORADA if (_autenticado_actual and _espacio_actual == "circular") else PALETA_ROSA

# --- ESTILOS CSS ---
_css_base = \
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');

    :root {
        --bg-main: %%BG_MAIN%%;
        --text-main: #2A2730;
        --text-soft: #756E78;
        --accent: %%ACCENT%%;
        --accent-strong: %%ACCENT_STRONG%%;
        --accent-strong-hover: %%ACCENT_STRONG_HOVER%%;
        --accent-soft-bg: %%ACCENT_SOFT_BG%%;
        --bg-sidebar: %%BG_SIDEBAR%%;
        --bg-card: #FFFFFF;
        --border-radius: 12px;
        --border-soft: %%BORDER_SOFT%%;
    }

/* Ocultar cabecera en PC, pero mostrar el menú hamburguesa en celulares */
    @media (min-width: 769px) {
        [data-testid="stHeader"] {visibility: hidden; height: 0px;}
    }
    @media (max-width: 768px) {
        [data-testid="stHeader"] {
            visibility: visible !important;
            background: transparent !important;
        }
        /* Blindar el icono de hamburguesa contra el modo oscuro */
        [data-testid="stHeader"] button, 
        [data-testid="stHeader"] svg, 
        [data-testid="stHeader"] path {
            color: var(--accent-strong) !important;
            stroke: var(--accent-strong) !important;
            fill: var(--accent-strong) !important;
        }
    }
    
    footer {visibility: hidden;}

    /* Forzar que todos los inputs sean blancos ignorando el modo oscuro del celular */
    div[data-baseweb="input"] input, 
    div[data-baseweb="number-input"] input,
    div[data-baseweb="select"],
    div[data-baseweb="textarea"] textarea {
        background-color: #FFFFFF !important;
        color: #2A2730 !important;
        -webkit-text-fill-color: #2A2730 !important;
    }

    .stApp {
        background: linear-gradient(180deg, %%APP_GRADIENT_START%% 0%, %%BG_MAIN%% 280px, %%BG_MAIN%% 100%);
    }

    div[data-testid="stNumberInput"] button { display: none !important; }
    div[data-testid="stNumberInput"] input { text-align: left; }

    /* ===== HERO / ENCABEZADO ===== */
    .hero-header {
        background: linear-gradient(135deg, #FFFFFF 0%, %%HERO_GRADIENT_END%% 100%);
        color: var(--text-main);
        padding: 26px 32px;
        border-radius: 18px;
        box-shadow: 0 10px 28px -12px rgba(%%SHADOW_RGB%%, 0.18);
        margin-bottom: 28px;
        border: 1px solid var(--border-soft);
        position: relative;
        overflow: hidden;
    }
    .hero-header::before {
        content: "";
        position: absolute;
        top: 0; left: 0;
        width: 6px; height: 100%;
        background: linear-gradient(180deg, var(--accent-strong), var(--accent));
    }
    .hero-header h1 {
        color: var(--accent-strong) !important;
        font-weight: 800;
        font-size: 1.75rem;
        letter-spacing: -0.3px;
        margin: 0;
    }
    .hero-header p {
        color: var(--text-soft) !important;
        margin: 6px 0 0 0;
        font-size: 0.95rem;
    }

    /* ===== SIDEBAR ===== */
    div[data-testid="stSidebar"] {
        background-color: var(--bg-sidebar) !important;
        border-right: 1px solid var(--border-soft);
        padding: 22px 12px;
    }

    .sidebar-section-title {
        color: var(--text-soft);
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        margin-top: 18px;
        margin-bottom: 10px;
        padding-left: 2px;
    }

    /* ===== CONTENEDORES / TARJETAS ===== */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: var(--bg-card) !important;
        border-radius: var(--border-radius) !important;
        border: 1px solid var(--border-soft) !important;
        box-shadow: 0 6px 18px -10px rgba(42, 39, 48, 0.12);
        transition: box-shadow 0.2s ease, border-color 0.2s ease, transform 0.15s ease;
        padding: 1.5rem !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 10px 24px -10px rgba(%%SHADOW_RGB%%, 0.18);
        border-color: var(--accent) !important;
    }

    /* ===== BOTONES ===== */
    /* Selectores múltiples para cubrir distintas versiones de Streamlit:
       - div[data-testid="stButton"] button  -> versiones más antiguas
       - button[data-testid^="stBaseButton"] -> versiones recientes (1.4x+)
       - button[kind]                        -> respaldo genérico */
    div[data-testid="stButton"] button,
    button[data-testid^="stBaseButton"],
    button[kind="secondary"],
    button[kind="secondaryFormSubmit"] {
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-family: 'Poppins', sans-serif !important;
        transition: all 0.15s ease !important;
        border: 1px solid var(--border-soft) !important;
        color: var(--text-main) !important;
        background-color: var(--bg-card) !important;
        box-shadow: none !important;
    }
    div[data-testid="stButton"] button:hover,
    button[data-testid^="stBaseButton"]:hover,
    button[kind="secondary"]:hover {
        border-color: var(--accent) !important;
        color: var(--accent-strong) !important;
        background-color: var(--accent-soft-bg) !important;
        transform: translateY(-1px);
    }
    div[data-testid="stButton"] button[kind="primary"],
    button[data-testid^="stBaseButton"][kind="primary"],
    button[kind="primary"],
    button[kind="primaryFormSubmit"] {
        background: linear-gradient(135deg, var(--accent-strong), %%ACCENT_STRONG_2%%) !important;
        border: none !important;
        color: #FFFFFF !important;
        box-shadow: 0 6px 16px -4px rgba(%%SHADOW_RGB%%, 0.4) !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover,
    button[data-testid^="stBaseButton"][kind="primary"]:hover,
    button[kind="primary"]:hover {
        box-shadow: 0 8px 20px -4px rgba(%%SHADOW_RGB%%, 0.5) !important;
        transform: translateY(-1px);
        color: #FFFFFF !important;
    }
    /* Asegura que el texto interno del botón herede el color, no un gris/azul por defecto */
    div[data-testid="stButton"] button p,
    button[data-testid^="stBaseButton"] p,
    button[kind] p {
        color: inherit !important;
        font-family: 'Poppins', sans-serif !important;
        font-weight: inherit !important;
    }

    /* Botones de navegación del sidebar: look tipo lista limpia */
    div[data-testid="stSidebar"] div[data-testid="stButton"] button,
    div[data-testid="stSidebar"] button[data-testid^="stBaseButton"] {
        text-align: left !important;
        justify-content: flex-start !important;
        background-color: transparent !important;
        border: 1px solid transparent !important;
        font-weight: 500 !important;
        padding: 0.5rem 0.75rem !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stButton"] button:hover,
    div[data-testid="stSidebar"] button[data-testid^="stBaseButton"]:hover {
        background-color: #FFFFFF !important;
        border-color: var(--border-soft) !important;
        transform: none;
    }
    div[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"],
    div[data-testid="stSidebar"] button[data-testid^="stBaseButton"][kind="primary"] {
        background: #FFFFFF !important;
        color: var(--accent-strong) !important;
        border: 1px solid var(--accent) !important;
        box-shadow: 0 2px 8px -2px rgba(%%SHADOW_RGB%%, 0.15) !important;
        font-weight: 700 !important;
    }

    /* ===== MÉTRICAS ===== */
    div[data-testid="stMetric"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border-soft);
        border-radius: var(--border-radius);
        padding: 16px 18px;
        box-shadow: 0 4px 12px -6px rgba(42, 39, 48, 0.1);
    }
    div[data-testid="stMetricLabel"] {
        color: var(--text-soft);
        font-weight: 600;
    }
    div[data-testid="stMetricValue"] {
        color: var(--accent-strong);
        font-weight: 800;
    }

    /* ===== INPUTS ===== */
    div[data-baseweb="input"],
    div[data-baseweb="select"] > div,
    div[data-baseweb="number-input"],
    div[data-baseweb="textarea"] {
        border-radius: 10px !important;
        border: 1px solid var(--border-soft) !important;
        background-color: #FFFFFF !important;
        transition: all 0.15s ease;
    }

    div[data-baseweb="input"]:focus-within,
    div[data-baseweb="select"] > div:focus-within,
    div[data-baseweb="number-input"]:focus-within,
    div[data-baseweb="textarea"]:focus-within {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px rgba(%%FOCUS_RGB%%, 0.22) !important;
    }

    label p {
        font-weight: 600 !important;
        color: var(--text-main) !important;
        font-size: 0.88rem !important;
    }

    h1, h2, h3, h4, h5, h6 { color: var(--text-main) !important; font-weight: 700 !important; }
    h3, h4, h5 { color: var(--accent-strong) !important; }

    /* Subtítulos con acento lateral, estilo más moderno */
    h3::before, h4::before {
        content: "";
        display: inline-block;
        width: 4px;
        height: 0.9em;
        background: linear-gradient(180deg, var(--accent-strong), var(--accent));
        border-radius: 3px;
        margin-right: 8px;
        vertical-align: middle;
    }

    hr {
        border: none !important;
        border-top: 1px solid var(--border-soft) !important;
        margin: 1.4rem 0 !important;
    }

    div[data-testid="stDataFrame"] {
        border-radius: var(--border-radius);
        overflow: hidden;
        border: 1px solid var(--border-soft);
    }

    div[data-testid="stAlertContainer"] {
        border-radius: var(--border-radius) !important;
        border: 1px solid var(--border-soft) !important;
    }

    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-thumb { background: var(--accent); border-radius: var(--border-radius); }
    ::-webkit-scrollbar-thumb:hover { background: var(--accent-strong); }

    /* ===== LOGIN ===== */
    .login-hero {
        text-align: center;
        padding: 56px 10px 28px 10px;
    }
    .login-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 64px;
        height: 64px;
        border-radius: 18px;
        background: linear-gradient(135deg, var(--accent-strong), %%ACCENT_STRONG_2%%);
        color: #FFFFFF;
        font-size: 1.9rem;
        box-shadow: 0 10px 24px -8px rgba(%%SHADOW_RGB%%, 0.45);
        margin-bottom: 18px;
    }
    .login-title {
        color: var(--text-main);
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin: 0 0 8px 0;
    }
    .login-subtitle {
        color: var(--text-soft);
        font-size: 0.98rem;
        line-height: 1.5;
        margin: 0;
    }
    .login-form-title {
        color: var(--accent-strong) !important;
        font-weight: 700 !important;
        font-size: 1.15rem !important;
        margin-bottom: 18px !important;
        padding-left: 12px;
        border-left: 4px solid var(--accent);
        border-radius: 2px;
    }

    /* Botón "Entorno de trabajo" tipo switch/pill */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        background-color: #FFFFFF;
        padding: 4px;
        border-radius: 12px;
        border: 1px solid var(--border-soft);
        gap: 4px !important;
        align-items: stretch !important;
    }
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div {
        display: flex !important;
    }
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button {
        border: none !important;
        border-radius: 9px !important;
        min-height: 52px !important;
        height: 100% !important;
        width: 100% !important;
        font-size: 0.82rem !important;
        line-height: 1.15 !important;
        white-space: normal !important;
        word-wrap: break-word;
        padding: 6px 8px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
    }
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button p {
        font-size: 0.82rem !important;
        line-height: 1.15 !important;
        white-space: normal !important;
        text-align: center !important;
    }
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:nth-child(2) button[kind="primary"] {
        background: linear-gradient(135deg, #7C3AED, #6D28D9) !important;
        border-color: #5B21B6 !important;
        color: white !important;
        box-shadow: none;
    }
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:nth-child(2) button[kind="primary"]:hover {
        background: linear-gradient(135deg, #6D28D9, #5B21B6) !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
    }
    </style>
"""

_css_final = _css_base
for _clave, _valor in _paleta_activa.items():
    _css_final = _css_final.replace(f"%%{_clave}%%", _valor)

st.markdown(_css_final, unsafe_allow_html=True)

# --- CONEXIÓN SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["SUPABASE_URL"]
    key = st.secrets["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except KeyError:
    st.error("⚠️ No se encontraron las credenciales de Supabase en `st.secrets`.")
    st.stop()
except Exception as e:
    st.error(f"⚠️ No se pudo conectar con Supabase: {e}")
    st.stop()

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

def _fecha_para_ordenar(fecha_str):
    """
    Convierte un texto de fecha (ej. '31/07/2026 - 18/08/2026' o '31/07/2026')
    en un datetime real para poder ordenar por la fecha MÁS RECIENTE,
    en vez de por el orden en que se insertó el registro en la base de datos.
    Si no se puede interpretar, devuelve la fecha mínima (va al final).
    """
    if not fecha_str:
        return datetime.datetime.min
    texto = str(fecha_str).strip()
    # Si es un rango "inicio - fin", usamos la fecha de FIN (la más reciente del proyecto)
    if " - " in texto:
        texto = texto.split(" - ")[-1].strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(texto, formato)
        except ValueError:
            continue
    return datetime.datetime.min

def cargar_proyectos(estado=None):
    try:
        query = supabase.table("proyectos").select("*").order('id', desc=True)
        if estado: query = query.eq("estado", estado)
        datos = query.execute().data
        # Ordenar siempre por la fecha real del proyecto (más reciente primero),
        # no por el orden de inserción (id), ya que "Carga Rápida Histórica"
        # puede registrar proyectos antiguos después de proyectos nuevos.
        datos.sort(key=lambda p: _fecha_para_ordenar(p.get("fecha")), reverse=True)
        return datos
    except Exception: return []

def eliminar_proyecto_bd(proyecto_id, codigo_proy):
    try:
        if proyecto_id: supabase.table("proyectos").delete().eq("id", proyecto_id).execute()
        elif codigo_proy: supabase.table("proyectos").delete().eq("codigo", codigo_proy).execute()
        return True
    except Exception: return False

@st.dialog("⚠️ Confirmar Eliminación Permanente")
def modal_confirmar_eliminacion(proyecto):
    st.warning(f"¿Estás seguro de que deseas eliminar permanentemente el proyecto **{proyecto.get('cliente', 'Sin Nombre')}** (`{proyecto.get('codigo', '')}`)?\n\nEsta acción **no se puede deshacer** y borrará todos los datos asociados de la base de datos.")
    col_confirm, col_cancel = st.columns(2)
    if col_confirm.button("Sí, Eliminar Definitivamente", use_container_width=True, type="primary"):
        if eliminar_proyecto_bd(proyecto.get("id"), proyecto.get("codigo")):
            st.session_state.proyecto_editar = {}
            st.session_state.form_version += 1
            st.toast("Proyecto eliminado con éxito.")
            st.rerun()
    if col_cancel.button("Cancelar", use_container_width=True): st.rerun()

@st.dialog("⚠️ Confirmar Eliminación Masiva")
def modal_confirmar_eliminacion_masiva(proyectos_a_borrar):
    st.warning(f"¿Estás seguro de que deseas eliminar permanentemente **{len(proyectos_a_borrar)}** proyectos seleccionados?\n\nEsta acción **no se puede deshacer** y borrará todos los datos asociados de la base de datos.")
    col_confirm, col_cancel = st.columns(2)
    if col_confirm.button("Sí, Eliminar Todos", use_container_width=True, type="primary"):
        for p in proyectos_a_borrar: eliminar_proyecto_bd(p.get("id"), p.get("codigo"))
        st.session_state.proyecto_editar = {}
        st.session_state.form_version += 1
        st.toast(f"{len(proyectos_a_borrar)} proyectos eliminados con éxito.")
        for p in proyectos_a_borrar:
            k = f"bulk_del_{p.get('id', p.get('codigo'))}"
            if k in st.session_state: del st.session_state[k]
        st.rerun()
    if col_cancel.button("Cancelar", use_container_width=True): st.rerun()

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
        self.drawCentredString(612 / 2.0, 22, "Promoviendo el desarrollo sostenible a través de la economía circular y el empoderamiento de mujeres")
        self.drawCentredString(612 / 2.0, 12, "emprendedoras")
        self.restoreState()

def generar_constancia_desde_plantilla_word(contexto: dict, ruta_plantilla=None) -> bytes:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cwd_dir = os.getcwd()
    posibles_rutas = [
        ruta_plantilla if ruta_plantilla else "",
        os.path.join(base_dir, "plantilla_constancia.docx"), os.path.join(cwd_dir, "plantilla_constancia.docx"),
        os.path.join(base_dir, "Constancia - Plantilla.docx"), os.path.join(cwd_dir, "Constancia - Plantilla.docx"),
        os.path.join(base_dir, "Plantilla_constancia.docx"), os.path.join(cwd_dir, "Plantilla_constancia.docx"),
    ]
    ruta_encontrada = None
    for r in posibles_rutas:
        if r and os.path.exists(r) and os.path.isfile(r) and os.path.getsize(r) > 0:
            ruta_encontrada = r; break
    if not ruta_encontrada:
        for f in os.listdir(base_dir):
            if f.lower().endswith(".docx") and not f.startswith("~"):
                candidato = os.path.join(base_dir, f)
                if os.path.getsize(candidato) > 0:
                    ruta_encontrada = candidato; break
    if not ruta_encontrada and os.path.exists(cwd_dir):
        for f in os.listdir(cwd_dir):
            if f.lower().endswith(".docx") and not f.startswith("~"):
                candidato = os.path.join(cwd_dir, f)
                if os.path.getsize(candidato) > 0:
                    ruta_encontrada = candidato; break
    if not ruta_encontrada: raise FileNotFoundError("No se encontró el archivo de plantilla Word (.docx)")

    doc = DocxTemplate(ruta_encontrada)
    doc.render(contexto)
    with tempfile.TemporaryDirectory() as tmpdir:
        docx_temp = os.path.join(tmpdir, "constancia_generada.docx")
        doc.save(docx_temp)
        subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", docx_temp, "--outdir", tmpdir], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        pdf_temp = os.path.join(tmpdir, "constancia_generada.pdf")
        if os.path.exists(pdf_temp) and os.path.getsize(pdf_temp) > 0:
            with open(pdf_temp, "rb") as f: return f.read()
        else: raise RuntimeError("Error al convertir DOCX a PDF con LibreOffice.")

# --- CARGA INTELIGENTE DE CATÁLOGOS DESDE SUPABASE ---
def inicializar_y_cargar_catalogos():
    try:
        res = supabase.table("catalogos").select("*").execute()
        datos = res.data
        
        if not datos:
            seed_data = []
            for k, v in FACTORES_CO2_BASE.items():
                seed_data.append({"tipo": "material_co2", "nombre": k, "valor_num": v})
            for p in PRODUCTOS_CATALOGO_BASE:
                if "Otro" not in p: seed_data.append({"tipo": "producto", "nombre": p, "valor_num": 0})
            for pers in PERSONAL_CONFECCION_BASE:
                if "Otro" not in pers: seed_data.append({"tipo": "personal", "nombre": pers, "valor_num": 0})
            
            for i in range(0, len(seed_data), 50):
                supabase.table("catalogos").insert(seed_data[i:i+50]).execute()
            
            res = supabase.table("catalogos").select("*").execute()
            datos = res.data

        materiales = {}
        productos = []
        personal = []
        
        for fila in datos:
            if fila["tipo"] == "material_co2": materiales[fila["nombre"]] = float(fila["valor_num"])
            elif fila["tipo"] == "producto": productos.append(fila["nombre"])
            elif fila["tipo"] == "personal": personal.append(fila["nombre"])
            
        nuevas_mermas = {
            "Merma de Acrílico / Dralon": 6.0, 
            "Merma de Alfombra / Tapiz": 8.5, 
            "Merma de Algodón": 5.0, 
            "Merma de Cuerina (PU/PVC)": 7.5, 
            "Merma de Denim / Jean": 5.0, 
            "Merma de Drill": 5.9, 
            "Merma de Elastano / Spandex": 9.0, 
            "Merma de Lana": 13.0, 
            "Merma de Lino": 6.5, 
            "Merma de Nylon / Poliamida": 8.0, 
            "Merma de Polar": 6.0,
            "Merma de Poliéster": 9.5, 
            "Merma de Seda": 14.0, 
            "Merma de Viscosa / Rayón": 4.0
        }
        mermas_a_insertar = []
        for k, v in nuevas_mermas.items():
            if k not in materiales:
                materiales[k] = v
                mermas_a_insertar.append({"tipo": "material_co2", "nombre": k, "valor_num": v})
        
        if mermas_a_insertar:
            try: supabase.table("catalogos").insert(mermas_a_insertar).execute()
            except: pass
        
        productos.sort()
        personal.sort()

        if "Otro (Escribir nuevo producto)" in productos: productos.remove("Otro (Escribir nuevo producto)")
        productos.append("Otro (Escribir nuevo producto)")

        return materiales, productos, personal
        
    except Exception as e:
        st.error(f"⚠️ Error de Supabase al cargar catálogos: {e}")
        return dict(FACTORES_CO2_BASE), list(PRODUCTOS_CATALOGO_BASE), list(PERSONAL_CONFECCION_BASE)

# --- GENERADOR DEL INFORME TÉCNICO COMPLETO (Oficial B2B) ---
def generar_pdf_oficial(
    cliente, ruc, proyecto_nom, codigo_proy, fe_inicio, fe_fin, responsable, area, tipo_material,
    valorizacion, unidad_medida, guia_remision, origen, destino, lista_items, lista_trazabilidad,
    lista_productos, mat_transformado, retazos_aprovechables, perdida_no_aprovechable, total_procesado,
    pct_aprovechamiento_total, pct_perdida, lista_operaciones_pdf, lista_confeccion, total_horas_social,
    total_personas_social, co2_evitado_total, emisiones_transporte, emisiones_lavado, emisiones_corte,
    emisiones_bordado, lista_anexos=None,
):
    kg_recibidos = sum([item["peso_total"] for item in lista_items])
    emisiones_proceso = emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado
    co2_neto = co2_evitado_total - emisiones_proceso
    total_prod_unidades = sum([p_item["cantidad"] for p_item in lista_productos])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, leftMargin=45, rightMargin=45, topMargin=45, bottomMargin=50
    )

    styles = getSampleStyleSheet()

    h1_style = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=16, textColor=colors.HexColor("#0F172A"), alignment=0, spaceAfter=4)
    sub_style = ParagraphStyle("Sub", parent=styles["Normal"], fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#64748B"), alignment=0, spaceAfter=20)
    h2_style = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, textColor=colors.HexColor("#1E3A8A"), spaceBefore=18, spaceAfter=8)
    
    cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, textColor=colors.HexColor("#334155"), leading=12)
    cell_bold = ParagraphStyle("CellB", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, textColor=colors.HexColor("#0F172A"), leading=12)
    
    card_val = ParagraphStyle("CardV", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=14, textColor=colors.HexColor("#0F172A"), alignment=1)
    card_lbl = ParagraphStyle("CardL", parent=styles["Normal"], fontName="Helvetica", fontSize=6.8, textColor=colors.HexColor("#64748B"), alignment=1, spaceBefore=2)

    modern_table_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")), 
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, colors.HexColor("#1E3A8A")), 
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#E2E8F0")), 
        ("PADDING", (0, 0), (-1, -1), 8),
    ])

    elements = []

    logo_path_png = "pequeños detalles logo.png"
    logo_path_jpg = "pequeños detalles logo.jpg"
    logo_img = None
    
    if os.path.exists(logo_path_png):
        try: logo_img = Image(logo_path_png, width=110, height=110, kind='proportional') 
        except: pass
    elif os.path.exists(logo_path_jpg):
        try: logo_img = Image(logo_path_jpg, width=110, height=110, kind='proportional') 
        except: pass

    titulo = Paragraph("INFORME TÉCNICO DE TRAZABILIDAD Y SOSTENIBILIDAD", h1_style)
    subtitulo = Paragraph(f"<b>Código de Proyecto:</b> {codigo_proy}<br/><b>Fecha de Emisión:</b> {datetime.date.today().strftime('%d/%m/%Y')}", sub_style)
    
    celda_texto = [titulo, subtitulo]

    if logo_img:
        logo_img.hAlign = 'RIGHT'
        t_header = Table([[celda_texto, logo_img]], colWidths=[412, 110])
        t_header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        elements.append(t_header)
        elements.append(Spacer(1, 15))
    else:
        elements.extend(celda_texto)
        elements.append(Spacer(1, 15))

    resumen_texto = f"""Este documento certifica el proceso de economía circular ejecutado para la empresa <b>{cliente}</b>. 
    Se transformaron exitosamente <b>{total_procesado:.2f} kg</b> de textiles en desuso mediante la metodología de upcycling, resultando en 
    <b>{total_prod_unidades}</b> nuevos productos. Este proyecto generó un impacto ambiental neto positivo de <b>{co2_neto:.2f} kg de CO2e evitados</b> 
    y fomentó el desarrollo social mediante <b>{total_horas_social:.1f} horas</b> de trabajo gestionadas por <b>{total_personas_social}</b> mujeres emprendedoras."""
    
    elements.append(Paragraph(resumen_texto, ParagraphStyle("Resumen", parent=styles["Normal"], fontName="Helvetica", fontSize=9.5, leading=14, alignment=4, textColor=colors.HexColor("#334155"), spaceAfter=15)))

    cards_data = [
        [Paragraph(f"{kg_recibidos:.2f} kg", card_val), Paragraph(f"{pct_aprovechamiento_total:.2f}%", card_val), Paragraph(f"{co2_neto:.2f} kg", card_val), Paragraph(f"{total_horas_social:.1f} hrs", card_val)],
        [Paragraph("MATERIAL RECUPERADO", card_lbl), Paragraph("TASA APROVECHAMIENTO", card_lbl), Paragraph("CO2e NETO EVITADO", card_lbl), Paragraph(f"TRABAJO GENERADO ({total_personas_social} PERS.)", card_lbl)],
    ]
    t_cards = Table(cards_data, colWidths=[130.5, 130.5, 130.5, 130.5]) 
    t_cards.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),   
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),  
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(t_cards)
    elements.append(Spacer(1, 10))

    bloque_1 = []
    bloque_1.append(Paragraph("1. FICHA TÉCNICA DEL PROYECTO", h2_style))
    data_ficha = [
        [Paragraph("Cliente / Razón Social:", cell_bold), Paragraph(f"{cliente} (RUC: {ruc})", cell_style)],
        [Paragraph("Periodo de Ejecución:", cell_bold), Paragraph(f"{fe_inicio} al {fe_fin}", cell_style)],
        [Paragraph("Tipo de Servicio:", cell_bold), Paragraph(proyecto_nom, cell_style)],
        [Paragraph("Punto de Origen:", cell_bold), Paragraph(origen, cell_style)],
        [Paragraph("Punto de Destino:", cell_bold), Paragraph(destino, cell_style)], 
        [Paragraph("Guía de Remisión:", cell_bold), Paragraph(guia_remision if guia_remision else "N/A", cell_style)],
        [Paragraph("Responsable Interno:", cell_bold), Paragraph(responsable, cell_style)],
    ]
    t_ficha = Table(data_ficha, colWidths=[140, 382])
    t_ficha.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    bloque_1.append(t_ficha)
    elements.append(KeepTogether(bloque_1))

    def obtener_imagen_pdf(foto_data, width, height):
        if foto_data is not None and foto_data != "":
            import urllib.request
            try:
                if isinstance(foto_data, str) and foto_data.startswith("http"):
                    req = urllib.request.Request(foto_data, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response: img_data = io.BytesIO(response.read())
                    return Image(img_data, width=width, height=height, kind='proportional') 
                elif hasattr(foto_data, 'read'):
                    foto_data.seek(0); img_data = io.BytesIO(foto_data.read()); foto_data.seek(0)
                    return Image(img_data, width=width, height=height, kind='proportional')
            except Exception: pass
        return Paragraph("Sin foto", cell_style)

    bloque_2 = []
    bloque_2.append(Paragraph("2. REGISTRO DE MATERIAL RECIBIDO", h2_style))
    data_prendas_pdf = [[Paragraph("Ítem", cell_bold), Paragraph("Descripción", cell_bold), Paragraph("Unidades", cell_bold), Paragraph("Peso (kg)", cell_bold), Paragraph("Evidencia", cell_bold)]]
    total_unidades_ingreso = 0
    for i, item in enumerate(lista_items, 1):
        total_unidades_ingreso += item["unidades"]
        img_cell = obtener_imagen_pdf(item["foto"], 80, 80)
        data_prendas_pdf.append([Paragraph(str(i), cell_style), Paragraph(item["descripcion"], cell_style), Paragraph(str(item["unidades"]), cell_style), Paragraph(f"{item['peso_total']:.2f} kg", cell_style), img_cell])

    data_prendas_pdf.append([Paragraph("<b>TOTAL</b>", cell_bold), "", Paragraph(f"<b>{total_unidades_ingreso}</b>", cell_bold), Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", cell_bold), ""])
    
    t_prendas = Table(data_prendas_pdf, colWidths=[40, 202, 70, 70, 140]) 
    estilo_prendas = list(modern_table_style._cmds)
    estilo_prendas.extend([("ALIGN", (2, 0), (3, -1), "CENTER"), ("SPAN", (0, -1), (1, -1))])
    t_prendas.setStyle(TableStyle(estilo_prendas))
    bloque_2.append(t_prendas)
    elements.append(KeepTogether(bloque_2))

    bloque_3 = []
    bloque_3.append(Paragraph("3. TRAZABILIDAD DE PROCESOS", h2_style))
    data_traza_pdf = [[Paragraph("Etapa", cell_bold), Paragraph("Fecha", cell_bold), Paragraph("Responsable", cell_bold), Paragraph("Peso", cell_bold), Paragraph("Evidencia", cell_bold)]]

    for t_item in lista_trazabilidad:
        if t_item.get("no_aplica"):
            data_traza_pdf.append([Paragraph(t_item["etapa"], cell_style), Paragraph("-", cell_style), Paragraph("No aplica", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style)])
        else:
            img_cell = obtener_imagen_pdf(t_item["foto"], 100, 75)
            data_traza_pdf.append([Paragraph(t_item["etapa"], cell_style), Paragraph(t_item["fecha"], cell_style), Paragraph(t_item["responsable"], cell_style), Paragraph(f"{t_item['peso']:.2f} kg", cell_style), img_cell])

    t_traza = Table(data_traza_pdf, colWidths=[90, 70, 142, 70, 150])
    estilo_traza = list(modern_table_style._cmds)
    estilo_traza.extend([("ALIGN", (3, 0), (3, -1), "CENTER")])
    t_traza.setStyle(TableStyle(estilo_traza))
    bloque_3.append(t_traza)
    elements.append(KeepTogether(bloque_3))

    bloque_4 = []
    bloque_4.append(Paragraph("4. PRODUCTOS ELABORADOS (UPCYCLING)", h2_style))
    data_prod_pdf = [[Paragraph("Producto Generado", cell_bold), Paragraph("Cantidad", cell_bold), Paragraph("Evidencia Fotográfica", cell_bold)]]

    for p_item in lista_productos:
        img_cell = obtener_imagen_pdf(p_item["foto"], 130, 100) 
        data_prod_pdf.append([Paragraph(p_item["producto"], cell_style), Paragraph(str(p_item["cantidad"]), cell_style), img_cell])

    data_prod_pdf.append([Paragraph("<b>TOTAL PRODUCTOS</b>", cell_bold), Paragraph(f"<b>{total_prod_unidades}</b>", cell_bold), ""])
    t_prod = Table(data_prod_pdf, colWidths=[200, 100, 222])
    estilo_prod = list(modern_table_style._cmds)
    estilo_prod.extend([("ALIGN", (1, 0), (1, -1), "CENTER")])
    t_prod.setStyle(TableStyle(estilo_prod))
    bloque_4.append(t_prod)
    elements.append(KeepTogether(bloque_4))

    bloque_5 = []
    bloque_5.append(Paragraph("5. BALANCE DE MATERIA Y ANÁLISIS DE EMISIONES (CO2e)", h2_style))
    
    col_izq = [
        [Paragraph("<b>Flujo de Materiales</b>", cell_bold), ""],
        [Paragraph("Material ingresado:", cell_style), Paragraph(f"{kg_recibidos:.2f} kg", cell_style)],
        [Paragraph("Transformado en productos:", cell_style), Paragraph(f"{mat_transformado:.2f} kg", cell_style)],
        [Paragraph("Retazos aprovechables:", cell_style), Paragraph(f"{retazos_aprovechables:.2f} kg", cell_style)],
        [Paragraph("Pérdida (Merma final):", cell_style), Paragraph(f"{perdida_no_aprovechable:.2f} kg", cell_style)],
        [Paragraph("<b>Aprovechamiento Total:</b>", cell_bold), Paragraph(f"<b>{pct_aprovechamiento_total:.2f}%</b>", cell_bold)],
    ]
    
    col_der = [
        [Paragraph("<b>Detalle de Emisiones</b>", cell_bold), ""],
        [Paragraph("Mitigación por Upcycling:", cell_style), Paragraph(f"+ {co2_evitado_total:.2f} kg CO2e", cell_style)],
        [Paragraph("Huella Logística (Transporte):", cell_style), Paragraph(f"- {emisiones_transporte:.2f} kg CO2e", cell_style)],
        [Paragraph("Huella Operativa (Corte/Lav):", cell_style), Paragraph(f"- {(emisiones_lavado + emisiones_corte):.2f} kg CO2e", cell_style)],
        [Paragraph("Huella Acabados (Bordado):", cell_style), Paragraph(f"- {emisiones_bordado:.2f} kg CO2e", cell_style)],
        [Paragraph("<b>Impacto Ambiental Neto:</b>", cell_bold), Paragraph(f"<b>{co2_neto:.2f} kg CO2e</b>", cell_bold)],
    ]
    
    t_balance = Table(col_izq, colWidths=[150, 111])
    t_emisiones = Table(col_der, colWidths=[150, 111])
    
    estilo_bloques = TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#1E3A8A")),
        ("LINEBELOW", (0, 1), (-1, -2), 0.5, colors.HexColor("#E2E8F0")),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#1E3A8A")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (1, 0), (1, -1), "RIGHT")
    ])
    
    t_balance.setStyle(estilo_bloques)
    t_emisiones.setStyle(estilo_bloques)
    
    t_master = Table([[t_balance, t_emisiones]], colWidths=[261, 261])
    t_master.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 0)]))
    bloque_5.append(t_master)
    bloque_5.append(Spacer(1, 15))

    equiv_agua = int(max(0, total_procesado * 2500))
    equiv_arboles = round(co2_neto / 22.0, 1) if co2_neto < 22 else int(max(0, co2_neto / 22.0))
    if equiv_arboles == 0: equiv_arboles = 0.1 
    equiv_plastico = int(max(0, co2_neto * 30))

    texto_equiv = f"""<b>¿Qué significa este impacto ambiental?</b><br/>
    El ahorro de {co2_neto:.2f} kg de CO2e y la recuperación de {total_procesado:.2f} kg de textiles logrados en este proyecto equivalen a:<br/>
    • <b>Fijación de Carbono:</b> El equivalente al CO2 que absorberían <b>{equiv_arboles} árboles maduros</b> durante un año entero.<br/>
    • <b>Materiales Vírgenes:</b> Evitar las emisiones equivalentes a fabricar <b>{equiv_plastico:,} bolsas de plástico</b> nuevas.<br/>
    • <b>Huella Hídrica:</b> Ahorrar aproximadamente <b>{equiv_agua:,} litros de agua</b> en el ecosistema mundial."""
    
    texto_equiv = texto_equiv.replace(',', '.') 

    t_equiv = Table([[Paragraph(texto_equiv, ParagraphStyle("Eq", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=14, textColor=colors.HexColor("#064E3B")))]], colWidths=[522])
    t_equiv.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ECFDF5")), 
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#34D399")),     
        ("PADDING", (0, 0), (-1, -1), 12),
    ]))
    bloque_5.append(t_equiv)
    elements.append(KeepTogether(bloque_5))

    bloque_6 = []
    bloque_6.append(Paragraph("6. MATRIZ DE IMPACTO SOCIAL", h2_style))
    data_ops_pdf = [[Paragraph("Colaborador/a", cell_bold), Paragraph("Rol Operativo", cell_bold), Paragraph("Horas Totales", cell_bold)]]
    
    for op in lista_operaciones_pdf:
        data_ops_pdf.append([Paragraph(str(op["nombre"]), cell_style), Paragraph(str(op["rol"]), cell_style), Paragraph(f"{op['horas_totales']:.2f} hrs", cell_style)])
        
    for c_item in lista_confeccion:
        data_ops_pdf.append([Paragraph(c_item["persona"], cell_style), Paragraph(f"{c_item['rol']} ({c_item['producto']})", cell_style), Paragraph(f"{c_item['horas_totales']:.2f} hrs", cell_style)])
        
    data_ops_pdf.append([Paragraph("<b>TOTAL TRABAJO GENERADO</b>", cell_bold), "", Paragraph(f"<b>{total_horas_social:.2f} horas</b>", cell_bold)])
    
    t_soc = Table(data_ops_pdf, colWidths=[200, 222, 100])
    estilo_soc = list(modern_table_style._cmds)
    estilo_soc.extend([("ALIGN", (2, 0), (2, -1), "CENTER"), ("SPAN", (0, -1), (1, -1))])
    t_soc.setStyle(TableStyle(estilo_soc))
    bloque_6.append(t_soc)
    elements.append(KeepTogether(bloque_6))

    anexos_validos = [a for a in (lista_anexos or []) if a.get("foto") or a.get("nota", "").strip()]
    if anexos_validos:
        elements.append(PageBreak())
        elements.append(Paragraph("7. REGISTRO FOTOGRÁFICO ADICIONAL", h2_style))
        elements.append(Paragraph("Evidencias visuales complementarias de la gestión en taller y detalle de productos.", sub_style))
        elements.append(Spacer(1, 10))
        
        for idx_a, anexo in enumerate(anexos_validos, 1):
            img_cell = obtener_imagen_pdf(anexo["foto"], width=480, height=270) 
            nota_texto = anexo["nota"].strip() if anexo["nota"].strip() else "Sin descripción adicional provista."
            card_data = [[img_cell], [Paragraph(f"<b>Nota Evidencia {idx_a}:</b> {nota_texto}", cell_style)]]
            t_card = Table(card_data, colWidths=[522])
            t_card.setStyle(TableStyle([
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING", (0, 0), (-1, -1), 10),
            ]))
            
            elements.append(KeepTogether([t_card]))
            
            if idx_a < len(anexos_validos):
                if idx_a % 2 == 0:
                    elements.append(PageBreak())
                    elements.append(Paragraph("7. REGISTRO FOTOGRÁFICO ADICIONAL (Cont.)", h2_style))
                    elements.append(Spacer(1, 10))
                else:
                    elements.append(Spacer(1, 25))

    doc.build(elements, canvasmaker=ReporteCanvas)
    return buffer.getvalue()
    # --- GENERADOR DEL MINI INFORME (PRODUCCIÓN INTERNA) ---
def generar_pdf_produccion_interna(
    cliente, codigo_proy, fe_inicio, fe_fin, responsable, lista_items, 
    lista_productos, mat_transformado, retazos_aprovechables, perdida_no_aprovechable, 
    total_procesado, pct_aprovechamiento_total, co2_neto, total_prod_unidades
):
    kg_recibidos = sum([item["peso_total"] for item in lista_items])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, leftMargin=45, rightMargin=45, topMargin=45, bottomMargin=50
    )

    styles = getSampleStyleSheet()

    h1_style = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=16, textColor=colors.HexColor("#0F172A"), alignment=0, spaceAfter=4)
    sub_style = ParagraphStyle("Sub", parent=styles["Normal"], fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#64748B"), alignment=0, spaceAfter=20)
    h2_style = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, textColor=colors.HexColor("#1E3A8A"), spaceBefore=18, spaceAfter=8)
    
    cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, textColor=colors.HexColor("#334155"), leading=12)
    cell_bold = ParagraphStyle("CellB", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, textColor=colors.HexColor("#0F172A"), leading=12)
    
    card_val = ParagraphStyle("CardV", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=14, textColor=colors.HexColor("#0F172A"), alignment=1)
    card_lbl = ParagraphStyle("CardL", parent=styles["Normal"], fontName="Helvetica", fontSize=6.8, textColor=colors.HexColor("#64748B"), alignment=1, spaceBefore=2)

    modern_table_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")), 
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, colors.HexColor("#1E3A8A")), 
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#E2E8F0")), 
        ("PADDING", (0, 0), (-1, -1), 8),
    ])

    elements = []

    logo_path_png = "pequeños detalles logo.png"
    logo_path_jpg = "pequeños detalles logo.jpg"
    logo_img = None
    
    if os.path.exists(logo_path_png):
        try: logo_img = Image(logo_path_png, width=110, height=110, kind='proportional') 
        except: pass
    elif os.path.exists(logo_path_jpg):
        try: logo_img = Image(logo_path_jpg, width=110, height=110, kind='proportional') 
        except: pass

    titulo = Paragraph("REPORTE TÉCNICO DE PRODUCCIÓN INTERNA", h1_style)
    subtitulo = Paragraph(f"<b>Código de Proyecto:</b> {codigo_proy}<br/><b>Fecha de Emisión:</b> {datetime.date.today().strftime('%d/%m/%Y')}", sub_style)
    
    celda_texto = [titulo, subtitulo]

    if logo_img:
        logo_img.hAlign = 'RIGHT'
        t_header = Table([[celda_texto, logo_img]], colWidths=[412, 110])
        t_header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        elements.append(t_header)
        elements.append(Spacer(1, 15))
    else:
        elements.extend(celda_texto)
        elements.append(Spacer(1, 15))

    resumen_texto = f"""Este documento resume la producción interna realizada por <b>{cliente}</b>. 
    Se utilizaron <b>{total_procesado:.2f} kg</b> de material, resultando en 
    <b>{total_prod_unidades}</b> nuevos productos manufacturados. El proceso evitó <b>{co2_neto:.2f} kg de CO2e</b>."""
    
    elements.append(Paragraph(resumen_texto, ParagraphStyle("Resumen", parent=styles["Normal"], fontName="Helvetica", fontSize=9.5, leading=14, alignment=4, textColor=colors.HexColor("#334155"), spaceAfter=15)))

    cards_data = [
        [Paragraph(f"{kg_recibidos:.2f} kg", card_val), Paragraph(f"{pct_aprovechamiento_total:.2f}%", card_val), Paragraph(f"{co2_neto:.2f} kg", card_val), Paragraph(f"{total_prod_unidades} unid", card_val)],
        [Paragraph("MATERIAL RECUPERADO", card_lbl), Paragraph("TASA APROVECHAMIENTO", card_lbl), Paragraph("CO2e EVITADO", card_lbl), Paragraph("PRODUCTOS GENERADOS", card_lbl)],
    ]
    t_cards = Table(cards_data, colWidths=[130.5, 130.5, 130.5, 130.5]) 
    t_cards.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),   
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),  
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(t_cards)
    elements.append(Spacer(1, 10))

    bloque_1 = []
    bloque_1.append(Paragraph("1. DATOS GENERALES", h2_style))
    data_ficha = [
        [Paragraph("Entidad:", cell_bold), Paragraph(f"{cliente} (RUC: {ruc})", cell_style)],
        [Paragraph("Periodo:", cell_bold), Paragraph(f"{fe_inicio} al {fe_fin}", cell_style)],
        [Paragraph("Responsable:", cell_bold), Paragraph(responsable, cell_style)],
    ]
    t_ficha = Table(data_ficha, colWidths=[140, 382])
    t_ficha.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    bloque_1.append(t_ficha)
    elements.append(KeepTogether(bloque_1))

    bloque_2 = []
    bloque_2.append(Paragraph("2. REGISTRO DE MATERIAL UTILIZADO", h2_style))
    data_prendas_pdf = [[Paragraph("Ítem", cell_bold), Paragraph("Descripción del Material / Merma", cell_bold), Paragraph("Unid.", cell_bold), Paragraph("Peso (kg)", cell_bold)]]
    total_unidades_ingreso = 0
    for i, item in enumerate(lista_items, 1):
        total_unidades_ingreso += item["unidades"]
        data_prendas_pdf.append([Paragraph(str(i), cell_style), Paragraph(item["descripcion"], cell_style), Paragraph(str(item["unidades"]), cell_style), Paragraph(f"{item['peso_total']:.2f} kg", cell_style)])

    data_prendas_pdf.append([Paragraph("<b>TOTAL</b>", cell_bold), "", Paragraph(f"<b>{total_unidades_ingreso}</b>", cell_bold), Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", cell_bold)])
    
    t_prendas = Table(data_prendas_pdf, colWidths=[40, 342, 70, 70]) 
    estilo_prendas = list(modern_table_style._cmds)
    estilo_prendas.extend([("ALIGN", (2, 0), (3, -1), "CENTER"), ("SPAN", (0, -1), (1, -1))])
    t_prendas.setStyle(TableStyle(estilo_prendas))
    bloque_2.append(t_prendas)
    elements.append(KeepTogether(bloque_2))

    def obtener_imagen_pdf(foto_data, width, height):
        if foto_data is not None and foto_data != "":
            import urllib.request
            try:
                if isinstance(foto_data, str) and foto_data.startswith("http"):
                    req = urllib.request.Request(foto_data, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response: img_data = io.BytesIO(response.read())
                    return Image(img_data, width=width, height=height, kind='proportional') 
                elif hasattr(foto_data, 'read'):
                    foto_data.seek(0); img_data = io.BytesIO(foto_data.read()); foto_data.seek(0)
                    return Image(img_data, width=width, height=height, kind='proportional')
            except Exception: pass
        return Paragraph("Sin foto", cell_style)

    bloque_4 = []
    bloque_4.append(Paragraph("3. SALIDA DE PRODUCTOS", h2_style))
    data_prod_pdf = [[Paragraph("Producto Generado", cell_bold), Paragraph("Cantidad", cell_bold), Paragraph("Evidencia Fotográfica", cell_bold)]]

    for p_item in lista_productos:
        img_cell = obtener_imagen_pdf(p_item["foto"], 130, 100) 
        data_prod_pdf.append([Paragraph(p_item["producto"], cell_style), Paragraph(str(p_item["cantidad"]), cell_style), img_cell])

    data_prod_pdf.append([Paragraph("<b>TOTAL PRODUCTOS</b>", cell_bold), Paragraph(f"<b>{total_prod_unidades}</b>", cell_bold), ""])
    t_prod = Table(data_prod_pdf, colWidths=[200, 100, 222])
    estilo_prod = list(modern_table_style._cmds)
    estilo_prod.extend([("ALIGN", (1, 0), (1, -1), "CENTER")])
    t_prod.setStyle(TableStyle(estilo_prod))
    bloque_4.append(t_prod)
    elements.append(KeepTogether(bloque_4))

    bloque_5 = []
    bloque_5.append(Paragraph("4. BALANCE DE MATERIA", h2_style))
    
    col_izq = [
        [Paragraph("<b>Flujo de Materiales</b>", cell_bold), ""],
        [Paragraph("Material ingresado:", cell_style), Paragraph(f"{kg_recibidos:.2f} kg", cell_style)],
        [Paragraph("Transformado en productos:", cell_style), Paragraph(f"{mat_transformado:.2f} kg", cell_style)],
        [Paragraph("Retazos aprovechables:", cell_style), Paragraph(f"{retazos_aprovechables:.2f} kg", cell_style)],
        [Paragraph("Pérdida (Merma final):", cell_style), Paragraph(f"{perdida_no_aprovechable:.2f} kg", cell_style)],
        [Paragraph("<b>Aprovechamiento Total:</b>", cell_bold), Paragraph(f"<b>{pct_aprovechamiento_total:.2f}%</b>", cell_bold)],
    ]
    
    t_balance = Table(col_izq, colWidths=[300, 222])
    
    estilo_bloques = TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#1E3A8A")),
        ("LINEBELOW", (0, 1), (-1, -2), 0.5, colors.HexColor("#E2E8F0")),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#1E3A8A")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (1, 0), (1, -1), "RIGHT")
    ])
    
    t_balance.setStyle(estilo_bloques)
    
    bloque_5.append(t_balance)
    bloque_5.append(Spacer(1, 15))

    doc.build(elements, canvasmaker=ReporteCanvas)
    return buffer.getvalue()


def generar_pdf_dashboard(df_fil, sel_anio, sel_mes, sel_cli, sel_tipo):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=45, rightMargin=45, topMargin=45, bottomMargin=50)
    styles = getSampleStyleSheet()
    
    h1_style = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=16, textColor=colors.HexColor("#1E293B"), alignment=0, spaceAfter=6)
    sub_style = ParagraphStyle("Sub", parent=styles["Normal"], fontName="Helvetica", fontSize=10, textColor=colors.HexColor("#64748B"), alignment=0, spaceAfter=20)
    h2_style = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, textColor=colors.HexColor("#0F172A"), spaceBefore=15, spaceAfter=8)
    cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#334155"), leading=10)
    cell_bold = ParagraphStyle("CellB", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, textColor=colors.HexColor("#0F172A"), leading=10)
    
    elements = []
    
    logo_path_png = "pequeños detalles logo.png"
    logo_path_jpg = "pequeños detalles logo.jpg"
    logo_img = None
    
    if os.path.exists(logo_path_png):
        try: logo_img = Image(logo_path_png, width=110, height=110, kind='proportional')
        except: pass
    elif os.path.exists(logo_path_jpg):
        try: logo_img = Image(logo_path_jpg, width=110, height=110, kind='proportional')
        except: pass

    if sel_mes == "Todos" and sel_anio != "Todos" and sel_cli == "Todos":
        titulo_str = f"MEMORIA ANUAL DE SOSTENIBILIDAD {sel_anio}"
        sub_str = "Reporte consolidado del impacto ambiental y social generado durante el año."
    elif sel_mes != "Todos" and sel_anio != "Todos" and sel_cli == "Todos":
        titulo_str = f"REPORTE MENSUAL DE SOSTENIBILIDAD - {sel_mes.upper()} {sel_anio}"
        sub_str = "Resumen del impacto ambiental y social generado en el mes seleccionado."
    else:
        titulo_str = "REPORTE EJECUTIVO DE SOSTENIBILIDAD"
        sub_str = f"Filtros: Año: {sel_anio} | Mes: {sel_mes} | Cliente: {sel_cli} | Tipo: {sel_tipo}"
        
    titulo = Paragraph(titulo_str, h1_style)
    subtitulo = Paragraph(sub_str, sub_style)
    
    celda_texto = [titulo, subtitulo]
    
    if logo_img:
        logo_img.hAlign = 'RIGHT'
        t_header = Table([[celda_texto, logo_img]], colWidths=[412, 110])
        t_header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        elements.append(t_header)
        elements.append(Spacer(1, 15))
    else:
        elements.extend(celda_texto)
    
    if df_fil.empty:
        elements.append(Paragraph("No hay datos para mostrar con los filtros seleccionados.", cell_style))
        doc.build(elements, canvasmaker=ReporteCanvas)
        return buffer.getvalue()
        
    kg_tot = df_fil['Kg Procesados'].sum()
    co2_tot = df_fil['CO₂ Evitado'].sum()
    hrs_tot = df_fil['Horas de Trabajo'].sum()
    prods_tot = df_fil['Productos Creados'].sum()
    unid_tot = df_fil['Unidades Recibidas'].sum()
    num_proyectos = len(df_fil)
    num_clientes = df_fil['Cliente'].nunique()
    
    bloque_1 = []
    bloque_1.append(Paragraph("1. RESUMEN DE IMPACTO GLOBAL", h2_style))
    data_metrics = [
        [Paragraph("<b>Total Proyectos</b>", cell_bold), Paragraph("<b>Clientes Únicos</b>", cell_bold), Paragraph("<b>Peso Procesado</b>", cell_bold)],
        [Paragraph(f"{num_proyectos}", cell_style), Paragraph(f"{num_clientes}", cell_style), Paragraph(f"{kg_tot:.2f} kg", cell_style)],
        [Paragraph("<b>CO2e Neto Evitado</b>", cell_bold), Paragraph("<b>Productos Creados</b>", cell_bold), Paragraph("<b>Horas Generadas</b>", cell_bold)],
        [Paragraph(f"{co2_tot:.2f} kg", cell_style), Paragraph(f"{int(prods_tot)} unid", cell_style), Paragraph(f"{hrs_tot:.2f} hrs", cell_style)]
    ]
    t_metrics = Table(data_metrics, colWidths=[174, 174, 174])
    t_metrics.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")
    ]))
    bloque_1.append(t_metrics)
    bloque_1.append(Spacer(1, 15))
    
    equiv_agua_dash = int(max(0, kg_tot * 2500))
    equiv_arboles_dash = round(co2_tot / 22.0, 1) if co2_tot < 22 else int(max(0, co2_tot / 22.0))
    if equiv_arboles_dash == 0: equiv_arboles_dash = 0.1 
    equiv_plastico_dash = int(max(0, co2_tot * 30))

    texto_equiv_dash = f"""<b>Equivalencias Ambientales</b><br/>
    El impacto total registrado en este periodo equivale a:<br/>
    • <b>Fijación de Carbono:</b> El equivalente al CO2 que absorberían <b>{equiv_arboles_dash} árboles maduros</b> durante un año entero.<br/>
    • <b>Materiales Vírgenes:</b> Evitar las emisiones equivalentes a fabricar <b>{equiv_plastico_dash:,} bolsas de plástico</b> nuevas.<br/>
    • <b>Huella Hídrica:</b> Ahorrar aproximadamente <b>{equiv_agua_dash:,} litros de agua</b> en el ecosistema mundial."""
    
    texto_equiv_dash = texto_equiv_dash.replace(',', '.') 

    t_equiv_dash = Table([[Paragraph(texto_equiv_dash, ParagraphStyle("Eq", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=14, textColor=colors.HexColor("#064E3B")))]], colWidths=[522])
    t_equiv_dash.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ECFDF5")), 
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#34D399")),     
        ("PADDING", (0, 0), (-1, -1), 12),
    ]))
    bloque_1.append(t_equiv_dash)
    elements.append(KeepTogether(bloque_1))
    
    top5 = df_fil.groupby("Cliente")["CO₂ Evitado"].sum().reset_index().sort_values(by="CO₂ Evitado", ascending=False).head(5)
    if not top5.empty:
        bloque_2 = []
        bloque_2.append(Paragraph("2. TOP CLIENTES POR IMPACTO AMBIENTAL (CO2e)", h2_style))
        data_t5 = [[Paragraph("Ranking", cell_bold), Paragraph("Cliente / Empresa", cell_bold), Paragraph("CO2e Evitado", cell_bold)]]
        for i, r in enumerate(top5.itertuples(), 1):
            data_t5.append([Paragraph(str(i), cell_style), Paragraph(str(r.Cliente), cell_style), Paragraph(f"{r._2:.2f} kg", cell_style)])
        t_top5 = Table(data_t5, colWidths=[60, 302, 160])
        t_top5.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("PADDING", (0, 0), (-1, -1), 6)
        ]))
        bloque_2.append(t_top5)
        elements.append(KeepTogether(bloque_2))
        
    bloque_3 = []
    bloque_3.append(Paragraph("3. DESGLOSE DE PROYECTOS", h2_style))
    data_proy = [[Paragraph("Cliente", cell_bold), Paragraph("Mes", cell_bold), Paragraph("Kg Procesados", cell_bold), Paragraph("CO2e Evitado", cell_bold), Paragraph("Horas", cell_bold)]]
    for idx, r in df_fil.iterrows():
        data_proy.append([
            Paragraph(str(r["Cliente"]), cell_style),
            Paragraph(str(r["Mes"]), cell_style),
            Paragraph(f"{r['Kg Procesados']:.1f}", cell_style),
            Paragraph(f"{r['CO₂ Evitado']:.1f}", cell_style),
            Paragraph(f"{r['Horas de Trabajo']:.1f}", cell_style)
        ])
    t_proy = Table(data_proy, colWidths=[172, 80, 80, 90, 100])
    t_proy.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 5)
    ]))
    bloque_3.append(t_proy)
    elements.append(KeepTogether(bloque_3))
    
    doc.build(elements, canvasmaker=ReporteCanvas)
    return buffer.getvalue()

# --- CONTROL DE ESTADO DE ESPACIO DE TRABAJO ---
if "espacio" not in st.session_state:
    st.session_state.espacio = "textil"

if "pestaña_activa_ong" not in st.session_state:
    st.session_state.pestaña_activa_ong = "Nuevo Registro"

if "num_items_ong" not in st.session_state:
    st.session_state.num_items_ong = 1

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "rol" not in st.session_state:
    st.session_state.rol = "operario"

if "pestaña_activa" not in st.session_state:
    st.session_state.pestaña_activa = "Nuevo Reporte PDF"

if "proyecto_editar" not in st.session_state:
    st.session_state.proyecto_editar = {}

if "form_version" not in st.session_state:
    st.session_state.form_version = 0

# --- INICIALIZACIÓN CATÁLOGOS CON CONEXIÓN A SUPABASE ---
if "catalogos_cargados" not in st.session_state:
    mats, prods, pers = inicializar_y_cargar_catalogos()
    st.session_state.factores_co2 = mats
    st.session_state.catalogo_productos = prods
    st.session_state.lista_personal_confeccion = pers
    st.session_state.catalogos_cargados = True

if "num_anexos" not in st.session_state:
    st.session_state.num_anexos = 1

if "documentos_descarga" not in st.session_state:
    st.session_state.documentos_descarga = None

if "pct_aprovechamiento_random" not in st.session_state:
    st.session_state.pct_aprovechamiento_random = round(random.uniform(0.88, 0.94), 4)

if "pct_transformado_ratio" not in st.session_state:
    st.session_state.pct_transformado_ratio = round(random.uniform(0.78, 0.83), 4)

if "uid_proyecto" not in st.session_state:
    st.session_state.uid_proyecto = str(random.randint(1000, 9999))

try:
    USUARIO_ADMIN = st.secrets["auth"]["ADMIN_USER"]
    PASSWORD_ADMIN = st.secrets["auth"]["ADMIN_PASS"]
    
    USUARIO_OPE = st.secrets["auth"]["OPERARIO_USER"]
    PASSWORD_OPE = st.secrets["auth"]["OPERARIO_PASS"]
    
    # Credenciales de Arfumm (puedes agregarlas en tu st.secrets o dejarlas fijas aquí por ahora)
    USUARIO_ARFUMM = st.secrets.get("auth", {}).get("ARFUMM_USER", "arfumm")
    PASSWORD_ARFUMM = st.secrets.get("auth", {}).get("ARFUMM_PASS", "trujillo2026")
except KeyError:
    st.error("⚠️ Faltan las credenciales de acceso en `st.secrets`.")
    st.stop()

if not st.session_state.autenticado:
    st.markdown(
        """
        <div style="text-align: center; padding: 40px 10px;">
            <h1 style="color: #1E293B; font-size: 2.2rem; font-weight: 800;">Pequeños Detalles</h1>
            <p style="color: #64748B; font-size: 1.1rem;">Gestión de Sostenibilidad y Trazabilidad Circular</p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            st.subheader("Iniciar Sesión")
            usuario_input = st.text_input("Usuario")
            password_input = st.text_input("Contraseña", type="password")

            if st.button("Ingresar al Sistema", use_container_width=True, type="primary"):
                if usuario_input == USUARIO_ADMIN and password_input == PASSWORD_ADMIN:
                    st.session_state.autenticado = True
                    st.session_state.rol = "admin"
                    st.success("¡Bienvenido Administrador!")
                    st.rerun()
                elif usuario_input == USUARIO_OPE and password_input == PASSWORD_OPE:
                    st.session_state.autenticado = True
                    st.session_state.rol = "operario"
                    st.success("¡Bienvenido al panel operativo!")
                    st.rerun()
                elif usuario_input == USUARIO_ARFUMM and password_input == PASSWORD_ARFUMM:
                    st.session_state.autenticado = True
                    st.session_state.rol = "aliado_arfumm"
                    st.session_state.espacio = "circular" # Los fuerza a entrar a la ONG
                    st.success("¡Bienvenido Equipo Arfumm - Trujillo!")
                    st.rerun()
                else:
                    st.error("⚠️ Usuario o contraseña incorrectos.")

else:
    proyectos_wip = cargar_proyectos("EN_PROCESO")

    with st.sidebar:
        # Si NO es Arfumm, mostramos los botones para cambiar de espacio
        if st.session_state.rol != "aliado_arfumm":
            st.markdown("### Entorno de Trabajo")
            col_w1, col_w2 = st.columns(2)
            if col_w1.button("Pequeños Detalles", use_container_width=True, type="primary" if st.session_state.espacio == "textil" else "secondary"):
                st.session_state.espacio = "textil"
                st.rerun()
            if col_w2.button("ONG Mujer Power", use_container_width=True, type="secondary" if st.session_state.espacio == "textil" else "primary"): 
                st.session_state.espacio = "circular"
                st.rerun()
            st.write("---")
        else:
            # Si ES Arfumm, ocultamos el acceso a Pequeños Detalles y mostramos su sede
            st.markdown("### Entorno de Trabajo")
            st.info("📍 Sede Aliada: **Arfumm Trujillo**")
            st.write("---")

        if st.session_state.espacio == "textil":
            rol_display = "Administrador" if st.session_state.rol == "admin" else "Operario"
            st.caption(f"Perfil activo: **{rol_display}**")
            
            st.markdown('<p class="sidebar-section-title">Navegación</p>', unsafe_allow_html=True)
    
            es_nuevo_activo = (st.session_state.pestaña_activa == "Nuevo Reporte PDF") and (not st.session_state.proyecto_editar)
            
            if st.button(
                "Nuevo Reporte PDF",
                use_container_width=True,
                type="primary" if es_nuevo_activo else "secondary",
            ):
                st.session_state.proyecto_editar = {}
                st.session_state.documentos_descarga = None
                st.session_state.pestaña_activa = "Nuevo Reporte PDF"
                st.session_state.uid_proyecto = str(random.randint(1000, 9999))
                st.session_state.form_version += 1 
                st.rerun()
    
            if st.button(
                "Producción Interna",
                use_container_width=True,
                type="primary" if st.session_state.pestaña_activa == "Producción Interna" else "secondary",
            ):
                st.session_state.documentos_descarga = None
                st.session_state.pestaña_activa = "Producción Interna"
                st.session_state.uid_proyecto = str(random.randint(1000, 9999))
                st.session_state.form_version += 1
                st.rerun()
                
            if st.button(
            "Producción desde 0",
            use_container_width=True,
            type="primary" if st.session_state.pestaña_activa == "Producción desde 0" else "secondary",
            ):
                st.session_state.documentos_descarga = None
                st.session_state.pestaña_activa = "Producción desde 0"
                st.session_state.uid_proyecto = str(random.randint(1000, 9999))
                st.session_state.form_version += 1
                st.rerun()
            
            if st.button(
                "Carga Rápida Histórica",
                use_container_width=True,
                type="primary" if st.session_state.pestaña_activa == "Carga Rápida Histórica" else "secondary",
            ):
                st.session_state.documentos_descarga = None
                st.session_state.pestaña_activa = "Carga Rápida Histórica"
                st.rerun()
    
            st.markdown('<p class="sidebar-section-title">Proyectos Pendientes</p>', unsafe_allow_html=True)
    
            if proyectos_wip:
                for p in proyectos_wip:
                    cli_nombre = p.get("cliente", "Sin Nombre")
                    label_btn = f"{cli_nombre}"
    
                    es_activo = st.session_state.proyecto_editar.get("id") == p.get("id") or st.session_state.proyecto_editar.get("codigo") == p.get("codigo")
    
                    if st.button(
                        label_btn,
                        key=f"side_proj_{p.get('id', p.get('codigo', ''))}",
                        use_container_width=True,
                        type="primary" if es_activo else "secondary",
                    ):
                        st.session_state.proyecto_editar = p
                        st.session_state.documentos_descarga = None
                        st.session_state.pestaña_activa = "Nuevo Reporte PDF"
                        st.session_state.form_version += 1 
                        st.rerun()
    
                st.write("")
                if st.button("Ver Lista en Proceso", use_container_width=True):
                    st.session_state.documentos_descarga = None
                    st.session_state.pestaña_activa = "Proyectos en Proceso"
                    st.rerun()
            else:
                st.caption("No hay proyectos en borrador")
    
            st.markdown('<p class="sidebar-section-title">Analítica e Histórico</p>', unsafe_allow_html=True)
    
            if st.button(
                "Dashboard Analítico",
                use_container_width=True,
                type="primary" if st.session_state.pestaña_activa == "Dashboard Analítico" else "secondary",
            ):
                st.session_state.documentos_descarga = None
                st.session_state.pestaña_activa = "Dashboard Analítico"
                st.rerun()
    
            if st.button(
                "Historial Completo",
                use_container_width=True,
                type="primary" if st.session_state.pestaña_activa == "Historial Completo" else "secondary",
            ):
                st.session_state.documentos_descarga = None
                st.session_state.pestaña_activa = "Historial Completo"
                st.rerun()
                
        # --- MENÚ EXCLUSIVO PARA LA ONG ---
        else:
            rol_display = "Administrador" if st.session_state.rol == "admin" else "Operario"
            st.caption(f"Perfil activo: **{rol_display}**")
            
            st.markdown('<p class="sidebar-section-title">Navegación Circular</p>', unsafe_allow_html=True)
            
            if st.button("Nuevo Registro", use_container_width=True, type="primary" if st.session_state.pestaña_activa_ong == "Nuevo Registro" else "secondary"):
                st.session_state.pestaña_activa_ong = "Nuevo Registro"
                st.session_state.doc_ong_descarga = None # Limpia descargas previas
                st.rerun()
            if st.button("Dashboard ONG", use_container_width=True, type="primary" if st.session_state.pestaña_activa_ong == "Dashboard ONG" else "secondary"):
                st.session_state.pestaña_activa_ong = "Dashboard ONG"
                st.rerun()
            if st.button("Historial ONG", use_container_width=True, type="primary" if st.session_state.pestaña_activa_ong == "Historial ONG" else "secondary"):
                st.session_state.pestaña_activa_ong = "Historial ONG"
                st.rerun()

        st.write("---")
        if st.session_state.rol == "admin":
            with st.expander("🔧 Diagnóstico de Secrets"):
                claves_secrets = list(st.secrets.keys())
                st.caption("Claves de nivel superior en st.secrets:")
                st.code("\n".join(claves_secrets) if claves_secrets else "(vacío — no se está leyendo ningún secret)")

                st.caption("Contenido dentro de cada sección (solo nombres, ningún valor):")
                for _clave_top in claves_secrets:
                    _valor_top = st.secrets[_clave_top]
                    if hasattr(_valor_top, "keys"):
                        sub_claves = list(_valor_top.keys())
                        st.write(f"**[{_clave_top}]** contiene:", ", ".join(sub_claves) if sub_claves else "(vacío)")
                    else:
                        st.write(f"**{_clave_top}** → valor suelto (no es una sección)")

                st.write("---")
                st.write("¿'drive_client_id' presente?:", "drive_client_id" in st.secrets)
                st.write("¿'drive_client_secret' presente?:", "drive_client_secret" in st.secrets)
                st.write("¿'drive_refresh_token' presente?:", "drive_refresh_token" in st.secrets)
                st.write("¿'folder_id' presente?:", "folder_id" in st.secrets)
        st.write("---")
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state.autenticado = False
            st.session_state.proyecto_editar = {}
            st.session_state.documentos_descarga = None
            st.rerun()
# =========================================================================
    # LÓGICA DEL ESPACIO DE TRABAJO: PEQUEÑOS DETALLES (TEXTIL)
    # =========================================================================
    if st.session_state.espacio == "textil":
        titulo_header = st.session_state.pestaña_activa
        if st.session_state.pestaña_activa == "Dashboard Analítico":
            titulo_header = "Dashboard Analítico"
            
        st.markdown(
            f"""
            <div class="hero-header">
                <h1>Sistema de Gestión Textil</h1>
                <p>Sección Activa: <b>{titulo_header}</b></p>
            </div>
        """,
            unsafe_allow_html=True,
        )
    
        if st.session_state.pestaña_activa == "Producción Interna":
            fv_int = st.session_state.form_version
            
            st.subheader("Registro: Producción Interna")
            st.caption("Reporte especializado para contabilizar creaciones propias, con ingreso de material, fotos de productos y un mini-informe PDF.")
    
            # --- SECCIÓN 1: DATOS GENERALES FIJOS ---
            with st.container(border=True):
                st.markdown("##### 1. Ficha General (Datos Fijos)")
                c1, c2, c5, c6 = st.columns(4)
                cliente_int = c1.text_input("Cliente / Empresa", value="PEQUEÑOS DETALLES HANDMADE PERU S.A.C.", disabled=True)
                ruc_int = c2.text_input("RUC", value="20602573771", disabled=True)
                fe_inicio_dt = c5.date_input("Fecha Inicio", format="DD/MM/YYYY", key=f"f_ini_int_v{fv_int}")
                fe_fin_dt = c6.date_input("Fecha Término", format="DD/MM/YYYY", key=f"f_fin_int_v{fv_int}")
    
                c4, c7 = st.columns(2)
                tipo_int = c4.text_input("Tipo de Proyecto", value="Producción Interna", disabled=True)
                
                RESPONSABLES_BASE = ["Evelyn Prada Vizarreta", "Gabriel Manrique Hurtado"]
                opciones_responsables = list(dict.fromkeys(RESPONSABLES_BASE))
                responsables_seleccionados = c7.multiselect("Responsable *", options=opciones_responsables, placeholder="Selecciona uno o más", key=f"resp_int_v{fv_int}")
                responsable_int = ", ".join(responsables_seleccionados) if responsables_seleccionados else "Equipo Interno"
                
                mes_fin_nombre = MESES_ESPANOL.get(fe_fin_dt.month, "MES").upper()
                codigo_proy = f"INT_{mes_fin_nombre}{fe_fin_dt.year}-{random.randint(1000, 9999)}"
    
            st.write("")
    
            # --- SECCIÓN 2: INGRESO DE MATERIAL (Rápido, sin fotos) ---
            with st.container(border=True):
                st.markdown("##### 2. Ingreso de Material")
                
                with st.expander("Administrar Catálogo de Materiales y Calcular CO₂e"):
                    tab_mat_add, tab_mat_del = st.tabs(["Agregar / Calcular Material", "Eliminar Material"])
    
                    with tab_mat_add:
                        st.caption("Puedes usar la calculadora de porcentajes, o activar la opción manual para ingresar un factor directo.")
                        modo_manual = st.checkbox("Ingresar factor CO₂e manualmente (para materiales puros o mermas nuevas)", key=f"chk_manual_mat_int_v{fv_int}")
                        
                        col_m1, col_m2, col_m3 = st.columns([2, 1, 1])
                        nuevo_mat = col_m1.text_input("Nombre de la Prenda/Material (Ej. Buzo)", key=f"mat_new_nom_int_v{fv_int}")
    
                        if modo_manual:
                            factor_final = col_m2.number_input("Factor CO₂e (kg) *", min_value=0.0, value=5.0, step=0.1, key=f"mat_manual_input_int_v{fv_int}")
                        else:
                            p1, p2, p3, p4 = st.columns(4)
                            p_alg = p1.number_input("% Algodón", min_value=0, max_value=100, value=65, key=f"mat_alg_int_v{fv_int}")
                            p_pol = p2.number_input("% Poliéster", min_value=0, max_value=100, value=35, key=f"mat_pol_int_v{fv_int}")
                            p_dra = p3.number_input("% Acríl/Dralon", min_value=0, max_value=100, value=0, key=f"mat_dra_int_v{fv_int}")
                            p_cin = p4.number_input("% Cinta Ref.", min_value=0, max_value=100, value=0, key=f"mat_cin_int_v{fv_int}")
    
                            factor_final = (p_alg * 5.0 + p_pol * 9.5 + p_dra * 6.0 + p_cin * 12.0) / 100
                            st.session_state[f"mat_calc_int_v{fv_int}"] = f"{factor_final:.3f} kg"
                            col_m2.text_input("Factor Calculado", disabled=True, key=f"mat_calc_int_v{fv_int}")
    
                        if col_m3.button("Guardar Material", use_container_width=True, key=f"btn_save_mat_int_v{fv_int}"):
                            if nuevo_mat.strip():
                                nombre_formateado = nuevo_mat.strip().capitalize()
                                try:
                                    supabase.table("catalogos").delete().eq("tipo", "material_co2").eq("nombre", nombre_formateado).execute()
                                    supabase.table("catalogos").insert({"tipo": "material_co2", "nombre": nombre_formateado, "valor_num": factor_final}).execute()
                                except Exception: pass
                                st.session_state.factores_co2[nombre_formateado] = factor_final
                                st.toast(f"✅ Material '{nombre_formateado}' guardado en la nube.")
                                st.rerun()
    
                    with tab_mat_del:
                        col_d1, col_d2 = st.columns([3, 1])
                        materiales_borrables = [m for m in st.session_state.factores_co2.keys() if m != "Banner"]
                        mat_a_borrar = col_d1.selectbox("Material a eliminar:", materiales_borrables, key=f"mat_sel_del_int_v{fv_int}")
                        if col_d2.button("Eliminar de la nube", use_container_width=True, key=f"btn_del_mat_int_v{fv_int}"):
                            if mat_a_borrar in st.session_state.factores_co2:
                                try: supabase.table("catalogos").delete().eq("tipo", "material_co2").eq("nombre", mat_a_borrar).execute()
                                except Exception: pass
                                del st.session_state.factores_co2[mat_a_borrar]
                                st.toast(f"Material eliminado de la nube: {mat_a_borrar}")
                                st.rerun()
    
                if "num_items_int" not in st.session_state:
                    st.session_state.num_items_int = 1
    
                col_btn1, col_btn2, _ = st.columns([1, 1, 4])
                if col_btn1.button("Agregar Ítem", key=f"add_it_int_v{fv_int}"):
                    st.session_state.num_items_int += 1
                    st.rerun()
                if col_btn2.button("Quitar Ítem", key=f"del_it_int_v{fv_int}") and st.session_state.num_items_int > 1:
                    st.session_state.num_items_int -= 1
                    st.rerun()
    
                lista_items_int = []
                peso_total_recibido = 0.0
                co2_evitado_total = 0.0
                total_piezas_ingresadas = 0
    
                opciones_prendas = sorted(list(st.session_state.factores_co2.keys()))
    
                for i in range(st.session_state.num_items_int):
                    st.markdown(f"**Material {i+1}**")
                    
                    col_desc, col_unid, col_peso, col_tot = st.columns([3, 1.5, 1.5, 1.5]) 
    
                    desc = col_desc.selectbox("Tipo de Material / Merma *", opciones_prendas, key=f"desc_int_{i}_v{fv_int}")
                    unid = col_unid.number_input("Ingreso (unid. aprox) *", min_value=0, value=1, key=f"unid_int_{i}_v{fv_int}")
    
                    p_total = col_peso.number_input("Peso Total (kg) *", min_value=0.0, value=0.0, step=0.05, key=f"tot_input_int_{i}_v{fv_int}")
                    
                    peso_u = p_total / unid if unid > 0 else 0.0
                    st.session_state[f"peso_u_int_{i}_v{fv_int}"] = f"{peso_u:.2f} kg"
                    col_tot.text_input("Peso Unitario", disabled=True, key=f"peso_u_int_{i}_v{fv_int}")
    
                    factor = st.session_state.factores_co2.get(desc, 6.575)
                    co2_item = p_total * factor
                    co2_evitado_total += co2_item
                    peso_total_recibido += p_total
                    total_piezas_ingresadas += unid
    
                    lista_items_int.append({
                        "descripcion": desc, "unidades": unid, "peso_unitario": peso_u, "peso_total": p_total, "co2_evitado": co2_item
                    })
    
                st.info(f"**Total Material Recibido:** {peso_total_recibido:.2f} kg | **CO₂ Evitado Calculado:** {co2_evitado_total:.2f} kg CO₂e")
    
            st.write("")
    
            # --- SECCIÓN 3: SALIDA DE PRODUCTOS (Con Fotos) ---
            with st.container(border=True):
                st.markdown("##### 3. Salida de Productos")
                
                with st.expander("Administrar Catálogo de Productos (Conectado a la Nube)"):
                    tab_p_add, tab_p_edit, tab_p_del = st.tabs(["Agregar Producto", "Modificar Nombre", "Eliminar de la Lista"])
    
                    with tab_p_add:
                        col_pa1, col_pa2 = st.columns([3, 1])
                        nuevo_producto_cat = col_pa1.text_input("Nombre del nuevo producto:", placeholder="Ej. Lote Llaveros", key=f"adm_prod_input_add_int_v{fv_int}")
                        if col_pa2.button("Guardar en Nube", use_container_width=True, key=f"btn_add_prod_cat_int_v{fv_int}"):
                            np_limpio = nuevo_producto_cat.strip()
                            if np_limpio and np_limpio not in st.session_state.catalogo_productos:
                                try: supabase.table("catalogos").insert({"tipo": "producto", "nombre": np_limpio, "valor_num": 0}).execute()
                                except Exception: pass
                                
                                if "Otro (Escribir nuevo producto)" in st.session_state.catalogo_productos:
                                    st.session_state.catalogo_productos.insert(-1, np_limpio)
                                else:
                                    st.session_state.catalogo_productos.append(np_limpio)
                                st.toast(f"✅ Producto guardado en la nube: {np_limpio}")
                                st.rerun()
    
                    with tab_p_edit:
                        col_pe1, col_pe2, col_pe3 = st.columns([2, 2, 1])
                        prods_editables = [p for p in st.session_state.catalogo_productos if "Otro" not in p]
                        prod_a_mod = col_pe1.selectbox("Producto a modificar:", prods_editables, key=f"adm_prod_sel_mod_int_v{fv_int}")
                        prod_modificado = col_pe2.text_input("Nombre corregido:", value=prod_a_mod if prod_a_mod else "", key=f"adm_prod_txt_mod_int_v{fv_int}")
                        if col_pe3.button("Actualizar", use_container_width=True, key=f"btn_edit_prod_cat_int_v{fv_int}"):
                            if prod_modificado.strip() and prod_a_mod in st.session_state.catalogo_productos:
                                try: supabase.table("catalogos").update({"nombre": prod_modificado.strip()}).eq("tipo", "producto").eq("nombre", prod_a_mod).execute()
                                except Exception: pass
                                
                                idx_mod = st.session_state.catalogo_productos.index(prod_a_mod)
                                st.session_state.catalogo_productos[idx_mod] = prod_modificado.strip()
                                st.toast(f"✅ Producto actualizado en la nube: {prod_modificado.strip()}")
                                st.rerun()
    
                    with tab_p_del:
                        col_pd1, col_pd2 = st.columns([3, 1])
                        prods_borrables = [p for p in st.session_state.catalogo_productos if "Otro" not in p]
                        prod_a_borrar = col_pd1.selectbox("Producto a eliminar del catálogo:", prods_borrables, key=f"adm_prod_sel_del_int_v{fv_int}")
                        if col_pd2.button("Eliminar", use_container_width=True, key=f"btn_del_prod_cat_int_v{fv_int}"):
                            if prod_a_borrar in st.session_state.catalogo_productos:
                                try: supabase.table("catalogos").delete().eq("tipo", "producto").eq("nombre", prod_a_borrar).execute()
                                except Exception: pass
                                
                                st.session_state.catalogo_productos.remove(prod_a_borrar)
                                st.toast(f"Producto eliminado de la nube: {prod_a_borrar}")
                                st.rerun()
    
                if "num_prods_int" not in st.session_state:
                    st.session_state.num_prods_int = 1
    
                col_btnp1, col_btnp2, _ = st.columns([1, 1, 4])
                if col_btnp1.button("Agregar Producto", key=f"add_p_int_v{fv_int}"):
                    st.session_state.num_prods_int += 1
                    st.rerun()
                if col_btnp2.button("Quitar Producto", key=f"del_p_int_v{fv_int}") and st.session_state.num_prods_int > 1:
                    st.session_state.num_prods_int -= 1
                    st.rerun()
    
                lista_productos_int = []
                total_prod_unid = 0
    
                for i in range(st.session_state.num_prods_int):
                    st.markdown(f"**Producto {i+1}**")
                    
                    col_psel, col_pnom_nuevo, col_pcant, col_pfoto = st.columns([3, 2.5, 1.5, 3])
    
                    prod_seleccionado = col_psel.selectbox("Seleccionar Producto Base *", st.session_state.catalogo_productos, key=f"prod_sel_int_{i}_v{fv_int}")
    
                    if prod_seleccionado == "Otro (Escribir nuevo producto)":
                        nuevo_nombre = col_pnom_nuevo.text_input("Escriba el Nuevo Producto *", key=f"prod_nuevo_txt_int_{i}_v{fv_int}")
                        nombre_final = nuevo_nombre.strip() if nuevo_nombre.strip() else f"Producto {i+1}"
                        if nuevo_nombre.strip() and nuevo_nombre.strip() not in st.session_state.catalogo_productos:
                            try: supabase.table("catalogos").insert({"tipo": "producto", "nombre": nuevo_nombre.strip(), "valor_num": 0}).execute()
                            except Exception: pass
                            st.session_state.catalogo_productos.insert(-1, nuevo_nombre.strip())
                    else:
                        st.session_state[f"prod_dis_int_{i}_v{fv_int}"] = prod_seleccionado
                        col_pnom_nuevo.text_input("Producto", disabled=True, key=f"prod_dis_int_{i}_v{fv_int}")
                        nombre_final = prod_seleccionado
    
                    p_cant = col_pcant.number_input("Cantidad (Unid.) *", min_value=0, value=1, key=f"prod_cant_int_{i}_v{fv_int}")
                    p_foto = col_pfoto.file_uploader("Evidencia Foto", type=["jpg", "png", "jpeg"], key=f"prod_foto_int_{i}_v{fv_int}")
    
                    if p_foto is not None:
                        col_pfoto.image(p_foto, width=80)
    
                    total_prod_unid += p_cant
                    lista_productos_int.append({
                        "producto": nombre_final, "cantidad": p_cant, "foto_up": p_foto, "foto_url": "", "foto": p_foto
                    })
    
                st.success(f"**Suma Total de Productos Obtenidos:** {total_prod_unid} unidades")
    
            st.write("")
    
            # --- SECCIÓN 4: BALANCE DE MATERIAL ---
            with st.container(border=True):
                st.markdown("##### 4. Balance de Material")
                
                pct_aprov_auto = st.session_state.pct_aprovechamiento_random
                pct_transf_auto = min(st.session_state.pct_transformado_ratio, pct_aprov_auto - 0.05)
                pct_retazos_auto = pct_aprov_auto - pct_transf_auto
    
                mat_transf_def = round(peso_total_recibido * pct_transf_auto, 2)
                retazos_def = round(peso_total_recibido * pct_retazos_auto, 2)
                perdida_def = round(peso_total_recibido - mat_transf_def - retazos_def, 2) if peso_total_recibido > 0 else 0.0
    
                editar_balance = st.checkbox("Editar balance manually", value=False, key=f"chk_edit_balance_int_v{fv_int}")
    
                col_bm1, col_bm2, col_bm3 = st.columns(3)
                mat_transformado = col_bm1.number_input("Transformado en productos (kg)", min_value=0.0, value=float(mat_transf_def), step=0.1, disabled=not editar_balance, key=f"bm_mat_transf_int_v{fv_int}")
                retazos_aprovechables = col_bm2.number_input("Retazos aprovechables (kg)", min_value=0.0, value=float(retazos_def), step=0.1, disabled=not editar_balance, key=f"bm_retazos_int_v{fv_int}")
                perdida_no_aprovechable = col_bm3.number_input("Pérdida (Merma final) (kg)", min_value=0.0, value=float(perdida_def), step=0.1, disabled=not editar_balance, key=f"bm_perdida_int_v{fv_int}")
    
                total_procesado = mat_transformado + retazos_aprovechables + perdida_no_aprovechable
    
                if peso_total_recibido > 0:
                    pct_aprovechamiento_total = ((mat_transformado + retazos_aprovechables) / peso_total_recibido) * 100
                else:
                    pct_aprovechamiento_total = 0.0
    
            st.write("")
            
            # --- BOTÓN DE GUARDADO + MINI PDF ---
            with st.container(border=True):
                st.markdown("##### Generar y Registrar")
                st.caption("Se guardará en tu base de datos, se generará el mini-reporte PDF con las fotos y se respaldará en Drive.")
                
                if st.button("Crear Reporte y Guardar en Dashboard", type="primary", use_container_width=True):
                    if peso_total_recibido <= 0:
                        st.error("⚠️ Debes ingresar al menos el peso del material utilizado.")
                    else:
                        with st.spinner("Generando Mini Reporte PDF y guardando fotos en la nube..."):
                            try:
                                import time
                                ts = int(time.time())
                                
                                prods_db = []
                                for idx, pr in enumerate(lista_productos_int):
                                    url = ""
                                    if pr["foto_up"] is not None:
                                        pr["foto_up"].seek(0)
                                        url = subir_imagen_supabase(f"fotos/{codigo_proy}/prod_int_{idx}_{ts}.jpg", pr["foto_up"].read())
                                    prods_db.append({
                                        "producto": pr["producto"], "cantidad": pr["cantidad"], "foto_url": url, "foto": pr["foto_up"]
                                    })
                                    pr["foto"] = pr["foto_up"] 
                                    
                                pdf_bytes = generar_pdf_produccion_interna(
                                    cliente_int, codigo_proy, fe_inicio_dt.strftime('%d/%m/%Y'), fe_fin_dt.strftime('%d/%m/%Y'), 
                                    responsable_int, lista_items_int, lista_productos_int, 
                                    mat_transformado, retazos_aprovechables, perdida_no_aprovechable, 
                                    total_procesado, pct_aprovechamiento_total, co2_evitado_total, total_prod_unid
                                )
                                
                                url_pdf = subir_pdf_supabase(f"Produccion_Interna_{codigo_proy}.pdf", pdf_bytes)
                                
                                st.session_state.pop("_drive_last_error", None)
                                try:
                                    nombre_subcarpeta = f"Prod_Interna {fe_fin_dt.strftime('%d-%m-%Y')} (PIN {st.session_state.uid_proyecto})"
                                    carpeta_id = obtener_carpeta_destino_drive(cliente_int, fe_fin_dt, nombre_subcarpeta)
                                    subir_a_drive(f"Reporte_Interno_{codigo_proy}.pdf", pdf_bytes, "application/pdf", custom_folder_id=carpeta_id)
                                except Exception as e_drive:
                                    st.session_state["_drive_last_error"] = str(e_drive)
                                drive_error_int = st.session_state.pop("_drive_last_error", None)
                                
                                datos_completado = {
                                    "codigo": codigo_proy,
                                    "cliente": cliente_int,
                                    "ruc": ruc_int,
                                    "tipo_proyecto": tipo_int,
                                    "responsable": responsable_int,
                                    "fecha": f"{fe_inicio_dt.strftime('%d/%m/%Y')} - {fe_fin_dt.strftime('%d/%m/%Y')}",
                                    "estado": "COMPLETADO",
                                    "peso_recibido": peso_total_recibido,
                                    "peso_transformado": mat_transformado,
                                    "aprovechamiento": pct_aprovechamiento_total,
                                    "co2_neto": co2_evitado_total,
                                    "horas_totales": 0.0,
                                    "productos_unids": total_prod_unid,
                                    "punto_origen": "Taller Interno",
                                    "pdf_url": url_pdf,
                                    "constancia_url": "",
                                    "datos_completos": {
                                        "unidades_recibidas": total_piezas_ingresadas,
                                        "participantes": 0,
                                        "items": lista_items_int,
                                        "productos": prods_db,
                                        "balance": {
                                            "mat_transformado": mat_transformado,
                                            "retazos_aprovechables": retazos_aprovechables,
                                            "perdida_no_aprovechable": perdida_no_aprovechable
                                        }
                                    }
                                }
                                
                                supabase.table("proyectos").insert(datos_completado).execute()
                                
                                st.session_state.num_items_int = 1
                                st.session_state.num_prods_int = 1
                                st.session_state.form_version += 1
                                
                                st.session_state.documentos_descarga = {
                                    "bytes_informe": pdf_bytes,
                                    "nombre_archivo": f"Reporte_Interno_{codigo_proy}.pdf",
                                    "drive_error": drive_error_int,
                                }
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"❌ Error al procesar: {e}")
                                
            if st.session_state.documentos_descarga and "nombre_archivo" in st.session_state.documentos_descarga:
                docs = st.session_state.documentos_descarga
                if docs.get("drive_error"):
                    st.warning(f"⚠️ El reporte se generó y guardó correctamente, pero NO se pudo respaldar en Google Drive. Detalle: {docs['drive_error']}")
                else:
                    st.success("¡Éxito! Tu producción interna ha sido registrada oficialmente y el reporte generado.")
                st.balloons()
                st.download_button("Descargar Mini-Reporte PDF", data=docs["bytes_informe"], file_name=docs["nombre_archivo"], mime="application/pdf", use_container_width=True, type="primary")
    # =========================================================================
    # NUEVO MÓDULO: PRODUCCIÓN DESDE 0 (IMPACTO SOCIAL)
    # =========================================================================
        elif st.session_state.pestaña_activa == "Producción desde 0":
                fv_p0 = st.session_state.form_version
                
                st.subheader("Registro: Producción desde 0 (Impacto Social)")
                st.caption("Módulo exclusivo para contabilizar la fabricación con tela virgen. Registra las prendas y genera una constancia enfocada 100% en las horas de trabajo social (sin contabilizar mitigación de CO₂e).")
        
                # --- SECCIÓN 1: DATOS GENERALES ---
                with st.container(border=True):
                    st.markdown("##### 1. Ficha General")
                    c1, c2, c5, c6 = st.columns(4)
                    cliente_p0 = c1.text_input("Cliente / Empresa *", key=f"cli_p0_v{fv_p0}")
                    ruc_p0 = c2.text_input("RUC * (11 dígitos)", max_chars=11, key=f"ruc_p0_v{fv_p0}")
                    fe_inicio_dt = c5.date_input("Fecha Inicio", format="DD/MM/YYYY", key=f"f_ini_p0_v{fv_p0}")
                    fe_fin_dt = c6.date_input("Fecha Término", format="DD/MM/YYYY", key=f"f_fin_p0_v{fv_p0}")
        
                    c4, c7 = st.columns(2)
                    tipo_p0 = c4.text_input("Tipo de Proyecto", value="PRODUCCIÓN DESDE CERO", disabled=True)
                    
                    RESPONSABLES_BASE = ["Evelyn Prada Vizarreta", "Gabriel Manrique Hurtado"]
                    opciones_responsables = list(dict.fromkeys(RESPONSABLES_BASE))
                    responsables_seleccionados = c7.multiselect("Responsable *", options=opciones_responsables, placeholder="Selecciona uno o más", key=f"resp_p0_v{fv_p0}")
                    responsable_p0 = ", ".join(responsables_seleccionados) if responsables_seleccionados else "Equipo Interno"
                    
                    mes_fin_nombre = MESES_ESPANOL.get(fe_fin_dt.month, "MES").upper()
                    str_empresa = cliente_p0.strip() if cliente_p0.strip() else "EMPRESA"
                    cliente_clean = re.sub(r'[^a-zA-Z0-9]', '', str_empresa).upper()[:8]
                    codigo_proy = f"P0_{cliente_clean}_{mes_fin_nombre}{fe_fin_dt.year}-{random.randint(1000, 9999)}"
        
                st.write("")
        
                # --- SECCIÓN 2: SALIDA DE PRODUCTOS ---
                with st.container(border=True):
                    st.markdown("##### 2. Catálogo de Productos Fabricados")
                    
                    if "num_prods_p0" not in st.session_state:
                        st.session_state.num_prods_p0 = 1
        
                    col_btnp1, col_btnp2, _ = st.columns([1, 1, 4])
                    if col_btnp1.button("Agregar Producto", key=f"add_p_p0_v{fv_p0}"):
                        st.session_state.num_prods_p0 += 1
                        st.rerun()
                    if col_btnp2.button("Quitar Producto", key=f"del_p_p0_v{fv_p0}") and st.session_state.num_prods_p0 > 1:
                        st.session_state.num_prods_p0 -= 1
                        st.rerun()
        
                    lista_productos_p0 = []
                    total_prod_unid = 0
        
                    for i in range(st.session_state.num_prods_p0):
                        col_psel, col_pnom_nuevo, col_pcant = st.columns([3, 2.5, 1.5])
        
                        prod_seleccionado = col_psel.selectbox(f"Producto {i+1} *", st.session_state.catalogo_productos, key=f"prod_sel_p0_{i}_v{fv_p0}")
        
                        if prod_seleccionado == "Otro (Escribir nuevo producto)":
                            nuevo_nombre = col_pnom_nuevo.text_input("Escriba el Nuevo Producto *", key=f"prod_nuevo_txt_p0_{i}_v{fv_p0}")
                            nombre_final = nuevo_nombre.strip() if nuevo_nombre.strip() else f"Producto {i+1}"
                        else:
                            st.session_state[f"prod_dis_p0_{i}_v{fv_p0}"] = prod_seleccionado
                            col_pnom_nuevo.text_input("Nombre Seleccionado", disabled=True, key=f"prod_dis_p0_{i}_v{fv_p0}")
                            nombre_final = prod_seleccionado
        
                        p_cant = col_pcant.number_input("Cantidad (Unid.) *", min_value=0, value=1, key=f"prod_cant_p0_{i}_v{fv_p0}")
        
                        total_prod_unid += p_cant
                        lista_productos_p0.append({
                            "producto": nombre_final, "cantidad": p_cant
                        })
        
                    st.info(f"**Total de Unidades a Fabricar:** {total_prod_unid} unidades")
        
                st.write("")
        
                # --- SECCIÓN 3: IMPACTO SOCIAL (MATRIZ) ---
                with st.container(border=True):
                    st.markdown("##### 3. Equipo de Trabajo y Generación de Horas (Impacto Social)")
                    st.caption("Asigna los tiempos de trabajo manual de corte, logística y confección.")
        
                    st.markdown("#### A. Operaciones – Corte y Logística")
                    lista_operaciones_p0 = []
                    total_horas_ops = 0.0
        
                    h_col1, h_col2, h_col3, h_col4, h_col5, h_col6 = st.columns([1.5, 2.5, 0.8, 1.2, 1.2, 1.2])
                    h_col1.markdown("**Rol**")
                    h_col2.markdown("**Nombre**")
                    h_col3.markdown("**Editar**")
                    h_col4.markdown("**Días**")
                    h_col5.markdown("**Hrs/día**")
                    h_col6.markdown("**Total**")
                    st.write("---")
        
                    for idx, p_fijo in enumerate(PERSONAL_FIJO_OPERACIONES):
                        c_rol, c_nom, c_chk, c_dias, c_hdia, c_tot = st.columns([1.5, 2.5, 0.8, 1.2, 1.2, 1.2])
        
                        rol_val = p_fijo["rol"]
                        c_rol.text_input("Rol", value=rol_val, disabled=True, key=f"ops_rol_p0_{idx}_v{fv_p0}", label_visibility="collapsed")
        
                        editar_fila = c_chk.checkbox("✅", value=False, key=f"ops_chk_p0_{idx}_v{fv_p0}", label_visibility="collapsed")
                        nom_val = c_nom.text_input("Nombre", value=p_fijo["nombre"], disabled=not editar_fila, key=f"ops_nom_p0_{idx}_v{fv_p0}", label_visibility="collapsed")
        
                        val_dias = c_dias.number_input("Días", min_value=0, value=0, step=1, disabled=not editar_fila, key=f"ops_dias_p0_{idx}_v{fv_p0}", label_visibility="collapsed")
                        val_hdia = c_hdia.number_input("Hrs/Día", min_value=0.0, value=0.0, step=0.5, disabled=not editar_fila, key=f"ops_hdia_p0_{idx}_v{fv_p0}", label_visibility="collapsed")
        
                        tot_hrs_pers = float(val_dias) * float(val_hdia)
                        c_tot.text_input("Total", value=f"{tot_hrs_pers:.2f}", disabled=True, key=f"ops_tot_p0_{idx}_v{fv_p0}", label_visibility="collapsed")
        
                        total_horas_ops += tot_hrs_pers
                        lista_operaciones_p0.append({
                            "rol": rol_val, "nombre": nom_val, "dias": val_dias, "horas_dia": val_hdia, "horas_totales": tot_hrs_pers
                        })
        
                    st.write("---")
                    st.markdown("#### B. Confección y Acabado (Base IA)")
        
                    lista_confeccion_p0 = []
                    horas_confeccion_total = 0.0
        
                    for idx, prod in enumerate(lista_productos_p0):
                        p_nom = prod["producto"]
                        p_cant = prod["cantidad"]
                        tiempo_base_ia = estimar_tiempo_unidad(p_nom)
        
                        st.markdown(f"**Producto {idx+1}: {p_nom}** *(Cantidad: {p_cant} unid | Estimado IA: {tiempo_base_ia:.2f} hrs/unid)*")
        
                        key_num_pers = f"num_pers_p0_prod_{idx}"
                        if key_num_pers not in st.session_state:
                            st.session_state[key_num_pers] = 1
        
                        col_b1, col_b2, _ = st.columns([1.5, 1.5, 5])
                        if col_b1.button("Añadir Persona", key=f"add_pers_p0_{idx}"):
                            st.session_state[key_num_pers] += 1
                            st.rerun()
                        if col_b2.button("Quitar Persona", key=f"del_pers_p0_{idx}") and st.session_state[key_num_pers] > 1:
                            st.session_state[key_num_pers] -= 1
                            st.rerun()
        
                        for p_idx in range(st.session_state[key_num_pers]):
                            c_rol, c_persona, c_cant_asig, c_tiempo, c_tot = st.columns([1.8, 3.0, 1.4, 1.8, 1.8])
                            
                            rol_sel = c_rol.selectbox("Rol *", ["Confección", "Acabado", "Entretela", "Estampado"], key=f"soc_rol_p0_{idx}_{p_idx}_v{fv_p0}")
                            persona_sel = c_persona.selectbox("Operaria *", st.session_state.lista_personal_confeccion, key=f"soc_pers_sel_p0_{idx}_{p_idx}_v{fv_p0}")
                            
                            cant_sugerida = max(1, int(p_cant / st.session_state[key_num_pers])) if p_cant > 0 else 0
                            cant_asig = c_cant_asig.number_input("Unid. Asignadas *", min_value=0, value=cant_sugerida, key=f"soc_cant_p0_{idx}_{p_idx}_v{fv_p0}")
        
                            if rol_sel == "Confección": t_unit = float(tiempo_base_ia)
                            elif rol_sel == "Acabado": t_unit = round(tiempo_base_ia * 0.20, 3)
                            elif rol_sel == "Entretela": t_unit = round(tiempo_base_ia * 0.10, 3)
                            else: t_unit = round(5.0 / 60.0, 3)
        
                            tiempo_unitario = c_tiempo.number_input("Tiempo (hrs/unid)", min_value=0.0, value=t_unit, step=0.05, key=f"soc_tunit_p0_{idx}_{p_idx}_v{fv_p0}")
                            
                            horas_persona = cant_asig * tiempo_unitario
                            c_tot.text_input("Horas Totales", value=f"{horas_persona:.2f} hrs", disabled=True, key=f"soc_htot_p0_{idx}_{p_idx}_v{fv_p0}")
        
                            horas_confeccion_total += horas_persona
                            lista_confeccion_p0.append({
                                "producto": p_nom, "rol": rol_sel, "persona": persona_sel, "cantidad": cant_asig, "horas_totales": horas_persona
                            })
        
                    total_horas_social = total_horas_ops + horas_confeccion_total
                    nombres_unicos = set()
                    for op in lista_operaciones_p0:
                        if op.get("horas_totales", 0) > 0 and op.get("nombre", "").strip():
                            nombres_unicos.add(op["nombre"].strip().title())
                    for conf in lista_confeccion_p0:
                        if conf.get("horas_totales", 0) > 0 and conf.get("persona", "").strip():
                            nombres_unicos.add(conf["persona"].strip().title())
                            
                    total_personas_social = len(nombres_unicos)
        
                    st.info(f"‍‍**Impacto Social Total:** {total_horas_social:.2f} horas generadas | {total_personas_social} personas beneficiadas.")
        
                st.write("")
        
                # --- BOTÓN DE GUARDADO + CONSTANCIA SOCIAL ---
                with st.container(border=True):
                    st.markdown("##### Generar Constancia Social y Registrar")
                    st.caption("Este proceso emitirá la constancia oficial de impacto social en formato PDF y registrará las horas de trabajo generadas.")
                    
                    if st.button("Registrar Producción desde 0", type="primary", use_container_width=True):
                        if not cliente_p0.strip():
                            st.error("⚠️ Debes ingresar el nombre del cliente.")
                        else:
                            with st.spinner("Generando Constancia Social y guardando en la base de datos..."):
                                try:
                                    # 1. Generar Documento Word -> PDF
                                    contexto_social = {
                                        "cliente": cliente_p0.upper(),
                                        "ruc": ruc_p0,
                                        "fecha_inicio": fe_inicio_dt.strftime('%d/%m/%Y'),
                                        "fecha_fin": fe_fin_dt.strftime('%d/%m/%Y'),
                                        "total_unidades": str(total_prod_unid),
                                        "total_horas": f"{total_horas_social:.1f}",
                                        "total_personas": str(total_personas_social)
                                    }
                                    
                                    bytes_constancia = generar_constancia_desde_plantilla_word(contexto_social, "Plantilla_Impacto_Social.docx")
                                    url_constancia = subir_pdf_supabase(f"Constancia_Social_{codigo_proy}.pdf", bytes_constancia)
                                    
                                    # 2. Guardar en Base de Datos (Métricas Ambientales bloqueadas en CERO)
                                    datos_sociales = {
                                        "codigo": codigo_proy,
                                        "cliente": cliente_p0,
                                        "ruc": ruc_p0,
                                        "tipo_proyecto": tipo_p0,
                                        "responsable": responsable_p0,
                                        "fecha": f"{fe_inicio_dt.strftime('%d/%m/%Y')} - {fe_fin_dt.strftime('%d/%m/%Y')}",
                                        "estado": "COMPLETADO",
                                        "peso_recibido": 0.0,
                                        "peso_transformado": 0.0,
                                        "aprovechamiento": 0.0,
                                        "co2_neto": 0.0,
                                        "horas_totales": total_horas_social,
                                        "productos_unids": total_prod_unid,
                                        "punto_origen": "Producción desde cero",
                                        "constancia_url": url_constancia,
                                        "pdf_url": "",
                                        "datos_completos": {
                                            "productos": lista_productos_p0,
                                            "operaciones": lista_operaciones_p0,
                                            "confeccion": lista_confeccion_p0,
                                            "participantes": total_personas_social
                                        }
                                    }
                                    
                                    supabase.table("proyectos").insert(datos_sociales).execute()
                                    
                                    st.session_state.num_prods_p0 = 1
                                    st.session_state.form_version += 1
                                    
                                    st.session_state.documentos_descarga = {
                                        "bytes_informe": bytes_constancia,
                                        "nombre_archivo": f"Constancia_Social_{codigo_proy}.pdf"
                                    }
                                    st.rerun()
                                    
                                except FileNotFoundError:
                                    st.error("❌ No se encontró el archivo 'Plantilla_Impacto_Social.docx'. Asegúrate de haberlo subido junto a tu código.")
                                except Exception as e:
                                    st.error(f"❌ Error al procesar: {e}")
                                    
                if st.session_state.documentos_descarga and "Constancia_Social" in st.session_state.documentos_descarga.get("nombre_archivo", ""):
                    docs = st.session_state.documentos_descarga
                    st.success("¡Éxito! Tu producción ha sido registrada como impacto social (CO₂ = 0 kg).")
                    st.balloons()
                    st.download_button("Descargar Constancia Social (PDF)", data=docs["bytes_informe"], file_name=docs["nombre_archivo"], mime="application/pdf", use_container_width=True, type="primary")
            
        elif st.session_state.pestaña_activa == "Carga Rápida Histórica":
            st.subheader("Carga Rápida de Proyectos Históricos")
            st.caption("Registra proyectos individuales o sube tu tabla completa en segundos.")
    
            tab_manual, tab_masiva = st.tabs(["Carga Manual Individual", "Carga Masiva Inteligente (CSV/Excel)"])
    
            with tab_manual:
                with st.container(border=True):
                    st.markdown("##### 1. Datos Generales")
                    rq1, rq2, rq3, rq4 = st.columns([2.5, 1.5, 1, 1.5])
                    fast_cliente = rq1.text_input("Cliente / Razón Social *")
                    fast_mes = rq2.selectbox("Mes del pedido *", MESES_ORDEN, index=datetime.date.today().month - 1)
                    fast_anio = rq3.selectbox("Año", [2024, 2025, 2026, 2027], index=2)
                    fast_tipo = rq4.selectbox("Tipo de Proyecto", ["Upcycling", "Mermas Textiles", "Producción Interna", "Producción desde 0", "Cambio logo", "Banner"])
                    
                    mes_num = MESES_ORDEN.index(fast_mes) + 1
                    cli_clean = fast_cliente.strip() if fast_cliente.strip() else "EMPRESA"
                    fast_codigo = f"HIST_{cli_clean[:8]}_{mes_num:02d}{fast_anio}-{random.randint(1000, 9999)}"
    
                with st.container(border=True):
                    st.markdown("##### 2. Métricas para el Dashboard")
                    rm1, rm2, rm3 = st.columns(3)
                    fast_peso = rm1.number_input("Kg Recibidos (Peso Total) *", min_value=0.0, step=0.1)
                    fast_unid_recibidas = rm2.number_input("Unidades Recibidas", min_value=0, step=1)
                    fast_unid = rm3.number_input("Productos Creados *", min_value=0, step=1)
    
                    rm4, rm5, rm6 = st.columns(3)
                    fast_co2 = rm4.number_input("CO₂e Evitado (kg) *", min_value=0.0, step=0.1)
                    fast_horas = rm5.number_input("Horas de Trabajo *", min_value=0.0, step=0.5)
                    fast_personas = rm6.number_input("Participantes *", min_value=0, step=1)
    
                st.write("")
    
                if st.button("Guardar Proyecto Histórico", type="primary", use_container_width=True):
                    if not fast_cliente.strip():
                        st.error("El campo **Cliente / Razón Social** es obligatorio.")
                    else:
                        try:
                            with st.spinner("Registrando proyecto..."):
                                supabase.table("proyectos").upsert({
                                    "codigo": fast_codigo, 
                                    "cliente": fast_cliente, 
                                    "ruc": "00000000000", 
                                    "tipo_proyecto": fast_tipo, 
                                    "responsable": "Sostenibilidad (Histórico)",
                                    "fecha": f"01/{mes_num:02d}/{fast_anio} - 28/{mes_num:02d}/{fast_anio}", 
                                    "estado": "COMPLETADO",
                                    "peso_recibido": fast_peso, 
                                    "peso_transformado": fast_peso,
                                    "aprovechamiento": 100.0, 
                                    "co2_neto": fast_co2, 
                                    "horas_totales": fast_horas, 
                                    "productos_unids": fast_unid, 
                                    "punto_origen": "Histórico",
                                    "datos_completos": {
                                        "participantes": fast_personas, 
                                        "unidades_recibidas": fast_unid_recibidas
                                    }
                                }).execute()
                            st.success(f"✅ ¡Proyecto **{fast_cliente}** registrado con éxito!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Error: {e}")
    
            with tab_masiva:
                with st.container(border=True):
                    st.markdown("##### Carga Masiva Automática")
                    st.markdown("El sistema lee CSV (recomendado) o Excel automáticamente. Detecta columnas y soluciona errores de codificación o separadores.")
                    
                    archivo_cargado = st.file_uploader("Selecciona tu archivo CSV o Excel", type=["csv", "xlsx"])
                    anio_masivo = st.selectbox("Año aplicable para los proyectos subidos", [2024, 2025, 2026, 2027], index=2)
    
                    if archivo_cargado is not None:
                        df_subido = None
                        try:
                            if archivo_cargado.name.endswith('.csv'):
                                try:
                                    df_subido = pd.read_csv(archivo_cargado, encoding='utf-8', sep=None, engine='python')
                                except UnicodeDecodeError:
                                    archivo_cargado.seek(0)
                                    df_subido = pd.read_csv(archivo_cargado, encoding='latin1', sep=None, engine='python')
                            else:
                                try:
                                    df_subido = pd.read_excel(archivo_cargado)
                                except ImportError:
                                    st.error("⚠️ Para archivos Excel (.xlsx) se requiere 'openpyxl'. Por favor, guarda tu archivo como **CSV** y súbelo.")
                        except Exception as e:
                            st.error(f"❌ Error al leer el archivo: {e}")
    
                        if df_subido is not None:
                            st.write("Vista previa inteligente (Columnas detectadas):", df_subido.head(3))
    
                            if st.button("Importar Todos los Proyectos", type="primary", use_container_width=True):
                                with st.spinner("Importando masivamente..."):
                                    meses_map = {m.lower(): i for i, m in MESES_ESPANOL.items()}
                                    
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
    
                                    def safe_float(val):
                                        try: return float(val) if pd.notna(val) else 0.0
                                        except: return 0.0
                                        
                                    def safe_int(val):
                                        try: return int(float(val)) if pd.notna(val) else 0
                                        except: return 0
    
                                    count_exito = 0
                                    for idx_row, row in df_subido.iterrows():
                                        cli_val = row.get(cli_col)
                                        if pd.isna(cli_val): continue
                                        cli = str(cli_val).strip()
                                        if cli.upper() == "NAN" or not cli: continue
                                        
                                        mes_txt = str(row.get(mes_col, "enero")).strip().lower()
                                        mes_n = meses_map.get(mes_txt, 1)
                                        
                                        fe_i = f"01/{mes_n:02d}/{anio_masivo}"
                                        fe_f = f"28/{mes_n:02d}/{anio_masivo}"
                                        
                                        unid_rec = safe_int(row.get(unid_col))
                                        kg_rec = safe_float(row.get(kg_col))
                                        co2_val = safe_float(row.get(co2_col))
                                        horas_val = safe_float(row.get(hr_col))
                                        prod_val = safe_int(row.get(prod_col))
                                        part_val = safe_int(row.get(part_col))
                                        
                                        tipo_val = row.get(tipo_col)
                                        tipo_proy = str(tipo_val).upper() if pd.notna(tipo_val) else "UPCYCLING"
    
                                        cli_limpio = cli[:6].replace(" ", "")
                                        codigo_H = f"MAS_{cli_limpio}_{mes_n:02d}{anio_masivo}-{idx_row}-{random.randint(10000, 99999)}"
    
                                        supabase.table("proyectos").upsert({
                                            "codigo": codigo_H, "cliente": cli, "ruc": "00000000000",
                                            "tipo_proyecto": tipo_proy, "responsable": "Sostenibilidad (Histórico)",
                                            "fecha": f"{fe_i} - {fe_f}", "estado": "COMPLETADO",
                                            "peso_recibido": kg_rec, "peso_transformado": kg_rec,
                                            "aprovechamiento": 100.0, "co2_neto": co2_val,
                                            "horas_totales": horas_val, "productos_unids": prod_val,
                                            "punto_origen": "Histórico Masivo",
                                            "datos_completos": {"participantes": part_val, "unidades_recibidas": unid_rec}
                                        }).execute()
                                        count_exito += 1
    
                                    st.success(f"¡Se han importado exitosamente **{count_exito} proyectos** a tu Dashboard!")
                                    st.balloons()
    
        elif st.session_state.pestaña_activa == "Proyectos en Proceso":
            st.subheader("Lista de Proyectos en Proceso (Borradores)")
            st.caption("Proyectos guardados pendientes de culminación o emisión definitiva.")
    
            proyectos_lista = cargar_proyectos("EN_PROCESO")
    
            if proyectos_lista:
                for b in proyectos_lista:
                    with st.container(border=True):
                        bc1, bc2, bc3 = st.columns([3, 2, 2])
                        
                        nombre_cli_ui = b.get('cliente', 'Sin Nombre')
                        bc1.markdown(f"**Cliente:** {nombre_cli_ui}")
                        bc1.caption(f"Código: `{b.get('codigo', '')}`")
                        bc2.markdown(f"**Tipo:** {b.get('tipo_proyecto', 'Upcycling')}")
                        bc2.caption(f"Fecha: {b.get('fecha', '')}")
    
                        if bc3.button(
                            "Retomar Edición",
                            key=f"retomar_{b.get('id', b.get('codigo'))}",
                            use_container_width=True,
                            type="primary",
                        ):
                            st.session_state.proyecto_editar = b
                            st.session_state.documentos_descarga = None
                            st.session_state.pestaña_activa = "Nuevo Reporte PDF"
                            st.session_state.form_version += 1 
                            st.rerun()
            else:
                st.info("No hay borradores en proceso actualmente.")
    
        elif st.session_state.pestaña_activa == "Dashboard Analítico":
            st.markdown("<h3 style='color: #1E293B; font-weight: 700; margin-bottom: 5px;'>Panel de Control y Analítica Avanzada</h3>", unsafe_allow_html=True)
            st.markdown("<p style='color: #64748B; font-size: 0.95rem; margin-bottom: 25px;'>Filtra, analiza y visualiza el impacto histórico generado por los proyectos de sostenibilidad.</p>", unsafe_allow_html=True)
    
            completados = cargar_proyectos("COMPLETADO")
            
            if not completados:
                st.info("Aún no hay proyectos completados para mostrar en las métricas.")
            else:
                tabla_data = []
                for p in completados:
                    dc = p.get("datos_completos") or {}
                    unid_rec = sum([int(it.get("unidades", 0)) for it in dc.get("items", [])]) if "items" in dc else int(dc.get("unidades_recibidas", 0))
                    partic = (6 + len(set([c.get("persona", "").strip() for c in dc.get("confeccion", []) if c.get("persona", "").strip()]))) if "items" in dc else int(dc.get("participantes", 0))
    
                    mes_txt, anio_txt = "N/D", "2026"
                    if p.get("fecha") and "-" in p.get("fecha"):
                        try:
                            partes_fecha = p.get("fecha").split("-")[1].strip().split("/")
                            mes_txt, anio_txt = MESES_ESPANOL.get(int(partes_fecha[1]), "N/D").capitalize(), str(partes_fecha[2])
                        except: pass
    
                    tabla_data.append({
                        "Cliente": p.get("cliente", "Sin Nombre"),
                        "Año": anio_txt,
                        "Mes": mes_txt,
                        "Unidades Recibidas": unid_rec,
                        "Kg Procesados": float(p.get("peso_recibido") or 0),
                        "CO₂ Evitado": float(p.get("co2_neto") or 0),
                        "Horas de Trabajo": float(p.get("horas_totales") or 0),
                        "Productos Creados": int(p.get("productos_unids") or 0),
                        "Participantes": partic,
                        "Tipo de Servicio": str(p.get("tipo_proyecto", "UPCYCLING")).upper(),
                        "DatosCompletos": dc
                    })
    
                df = pd.DataFrame(tabla_data)
    
                st.markdown("<h5 style='color: #1E293B; margin-bottom: 15px;'>Filtros de Análisis</h5>", unsafe_allow_html=True)
                f0, f1, f2, f3 = st.columns(4)
    
                sel_anio = f0.selectbox("Año", ["Todos"] + sorted(list(df["Año"].unique()), reverse=True))
                sel_mes = f1.selectbox("Mes", ["Todos"] + [m for m in MESES_ORDEN if m in df["Mes"].unique()])
                sel_cli = f2.selectbox("Cliente", ["Todos"] + sorted([str(x) for x in df["Cliente"].unique() if x != "N/D"]))
                sel_tipo = f3.selectbox("Tipo de Servicio", ["Todos"] + sorted([str(x) for x in df["Tipo de Servicio"].unique() if x != "N/D"]))
    
                df_fil = df.copy()
                if sel_anio != "Todos": df_fil = df_fil[df_fil["Año"] == sel_anio]
                if sel_mes != "Todos": df_fil = df_fil[df_fil["Mes"] == sel_mes]
                if sel_cli != "Todos": df_fil = df_fil[df_fil["Cliente"] == sel_cli]
                if sel_tipo != "Todos": df_fil = df_fil[df_fil["Tipo de Servicio"] == sel_tipo]
    
                st.write("")
                c_tit1, c_tit2 = st.columns([3, 1])
                c_tit1.markdown("<h5 style='color: #1E293B; margin-bottom: 15px;'>Impacto Acumulado</h5>", unsafe_allow_html=True)
                
                if not df_fil.empty:
                    pdf_bytes = generar_pdf_dashboard(df_fil, sel_anio, sel_mes, sel_cli, sel_tipo)
                    
                    if sel_mes == "Todos" and sel_anio != "Todos":
                        nombre_archivo = f"Memoria_Anual_Sostenibilidad_{sel_anio}.pdf"
                    elif sel_mes != "Todos" and sel_anio != "Todos":
                        nombre_archivo = f"Reporte_Mensual_{sel_mes}_{sel_anio}.pdf"
                    else:
                        nombre_archivo = "Reporte_Sostenibilidad_Personalizado.pdf"
    
                    c_tit2.download_button(
                        label="Descargar Reporte PDF",
                        data=pdf_bytes,
                        file_name=nombre_archivo,
                        mime="application/pdf",
                        use_container_width=True,
                        type="primary"
                    )
                
                # NUEVAS MÉTRICAS DEL DASHBOARD
                dm1, dm2, dm3, dm4 = st.columns(4)
                dm1.metric("Total Proyectos", f"{len(df_fil):,}")
                dm2.metric("Clientes Únicos", f"{df_fil['Cliente'].nunique():,}")
                dm3.metric("Peso Procesado", f"{df_fil['Kg Procesados'].sum():,.2f} kg")
                dm4.metric("CO₂e Evitado", f"{df_fil['CO₂ Evitado'].sum():,.2f} kg")
    
                st.write("")
                dm5, dm6, dm7 = st.columns(3)
                dm5.metric("Unidades Recibidas", f"{int(df_fil['Unidades Recibidas'].sum()):,} unid")
                dm6.metric("Productos Creados", f"{int(df_fil['Productos Creados'].sum()):,} unid")
                dm7.metric("‍‍Horas de Trabajo", f"{df_fil['Horas de Trabajo'].sum():,.2f} hrs")
    
                st.write("---")
    
                st.markdown("<h5 style='color: #1E293B; margin-bottom: 15px;'>Análisis de Producción e Innovación</h5>", unsafe_allow_html=True)
                
                prod_list_dash = []
                for _, row in df_fil.iterrows():
                    dc_row = row["DatosCompletos"]
                    if isinstance(dc_row, dict) and "productos" in dc_row:
                        for pr in dc_row["productos"]:
                            prod_list_dash.append({
                                "Producto": pr.get("producto", "N/D"),
                                "Cantidad": int(pr.get("cantidad", 0))
                            })
                
                if prod_list_dash:
                    df_p = pd.DataFrame(prod_list_dash)
                    df_p_grp = df_p.groupby("Producto")["Cantidad"].sum().reset_index().sort_values(by="Cantidad", ascending=False)
                    
                    cp1, cp2 = st.columns([1, 2])
                    with cp1:
                        with st.container(border=True):
                            st.metric("Total Productos Diferentes", f"{len(df_p_grp):,}", help="Mide la diversificación e innovación de tu catálogo en el periodo seleccionado.")
                        with st.container(border=True):
                            st.metric("Producto Estrella ", df_p_grp.iloc[0]["Producto"], f"{df_p_grp.iloc[0]['Cantidad']:,} unid.")
                        if len(df_p_grp) > 1:
                            with st.container(border=True):
                                st.metric("Menos Fabricado ", df_p_grp.iloc[-1]["Producto"], f"{df_p_grp.iloc[-1]['Cantidad']:,} unid.")
                    
                    with cp2:
                        fig_p = px.bar(df_p_grp.head(10), x="Cantidad", y="Producto", orientation='h', title="Top 10 Productos Más Fabricados", color_discrete_sequence=["#10B981"])
                        fig_p.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=0, r=0, t=30, b=0))
                        st.plotly_chart(fig_p, use_container_width=True)
                else:
                    st.info("No hay datos de productos detallados para los filtros seleccionados.")
    
                st.write("---")
    
                cg1, cg2, cg3 = st.columns([2.5, 1.2, 1.2])
                with cg1:
                    st.markdown("<span style='font-weight: 600; color: #475569;'>Evolución Mensual (CO₂e)</span>", unsafe_allow_html=True)
                    if not df_fil.empty:
                        df_mes_graf = df_fil.groupby("Mes")["CO₂ Evitado"].sum().reset_index()
                        df_mes_graf["Mes_cat"] = pd.Categorical(df_mes_graf["Mes"], categories=MESES_ORDEN, ordered=True)
                        fig1 = px.bar(df_mes_graf.sort_values("Mes_cat"), x="Mes", y="CO₂ Evitado", text_auto='.0f', color_discrete_sequence=["#3B82F6"])
                        fig1.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                        fig1.update_layout(margin=dict(l=0, r=0, t=20, b=0), yaxis_title="Kg CO₂e", xaxis_title="")
                        st.plotly_chart(fig1, use_container_width=True)
                    else: st.caption("No hay datos.")
    
                with cg2:
                    st.markdown("<span style='font-weight: 600; color: #475569;'>Distribución de Servicios</span>", unsafe_allow_html=True)
                    if not df_fil.empty:
                        fig2 = px.pie(df_fil.groupby("Tipo de Servicio")["Kg Procesados"].sum().reset_index(), values="Kg Procesados", names="Tipo de Servicio", hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
                        fig2.update_traces(textposition='inside', textinfo='percent')
                        fig2.update_layout(margin=dict(l=0, r=0, t=20, b=0), showlegend=True, legend=dict(orientation="h", y=-0.2))
                        st.plotly_chart(fig2, use_container_width=True)
                    else: st.caption("No hay datos.")
    
                with cg3:
                    st.markdown("<span style='font-weight: 600; color: #475569;'>Top 5 Clientes (Impacto)</span>", unsafe_allow_html=True)
                    if not df_fil.empty:
                        top5 = df_fil.groupby("Cliente")["CO₂ Evitado"].sum().reset_index().sort_values(by="CO₂ Evitado", ascending=False).head(5)
                        top5.insert(0, "Top", [1, 2, 3, 4, 5][:len(top5)])
                        st.dataframe(top5[["Top", "Cliente", "CO₂ Evitado"]], use_container_width=True, hide_index=True)
    
                st.write("---")
    
                st.markdown("<h5 style='color: #1E293B; margin-bottom: 15px;'>Detalle de Proyectos (Filtrado)</h5>", unsafe_allow_html=True)
                if not df_fil.empty:
                    max_k = float(df_fil["Kg Procesados"].max()) if not df_fil.empty else 100.0
                    max_c = float(df_fil["CO₂ Evitado"].max()) if not df_fil.empty else 100.0
                    
                    df_vista = df_fil.drop(columns=["DatosCompletos"])
                    
                    st.dataframe(
                        df_vista,
                        use_container_width=True,
                        hide_index=True,
                        height=300,
                        column_config={
                            "Cliente": st.column_config.TextColumn("Cliente", width="medium"),
                            "Año": st.column_config.TextColumn("Año", alignment="center"),
                            "Mes": st.column_config.TextColumn("Mes", alignment="center"),
                            "Kg Procesados": st.column_config.ProgressColumn("Kg Procesados", format="%,.1f", min_value=0, max_value=max_k),
                            "CO₂ Evitado": st.column_config.ProgressColumn("CO₂ Evitado", format="%,.1f", min_value=0, max_value=max_c),
                            "Unidades Recibidas": st.column_config.NumberColumn("Unidades Recibidas", format="%,d", alignment="center"),
                            "Horas de Trabajo": st.column_config.NumberColumn("Horas de Trabajo", format="%,.1f", alignment="center"),
                            "Productos Creados": st.column_config.NumberColumn("Productos Creados", format="%,d", alignment="center"),
                            "Participantes": st.column_config.NumberColumn("Participantes", format="%,d", alignment="center"),
                            "Tipo de Servicio": st.column_config.TextColumn("Tipo de Servicio", alignment="center"),
                        }
                    )
    
        elif st.session_state.pestaña_activa == "Historial Completo":
            st.subheader("Historial Completo de Proyectos")
            st.caption("Listado general de todos los proyectos registrados. Usa el buscador para encontrar reportes rápidos.")
    
            proyectos_lista = cargar_proyectos()
    
            if proyectos_lista:
                with st.expander("Buscar y Filtrar Historial", expanded=True):
                    f1, f2, f3 = st.columns([2, 1, 1])
                    busqueda = f1.text_input("Buscar por Cliente o Código", placeholder="Ej. Antamina o HIST_...")
                    filtro_estado = f2.selectbox("Estado del Proyecto", ["Todos", "COMPLETADO", "EN_PROCESO"])
                    filtro_tipo = f3.selectbox("Tipo de Servicio", ["Todos", "UPCYCLING", "Mermas Textiles", "Producción Interna", "PRODUCCIÓN DESDE CERO", "CAMBIO LOGO", "BANNER"])
                
                proyectos_filtrados = []
                for p in proyectos_lista:
                    match_txt = busqueda.lower() in str(p.get("cliente", "")).lower() or busqueda.lower() in str(p.get("codigo", "")).lower() if busqueda else True
                    match_est = filtro_estado == "Todos" or p.get("estado") == filtro_estado
                    match_tip = filtro_tipo == "Todos" or str(p.get("tipo_proyecto", "")).upper() == filtro_tipo.upper()
                    
                    if match_txt and match_est and match_tip:
                        proyectos_filtrados.append(p)
    
                st.write("---")
                col_top1, col_top2 = st.columns([4, 2])
                
                if st.session_state.rol == "admin":
                    modo_edicion = col_top1.toggle("Habilitar selección múltiple para borrar")
                    
                    if modo_edicion:
                        proyectos_seleccionados = [p for p in proyectos_filtrados if st.session_state.get(f"bulk_del_{p.get('id', p.get('codigo'))}", False)]
                        if col_top2.button(
                            f"Eliminar Seleccionados ({len(proyectos_seleccionados)})", 
                            disabled=len(proyectos_seleccionados) == 0, 
                            type="secondary",
                            use_container_width=True
                        ):
                            modal_confirmar_eliminacion_masiva(proyectos_seleccionados)
                    else:
                        for p in proyectos_filtrados:
                            k = f"bulk_del_{p.get('id', p.get('codigo'))}"
                            if k in st.session_state:
                                st.session_state[k] = False
                else:
                    modo_edicion = False
                    col_top1.info("Modo de solo lectura y edición. La eliminación masiva requiere permisos de Administrador.")
    
                if len(proyectos_filtrados) == 0:
                    st.info("No se encontraron proyectos con los filtros seleccionados.")
                else:
                    st.caption(f"Mostrando **{len(proyectos_filtrados)}** de **{len(proyectos_lista)}** proyectos.")
    
                    for p in proyectos_filtrados:
                        with st.container(border=True):
                            
                            if modo_edicion and st.session_state.rol == "admin":
                                c_chk, hc1, hc2, hc3, hc4, hc5, hc6 = st.columns([0.4, 2.5, 1.6, 1.6, 1.8, 1.8, 0.7])
                                c_chk.write("") 
                                c_chk.checkbox(" ", key=f"bulk_del_{p.get('id', p.get('codigo'))}", label_visibility="collapsed")
                            elif st.session_state.rol == "admin":
                                hc1, hc2, hc3, hc4, hc5, hc6 = st.columns([2.9, 1.6, 1.6, 1.8, 1.8, 0.7])
                            else:
                                hc1, hc2, hc3, hc4, hc5 = st.columns([2.9, 1.6, 1.6, 1.8, 1.8])
                            
                            nombre_cli_ui = p.get('cliente', 'Sin Nombre')
    
                            hc1.markdown(f"**{nombre_cli_ui}**")
                            hc1.caption(f"ID/Código: `{p.get('codigo', '')}`")
                            hc2.markdown(f"Estado: **{p.get('estado', 'N/D')}**")
                            hc2.caption(f"Tipo: {str(p.get('tipo_proyecto', 'UPCYCLING')).upper()}")
                            hc3.markdown(f"Peso: `{float(p.get('peso_recibido', 0) or 0):.2f} kg`")
                            hc3.caption(f"Fecha: {p.get('fecha', 'N/D')}")
    
                            pdf_link = p.get("pdf_url")
                            if pdf_link:
                                hc4.link_button("Informe PDF", pdf_link, use_container_width=True)
                            else:
                                hc4.caption("Sin Informe")
    
                            const_link = p.get("constancia_url")
                            if const_link:
                                if st.session_state.rol == "admin":
                                    hc5.link_button("Constancia PDF", const_link, use_container_width=True)
                                else:
                                    hc5.link_button("Constancia", const_link, use_container_width=True)
                            else:
                                hc5.caption("Sin Constancia")
    
                            if st.session_state.rol == "admin":
                                if hc6.button(
                                    "Eliminar",
                                    key=f"hist_del_{p.get('id', p.get('codigo'))}",
                                    use_container_width=True,
                                    help="Eliminar proyecto",
                                ):
                                    modal_confirmar_eliminacion(p)
            else:
                st.info("No hay proyectos registrados en el historial.")
# --- VISTA: NUEVO REPORTE PDF ---
        elif st.session_state.pestaña_activa == "Nuevo Reporte PDF":
            fv = st.session_state.form_version
            p_edit = st.session_state.proyecto_editar
    
            target_proj_id = p_edit.get("id") or p_edit.get("codigo") or "__nuevo__"
            current_loaded = st.session_state.get("_loaded_project_id", None)
    
            if current_loaded != target_proj_id:
                st.session_state._loaded_project_id = target_proj_id
                st.session_state.form_version += 1 
                fv = st.session_state.form_version 
    
                dc_init = p_edit.get("datos_completos") or p_edit.get("datos_formulario") or {}
    
                if dc_init.get("num_items"):
                    st.session_state.num_items = dc_init["num_items"]
                elif "items" in dc_init and len(dc_init["items"]) > 0:
                    st.session_state.num_items = len(dc_init["items"])
                else:
                    st.session_state.num_items = 2
    
                if dc_init.get("num_prods"):
                    st.session_state.num_prods = dc_init["num_prods"]
                elif "productos" in dc_init and len(dc_init["productos"]) > 0:
                    st.session_state.num_prods = len(dc_init["productos"])
                else:
                    st.session_state.num_prods = 2
    
                if dc_init.get("num_anexos"):
                    st.session_state.num_anexos = dc_init["num_anexos"]
                elif "anexos" in dc_init and len(dc_init["anexos"]) > 0:
                    st.session_state.num_anexos = len(dc_init["anexos"])
                else:
                    st.session_state.num_anexos = 1
    
                conf_num_map = dc_init.get("confeccion_num_pers", {})
                for k_np, v_np in conf_num_map.items():
                    st.session_state[k_np] = v_np
    
            dc = p_edit.get("datos_completos") or p_edit.get("datos_formulario") or {}
    
            if p_edit:
                st.warning(
                    f"**Modo Edición Activo:** Modificando borrador de **{p_edit.get('cliente', '')}** (`{p_edit.get('codigo', '')}`)"
                )
                col_desc, col_elim = st.columns([2, 2])
                if col_desc.button("❌ Descartar selección y limpiar formulario", use_container_width=True):
                    st.session_state.proyecto_editar = {}
                    st.session_state.documentos_descarga = None
                    st.session_state.form_version += 1
                    st.rerun()
    
                if st.session_state.rol == "admin":
                    if col_elim.button("Eliminar Proyecto Definitivamente", use_container_width=True):
                        modal_confirmar_eliminacion(p_edit)
                else:
                    col_elim.info("Solo los Administradores pueden borrar proyectos guardados.")
    
            # --- SECCIÓN 1: FICHA GENERAL ---
            with st.container(border=True):
                st.subheader("1. Ficha General del Proyecto")
    
                fechas_raw = p_edit.get("fecha", " - ").split(" - ")
                try: def_f_ini = datetime.datetime.strptime(fechas_raw[0].strip(), "%d/%m/%Y").date()
                except Exception: def_f_ini = datetime.date.today()
    
                try: def_f_fin = datetime.datetime.strptime(fechas_raw[1].strip(), "%d/%m/%Y").date()
                except Exception: def_f_fin = datetime.date.today()
    
                c1, c2, c5, c6 = st.columns(4)
                cliente = c1.text_input("Cliente / Empresa *", value=p_edit.get("cliente", ""), help="Nombre de la empresa o cliente corporativo.")
                ruc = c2.text_input("RUC * (11 dígitos)", value=p_edit.get("ruc", ""), max_chars=11, help="RUC de 11 dígitos de la empresa cliente.")
                
                fe_inicio_dt = c5.date_input("Fecha Inicio *", value=def_f_ini, format="DD/MM/YYYY", help="Fecha en la que se recibieron los uniformes o materiales.")
                fe_fin_dt = c6.date_input("Fecha Término *", value=def_f_fin, format="DD/MM/YYYY", help="Fecha de culminación y entrega final del proceso.")
    
                fe_inicio = fe_inicio_dt.strftime("%d/%m/%Y")
                fe_fin = fe_fin_dt.strftime("%d/%m/%Y")
    
                str_empresa = cliente.strip() if cliente.strip() else "EMPRESA"
                mes_fin_nombre = MESES_ESPANOL.get(fe_fin_dt.month, "MES").upper()
                
                if p_edit.get("codigo"):
                    codigo_proy = p_edit["codigo"]
                else:
                    cliente_clean = re.sub(r'[^a-zA-Z0-9]', '', str_empresa).upper()[:8]
                    codigo_proy = f"{cliente_clean}_{mes_fin_nombre}{fe_fin_dt.year}"
    
                st.info(f"🆔 **Código del Proyecto:** `{codigo_proy}`")
    
                c4, c7, c8, c9 = st.columns(4)
                
                opciones_tipo_proyecto = ["Upcycling", "Mermas Textiles", "Cambio logo", "Banner"]
                tipo_actual = p_edit.get("tipo_proyecto", "Upcycling")
                idx_tipo = opciones_tipo_proyecto.index(tipo_actual) if tipo_actual in opciones_tipo_proyecto else 0
    
                proyecto_nom = c4.selectbox("Tipo de Proyecto *", opciones_tipo_proyecto, index=idx_tipo, help="Clasificación del tipo de servicio realizado.")
    
                RESPONSABLES_BASE = ["Evelyn Prada Vizarreta", "Gabriel Manrique Hurtado"]
                responsables_guardados = p_edit.get("responsables", [])
                if not isinstance(responsables_guardados, list):
                    responsables_guardados = [r.strip() for r in str(responsables_guardados).split(",") if r.strip()]
    
                responsable_anterior = p_edit.get("responsable", "")
                if responsable_anterior and not responsables_guardados:
                    responsables_guardados = [r.strip() for r in str(responsable_anterior).split(",") if r.strip()]
    
                if not responsables_guardados and dc.get("responsables_seleccionados"):
                    responsables_guardados = dc.get("responsables_seleccionados", [])
    
                opciones_responsables = list(dict.fromkeys(RESPONSABLES_BASE + responsables_guardados))
    
                responsables_seleccionados = c7.multiselect(
                    "Responsable *",
                    options=opciones_responsables,
                    default=[r for r in responsables_guardados if r in opciones_responsables],
                    placeholder="Selecciona uno o más",
                    key=f"responsables_proyecto_v{fv}",
                    help="Responsable(s) internos a cargo del proyecto."
                )
    
                nuevo_responsable = c7.text_input("Agregar otro responsable", placeholder="Nombre completo", key=f"nuevo_responsable_proyecto_v{fv}")
    
                if nuevo_responsable.strip():
                    if nuevo_responsable.strip() not in responsables_seleccionados:
                        responsables_seleccionados.append(nuevo_responsable.strip())
    
                responsable = ", ".join(responsables_seleccionados)
                area = c8.text_input("Área", value="Sostenibilidad", disabled=True, help="Área interna encargada.")
                guia_remision = c9.text_input("Nº Guía Remisión", value=p_edit.get("guia", "") or dc.get("guia_remision", ""), help="Guía de remisión con la que llegaron los uniformes.")
    
                origen_default = p_edit.get("origen", "") or p_edit.get("punto_origen", "") or dc.get("origen", "")
                
                st.markdown("**Punto Origen \*** <span style='font-weight: normal; color: #64748B; font-size: 0.85rem;'>(Lugar o dirección de donde vinieron los uniformes)</span>", unsafe_allow_html=True)
                origen = st.text_input("Punto Origen *", value=origen_default, label_visibility="collapsed")
                
                destino = "Jr. Las Caléndulas 610, Las Flores, SJL."
    
            st.write("")
    
            # --- SECCIÓN 2: MATERIAL ---
            with st.container(border=True):
                st.subheader("2. Ingreso de Material")
                
                with st.expander("Administrar Catálogo de Materiales y Calcular CO₂e"):
                    tab_mat_add, tab_mat_del = st.tabs(["Agregar / Calcular Material", "Eliminar Material"])
    
                    with tab_mat_add:
                        st.caption("Puedes usar la calculadora de porcentajes, o activar la opción manual para ingresar un factor directo.")
                        
                        modo_manual = st.checkbox("Ingresar factor CO₂e manualmente (para materiales puros o mermas nuevas)", key=f"chk_manual_mat_v{fv}")
                        
                        col_m1, col_m2, col_m3 = st.columns([2, 1, 1])
                        nuevo_mat = col_m1.text_input("Nombre de la Prenda/Material (Ej. Buzo)", key=f"mat_new_nom_v{fv}")
    
                        if modo_manual:
                            factor_final = col_m2.number_input("Factor CO₂e (kg) *", min_value=0.0, value=5.0, step=0.1, key=f"mat_manual_input_v{fv}")
                        else:
                            p1, p2, p3, p4 = st.columns(4)
                            p_alg = p1.number_input("% Algodón", min_value=0, max_value=100, value=65, key=f"mat_alg_v{fv}")
                            p_pol = p2.number_input("% Poliéster", min_value=0, max_value=100, value=35, key=f"mat_pol_v{fv}")
                            p_dra = p3.number_input("% Acríl/Dralon", min_value=0, max_value=100, value=0, key=f"mat_dra_v{fv}")
                            p_cin = p4.number_input("% Cinta Ref.", min_value=0, max_value=100, value=0, key=f"mat_cin_v{fv}")
    
                            factor_final = (p_alg * 5.0 + p_pol * 9.5 + p_dra * 6.0 + p_cin * 12.0) / 100
    
                            st.session_state[f"mat_calc_v{fv}"] = f"{factor_final:.3f} kg"
                            col_m2.text_input("Factor Calculado", disabled=True, key=f"mat_calc_v{fv}")
    
                        if col_m3.button("Guardar Material", use_container_width=True, key=f"btn_save_mat_v{fv}"):
                            if nuevo_mat.strip():
                                nombre_formateado = nuevo_mat.strip().capitalize()
                                try:
                                    supabase.table("catalogos").delete().eq("tipo", "material_co2").eq("nombre", nombre_formateado).execute()
                                    supabase.table("catalogos").insert({"tipo": "material_co2", "nombre": nombre_formateado, "valor_num": factor_final}).execute()
                                except Exception: pass
                                
                                st.session_state.factores_co2[nombre_formateado] = factor_final
                                st.toast(f"✅ Material '{nombre_formateado}' guardado en la nube.")
                                st.rerun()
    
                    with tab_mat_del:
                        col_d1, col_d2 = st.columns([3, 1])
                        materiales_borrables = [m for m in st.session_state.factores_co2.keys() if m != "Banner"]
                        mat_a_borrar = col_d1.selectbox("Material a eliminar:", materiales_borrables, key=f"mat_sel_del_v{fv}")
                        if col_d2.button("Eliminar de la nube", use_container_width=True, key=f"btn_del_mat_v{fv}"):
                            if mat_a_borrar in st.session_state.factores_co2:
                                try: supabase.table("catalogos").delete().eq("tipo", "material_co2").eq("nombre", mat_a_borrar).execute()
                                except Exception: pass
                                
                                del st.session_state.factores_co2[mat_a_borrar]
                                st.toast(f"Material eliminado de la nube: {mat_a_borrar}")
                                st.rerun()
    
                if "num_items" not in st.session_state:
                    st.session_state.num_items = 2
    
                col_btn1, col_btn2, _ = st.columns([1, 1, 4])
                if col_btn1.button("Agregar Ítem"):
                    st.session_state.num_items += 1
                    st.rerun()
                if col_btn2.button("Quitar Ítem") and st.session_state.num_items > 1:
                    st.session_state.num_items -= 1
                    st.rerun()
    
                lista_items = []
                peso_total_recibido = 0.0
                co2_evitado_total = 0.0
                total_piezas_ingresadas = 0
    
                todas_prendas = sorted(list(st.session_state.factores_co2.keys()))
                if proyecto_nom == "Mermas Textiles":
                    opciones_prendas = [p for p in todas_prendas if "merma" in p.lower()]
                elif proyecto_nom == "Banner":
                    opciones_prendas = todas_prendas
                else:
                    opciones_prendas = [p for p in todas_prendas if "merma" not in p.lower()]
                    
                if not opciones_prendas:
                    opciones_prendas = todas_prendas
    
                opciones_prendas = sorted(opciones_prendas)
    
                saved_items = dc.get("items", [])
    
                for i in range(st.session_state.num_items):
                    st.markdown(f"**Material {i+1}**")
                    
                    col_desc, col_unid, col_peso, col_tot, col_foto = st.columns([3, 1.5, 1.5, 1.5, 3])
    
                    item_prev = saved_items[i] if i < len(saved_items) else {}
                    desc_prev = item_prev.get("descripcion", opciones_prendas[0])
                    idx_desc = opciones_prendas.index(desc_prev) if desc_prev in opciones_prendas else 0
                    unid_prev = int(item_prev.get("unidades", 0))
                    peso_prev = float(item_prev.get("peso_total", 0.0))
                    foto_url_prev = item_prev.get("foto_url", "")
    
                    desc = col_desc.selectbox("Tipo de Producto / Prenda *", opciones_prendas, index=idx_desc, key=f"desc_{i}_v{fv}")
                    unid = col_unid.number_input("Ingreso (unid.) *", min_value=0, value=unid_prev, key=f"unid_{i}_v{fv}")
    
                    p_total = col_peso.number_input("Peso Total (kg) *", min_value=0.0, value=peso_prev, step=0.05, key=f"tot_input_{i}_v{fv}")
                    
                    peso_u = p_total / unid if unid > 0 else 0.0
                    st.session_state[f"peso_u_{i}_v{fv}"] = f"{peso_u:.2f} kg"
                    col_tot.text_input("Peso Unitario", disabled=True, key=f"peso_u_{i}_v{fv}")
    
                    foto = col_foto.file_uploader("Evidencia Foto", type=["jpg", "png", "jpeg"], key=f"foto_{i}_v{fv}")
    
                    if foto is not None:
                        col_foto.image(foto, width=80)
                    elif foto_url_prev:
                        col_foto.image(foto_url_prev, width=80)
    
                    factor = st.session_state.factores_co2.get(desc, 6.575)
                    co2_item = p_total * factor
                    co2_evitado_total += co2_item
                    peso_total_recibido += p_total
                    total_piezas_ingresadas += unid
    
                    lista_items.append({
                        "descripcion": desc, "unidades": unid, "peso_unitario": peso_u, "peso_total": p_total,
                        "foto_up": foto, "foto_url": foto_url_prev, "foto": foto if foto is not None else foto_url_prev,
                        "co2_evitado": co2_item,
                    })
    
                st.info(f"    **Total Material Recibido:** {peso_total_recibido:.2f} kg | **CO₂ Evitado Calculado:** {co2_evitado_total:.2f} kg CO₂e")
    
            st.write("")
    
            # --- SECCIÓN 3: TRAZABILIDAD ---
            with st.container(border=True):
                st.subheader("3. Trazabilidad del Proceso en Upcycling")
    
                peso_corte_conf_auto = round(peso_total_recibido * st.session_state.pct_aprovechamiento_random, 2)
    
                etapas_fijas = [
                    {"etapa": "Clasificación", "fecha": fe_inicio_dt, "resp_defecto": "Evelyn Prada Vizarreta", "peso_defecto": peso_total_recibido, "tipo": "Registro interno"},
                    {"etapa": "Lavado", "fecha": datetime.date.today(), "resp_defecto": "Lavandería", "peso_defecto": 0.0, "tipo": "Servicio Externo"},
                    {"etapa": "Corte", "fecha": datetime.date.today(), "resp_defecto": "Taller de corte (5 integrantes)", "peso_defecto": peso_corte_conf_auto, "tipo": "Pesaje real"},
                    {"etapa": "Confección", "fecha": datetime.date.today(), "resp_defecto": "Producción descentralizada", "peso_defecto": peso_corte_conf_auto, "tipo": "Entrega / Recepción"},
                ]
                lista_trazabilidad = []
                peso_lavado_auto = 0.0
                peso_corte_auto = 0.0
    
                saved_traza = dc.get("trazabilidad", [])
    
                for i, item_fijo in enumerate(etapas_fijas):
                    st.markdown(f"**Etapa {i+1}**")
                    
                    col_etapa, col_fecha, col_resp, col_edit_chk, col_peso, col_tipo, col_foto = st.columns([1.5, 1.5, 2, 1.2, 1.2, 1.6, 2])
    
                    traza_prev = saved_traza[i] if i < len(saved_traza) else {}
                    fec_prev_str = traza_prev.get("fecha")
                    no_aplica_prev = traza_prev.get("no_aplica", False)
                    
                    if item_fijo["etapa"] == "Clasificación":
                        fec_val_def = fe_inicio_dt
                    else:
                        if fec_prev_str:
                            try: fec_val_def = datetime.datetime.strptime(fec_prev_str, "%d/%m/%Y").date()
                            except Exception: fec_val_def = item_fijo["fecha"]
                        else:
                            fec_val_def = item_fijo["fecha"]
    
                    resp_prev_val = traza_prev.get("responsable", item_fijo["resp_defecto"])
                    peso_prev_val = float(traza_prev.get("peso", item_fijo["peso_defecto"]))
                    tipo_prev_val = traza_prev.get("tipo_registro", item_fijo["tipo"])
                    is_edited_prev = traza_prev.get("editado", resp_prev_val != item_fijo["resp_defecto"])
                    foto_url_prev = traza_prev.get("foto_url", "")
    
                    if item_fijo["etapa"] == "Lavado":
                        no_aplica = col_edit_chk.checkbox("No aplica", value=bool(no_aplica_prev), key=f"chk_no_aplica_{i}_v{fv}")
                        permitir_editar = not no_aplica
                        deshabilitar_peso = no_aplica
                    else:
                        no_aplica = False
                        permitir_editar = col_edit_chk.checkbox("Editar", value=bool(is_edited_prev), key=f"chk_edit_{i}_v{fv}")
                        deshabilitar_peso = not permitir_editar
    
                    if no_aplica:
                        resp_val_ui = "N/A"
                        peso_val_ui = 0.0
                        tipo_val_ui = "N/A"
                    else:
                        resp_val_ui = resp_prev_val if permitir_editar else item_fijo["resp_defecto"]
                        peso_val_ui = peso_prev_val if permitir_editar else item_fijo["peso_defecto"]
                        tipo_val_ui = tipo_prev_val
    
                    st.session_state[f"tr_etapa_{i}_v{fv}"] = item_fijo["etapa"]
                    e_nom = col_etapa.text_input("Etapa", disabled=True, key=f"tr_etapa_{i}_v{fv}")
                    
                    deshabilitar_fec = (item_fijo["etapa"] == "Clasificación") or no_aplica
                    e_fec_val = col_fecha.date_input("Fecha *", value=fec_val_def, format="DD/MM/YYYY", disabled=deshabilitar_fec, key=f"tr_fecha_{i}_v{fv}")
    
                    # FIX: Obligar a Streamlit a refrescar el valor usando una key dinámica atada al peso
                    if not permitir_editar:
                        e_res = col_resp.text_input("Responsable *", value=resp_val_ui, disabled=True, key=f"tr_resp_dis_{i}_{resp_val_ui}_v{fv}")
                    else:
                        e_res = col_resp.text_input("Responsable *", value=resp_val_ui, key=f"tr_resp_{i}_v{fv}")
    
                    if deshabilitar_peso:
                        e_pes_str = col_peso.text_input("Peso (kg) *", value=f"{peso_val_ui:.2f}", disabled=True, key=f"tr_peso_dis_{i}_{peso_val_ui}_v{fv}")
                    else:
                        e_pes_str = col_peso.text_input("Peso (kg) *", value=f"{peso_val_ui:.2f}", key=f"tr_peso_{i}_v{fv}")
    
                    try: e_pes_num = float(e_pes_str)
                    except ValueError: e_pes_num = 0.0
    
                    if item_fijo["etapa"] == "Lavado":
                        peso_lavado_auto = 0.0 if no_aplica else e_pes_num
                    elif item_fijo["etapa"] == "Corte": 
                        peso_corte_auto = e_pes_num
    
                    st.session_state[f"tr_tipo_{i}_v{fv}"] = tipo_val_ui
                    e_tip = col_tipo.text_input("Tipo Registro", disabled=True, key=f"tr_tipo_{i}_v{fv}")
                    
                    if no_aplica:
                        e_fot = None
                        col_foto.info("No aplica")
                    else:
                        e_fot = col_foto.file_uploader("Evidencia", type=["jpg", "png", "jpeg"], key=f"tr_foto_{i}_v{fv}")
                        if e_fot is not None:
                            col_foto.image(e_fot, width=70)
                        elif foto_url_prev:
                            col_foto.image(foto_url_prev, width=70)
    
                    lista_trazabilidad.append({
                        "etapa": e_nom, "fecha": e_fec_val.strftime("%d/%m/%Y"), "responsable": e_res,
                        "peso": e_pes_num, "tipo_registro": e_tip, "editado": permitir_editar, "no_aplica": no_aplica,
                        "foto_up": e_fot, "foto_url": foto_url_prev if not no_aplica else "", 
                        "foto": e_fot if e_fot is not None else (foto_url_prev if not no_aplica else "")
                    })
    
            st.write("")
    
            # --- SECCIÓN 4: PRODUCTOS ---
            with st.container(border=True):
                st.subheader("4. Salida de Productos")
                
                with st.expander("Administrar Catálogo de Productos (Conectado a la Nube)"):
                    tab_p_add, tab_p_edit, tab_p_del = st.tabs(["Agregar Producto", "Modificar Nombre", "Eliminar de la Lista"])
    
                    with tab_p_add:
                        col_pa1, col_pa2 = st.columns([3, 1])
                        nuevo_producto_cat = col_pa1.text_input("Nombre del nuevo producto:", placeholder="Ej. Mochila ejecutiva", key=f"adm_prod_input_add_v{fv}")
                        if col_pa2.button("Guardar en Nube", use_container_width=True, key=f"btn_add_prod_cat_v{fv}"):
                            np_limpio = nuevo_producto_cat.strip()
                            if np_limpio and np_limpio not in st.session_state.catalogo_productos:
                                try: supabase.table("catalogos").insert({"tipo": "producto", "nombre": np_limpio, "valor_num": 0}).execute()
                                except Exception: pass
                                
                                if "Otro (Escribir nuevo producto)" in st.session_state.catalogo_productos:
                                    st.session_state.catalogo_productos.insert(-1, np_limpio)
                                else:
                                    st.session_state.catalogo_productos.append(np_limpio)
                                st.toast(f"✅ Producto guardado en la nube: {np_limpio}")
                                st.rerun()
    
                    with tab_p_edit:
                        col_pe1, col_pe2, col_pe3 = st.columns([2, 2, 1])
                        prods_editables = [p for p in st.session_state.catalogo_productos if "Otro" not in p]
                        prod_a_mod = col_pe1.selectbox("Producto a modificar:", prods_editables, key=f"adm_prod_sel_mod_v{fv}")
                        prod_modificado = col_pe2.text_input("Nombre corregido:", value=prod_a_mod if prod_a_mod else "", key=f"adm_prod_txt_mod_v{fv}")
                        if col_pe3.button("Actualizar", use_container_width=True, key=f"btn_edit_prod_cat_v{fv}"):
                            if prod_modificado.strip() and prod_a_mod in st.session_state.catalogo_productos:
                                try: supabase.table("catalogos").update({"nombre": prod_modificado.strip()}).eq("tipo", "producto").eq("nombre", prod_a_mod).execute()
                                except Exception: pass
                                
                                idx_mod = st.session_state.catalogo_productos.index(prod_a_mod)
                                st.session_state.catalogo_productos[idx_mod] = prod_modificado.strip()
                                st.toast(f"✅ Producto actualizado en la nube: {prod_modificado.strip()}")
                                st.rerun()
    
                    with tab_p_del:
                        col_pd1, col_pd2 = st.columns([3, 1])
                        prods_borrables = [p for p in st.session_state.catalogo_productos if "Otro" not in p]
                        prod_a_borrar = col_pd1.selectbox("Producto a eliminar del catálogo:", prods_borrables, key=f"adm_prod_sel_del_v{fv}")
                        if col_pd2.button("Eliminar", use_container_width=True, key=f"btn_del_prod_cat_v{fv}"):
                            if prod_a_borrar in st.session_state.catalogo_productos:
                                try: supabase.table("catalogos").delete().eq("tipo", "producto").eq("nombre", prod_a_borrar).execute()
                                except Exception: pass
                                
                                st.session_state.catalogo_productos.remove(prod_a_borrar)
                                st.toast(f"Producto eliminado de la nube: {prod_a_borrar}")
                                st.rerun()
    
                if "num_prods" not in st.session_state:
                    st.session_state.num_prods = 2
    
                col_btnp1, col_btnp2, _ = st.columns([1, 1, 4])
                if col_btnp1.button("Agregar Producto"):
                    st.session_state.num_prods += 1
                    st.rerun()
                if col_btnp2.button("Quitar Producto") and st.session_state.num_prods > 1:
                    st.session_state.num_prods -= 1
                    st.rerun()
    
                lista_productos = []
                total_prod_unid = 0
                saved_prods = dc.get("productos", [])
    
                for i in range(st.session_state.num_prods):
                    st.markdown(f"**Producto {i+1}**")
                    
                    col_psel, col_pnom_nuevo, col_pcant, col_pfoto = st.columns([3, 2.5, 1.5, 3])
    
                    prod_prev = saved_prods[i] if i < len(saved_prods) else {}
                    prod_nom_prev = prod_prev.get("producto", "")
                    cant_prev = int(prod_prev.get("cantidad", 0))
                    foto_url_prev = prod_prev.get("foto_url", "")
    
                    if prod_nom_prev and prod_nom_prev not in st.session_state.catalogo_productos:
                        st.session_state.catalogo_productos.insert(-1, prod_nom_prev)
    
                    idx_psel = st.session_state.catalogo_productos.index(prod_nom_prev) if prod_nom_prev in st.session_state.catalogo_productos else 0
    
                    prod_seleccionado = col_psel.selectbox("Seleccionar Producto Base *", st.session_state.catalogo_productos, index=idx_psel, key=f"prod_sel_{i}_v{fv}")
    
                    if prod_seleccionado == "Otro (Escribir nuevo producto)":
                        nuevo_nombre = col_pnom_nuevo.text_input("Escriba el Nuevo Producto *", key=f"prod_nuevo_txt_{i}_v{fv}")
                        nombre_final = nuevo_nombre.strip() if nuevo_nombre.strip() else f"Producto {i+1}"
                        if nuevo_nombre.strip() and nuevo_nombre.strip() not in st.session_state.catalogo_productos:
                            try: supabase.table("catalogos").insert({"tipo": "producto", "nombre": nuevo_nombre.strip(), "valor_num": 0}).execute()
                            except Exception: pass
                            st.session_state.catalogo_productos.insert(-1, nuevo_nombre.strip())
                    else:
                        st.session_state[f"prod_dis_{i}_v{fv}"] = prod_seleccionado
                        col_pnom_nuevo.text_input("Producto", disabled=True, key=f"prod_dis_{i}_v{fv}")
                        nombre_final = prod_seleccionado
    
                    p_cant = col_pcant.number_input("Cantidad (Unid.) *", min_value=0, value=cant_prev, key=f"prod_cant_{i}_v{fv}")
                    p_foto = col_pfoto.file_uploader("Evidencia Foto", type=["jpg", "png", "jpeg"], key=f"prod_foto_{i}_v{fv}")
    
                    if p_foto is not None:
                        col_pfoto.image(p_foto, width=80)
                    elif foto_url_prev:
                        col_pfoto.image(foto_url_prev, width=80)
    
                    total_prod_unid += p_cant
                    lista_productos.append({
                        "producto": nombre_final, "cantidad": p_cant,
                        "foto_up": p_foto, "foto_url": foto_url_prev, "foto": p_foto if p_foto is not None else foto_url_prev
                    })
    
                st.success(f"**Suma Total de Productos Obtenidos:** {total_prod_unid} unidades")
    
            st.write("")
    
            # --- SECCIÓN 5: BALANCE ---
            with st.container(border=True):
                st.subheader("5. Balance de Material")
                st.info(f"    **Material Recibido (calculado automáticamente):** {peso_total_recibido:.2f} kg")
    
                pct_aprov_auto = st.session_state.pct_aprovechamiento_random
                pct_transf_auto = min(st.session_state.pct_transformado_ratio, pct_aprov_auto - 0.05)
                pct_retazos_auto = pct_aprov_auto - pct_transf_auto
    
                saved_bm = dc.get("balance", {})
                editar_balance_prev = saved_bm.get("editar_manual", False)
    
                if editar_balance_prev:
                    mat_transf_def = float(saved_bm.get("mat_transformado", 0.0))
                    retazos_def = float(saved_bm.get("retazos_aprovechables", 0.0))
                    perdida_def = float(saved_bm.get("perdida_no_aprovechable", 0.0))
                else:
                    mat_transf_def = round(peso_total_recibido * pct_transf_auto, 2)
                    retazos_def = round(peso_total_recibido * pct_retazos_auto, 2)
                    perdida_def = round(peso_total_recibido - mat_transf_def - retazos_def, 2) if peso_total_recibido > 0 else 0.0
    
                editar_balance = st.checkbox("Editar balance manualmente", value=editar_balance_prev, key=f"chk_edit_balance_v{fv}")
    
                col_bm1, col_bm2 = st.columns(2)
                mat_transformado = col_bm1.number_input(
                    "Material transformado en productos (kg)",
                    min_value=0.0, value=float(mat_transf_def), step=0.1, disabled=not editar_balance,
                    key=f"bm_mat_transf_v{fv}",
                )
                retazos_aprovechables = col_bm2.number_input(
                    "Retazos aprovechables (kg)",
                    min_value=0.0, value=float(retazos_def), step=0.1, disabled=not editar_balance,
                    key=f"bm_retazos_v{fv}",
                )
    
                col_bm3, _ = st.columns([1, 1])
                perdida_no_aprovechable = col_bm3.number_input(
                    "Pérdida no aprovechable (kg)",
                    min_value=0.0, value=float(perdida_def), step=0.1, disabled=not editar_balance,
                    key=f"bm_perdida_v{fv}",
                )
    
                total_procesado = mat_transformado + retazos_aprovechables + perdida_no_aprovechable
    
                if peso_total_recibido > 0:
                    pct_aprovechamiento_total = ((mat_transformado + retazos_aprovechables) / peso_total_recibido) * 100
                    pct_perdida = (perdida_no_aprovechable / peso_total_recibido) * 100
                else:
                    pct_aprovechamiento_total = 0.0
                    pct_perdida = 0.0
    
                st.markdown("##### Resumen de Indicadores")
                ind1, ind2, ind3 = st.columns(3)
                ind1.metric("Total Procesado", f"{total_procesado:.2f} kg")
                ind2.metric("% Aprovechamiento Total", f"{pct_aprovechamiento_total:.2f}%")
                ind3.metric("% Pérdida", f"{pct_perdida:.2f}%")
    
            st.write("")
    
            # --- SECCIÓN 6: EMISIONES ---
            with st.container(border=True):
                st.subheader("6. Balance de Emisiones (CO₂e)")
                st.markdown("##### A. Cálculo de Transporte")
                st.caption("Destino Fijo: **Taller Las Flores, San Juan de Lurigancho (SJL)**")
    
                saved_trans = dc.get("transporte", {})
                dist_sel_prev = saved_trans.get("distrito", list(DISTANCIAS_LIMA_SJL.keys())[0])
                idx_dist = list(DISTANCIAS_LIMA_SJL.keys()).index(dist_sel_prev) if dist_sel_prev in DISTANCIAS_LIMA_SJL else 0
    
                col_t1, col_t2, col_t3, col_t4 = st.columns([2.5, 1.2, 1.8, 1.5])
                distrito_sel = col_t1.selectbox(
                    "Distrito de Origen (Recojo de Material) *", list(DISTANCIAS_LIMA_SJL.keys()), index=idx_dist, key=f"transporte_distrito_origen_v{fv}"
                )
    
                dist_defecto = float(DISTANCIAS_LIMA_SJL.get(distrito_sel, 0.0))
                saved_dist_km = float(saved_trans.get("distancia", dist_defecto)) if dist_sel_prev == distrito_sel else dist_defecto
    
                # FIX: Se añade el nombre del distrito al 'key' para forzar la actualización visual
                if distrito_sel == "Otro / Fuera de Lima (Ingreso manual)":
                    distancia_km = col_t2.number_input("Distancia (km) *", min_value=0.0, value=saved_dist_km, step=1.0, key=f"dist_km_manual_{distrito_sel}_v{fv}")
                else:
                    distancia_km = col_t2.number_input("Distancia (km)", min_value=0.0, value=saved_dist_km, step=0.5, key=f"dist_km_auto_{distrito_sel}_v{fv}")
    
                vehiculo_prev = saved_trans.get("vehiculo", list(FACTORES_TRANSPORTE.keys())[0])
                idx_veh = list(FACTORES_TRANSPORTE.keys()).index(vehiculo_prev) if vehiculo_prev in FACTORES_TRANSPORTE else 0
    
                vehiculo_sel = col_t3.selectbox("Tipo de Vehículo Utilizado", list(FACTORES_TRANSPORTE.keys()), index=idx_veh, key=f"transporte_vehiculo_v{fv}")
    
                rec_prev = saved_trans.get("recorrido", "Ida y Vuelta (2)")
                idx_rec = 0 if "2" in rec_prev else 1
                recorrido_tipo = col_t4.selectbox("Tipo de Recorrido", ["Ida y Vuelta (2)", "Ida sola (1)"], index=idx_rec, key=f"transporte_recorrido_v{fv}")
    
                factor_veh = FACTORES_TRANSPORTE[vehiculo_sel]
                mult_recorrido = 2.0 if "2" in recorrido_tipo else 1.0
                emisiones_transporte = distancia_km * mult_recorrido * factor_veh["consumo"] * factor_veh["factor"]
    
                st.caption(f"Distancia considerada: **{distancia_km:.1f} km** ({recorrido_tipo}) | Emisión de Transporte estimada: **{emisiones_transporte:.2f} kg CO₂e**")
    
                st.markdown("##### B. Lavandería y Taller de Corte (Calculado desde Trazabilidad)")
                emisiones_lavado = peso_lavado_auto * 0.30
                emisiones_corte = peso_corte_auto * 0.05
    
                clav, ccort = st.columns(2)
                clav.info(f"**Lavandería ({peso_lavado_auto:.2f} kg):** {emisiones_lavado:.2f} kg CO₂e *(Factor: 0.30)*")
                ccort.info(f"**Corte ({peso_corte_auto:.2f} kg):** {emisiones_corte:.2f} kg CO₂e *(Factor: 0.05)*")
    
                st.markdown("##### C. Cálculo de Bordado o Estampado")
                saved_bord = dc.get("bordado", {})
                cant_bord_prev = int(saved_bord.get("cantidad", 0))
                tipo_bord_prev = saved_bord.get("tipo", list(FACTORES_BORDADO.keys())[0])
                idx_tbord = list(FACTORES_BORDADO.keys()).index(tipo_bord_prev) if tipo_bord_prev in FACTORES_BORDADO else 0
    
                cb1, cb2 = st.columns(2)
                cant_prendas_bordado = cb1.number_input("Cantidad de prendas que requieren bordado o estampado", min_value=0, value=cant_bord_prev, step=1, key=f"bord_cant_v{fv}")
                tipo_diseno_bordado = cb2.selectbox("Tipo de Diseño / Complejidad", list(FACTORES_BORDADO.keys()), index=idx_tbord, key=f"bord_tipo_v{fv}")
    
                factor_bordado = FACTORES_BORDADO[tipo_diseno_bordado]
                emisiones_bordado = cant_prendas_bordado * factor_bordado
    
                st.caption(f"Emisión estimada (Bordado/Estampado): **{emisiones_bordado:.2f} kg CO₂e**")
    
                emisiones_proceso = emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado
                co2_neto = co2_evitado_total - emisiones_proceso
    
                st.warning(f"**Total Emisiones del Proceso:** {emisiones_proceso:.2f} kg CO₂e | **Impacto Ambiental Neto Evitado:** {co2_neto:.2f} kg CO₂e")
    
            st.write("")
    
            # --- SECCIÓN 7: IMPACTO SOCIAL ---
            with st.container(border=True):
                st.subheader("7. Equipo de Trabajo y Generación de Horas")
    
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
    
                h_col1, h_col2, h_col3, h_col4, h_col5, h_col6 = st.columns([1.5, 2.5, 0.8, 1.2, 1.2, 1.2])
                h_col1.markdown("**Rol**")
                h_col2.markdown("**Nombre**")
                h_col3.markdown("**Editar**")
                h_col4.markdown("**Días trabajados**")
                h_col5.markdown("**Hora/día**")
                h_col6.markdown("**Horas totales**")
    
                st.write("---")
    
                saved_ops = dc.get("operaciones", [])
    
                for idx, p_fijo in enumerate(PERSONAL_FIJO_OPERACIONES):
                    c_rol, c_nom, c_chk, c_dias, c_hdia, c_tot = st.columns([1.5, 2.5, 0.8, 1.2, 1.2, 1.2])
    
                    op_prev = saved_ops[idx] if idx < len(saved_ops) else {}
                    is_edited_op = op_prev.get("editado", False)
                    nom_prev_op = op_prev.get("nombre", p_fijo["nombre"])
    
                    rol_val = p_fijo["rol"]
                    st.session_state[f"ops_rol_{idx}_v{fv}"] = rol_val
                    c_rol.text_input("Rol", disabled=True, key=f"ops_rol_{idx}_v{fv}", label_visibility="collapsed")
    
                    editar_fila = c_chk.checkbox("✅", value=bool(is_edited_op), key=f"ops_chk_{idx}_v{fv}", label_visibility="collapsed")
                    nom_val = c_nom.text_input("Nombre", value=nom_prev_op, disabled=not editar_fila, key=f"ops_nom_{idx}_v{fv}", label_visibility="collapsed")
    
                    if rol_val == "Logística":
                        val_dias_defecto = dias_calc_log
                        val_hdia_defecto = hdia_calc_log
                    else:
                        val_dias_defecto = dias_calc_corte
                        val_hdia_defecto = hdia_calc_corte
    
                    dias_init = int(op_prev.get("dias", val_dias_defecto)) if is_edited_op else int(val_dias_defecto)
                    hdia_init = float(op_prev.get("horas_dia", val_hdia_defecto)) if is_edited_op else float(val_hdia_defecto)
    
                    val_dias = c_dias.number_input(
                        "Días", min_value=0, value=dias_init, step=1, disabled=not editar_fila,
                        key=f"ops_dias_dyn_{idx}_v{fv}", label_visibility="collapsed"
                    )
                    val_hdia = c_hdia.number_input(
                        "Hrs/Día", min_value=0.0, value=hdia_init, step=0.5, disabled=not editar_fila,
                        key=f"ops_hdia_dyn_{idx}_v{fv}", label_visibility="collapsed"
                    )
    
                    tot_hrs_pers = float(val_dias) * float(val_hdia)
                    st.session_state[f"ops_tot_{idx}_v{fv}"] = f"{tot_hrs_pers:.2f}"
                    c_tot.text_input("Total", disabled=True, key=f"ops_tot_{idx}_v{fv}", label_visibility="collapsed")
    
                    total_horas_ops += tot_hrs_pers
                    lista_operaciones.append({
                        "rol": rol_val, "nombre": nom_val, "dias": val_dias, "horas_dia": val_hdia,
                        "horas_totales": tot_hrs_pers, "editado": editar_fila,
                    })
    
                st.write("---")
    
                st.markdown("#### Confección y Acabado – Asignación de Personal")
                with st.expander("Administrar Catálogo de Personal (Conectado a la Nube)"):
                    tab_add, tab_edit, tab_del = st.tabs(["Agregar Personal", "Modificar Nombre", "Eliminar de la Lista"])
    
                    with tab_add:
                        col_a1, col_a2 = st.columns([3, 1])
                        nuevo_integrante = col_a1.text_input("Nombre completo de la nueva persona:", placeholder="Ej. Rosa María Quispe", key=f"adm_input_add_v{fv}")
                        if col_a2.button("Guardar en Nube", use_container_width=True, key=f"btn_add_pers_v{fv}"):
                            n_limpio = nuevo_integrante.strip()
                            if n_limpio and n_limpio not in st.session_state.lista_personal_confeccion:
                                try: supabase.table("catalogos").insert({"tipo": "personal", "nombre": n_limpio, "valor_num": 0}).execute()
                                except Exception: pass
                                
                                st.session_state.lista_personal_confeccion.append(n_limpio)
                                st.session_state.lista_personal_confeccion.sort()
                                st.toast(f"✅ Guardado en la nube: {n_limpio}")
                                st.rerun()
    
                    with tab_edit:
                        col_e1, col_e2, col_e3 = st.columns([2, 2, 1])
                        pers_a_mod = col_e1.selectbox("Persona a modificar:", st.session_state.lista_personal_confeccion, key=f"adm_sel_mod_v{fv}")
                        nombre_modificado = col_e2.text_input("Nombre corregido:", value=pers_a_mod, key=f"adm_txt_mod_v{fv}")
                        if col_e3.button("Actualizar", use_container_width=True, key=f"btn_edit_pers_v{fv}"):
                            if nombre_modificado.strip() and pers_a_mod in st.session_state.lista_personal_confeccion:
                                try: supabase.table("catalogos").update({"nombre": nombre_modificado.strip()}).eq("tipo", "personal").eq("nombre", pers_a_mod).execute()
                                except Exception: pass
                                
                                idx_mod = st.session_state.lista_personal_confeccion.index(pers_a_mod)
                                st.session_state.lista_personal_confeccion[idx_mod] = nombre_modificado.strip()
                                st.session_state.lista_personal_confeccion.sort()
                                st.toast(f"✅ Actualizado en la nube: {nombre_modificado.strip()}")
                                st.rerun()
    
                    with tab_del:
                        col_d1, col_d2 = st.columns([3, 1])
                        pers_a_borrar = col_d1.selectbox("Persona a eliminar del catálogo:", st.session_state.lista_personal_confeccion, key=f"adm_sel_del_v{fv}")
                        if col_d2.button("Eliminar", use_container_width=True, key=f"btn_del_pers_v{fv}"):
                            if pers_a_borrar in st.session_state.lista_personal_confeccion:
                                try: supabase.table("catalogos").delete().eq("tipo", "personal").eq("nombre", pers_a_borrar).execute()
                                except Exception: pass
                                
                                st.session_state.lista_personal_confeccion.remove(pers_a_borrar)
                                st.toast(f"Eliminado de la nube: {pers_a_borrar}")
                                st.rerun()
    
                lista_confeccion = []
                horas_confeccion_total = 0.0
                
                saved_conf_list = dc.get("confeccion", [])
    
                for idx, prod in enumerate(lista_productos):
                    p_nom = prod["producto"]
                    p_cant = prod["cantidad"]
    
                    tiempo_base_ia = estimar_tiempo_unidad(p_nom)
    
                    st.markdown(f"**Producto {idx+1}: {p_nom}** *(Cantidad Total: {p_cant} unid | Base IA Confección: {tiempo_base_ia:.2f} hrs/unid)*")
    
                    key_num_pers = f"num_pers_prod_{idx}"
                    if key_num_pers not in st.session_state:
                        st.session_state[key_num_pers] = 1
    
                    col_b1, col_b2, _ = st.columns([1.5, 1.5, 5])
                    if col_b1.button("Persona", key=f"add_pers_{idx}"):
                        st.session_state[key_num_pers] += 1
                        st.rerun()
                    if col_b2.button("Quitar", key=f"del_pers_{idx}") and st.session_state[key_num_pers] > 1:
                        st.session_state[key_num_pers] -= 1
                        st.rerun()
    
                    conf_del_prod = [c for c in saved_conf_list if c.get("producto") == p_nom]
    
                    for p_idx in range(st.session_state[key_num_pers]):
                        
                        c_rol, c_persona, c_cant_asig, c_tiempo, c_tot = st.columns([1.8, 3.0, 1.4, 1.8, 1.8])
    
                        c_item_prev = conf_del_prod[p_idx] if p_idx < len(conf_del_prod) else {}
                        rol_prev_val = c_item_prev.get("rol", "Confección")
                        
                        opciones_roles = ["Confección", "Acabado", "Entretela", "Estampado"]
                        idx_rol = opciones_roles.index(rol_prev_val) if rol_prev_val in opciones_roles else 0
    
                        rol_sel = c_rol.selectbox("Rol *", opciones_roles, index=idx_rol, key=f"soc_rol_{idx}_{p_idx}_v{fv}")
    
                        opciones_personas = list(st.session_state.lista_personal_confeccion)
                        opcion_otro = "Otro (Escribir nuevo nombre)"
                        if opcion_otro not in opciones_personas:
                            opciones_personas.append(opcion_otro)
    
                        pers_guardada = c_item_prev.get("persona", "")
                        if pers_guardada and pers_guardada not in opciones_personas and pers_guardada != opcion_otro:
                            st.session_state.lista_personal_confeccion.append(pers_guardada)
                            st.session_state.lista_personal_confeccion.sort()
                            opciones_personas = list(st.session_state.lista_personal_confeccion) + [opcion_otro]
    
                        idx_pers = opciones_personas.index(pers_guardada) if pers_guardada in opciones_personas else 0
    
                        persona_sel = c_persona.selectbox("Persona Encargada *", opciones_personas, index=idx_pers, key=f"soc_pers_sel_{idx}_{p_idx}_v{fv}")
    
                        if persona_sel == opcion_otro:
                            nuevo_nombre_escrito = c_persona.text_input("Escribe el nombre *", placeholder="Nombre y Apellido", key=f"soc_pers_txt_custom_{idx}_{p_idx}_v{fv}")
                            persona_nom = nuevo_nombre_escrito.strip() if nuevo_nombre_escrito.strip() else f"Persona {p_idx+1}"
                            if nuevo_nombre_escrito.strip() and nuevo_nombre_escrito.strip() not in st.session_state.lista_personal_confeccion:
                                try: supabase.table("catalogos").insert({"tipo": "personal", "nombre": nuevo_nombre_escrito.strip(), "valor_num": 0}).execute()
                                except Exception: pass
                                
                                st.session_state.lista_personal_confeccion.append(nuevo_nombre_escrito.strip())
                                st.session_state.lista_personal_confeccion.sort()
                        else:
                            persona_nom = persona_sel
    
                        cant_sugerida = max(1, int(p_cant / st.session_state[key_num_pers])) if p_cant > 0 else 0
                        cant_init = int(c_item_prev.get("cantidad", cant_sugerida))
    
                        limite_maximo = max(p_cant * 3, cant_init, 9999)
                        cant_asig = c_cant_asig.number_input("Unid. Asignadas *", min_value=0, max_value=limite_maximo, value=cant_init, key=f"soc_cant_{idx}_{p_idx}_v{fv}")
    
                        if rol_sel == "Confección":
                            tiempo_unitario = float(tiempo_base_ia)
                            st.session_state[f"calc_{idx}_{p_idx}_{rol_sel}_v{fv}"] = f"{tiempo_unitario:.3f} hrs"
                            c_tiempo.text_input("Tiempo/Unid (hrs) [Base IA]", disabled=True, key=f"calc_{idx}_{p_idx}_{rol_sel}_v{fv}")
                        elif rol_sel == "Acabado":
                            tiempo_unitario = round(tiempo_base_ia * 0.20, 3)
                            st.session_state[f"calc_{idx}_{p_idx}_{rol_sel}_v{fv}"] = f"{tiempo_unitario:.3f} hrs"
                            c_tiempo.text_input("Tiempo/Unid (hrs) [Acab. 20%]", disabled=True, key=f"calc_{idx}_{p_idx}_{rol_sel}_v{fv}")
                        elif rol_sel == "Entretela":
                            tiempo_unitario = round(tiempo_base_ia * 0.10, 3)
                            st.session_state[f"calc_{idx}_{p_idx}_{rol_sel}_v{fv}"] = f"{tiempo_unitario:.3f} hrs"
                            c_tiempo.text_input("Tiempo/Unid (hrs) [Entret. 10%]", disabled=True, key=f"calc_{idx}_{p_idx}_{rol_sel}_v{fv}")
                        elif rol_sel == "Estampado":
                            tiempo_unitario = round(5.0 / 60.0, 3)
                            st.session_state[f"calc_{idx}_{p_idx}_{rol_sel}_v{fv}"] = f"{tiempo_unitario:.3f} hrs"
                            c_tiempo.text_input("Tiempo/Unid (hrs) [5 min]", disabled=True, key=f"calc_{idx}_{p_idx}_{rol_sel}_v{fv}")
                        else:
                            tunit_init = float(c_item_prev.get("tiempo_unitario", tiempo_base_ia))
                            tiempo_unitario = c_tiempo.number_input("Tiempo/Unid (hrs) *", min_value=0.0, value=tunit_init, step=0.05, key=f"soc_tunit_{idx}_{p_idx}_{p_nom}_v{fv}")
    
                        horas_persona = cant_asig * tiempo_unitario
                        st.session_state[f"soc_htot_{idx}_{p_idx}_v{fv}"] = f"{horas_persona:.2f} hrs"
                        c_tot.text_input("Horas Totales", disabled=True, key=f"soc_htot_{idx}_{p_idx}_v{fv}")
    
                        horas_confeccion_total += horas_persona
                        
                        lista_confeccion.append({
                            "producto": p_nom, "rol": rol_sel, "persona": persona_nom,
                            "cantidad": cant_asig, "tiempo_unitario": tiempo_unitario, "horas_totales": horas_persona,
                        })
    
                total_horas_social = total_horas_ops + horas_confeccion_total
                
                nombres_unicos = set()
                for op in lista_operaciones:
                    if op.get("nombre", "").strip():
                        nombres_unicos.add(op["nombre"].strip().title())
                for conf in lista_confeccion:
                    if conf.get("persona", "").strip():
                        nombres_unicos.add(conf["persona"].strip().title())
                        
                total_personas_social = len(nombres_unicos)
    
                st.info(f"‍‍**Impacto Social Total:** {total_horas_social:.2f} horas generadas | {total_personas_social} personas beneficiadas (conteo único).")
    
            st.write("")
    
            # --- SECCIÓN 8: ANEXOS ---
            with st.container(border=True):
                st.subheader("8. Anexos (Registro Fotográfico Adicional)")
                st.caption("Agrega fotografías adicionales de colaboradoras con sus productos, procesos en taller, etc.")
    
                col_anx1, col_anx2, _ = st.columns([1, 1, 4])
                if col_anx1.button("Agregar Anexo"):
                    st.session_state.num_anexos += 1
                    st.rerun()
                if col_anx2.button("Quitar Anexo") and st.session_state.num_anexos > 0:
                    st.session_state.num_anexos -= 1
                    st.rerun()
    
                lista_anexos = []
                saved_anexos = dc.get("anexos", [])
    
                for a_i in range(st.session_state.num_anexos):
                    st.markdown(f"**Evidencia Anexa {a_i+1}**")
                    
                    col_afoto, col_anota = st.columns([1.5, 3])
    
                    anx_prev = saved_anexos[a_i] if a_i < len(saved_anexos) else {}
                    nota_prev = anx_prev.get("nota", "")
                    foto_url_prev = anx_prev.get("foto_url", "")
    
                    foto_anx = col_afoto.file_uploader("Fotografía de Evidencia", type=["jpg", "png", "jpeg"], key=f"anx_foto_{a_i}_v{fv}")
    
                    if foto_anx is not None:
                        col_afoto.image(foto_anx, width=110)
                    elif foto_url_prev:
                        col_afoto.image(foto_url_prev, width=110)
    
                    nota_anx = col_anota.text_area("Nota / Descripción de la evidencia", value=nota_prev, placeholder="Ej. Colaboradora elaborando productos...", key=f"anx_nota_{a_i}_v{fv}", height=90)
    
                    lista_anexos.append({
                        "foto_up": foto_anx, "foto_url": foto_url_prev, "nota": nota_anx, "foto": foto_anx if foto_anx is not None else foto_url_prev
                    })
    
            st.write("")
    
            def _validar_informe_final(cliente_val, ruc_val, responsable_val, origen_val, items_val):
                errores = []
                if not cliente_val.strip(): errores.append("Falta 'Cliente / Empresa' en Ficha General.")
                if not ruc_val.strip() or not re.fullmatch(r"\d{11}", ruc_val.strip()): errores.append("El 'RUC' debe tener 11 dígitos numéricos.")
                if not responsable_val.strip(): errores.append("Falta 'Responsable' en Ficha General.")
                if not origen_val.strip(): errores.append("Falta 'Punto Origen' en Ficha General.")
                for i_item, v_item in enumerate(items_val, 1):
                    if v_item["unidades"] <= 0 or v_item["peso_total"] <= 0:
                        errores.append(f"En Ingreso de Material (Ítem {i_item}), las unidades y el peso total deben ser mayores a 0.")
                return errores
    
            def procesar_fotos_y_armar_detalle():
                import time
                ts = int(time.time())
                
                items_db = []
                for idx, it in enumerate(lista_items):
                    url = it["foto_url"]
                    if it["foto_up"] is not None:
                        it["foto_up"].seek(0)
                        url = subir_imagen_supabase(f"fotos/{codigo_proy}/item_{idx}_{ts}.jpg", it["foto_up"].read())
                    items_db.append({
                        "descripcion": it["descripcion"], "unidades": it["unidades"],
                        "peso_unitario": it["peso_unitario"], "peso_total": it["peso_total"], "foto_url": url
                    })
                    
                traza_db = []
                for idx, tr in enumerate(lista_trazabilidad):
                    url = tr["foto_url"]
                    if tr["foto_up"] is not None:
                        tr["foto_up"].seek(0)
                        url = subir_imagen_supabase(f"fotos/{codigo_proy}/traza_{idx}_{ts}.jpg", tr["foto_up"].read())
                    traza_db.append({
                        "etapa": tr["etapa"], "fecha": tr["fecha"], "responsable": tr["responsable"],
                        "peso": tr["peso"], "tipo_registro": tr["tipo_registro"], "editado": tr.get("editado", False), 
                        "no_aplica": tr.get("no_aplica", False), "foto_url": url
                    })
    
                prods_db = []
                for idx, pr in enumerate(lista_productos):
                    url = pr["foto_url"]
                    if pr["foto_up"] is not None:
                        pr["foto_up"].seek(0)
                        url = subir_imagen_supabase(f"fotos/{codigo_proy}/prod_{idx}_{ts}.jpg", pr["foto_up"].read())
                    prods_db.append({
                        "producto": pr["producto"], "cantidad": pr["cantidad"], "foto_url": url
                    })
                    
                anexos_db = []
                for idx, ax in enumerate(lista_anexos):
                    url = ax["foto_url"]
                    if ax.get("foto_up") is not None:
                        ax["foto_up"].seek(0)
                        url = subir_imagen_supabase(f"fotos/{codigo_proy}/anexo_{idx}_{ts}.jpg", ax["foto_up"].read())
                    anexos_db.append({
                        "nota": ax["nota"], "foto_url": url
                    })
    
                return {
                    "guia_remision": guia_remision,
                    "responsables_seleccionados": responsables_seleccionados,
                    "origen": origen, "num_items": st.session_state.num_items,
                    "items": items_db, "trazabilidad": traza_db, "num_prods": st.session_state.num_prods,
                    "productos": prods_db,
                    "balance": {
                        "editar_manual": editar_balance, "mat_transformado": mat_transformado,
                        "retazos_aprovechables": retazos_aprovechables, "perdida_no_aprovechable": perdida_no_aprovechable,
                    },
                    "transporte": {
                        "distrito": distrito_sel, "distancia": distancia_km, "vehiculo": vehiculo_sel, "recorrido": recorrido_tipo,
                    },
                    "bordado": {"cantidad": cant_prendas_bordado, "tipo": tipo_diseno_bordado},
                    "operaciones": [
                        {"rol": op["rol"], "nombre": op["nombre"], "dias": op["dias"], "horas_dia": op["horas_dia"], "horas_totales": op["horas_totales"], "editado": op.get("editado", False)}
                        for op in lista_operaciones
                    ],
                    "confeccion_num_pers": {f"num_pers_prod_{idx_c}": st.session_state.get(f"num_pers_prod_{idx_c}", 1) for idx_c in range(len(lista_productos))},
                    "confeccion": [
                        {"producto": c["producto"], "rol": c["rol"], "persona": c["persona"], "cantidad": c["cantidad"], "tiempo_unitario": c["tiempo_unitario"], "horas_totales": c["horas_totales"]}
                        for c in lista_confeccion
                    ],
                    "num_anexos": st.session_state.num_anexos,
                    "anexos": anexos_db,
                }
    
            with st.container(border=True):
                col_gen1, col_gen2 = st.columns([2, 1])
    
                if col_gen2.button("Guardar como Borrador", use_container_width=True):
                    try:
                        with st.spinner("Guardando en la base de datos y subiendo fotos a la nube..."):
                            datos_detalle = procesar_fotos_y_armar_detalle()
    
                            datos_borrador = {
                                "codigo": codigo_proy,
                                "cliente": cliente,
                                "ruc": ruc,
                                "tipo_proyecto": proyecto_nom,
                                "responsable": responsable,
                                "fecha": f"{fe_inicio} - {fe_fin}",
                                "estado": "EN_PROCESO",
                                "peso_recibido": peso_total_recibido,
                                "peso_transformado": mat_transformado,
                                "aprovechamiento": pct_aprovechamiento_total,
                                "co2_neto": co2_neto,
                                "horas_totales": total_horas_social,
                                "productos_unids": total_prod_unid,
                                "punto_origen": origen,
                                "guia": guia_remision,
                                "datos_completos": datos_detalle,
                            }
    
                            proyecto_id = p_edit.get("id")
                            if not proyecto_id:
                                busca_existente = supabase.table("proyectos").select("id").eq("codigo", codigo_proy).execute()
                                if busca_existente.data:
                                    proyecto_id = busca_existente.data[0]["id"]
                            
                            if proyecto_id:
                                supabase.table("proyectos").update(datos_borrador).eq("id", proyecto_id).execute()
                                datos_borrador["id"] = proyecto_id
                            else:
                                res = supabase.table("proyectos").insert(datos_borrador).execute()
                                if res.data:
                                    datos_borrador["id"] = res.data[0]["id"]
    
                        st.success("✅ Borrador y fotos guardados exitosamente.")
                        
                        st.session_state.form_version += 1 
                        datos_borrador["datos_formulario"] = datos_detalle
                        st.session_state.proyecto_editar = datos_borrador
    
                        st.session_state.documentos_descarga = None
                        st.rerun()
    
                    except Exception as e:
                        st.error(f"⚠️ Error al guardar el borrador: {e}")
    
                if col_gen1.button("Generar Reportes Oficiales (Informe + Constancia)", type="primary", use_container_width=True):
                    errores_final = _validar_informe_final(cliente, ruc, responsable, origen, lista_items)
                    if errores_final:
                        st.error("⚠️  Por favor, corrige los siguientes errores antes de generar los reportes:")
                        for err in errores_final: st.markdown(f"- {err}")
                    else:
                        with st.spinner("Generando documentos, subiendo fotos y respaldando en la nube..."):
                            try:
                                # CORRECCIÓN: Ahora se guarda directamente en bytes_informe
                                bytes_informe = generar_pdf_oficial(
                                    cliente, ruc, proyecto_nom, codigo_proy, fe_inicio, fe_fin, responsable, area,
                                    "Textiles en desuso", "Upcycling", "Kilogramos (kg)", guia_remision, origen, destino,
                                    lista_items, lista_trazabilidad, lista_productos, mat_transformado, retazos_aprovechables,
                                    perdida_no_aprovechable, total_procesado, pct_aprovechamiento_total, pct_perdida,
                                    lista_operaciones, lista_confeccion, total_horas_social, total_personas_social,
                                    co2_evitado_total, emisiones_transporte, emisiones_lavado, emisiones_corte, emisiones_bordado,
                                    lista_anexos=lista_anexos,
                                )

                                # Definir el texto dinámico según el tipo de proyecto seleccionado
                                if proyecto_nom == "Mermas Textiles":
                                    titulo_constancia = "Constancia de valorización de mermas textiles"
                                    tipo_proyecto_texto = "mermas textiles"
                                elif proyecto_nom == "Banner":
                                    titulo_constancia = "Constancia de valorización y upcycling de banners"
                                    tipo_proyecto_texto = "banners publicitarios"
                                elif proyecto_nom == "Cambio logo":
                                    titulo_constancia = "Constancia de servicios de customización y cambio de logo"
                                    tipo_proyecto_texto = "textiles para servicio de customización"
                                else:
                                    titulo_constancia = "Constancia de transformación de uniformes en desuso"
                                    tipo_proyecto_texto = "uniformes en desuso"

                                mes_fin_nombre = MESES_ESPANOL.get(fe_fin_dt.month, "")
                                contexto_word = {
                                    "titulo_constancia": titulo_constancia,"tipo_proyecto_texto": tipo_proyecto_texto,
                                    "cliente": cliente.upper(), "mes": mes_fin_nombre, "anio": str(fe_fin_dt.year),
                                    "peso_recibido": f"{peso_total_recibido:.1f}", "unidades_ingreso": str(total_piezas_ingresadas),
                                    "co2_evitado": f"{co2_neto:.2f}", "aprovechamiento": f"{pct_aprovechamiento_total:.2f}",
                                    "total_mujeres": str(total_personas_social), "total_horas": f"{total_horas_social:.1f}",
                                    "productos_elaborados": str(total_prod_unid),
                                    "fecha_cierre": f"{fe_fin_dt.strftime('%d')} de {mes_fin_nombre} de {fe_fin_dt.year}",
                                }
                                bytes_constancia = generar_constancia_desde_plantilla_word(contexto_word, ruta_plantilla="plantilla_constancia.docx")
    
                                cliente_limpio = cliente.strip().replace("/", "-")
                                nombre_informe_limpio = f"Informe_Tecnico_{cliente_limpio}.pdf"
                                nombre_constancia_limpia = f"Constancia_{cliente_limpio}.pdf"
                                nombre_zip_limpio = f"Documentos_{cliente_limpio}.zip"
    
                                zip_buffer = io.BytesIO()
                                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                                    zip_file.writestr(nombre_informe_limpio, bytes_informe)
                                    zip_file.writestr(nombre_constancia_limpia, bytes_constancia)
                                zip_buffer.seek(0)
                                bytes_zip = zip_buffer.getvalue()
    
                                url_informe = subir_pdf_supabase(f"Informe_{codigo_proy}.pdf", bytes_informe)
                                url_constancia = subir_pdf_supabase(f"Constancia_{codigo_proy}.pdf", bytes_constancia)
                                
                                st.session_state.pop("_drive_last_error", None)
                                try:
                                    nombre_subcarpeta = f"Pedido {fe_fin_dt.strftime('%d-%m-%Y')} (PIN {st.session_state.uid_proyecto})"
                                    carpeta_destino_id = obtener_carpeta_destino_drive(cliente, fe_fin_dt, nombre_subcarpeta)
                                    
                                    subir_a_drive(nombre_informe_limpio, bytes_informe, "application/pdf", custom_folder_id=carpeta_destino_id)
                                    subir_a_drive(nombre_constancia_limpia, bytes_constancia, "application/pdf", custom_folder_id=carpeta_destino_id)
                                    subir_a_drive(nombre_zip_limpio, bytes_zip, "application/zip", custom_folder_id=carpeta_destino_id)
                                except Exception as e_drive:
                                    st.session_state["_drive_last_error"] = str(e_drive)
                                drive_error_actual = st.session_state.pop("_drive_last_error", None)
    
                                st.session_state.documentos_descarga = {
                                    "codigo": codigo_proy, 
                                    "cliente_limpio": cliente_limpio,
                                    "bytes_informe": bytes_informe,
                                    "bytes_constancia": bytes_constancia, 
                                    "bytes_zip": bytes_zip,
                                    "drive_error": drive_error_actual,
                                }
    
                                try:
                                    datos_detalle = procesar_fotos_y_armar_detalle()
    
                                    datos_completado = {
                                        "codigo": codigo_proy, "cliente": cliente, "ruc": ruc, "tipo_proyecto": proyecto_nom,
                                        "responsable": responsable, "fecha": f"{fe_inicio} - {fe_fin}", "estado": "COMPLETADO",
                                        "peso_recibido": peso_total_recibido, "peso_transformado": mat_transformado,
                                        "aprovechamiento": pct_aprovechamiento_total, "co2_neto": co2_neto,
                                        "horas_totales": total_horas_social, "productos_unids": total_prod_unid,
                                        "punto_origen": origen, "pdf_url": url_informe if url_informe else p_edit.get("pdf_url", ""),
                                        "constancia_url": url_constancia if url_constancia else p_edit.get("constancia_url", ""),
                                        "datos_completos": datos_detalle,
                                    }
                                    
                                    proyecto_id = p_edit.get("id")
                                    if not proyecto_id:
                                        busca_existente = supabase.table("proyectos").select("id").eq("codigo", codigo_proy).execute()
                                        if busca_existente.data: proyecto_id = busca_existente.data[0]["id"]
                                    
                                    if proyecto_id:
                                        supabase.table("proyectos").update(datos_completado).eq("id", proyecto_id).execute()
                                    else:
                                        supabase.table("proyectos").insert(datos_completado).execute()
                                        
                                    st.session_state.proyecto_editar = {}
                                    st.session_state.uid_proyecto = str(random.randint(1000, 9999))
                                    st.session_state.form_version += 1
                                    st.rerun()
    
                                except Exception as e_bd:
                                    st.error(f"⚠️ Documentos creados, pero falló la actualización de BD: {e_bd}")
    
                            except Exception as e:
                                st.error(f"❌ Error crítico al procesar los documentos: {e}")
    
            if st.session_state.documentos_descarga:
                docs = st.session_state.documentos_descarga
                if docs.get("drive_error"):
                    st.warning(
                        f"⚠️ Los reportes se generaron y guardaron correctamente, pero NO se pudieron "
                        f"respaldar en Google Drive. Detalle: {docs['drive_error']}"
                    )
                else:
                    st.success("✅ ¡Reportes generados, guardados y respaldados en Drive con éxito!")
    
                c_dzip, c_dinf, c_dconst = st.columns([1.5, 1.2, 1.2])
                c_dzip.download_button("Descargar Ambos (.ZIP)", data=docs["bytes_zip"], file_name=f"Documentos_{docs['cliente_limpio']}.zip", mime="application/zip", use_container_width=True, type="primary")
                c_dinf.download_button("Descargar Informe PDF", data=docs["bytes_informe"], file_name=f"Informe_Tecnico_{docs['cliente_limpio']}.pdf", mime="application/pdf", use_container_width=True)
                c_dconst.download_button("Descargar Constancia PDF", data=docs["bytes_constancia"], file_name=f"Constancia_{docs['cliente_limpio']}.pdf", mime="application/pdf", use_container_width=True)

# =========================================================================
    # ENTORNO 2: ONG MUJER POWER (CIRCULAR)
    # =========================================================================
    elif st.session_state.espacio == "circular":
        
        # --- NUEVA FUNCIÓN PARA SEPARAR EL DRIVE DE LA ONG ---
        # Crea una carpeta maestra llamada "ONG MUJER POWER" dentro de tu Drive actual
        def obtener_carpeta_ong_drive(cliente_ong: str, fecha_dt, nombre_subcarpeta: str):
            try:
                service, root_folder_id = _drive_service()
                if service is None:
                    return None

                # 1. Carpeta Maestra "ONG MUJER POWER" dentro de la raíz actual
                query_ong = f"name='ONG MUJER POWER' and mimeType='application/vnd.google-apps.folder' and '{root_folder_id}' in parents and trashed=false"
                res_ong = service.files().list(q=query_ong, fields='files(id)').execute()
                id_ong = res_ong.get('files')[0].get('id') if res_ong.get('files', []) else service.files().create(body={'name': 'ONG MUJER POWER', 'mimeType': 'application/vnd.google-apps.folder', 'parents': [root_folder_id]}, fields='id').execute().get('id')

                # 2. Año
                nombre_anio = str(fecha_dt.year)
                query_anio = f"name='{nombre_anio}' and mimeType='application/vnd.google-apps.folder' and '{id_ong}' in parents and trashed=false"
                res_anio = service.files().list(q=query_anio, fields='files(id)').execute()
                id_anio = res_anio.get('files')[0].get('id') if res_anio.get('files', []) else service.files().create(body={'name': nombre_anio, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [id_ong]}, fields='id').execute().get('id')

                # 3. Mes
                meses = {1:"ENERO", 2:"FEBRERO", 3:"MARZO", 4:"ABRIL", 5:"MAYO", 6:"JUNIO", 7:"JULIO", 8:"AGOSTO", 9:"SETIEMBRE", 10:"OCTUBRE", 11:"NOVIEMBRE", 12:"DICIEMBRE"}
                nombre_mes = meses.get(fecha_dt.month, 'MES')
                query_mes = f"name='{nombre_mes}' and mimeType='application/vnd.google-apps.folder' and '{id_anio}' in parents and trashed=false"
                res_mes = service.files().list(q=query_mes, fields='files(id)').execute()
                id_mes = res_mes.get('files')[0].get('id') if res_mes.get('files', []) else service.files().create(body={'name': nombre_mes, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [id_anio]}, fields='id').execute().get('id')

                # 4. Empresa Donante
                nombre_cli = cliente_ong.strip().upper().replace("'", "")
                query_cli = f"name='{nombre_cli}' and mimeType='application/vnd.google-apps.folder' and '{id_mes}' in parents and trashed=false"
                res_cli = service.files().list(q=query_cli, fields='files(id)').execute()
                id_cli = res_cli.get('files')[0].get('id') if res_cli.get('files', []) else service.files().create(body={'name': nombre_cli, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [id_mes]}, fields='id').execute().get('id')

                # 5. Subcarpeta del Evento
                query_proy = f"name='{nombre_subcarpeta}' and mimeType='application/vnd.google-apps.folder' and '{id_cli}' in parents and trashed=false"
                res_proy = service.files().list(q=query_proy, fields='files(id)').execute()
                id_proy = res_proy.get('files')[0].get('id') if res_proy.get('files', []) else service.files().create(body={'name': nombre_subcarpeta, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [id_cli]}, fields='id').execute().get('id')

                return id_proy
            except Exception as e:
                st.session_state["_drive_last_error"] = f"Carpetas Drive ONG: {e}"
                return None
        # ------------------------------------------------------

        # FACTORES RESPALDADOS POR EPA WARM Y DEFRA
        FACTORES_CO2_ONG = {
            "PET": 1.5, "Cocalata": 8.0, "Papel Blanco": 0.9, "Cartón": 0.8,
            "Chapita": 1.2, "Aluminio": 8.0, "Lata de Leche": 1.5,
            "RAEE Cat 1 (Línea Blanca)": 15.0,         
            "RAEE Cat 2 (Pequeños Electrod.)": 1.8,    
            "RAEE Cat 3 (Informática/Celulares)": 4.2, 
            "RAEE Cat 4 (Audio/TVs)": 2.2 
        }

        CATALOGO_EORS = {
            "FERROCAS E.I.R.L.": "EO-RS-0380-19-150118",
            "GRENE SERVICIOS GENERALES S.A.C.": "EO-RS-00233-2021-MINAM/VMGA/DGRS",
            "PRODECI EORS S.A.": "EO-RS-00100-2022-MINAM/VMGA/DGRS",
            "CIA QUIMICA INDUSTRIAL DEL PACIFICO S.A.": "EO-RS-0330-19-70101"
        }

        st.markdown(
            """
            <div class="hero-header" style="border-left: 6px solid #7C3AED;">
                <h1 style="color: #7C3AED !important;">Sistema Circular - ONG Mujer Power</h1>
                <p>Gestión y trazabilidad de residuos sólidos valorizables.</p>
            </div>
            """, unsafe_allow_html=True
        )

        pestaña_activa = st.session_state.get("pestaña_activa_ong", "Nuevo Registro")

        if pestaña_activa == "Nuevo Registro":
            st.subheader("Ficha de Ingreso de Residuos")
            
            with st.container(border=True):
                st.markdown("##### 1. Datos del Donante / Campaña")
                c1, c2 = st.columns(2)
                empresa_ong = c1.text_input("Empresa / Organización Donante *", placeholder="Ej. UPN, THE GRID")
                ruc_ong = c2.text_input("RUC (Opcional)")
                
                direccion_ong = st.text_input("Dirección Fiscal de la Empresa *", placeholder="Ej. Av. Los Ingenieros 123, Lima")

                c3, c4 = st.columns(2)
                fecha_ong = c3.date_input("Fecha de Recolección *", format="DD/MM/YYYY")
                evento_ong = c4.text_input("Nombre del Evento o Campaña *", placeholder="Ej. Reciclatón 1ra entrega")

            st.write("")

            with st.container(border=True):
                st.markdown("##### 2. Trazabilidad EO-RS")
                c_trans, c_val = st.columns(2)
                eors_transporte = c_trans.selectbox("EO-RS Transportista *", list(CATALOGO_EORS.keys()))
                eors_valorizacion = c_val.selectbox("EO-RS Valorizadora / Acondicionadora *", list(CATALOGO_EORS.keys()))

            st.write("")

            with st.container(border=True):
                st.markdown("##### 3. Detalle de Residuos Valorizables")
                
                lista_materiales_ong = []
                total_kg_ong = 0.0
                total_co2_ong = 0.0

                categorias_fijas = list(FACTORES_CO2_ONG.keys())

                h_mat, h_peso, h_co2 = st.columns([2, 1, 1])
                h_mat.markdown("<span style='font-size: 0.85rem; font-weight: 700; color: #64748B;'>MATERIAL</span>", unsafe_allow_html=True)
                h_peso.markdown("<span style='font-size: 0.85rem; font-weight: 700; color: #64748B;'>PESO (KG)</span>", unsafe_allow_html=True)
                h_co2.markdown("<span style='font-size: 0.85rem; font-weight: 700; color: #64748B;'>CO₂E EVITADO</span>", unsafe_allow_html=True)
                st.write("---")

                for i, material in enumerate(categorias_fijas):
                    c_mat, c_cant, c_co2 = st.columns([2, 1, 1])
                    c_mat.markdown(f"**{material}**")
                    factor_usado = FACTORES_CO2_ONG.get(material, 1.0)
                    kg_val = c_cant.number_input(f"Peso {material}", min_value=0.0, step=0.5, key=f"ong_kg_{i}", label_visibility="collapsed")
                    
                    co2_calculado = kg_val * factor_usado
                    c_co2.text_input(f"CO2 {material}", value=f"{co2_calculado:,.2f} kg", disabled=True, key=f"ong_co2_calc_{i}", label_visibility="collapsed")
                    
                    if kg_val > 0:
                        lista_materiales_ong.append({"material": material, "cantidad_kg": kg_val, "factor_co2_aplicado": factor_usado, "co2_evitado": co2_calculado})
                        total_kg_ong += kg_val
                        total_co2_ong += co2_calculado

                st.write("")
                st.success(f"**Total Recuperado:** {total_kg_ong:,.2f} Kg | **Total CO₂e Evitado:** {total_co2_ong:,.2f} Kg")

            st.write("")

            with st.container(border=True):
                st.markdown("##### Registrar y Generar Documentos")
                
                if st.button("Registrar, Subir a Drive y Generar Constancia PDF", type="primary", use_container_width=True):
                    if not empresa_ong.strip() or not direccion_ong.strip() or not evento_ong.strip():
                        st.error("⚠️ Falta el Nombre de la Empresa, Dirección o Evento.")
                    elif total_kg_ong <= 0:
                        st.error("⚠️ Ingresa al menos un material con un peso mayor a 0 kg.")
                    else:
                        with st.spinner("Registrando en la nube, procesando PDF y subiendo a Drive..."):
                            try:
                                # 1. Lógica del texto de operadoras
                                reg_transporte = CATALOGO_EORS[eors_transporte]
                                reg_valorizacion = CATALOGO_EORS[eors_valorizacion]
                                
                                if eors_transporte == eors_valorizacion:
                                    texto_op = f"los cuales fueron recolectados, transportados y valorizados por la empresa operadora {eors_transporte}, con Registro Autoritativo N° {reg_transporte}, entidad encargada de su correspondiente valorización y aprovechamiento final,"
                                else:
                                    texto_op = f"los cuales fueron recolectados y transportados por la empresa operadora de transporte de residuos sólidos {eors_transporte}, con Registro Autoritativo N° {reg_transporte}, y posteriormente entregados a la empresa operadora de valorización {eors_valorizacion}, con Registro Autoritativo N° {reg_valorizacion}, entidad encargada de su correspondiente valorización y aprovechamiento final,"

                                dict_pesos = { mat: 0.0 for mat in FACTORES_CO2_ONG.keys() }
                                for mat in lista_materiales_ong: dict_pesos[mat["material"]] = mat["cantidad_kg"]

                                # Suma de categorías RAEE para la constancia Word
                                kg_raee_total = dict_pesos["RAEE Cat 1 (Línea Blanca)"] + dict_pesos["RAEE Cat 2 (Pequeños Electrod.)"] + dict_pesos["RAEE Cat 3 (Informática/Celulares)"] + dict_pesos["RAEE Cat 4 (Audio/TVs)"]

                                meses_str = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                                mes_actual = meses_str[fecha_ong.month - 1]

                                # --- CÁLCULO DE CORRELATIVO Y RASTREO DE SEDE ---
                                try:
                                    res_corr = supabase.table("ong_registros").select("id").order("id", desc=True).limit(1).execute()
                                    siguiente_id = res_corr.data[0]["id"] + 1 if res_corr.data else 1
                                except Exception:
                                    siguiente_id = random.randint(1000, 9999) 
                                
                                correlativo_secuencial = f"{siguiente_id:03d}"

                                # Verificamos si es el aliado de Trujillo para marcar su código y su evento
                                si_es_arfumm = (st.session_state.get("rol") == "aliado_arfumm")
                                prefijo_codigo = "ARF" if si_es_arfumm else "ONG"
                                evento_final = evento_ong.strip() + " (Sede Arfumm Trujillo)" if si_es_arfumm else evento_ong.strip()
                                # -----------------------------------------

                                contexto = {
                                    "anio": str(fecha_ong.year), "correlativo": correlativo_secuencial,
                                    "partida": "14886638", "ciudad_sede": "Trujillo" if si_es_arfumm else "Lima", "resolucion_donaciones": "", 
                                    "empresa_donante": empresa_ong.strip(), "ruc_donante": ruc_ong.strip() if ruc_ong.strip() else "S/N",
                                    "direccion_donante": direccion_ong.strip(), "mes": mes_actual, "texto_operadoras": texto_op,
                                    "kg_pet": f"{dict_pesos['PET']:,.2f}", "kg_cocalata": f"{dict_pesos['Cocalata']:,.2f}",
                                    "kg_papel": f"{dict_pesos['Papel Blanco']:,.2f}", "kg_carton": f"{dict_pesos['Cartón']:,.2f}",
                                    "kg_chapita": f"{dict_pesos['Chapita']:,.2f}", "kg_raee": f"{kg_raee_total:,.2f}",
                                    "kg_aluminio": f"{dict_pesos['Aluminio']:,.2f}", "kg_lata": f"{dict_pesos['Lata de Leche']:,.2f}",
                                    "total_kg": f"{total_kg_ong:,.2f}", "ciudad_emision": "Trujillo" if si_es_arfumm else "Lima", "dia": str(datetime.date.today().day)
                                }

                                # 2. Generar el PDF
                                pdf_bytes = generar_constancia_desde_plantilla_word(contexto, "Plantilla_Constancia_Mujer_Power.docx")
                                
                                # Aplicamos el prefijo para saber quién lo hizo
                                codigo_ong = f"{prefijo_codigo}_{empresa_ong[:4].upper().replace(' ', '')}_{fecha_ong.strftime('%m%y')}-{correlativo_secuencial}"
                                nombre_pdf = f"Constancia_{codigo_ong}.pdf"

                                # 3. Subir el PDF a Supabase Storage
                                url_pdf = subir_pdf_supabase(nombre_pdf, pdf_bytes)

                                # 4. Subir a Google Drive (USANDO LA NUEVA ESTRUCTURA SEPARADA)
                                st.session_state.pop("_drive_last_error", None)
                                try:
                                    carpeta_ong_drive = obtener_carpeta_ong_drive(empresa_ong.strip(), fecha_ong, f"Campaña_{evento_ong.strip()}")
                                    subir_a_drive(nombre_pdf, pdf_bytes, "application/pdf", custom_folder_id=carpeta_ong_drive)
                                except Exception as e_drive:
                                    st.session_state["_drive_last_error"] = str(e_drive)
                                drive_error_ong = st.session_state.pop("_drive_last_error", None)

                                # 5. Guardar todo en Supabase
                                datos_ong = {
                                    "codigo_registro": codigo_ong, "empresa": empresa_ong.strip(), "ruc": ruc_ong.strip(),
                                    "fecha_recoleccion": fecha_ong.strftime("%d/%m/%Y"), "evento": evento_ong.strip(),
                                    "total_kg_recuperados": total_kg_ong, "total_co2_evitado": total_co2_ong,      
                                    "detalle_material": lista_materiales_ong,
                                    "pdf_url": url_pdf
                                }
                                supabase.table("ong_registros").insert(datos_ong).execute()
                                
                                # 6. Mantener el PDF listo para descarga en pantalla
                                st.session_state.doc_ong_descarga = {"nombre": nombre_pdf, "bytes": pdf_bytes, "drive_error": drive_error_ong}
                                st.rerun()

                            except FileNotFoundError:
                                st.error("❌ No se encontró 'Plantilla_Constancia_Mujer_Power.docx'. Asegúrate de que el archivo esté en la carpeta.")
                            except Exception as e:
                                st.error(f"❌ Ocurrió un error general: {e}")

            # Mostrar botón de descarga si el PDF se acaba de generar
            if "doc_ong_descarga" in st.session_state and st.session_state.doc_ong_descarga:
                if st.session_state.doc_ong_descarga.get("drive_error"):
                    st.warning(
                        f"⚠️ ¡Registro guardado! Pero la constancia NO se pudo respaldar en Google Drive. "
                        f"Detalle: {st.session_state.doc_ong_descarga['drive_error']}"
                    )
                else:
                    st.success("✅ ¡Registro exitoso! La constancia PDF ha sido generada y respaldada en la nube.")
                st.balloons()
                st.download_button(
                    label="Descargar Constancia (.pdf)",
                    data=st.session_state.doc_ong_descarga["bytes"],
                    file_name=st.session_state.doc_ong_descarga["nombre"],
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )
                if st.button("Limpiar y hacer nuevo registro"):
                    st.session_state.doc_ong_descarga = None
                    st.rerun()

        elif pestaña_activa == "Dashboard ONG":
            st.subheader("Dashboard de Impacto Circular - ONG Mujer Power")
            
            with st.spinner("Cargando métricas desde la nube..."):
                try:
                    res_ong = supabase.table("ong_registros").select("*").execute()
                    datos_ong = res_ong.data
                except Exception as e:
                    st.error(f"Error al cargar datos: {e}")
                    datos_ong = []

            if not datos_ong:
                st.info("Aún no hay registros en la base de datos.")
            else:
                df_ong = pd.DataFrame(datos_ong)
                total_kg = df_ong["total_kg_recuperados"].sum()
                total_co2 = df_ong["total_co2_evitado"].sum()
                total_empresas = df_ong["empresa"].nunique()
                total_campanas = df_ong["evento"].nunique()

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Recuperado", f"{total_kg:,.2f} kg")
                m2.metric("CO₂e Evitado", f"{total_co2:,.2f} kg")
                m3.metric("Empresas Aliadas", f"{total_empresas:,}")
                m4.metric("Campañas/Eventos", f"{total_campanas:,}")
                st.write("---")

                lista_materiales = []
                for _, row in df_ong.iterrows():
                    detalles = row.get("detalle_material", [])
                    if isinstance(detalles, list):
                        for item in detalles:
                            lista_materiales.append({
                                "Material": item.get("material", "Otro"),
                                "Peso (Kg)": float(item.get("cantidad_kg", 0)),
                                "CO2 Evitado": float(item.get("co2_evitado", 0))
                            })
                df_mat = pd.DataFrame(lista_materiales)

                c_graf1, c_graf2 = st.columns(2)
                with c_graf1:
                    with st.container(border=True):
                        st.markdown("<h6 style='text-align: center; color: #475569;'>Distribución por Tipo de Material (Kg)</h6>", unsafe_allow_html=True)
                        if not df_mat.empty:
                            df_mat_grp = df_mat.groupby("Material")["Peso (Kg)"].sum().reset_index()
                            fig_pie = px.pie(df_mat_grp, values="Peso (Kg)", names="Material", hole=0.45, color_discrete_sequence=px.colors.qualitative.Pastel)
                            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                            fig_pie.update_layout(margin=dict(l=0, r=0, t=10, b=10), showlegend=False)
                            st.plotly_chart(fig_pie, use_container_width=True)
                        else:
                            st.caption("No hay detalle de materiales.")

                with c_graf2:
                    with st.container(border=True):
                        st.markdown("<h6 style='text-align: center; color: #475569;'>Top 5 Empresas Aliadas (Kg Recuperados)</h6>", unsafe_allow_html=True)
                        df_emp = df_ong.groupby("empresa")["total_kg_recuperados"].sum().reset_index().sort_values(by="total_kg_recuperados", ascending=False).head(5)
                        fig_bar = px.bar(df_emp, x="total_kg_recuperados", y="empresa", orientation='h', color_discrete_sequence=["#7C3AED"])
                        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=0, r=0, t=10, b=10), xaxis_title="Kg Recuperados", yaxis_title="")
                        st.plotly_chart(fig_bar, use_container_width=True)

        elif pestaña_activa == "Historial ONG":
            st.subheader("Historial de Registros - ONG Mujer Power")
            st.caption("Consulta todos los registros de donaciones. Los administradores pueden eliminar registros incorrectos.")
            
            with st.spinner("Cargando historial..."):
                try:
                    res_hist = supabase.table("ong_registros").select("*").order("id", desc=True).execute()
                    historial_ong = res_hist.data
                    historial_ong.sort(key=lambda r: _fecha_para_ordenar(r.get("fecha_recoleccion")), reverse=True)
                except Exception as e:
                    st.error(f"Error al cargar historial: {e}")
                    historial_ong = []

            if not historial_ong:
                st.info("No hay registros en el historial.")
            else:
                for reg in historial_ong:
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([3, 2, 2, 1.5])
                        
                        c1.markdown(f"**{reg.get('empresa', 'Sin Nombre')}**")
                        c1.caption(f"Código: `{reg.get('codigo_registro', '')}`")
                        
                        c2.markdown(f"**Campaña:** {reg.get('evento', '')}")
                        c2.caption(f"Fecha: {reg.get('fecha_recoleccion', '')}")
                        
                        c3.markdown(f"**Total:** {reg.get('total_kg_recuperados', 0):,.2f} kg")
                        c3.caption(f"CO₂e: {reg.get('total_co2_evitado', 0):,.2f} kg")
                        
                        if reg.get("pdf_url"):
                            c4.link_button("Ver Constancia", reg.get("pdf_url"), use_container_width=True)
                        else:
                            c4.caption("Sin PDF")
                        
                        if st.session_state.rol == "admin":
                            if c4.button("Eliminar", key=f"del_ong_{reg['id']}", type="secondary", use_container_width=True):
                                try:
                                    supabase.table("ong_registros").delete().eq("id", reg["id"]).execute()
                                    st.toast(f"Registro {reg.get('codigo_registro')} eliminado.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al eliminar: {e}")

        st.stop()
