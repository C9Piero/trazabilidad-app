import streamlit as st
import pandas as pd

st.set_page_config(page_title="Sistema de Trazabilidad", layout="wide")

st.title("📋 Sistema de Trazabilidad y Gestión de Proyectos")

# ==========================================
# 1. FICHA GENERAL DEL PROYECTO
# ==========================================
st.markdown("### 1. Ficha General del Proyecto")

col1, col2, col3 = st.columns(3)
cliente = col1.text_input("Cliente / Empresa", value="")
ruc = col2.text_input("RUC", value="")
codigo_proyecto = col3.text_input("Código de Proyecto", value="")

col4, col5, col6 = st.columns(3)
# Opciones actualizadas según tus requerimientos
opciones_tipo_proyecto = [
    "Upcycling",
    "Producción desde cero",
    "Cambio de logo",
    "Mixto",
    "Banner"
]
tipo_proyecto = col4.selectbox("Tipo de Proyecto", opciones_tipo_proyecto)
fecha_inicio = col5.date_input("Fecha Inicio")
fecha_termino = col6.date_input("Fecha Término")

col7, col8, col9 = st.columns(3)
responsable = col7.text_input("Responsable", value="")
area = col8.text_input("Área", value="")
guia_remision = col9.text_input("Nº Guía Remisión", value="")

col10, col11 = st.columns(2)
punto_origen = col10.text_input("Punto Origen", value="")
punto_destino = col11.text_input("Punto Destino", value="")

st.markdown("---")

# ==========================================
# 2. DEFINICIÓN DE PRODUCTOS FINALES (Simulación)
# ==========================================
# Aseguramos una lista de productos base para las dinámicas posteriores
if "lista_productos" not in st.session_state:
    st.session_state.lista_productos = [
        {"producto": "Estrellas", "cantidad": 0}
    ]

lista_productos = st.session_state.lista_productos

# ==========================================
# TIEMPOS BASE Y CONFIGURACIÓN DE CONFECCIÓN
# ==========================================
# Lista de roles reducida únicamente a Confección y Acabado
TIEMPOS_IA_CONFECCION = {
    "Confección": 0.75,
    "Acabado": 0.20
}

# ==========================================
# 7. CORTE, LOGÍSTICA Y CONFECCIÓN
# ==========================================
st.markdown("### 7. Gestión de Producción y Confección")

st.markdown("#### Confección – Artesanas y Taller")
st.caption("Asigne la persona encargada y el tiempo aproximado para cada producto final.")

lista_confeccion = []
horas_confeccion_total = 0.0
personas_confeccion_set = set()

# Carga únicamente "Confección" y "Acabado"
roles_disponibles = list(TIEMPOS_IA_CONFECCION.keys())

for idx, prod in enumerate(lista_productos):
    p_nom = prod["producto"]
    p_cant = prod["cantidad"]

    st.markdown(f"**📦 Producto {idx+1}: {p_nom}** *(Cantidad: {p_cant} unid)*")
    c_rol, c_persona, c_tiempo, c_tot = st.columns([2.5, 2.5, 2, 2])

    # Desplegable ajustado a solo 2 roles
    rol_sel = c_rol.selectbox("Rol Asignado", roles_disponibles, key=f"soc_rol_{idx}")
    persona_nom = c_persona.text_input("Persona Encargada", value="", placeholder="Ej: Maria Ramos", key=f"soc_pers_{idx}")

    # Asignación automática del tiempo según el rol
    tiempo_ia = TIEMPOS_IA_CONFECCION.get(rol_sel, 0.5)
    tiempo_unitario = c_tiempo.number_input("Tiempo / Unidad (hrs)", min_value=0.0, value=float(tiempo_ia), step=0.05, key=f"soc_tunit_{idx}")

    horas_producto = p_cant * tiempo_unitario
    c_tot.metric("Horas Totales", f"{horas_producto:.2f} hrs")

    horas_confeccion_total += horas_producto
    if persona_nom.strip():
        personas_confeccion_set.add(persona_nom.strip())

    lista_confeccion.append({
        "producto": p_nom,
        "cantidad": p_cant,
        "rol": rol_sel,
        "persona": persona_nom if persona_nom.strip() else "Por asignar",
        "tiempo_unitario": tiempo_unitario,
        "horas_totales": horas_producto
    })

st.markdown("---")
