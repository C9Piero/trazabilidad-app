# 5. BALANCE DE MATERIAL
st.subheader("5. Balance de Material")

col_bm1, col_bm2 = st.columns(2)
mat_transformado = col_bm1.number_input("Material transformado en productos (kg)", min_value=0.0, value=0.0, step=0.1)
retazos_aprovechables = col_bm2.number_input("Retazos aprovechables (kg)", min_value=0.0, value=0.0, step=0.1)

col_bm3, col_bm4 = st.columns(2)
perdida_no_aprovechable = col_bm3.number_input("Pérdida no aprovechable (kg)", min_value=0.0, value=0.0, step=0.1)

# Cálculos automáticos basados en el material recibido
total_procesado = mat_transformado + retazos_aprovechables + perdida_no_aprovechable

if peso_total_recibido > 0:
    pct_aprovechamiento_total = ((mat_transformado + retazos_aprovechables) / peso_total_recibido) * 100
    pct_perdida = (perdida_no_aprovechable / peso_total_recibido) * 100
else:
    pct_aprovechamiento_total = 0.0
    pct_perdida = 0.0

# Muestra de Indicadores en pantalla
st.markdown("---")
c_ind1, c_ind2, c_ind3 = st.columns(3)
c_ind1.metric("Total Procesado", f"{total_procesado:.2f} kg")
c_ind2.metric("% Aprovechamiento Total", f"{pct_aprovechamiento_total:.2f}%")
c_ind3.metric("% Pérdida", f"{pct_perdida:.2f}%")

st.caption("📝 *Nota: El proceso presenta un alto nivel de aprovechamiento del material, donde los retazos generados son reincorporados como insumo en nuevos productos, reduciendo la generación de residuos.*")
