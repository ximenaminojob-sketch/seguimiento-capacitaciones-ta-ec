# app.py
import streamlit as st
import pandas as pd
import datetime as dt

st.set_page_config(page_title="Seguimiento TA/EC", layout="wide")

# =========================
# CONFIG
# =========================
DATA_PATH = "data/registro_ta_ec.xlsx"
HEADER_ROW = 2  # si tus encabezados están en la fila 3 (dos filas de título arriba)

# =========================
# THEME (modo oscuro por CSS)
# =========================
CSS_LIGHT = """
<style>
:root { color-scheme: light; }
html, body, [data-testid="stAppViewContainer"] { background: #FFFFFF !important; }
[data-testid="stSidebar"] { background: #F3F6FA !important; }
hr { border: none; border-top: 1px solid #E5E7EB; margin: 18px 0; }
</style>
"""

CSS_DARK = """
<style>
:root { color-scheme: dark; }
html, body, [data-testid="stAppViewContainer"] {
    background: #0E1117 !important;
    color: #E6E6E6 !important;
}
[data-testid="stSidebar"] { background: #0B1220 !important; }
h1,h2,h3,p,span,div,label { color: #E6E6E6 !important; }
hr { border: none; border-top: 1px solid #23314D; margin: 18px 0; }
</style>
"""

# =========================
# UI CSS (cards, badges)
# =========================
st.markdown("""
<style>
h1, h2, h3 { letter-spacing: -0.3px; }
.card {
  background: #F3F6FA;
  border: 1px solid #E2E8F0;
  border-radius: 16px;
  padding: 16px 18px;
  margin-bottom: 12px;
}
.card-title { font-weight: 700; font-size: 14px; color:#0B3A6E; margin-bottom: 6px; }
.card-kpi { font-size: 28px; font-weight: 800; color:#0B1F33; margin: 0; }
.card-sub { color:#4B5563; font-size: 13px; margin-top: 4px; }
.badge {
  display:inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  border: 1px solid #E2E8F0;
  background: #FFFFFF;
  margin-right: 6px;
}
.badge-ok { color:#0B3A6E; }
.badge-warn { color:#B45309; }
.badge-bad { color:#B91C1C; }
</style>
""", unsafe_allow_html=True)

# =========================
# HELPERS
# =========================
def fmt_fecha(x):
    """Muestra solo DD/MM/YYYY si es fecha real. Si no, devuelve el texto (S/N, etc.)."""
    if pd.isna(x):
        return "—"
    if isinstance(x, (pd.Timestamp, dt.date, dt.datetime)):
        return x.strftime("%d/%m/%Y")
    # Si viene como serial excel
    if isinstance(x, (int, float)) and not pd.isna(x) and x > 30000:
        try:
            d = pd.to_datetime(x, unit="D", origin="1899-12-30")
            return d.strftime("%d/%m/%Y")
        except Exception:
            return str(x)
    s = str(x).strip()
    return s if s else "—"

def is_real_date(x) -> bool:
    """True SOLO si es fecha real (date/datetime/timestamp) o serial excel grande."""
    if pd.isna(x):
        return False
    if isinstance(x, (pd.Timestamp, dt.date, dt.datetime)):
        return True
    if isinstance(x, (int, float)) and not pd.isna(x):
        return x > 30000
    return False

def norm_text(x) -> str:
    return str(x).strip().upper()

def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed", regex=True)].copy()

    required = [
        "Apellido y Nombre","DNI","Puesto","Especialidad",
        "TA - TEORÍA","TA - PRÁCTICA",
        "EC - TEORÍA","EC - PRÁCTICA",
        "Tipo de personal","Empresa"
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(
            f"Faltan columnas en el Excel: {missing}\n\n"
            f"Si existen pero no las detecta: cambiá HEADER_ROW (2, 1 o 0) según dónde estén los encabezados."
        )
        st.stop()

    # Limpieza y NaNs
    df["DNI"] = df["DNI"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    for col in ["Apellido y Nombre","Puesto","Especialidad","Tipo de personal","Empresa"]:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": "SIN DATO", "NaN": "SIN DATO", "None": "SIN DATO"}).fillna("SIN DATO")

    # Flags (base = teoría con FECHA)
    df["TA_Teoria_OK"] = df["TA - TEORÍA"].apply(is_real_date)
    df["EC_Teoria_OK"] = df["EC - TEORÍA"].apply(is_real_date)
    df["TA_Practica_OK"] = df["TA - PRÁCTICA"].apply(is_real_date)
    df["EC_Practica_OK"] = df["EC - PRÁCTICA"].apply(is_real_date)

    # Pendiente práctica: SOLO S/N (tu regla)
    df["TA_Practica_Pendiente_SN"] = df["TA - PRÁCTICA"].apply(lambda x: norm_text(x) in {"S/N", "SN"})
    df["EC_Practica_Pendiente_SN"] = df["EC - PRÁCTICA"].apply(lambda x: norm_text(x) in {"S/N", "SN"})

    # Estados para mostrar
    def estado(teo_ok, prac_ok, pend_sn):
        if teo_ok and prac_ok:
            return "CERTIFICABLE"
        if teo_ok and (not prac_ok) and pend_sn:
            return "SOLO TEORÍA (Pendiente práctica - S/N)"
        if teo_ok and (not prac_ok):
            return "SOLO TEORÍA (Sin práctica cargada)"
        if (not teo_ok) and prac_ok:
            return "INCONSISTENCIA (Práctica sin teoría)"
        return "SIN TEORÍA"

    df["TA_Estado"] = [estado(t, p, sn) for t, p, sn in zip(df["TA_Teoria_OK"], df["TA_Practica_OK"], df["TA_Practica_Pendiente_SN"])]
    df["EC_Estado"] = [estado(t, p, sn) for t, p, sn in zip(df["EC_Teoria_OK"], df["EC_Practica_OK"], df["EC_Practica_Pendiente_SN"])]

    # Badges simplificados (para listado)
    def badge_estado(x):
        if "CERTIFICABLE" in x:
            return "✅"
        if "SOLO TEORÍA" in x:
            return "🟡"
        if "INCONSISTENCIA" in x:
            return "⚠️"
        return "❌"

    df["TA"] = df["TA_Estado"].apply(badge_estado)
    df["EC"] = df["EC_Estado"].apply(badge_estado)

    def estado_general(r):
        if r["TA"] == "✅" and r["EC"] == "✅":
            return "CERTIFICABLE"
        if r["TA"] in ["✅","🟡"] or r["EC"] in ["✅","🟡"]:
            return "PARCIAL"
        return "SIN CAPACITACIÓN"

    df["Estado general"] = df.apply(estado_general, axis=1)

    def accion(r):
        if r["Estado general"] == "CERTIFICABLE":
            return "📄 Emitir certificado"
        if r["TA"] == "🟡" or r["EC"] == "🟡":
            return "🛠 Programar práctica"
        if r["TA"] == "⚠️" or r["EC"] == "⚠️":
            return "🔎 Revisar registros"
        return "📚 Programar teoría"

    df["Acción"] = df.apply(accion, axis=1)

    # Fechas “visibles” (una por tema, sin hora)
    def fecha_visible(estado_txt, fecha_teo, fecha_prac):
        # Si certificable -> fecha práctica
        if "CERTIFICABLE" in estado_txt:
            return fmt_fecha(fecha_prac)
        # Si solo teoría -> fecha teoría
        if "SOLO TEORÍA" in estado_txt:
            return fmt_fecha(fecha_teo)
        # Si inconsistencia y hay práctica -> mostrar práctica; si no, teoría; si no, —
        if "INCONSISTENCIA" in estado_txt:
            fp = fmt_fecha(fecha_prac)
            if fp != "—":
                return fp
            return fmt_fecha(fecha_teo)
        return "—"

    df["Fecha TA"] = df.apply(lambda r: fecha_visible(r["TA_Estado"], r["TA - TEORÍA"], r["TA - PRÁCTICA"]), axis=1)
    df["Fecha EC"] = df.apply(lambda r: fecha_visible(r["EC_Estado"], r["EC - TEORÍA"], r["EC - PRÁCTICA"]), axis=1)

    return df

def avance_sobre_teoria(dfx: pd.DataFrame, teo_ok: str, prac_ok: str):
    base = int(dfx[teo_ok].sum())
    certificables = int((dfx[teo_ok] & dfx[prac_ok]).sum())
    pendientes = base - certificables
    pct = (certificables / base * 100) if base else 0
    return base, certificables, pendientes, pct

@st.cache_data(show_spinner=False)
def load_data():
    df_raw = pd.read_excel(DATA_PATH, sheet_name=0, header=HEADER_ROW)
    return normalize_df(df_raw)

# =========================
# HEADER (título + controles)
# =========================
top_l, top_mid, top_r = st.columns([1.2, 2.2, 1.2])

with top_l:
    modo_oscuro = st.toggle("Modo oscuro", value=False)

# aplica CSS según toggle
st.markdown(CSS_DARK if modo_oscuro else CSS_LIGHT, unsafe_allow_html=True)

with top_mid:
    st.markdown("## Seguimiento de Capacitaciones (TA / EC)")
    st.caption("Avance medido sobre personas con **TEORÍA realizada (fecha)**. Certificable = **Teoría + Práctica (fecha)**.")

with top_r:
    if st.button("🔄 Actualizar datos"):
        st.cache_data.clear()
        st.rerun()

tema = st.selectbox("Tema", ["Ambos", "TA", "EC"])

# =========================
# LOAD DATA
# =========================
df = load_data()

# =========================
# SIDEBAR FILTERS
# =========================
st.sidebar.header("Filtros")

tipo_opts = sorted(df["Tipo de personal"].dropna().astype(str).unique())
empresa_opts = sorted(df["Empresa"].dropna().astype(str).unique())

tipo_sel = st.sidebar.multiselect("Tipo de personal", tipo_opts, default=tipo_opts)
empresa_sel = st.sidebar.multiselect("Empresa / Subcontrato", empresa_opts, default=empresa_opts)

df_f = df[df["Tipo de personal"].isin(tipo_sel) & df["Empresa"].isin(empresa_sel)].copy()

if df_f.empty:
    st.warning("Con los filtros actuales no hay registros para mostrar. Probá seleccionar más empresas/tipos.")
    st.stop()

show_ta = tema in ["Ambos", "TA"]
show_ec = tema in ["Ambos", "EC"]

# =========================
# TABS
# =========================
tab_dash, tab_persona, tab_empresa = st.tabs(["📊 Dashboard", "🔎 Buscar persona", "🏢 Por empresa"])

# =========================
# TAB 1: DASHBOARD
# =========================
with tab_dash:
    st.markdown("### Tablero de avance y gráficos")

    c1, c2 = st.columns(2)

    if show_ta:
        base, cert, pend, pct = avance_sobre_teoria(df_f, "TA_Teoria_OK", "TA_Practica_OK")
        with c1:
            st.markdown(f"""
<div class="card">
  <div class="card-title">TA – Trabajo en Altura</div>
  <div class="badge badge-ok">Base teoría: {base}</div>
  <div class="badge badge-ok">Certificables: {cert}</div>
  <div class="badge badge-warn">Pendientes: {pend}</div>
  <p class="card-kpi">{pct:.1f}%</p>
  <div class="card-sub">% Avance (certificables / base con teoría)</div>
</div>
""", unsafe_allow_html=True)
            st.progress(min(int(round(pct)), 100))
            chart_ta = pd.DataFrame({"Personas": [cert, pend]}, index=["Certificables", "Pendientes"])
            st.bar_chart(chart_ta)

    if show_ec:
        base, cert, pend, pct = avance_sobre_teoria(df_f, "EC_Teoria_OK", "EC_Practica_OK")
        with c2:
            st.markdown(f"""
<div class="card">
  <div class="card-title">EC – Espacios Confinados</div>
  <div class="badge badge-ok">Base teoría: {base}</div>
  <div class="badge badge-ok">Certificables: {cert}</div>
  <div class="badge badge-warn">Pendientes: {pend}</div>
  <p class="card-kpi">{pct:.1f}%</p>
  <div class="card-sub">% Avance (certificables / base con teoría)</div>
</div>
""", unsafe_allow_html=True)
            st.progress(min(int(round(pct)), 100))
            chart_ec = pd.DataFrame({"Personas": [cert, pend]}, index=["Certificables", "Pendientes"])
            st.bar_chart(chart_ec)

    st.markdown("---")
    st.caption("Tip: si filtrás por una empresa que no tiene teoría cargada, el avance queda en 0 porque la base se define por fecha en TEORÍA.")

# =========================
# TAB 2: BUSCAR PERSONA
# =========================
with tab_persona:
    st.markdown("### Buscar una persona")
    st.caption("Seleccioná por DNI o por Apellido y Nombre para ver su estado en TA y EC.")

    modo_busqueda = st.radio("Buscar por", ["DNI", "Nombre y Apellido"], horizontal=True)
    row = None

    if modo_busqueda == "DNI":
        opciones = sorted(df_f["DNI"].dropna().astype(str).unique())
        sel = st.selectbox("DNI", ["— Seleccioná —"] + opciones)
        if sel != "— Seleccioná —":
            fila = df_f[df_f["DNI"].astype(str) == sel]
            if not fila.empty:
                row = fila.iloc[0]
    else:
        opciones = sorted(df_f["Apellido y Nombre"].dropna().astype(str).unique())
        sel = st.selectbox("Nombre y Apellido", ["— Seleccioná —"] + opciones)
        if sel != "— Seleccioná —":
            fila = df_f[df_f["Apellido y Nombre"].astype(str) == sel]
            if not fila.empty:
                row = fila.iloc[0]

    if row is None:
        st.info("Elegí un DNI o un Nombre para comenzar.")
    else:
        empresa_txt = str(row.get("Empresa", "")).upper()

        # Header con logo SOLO para Techint
        col_logo, col_text = st.columns([1.2, 6.8], vertical_alignment="center")
        with col_logo:
            if "TECHINT" in empresa_txt:
                st.image("assets/techint.png", width=140)

        with col_text:
            st.markdown(f"### {row['Apellido y Nombre']} — DNI {row['DNI']}")
            st.caption(f"{row['Tipo de personal']} · {row['Empresa']} · {row['Puesto']} · {row['Especialidad']}")

        cta, cec = st.columns(2)

        with cta:
            st.markdown("#### TA – Trabajo en Altura")
            st.write(f"Teoría: **{fmt_fecha(row['TA - TEORÍA'])}**")
            st.write(f"Práctica: **{fmt_fecha(row['TA - PRÁCTICA'])}**")
            estado = row.get("TA_Estado", "")
            if "CERTIFICABLE" in estado:
                st.success(estado)
            elif "SOLO TEORÍA" in estado:
                st.warning(estado)
            elif "INCONSISTENCIA" in estado:
                st.error(estado)
            else:
                st.info(estado if estado else "SIN DATOS")

        with cec:
            st.markdown("#### EC – Espacios Confinados")
            st.write(f"Teoría: **{fmt_fecha(row['EC - TEORÍA'])}**")
            st.write(f"Práctica: **{fmt_fecha(row['EC - PRÁCTICA'])}**")
            estado = row.get("EC_Estado", "")
            if "CERTIFICABLE" in estado:
                st.success(estado)
            elif "SOLO TEORÍA" in estado:
                st.warning(estado)
            elif "INCONSISTENCIA" in estado:
                st.error(estado)
            else:
                st.info(estado if estado else "SIN DATOS")

# =========================
# TAB 3: POR EMPRESA
# =========================
with tab_empresa:
    st.markdown("### Seguimiento por Empresa / Subcontrato")

    empresa = st.selectbox("Elegí una empresa", sorted(df_f["Empresa"].dropna().astype(str).unique()))
    df_emp = df_f[df_f["Empresa"].astype(str) == empresa].copy()

    st.markdown(f"**{empresa}** — Personas: **{len(df_emp)}**")

    s1, s2 = st.columns(2)

    if show_ta:
        base, cert, pend, pct = avance_sobre_teoria(df_emp, "TA_Teoria_OK", "TA_Practica_OK")
        with s1:
            st.markdown(f"""
<div class="card">
  <div class="card-title">TA – Avance en {empresa}</div>
  <div class="badge badge-ok">Base teoría: {base}</div>
  <div class="badge badge-ok">Certificables: {cert}</div>
  <div class="badge badge-warn">Pendientes: {pend}</div>
  <p class="card-kpi">{pct:.1f}%</p>
</div>
""", unsafe_allow_html=True)

    if show_ec:
        base, cert, pend, pct = avance_sobre_teoria(df_emp, "EC_Teoria_OK", "EC_Practica_OK")
        with s2:
            st.markdown(f"""
<div class="card">
  <div class="card-title">EC – Avance en {empresa}</div>
  <div class="badge badge-ok">Base teoría: {base}</div>
  <div class="badge badge-ok">Certificables: {cert}</div>
  <div class="badge badge-warn">Pendientes: {pend}</div>
  <p class="card-kpi">{pct:.1f}%</p>
</div>
""", unsafe_allow_html=True)

    st.markdown("### Listado (simplificado con fechas)")
    cols_simplificadas = [
        "Apellido y Nombre","DNI","Empresa",
        "TA","Fecha TA",
        "EC","Fecha EC",
        "Estado general","Acción"
    ]
    st.dataframe(
        df_emp[cols_simplificadas].sort_values("Apellido y Nombre"),
        use_container_width=True,
        hide_index=True
    )
