import streamlit as st
import pandas as pd
import numpy as np
import datetime as dt

def fmt_fecha(x):
    if pd.isna(x):
        return "—"
    if isinstance(x, (pd.Timestamp, dt.date, dt.datetime)):
        return x.strftime("%d/%m/%Y")
    if str(x).strip().upper() == "S/N":
        return "S/N"
    return str(x)

st.set_page_config(page_title="Seguimiento TA/EC", layout="wide")

# ====== CSS (look corporativo + cards) ======
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
hr { border: none; border-top: 1px solid #E5E7EB; margin: 18px 0; }
</style>
""", unsafe_allow_html=True)

# ====== Config ======
DATA_PATH = "data/registro_ta_ec.xlsx"
HEADER_ROW = 2  # si tu encabezado está en la fila 3 (2 filas arriba de título)

# ====== Helpers ======
def is_real_date(x) -> bool:
    """True SOLO si es fecha real (date/datetime/timestamp) o serial excel grande."""
    if pd.isna(x):
        return False
    if isinstance(x, (pd.Timestamp, dt.date, dt.datetime)):
        return True
    if isinstance(x, (int, float)) and not pd.isna(x):
        return x > 30000
    return False

def norm_text(x):
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
            f"Si existen pero no las detecta: ajustá HEADER_ROW (2, 1 o 0)."
        )
        st.stop()

    df["DNI"] = df["DNI"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    for col in ["Apellido y Nombre","Puesto","Especialidad","Tipo de personal","Empresa"]:
        df[col] = df[col].astype(str).str.strip()

    # Flags: Teoría = fecha real
    df["TA_Teoria_OK"] = df["TA - TEORÍA"].apply(is_real_date)
    df["EC_Teoria_OK"] = df["EC - TEORÍA"].apply(is_real_date)

    # Práctica hecha = fecha real
    df["TA_Practica_OK"] = df["TA - PRÁCTICA"].apply(is_real_date)
    df["EC_Practica_OK"] = df["EC - PRÁCTICA"].apply(is_real_date)

    # Práctica pendiente (tu regla): SOLO "S/N"
    df["TA_Practica_Pendiente_SN"] = df["TA - PRÁCTICA"].apply(lambda x: norm_text(x) in {"S/N", "SN"})
    df["EC_Practica_Pendiente_SN"] = df["EC - PRÁCTICA"].apply(lambda x: norm_text(x) in {"S/N", "SN"})

    # Estados (para mostrar en ficha / tablas)
    def estado(teo_ok, prac_ok, pend_sn):
        if teo_ok and prac_ok:
            return "CERTIFICABLE"
        if teo_ok and (not prac_ok) and pend_sn:
            return "SOLO TEORÍA (Pendiente práctica - S/N)"
        if teo_ok and (not prac_ok) and (not pend_sn):
            return "SOLO TEORÍA (Sin práctica cargada)"
        if (not teo_ok) and prac_ok:
            return "INCONSISTENCIA (Práctica sin teoría)"
        return "SIN TEORÍA"

    df["TA_Estado"] = [estado(t, p, sn) for t, p, sn in zip(df["TA_Teoria_OK"], df["TA_Practica_OK"], df["TA_Practica_Pendiente_SN"])]
    df["EC_Estado"] = [estado(t, p, sn) for t, p, sn in zip(df["EC_Teoria_OK"], df["EC_Practica_OK"], df["EC_Practica_Pendiente_SN"])]

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

# ====== Header (logo + título) ======
top_l, top_r = st.columns([1, 3])
with top_l:
    # Si ya tenés el logo como imagen en repo, ponelo acá. Si no, borrá este bloque.
    # st.image("assets/techint.png", width=210)
    st.write("")
with top_r:
    st.markdown("# Seguimiento de Capacitaciones (TA / EC)")
    st.caption("Avance medido sobre personas con **TEORÍA realizada (fecha)**. Certificable = **Teoría + Práctica (fecha)**.")

# ====== Controles globales ======
c1, c2, c3, c4 = st.columns([1, 1, 2, 1])
with c1:
    modo_oscuro = st.toggle("Modo oscuro", value=False)
with c2:
    tema = st.selectbox("Tema", ["Ambos", "TA", "EC"])
with c3:
    st.write("")
with c4:
    if st.button("🔄 Actualizar datos"):
        st.cache_data.clear()

df = load_data()

# Filtros laterales (tipo/empresa)
st.sidebar.header("Filtros")
tipo_opts = sorted(df["Tipo de personal"].unique())
empresa_opts = sorted(df["Empresa"].unique())

tipo_sel = st.sidebar.multiselect("Tipo de personal", tipo_opts, default=tipo_opts)
empresa_sel = st.sidebar.multiselect("Empresa / Subcontrato", empresa_opts, default=empresa_opts)

df_f = df[df["Tipo de personal"].isin(tipo_sel) & df["Empresa"].isin(empresa_sel)].copy()

if df_f.empty:
    st.warning("Con los filtros actuales no hay registros para mostrar. Probá seleccionar más empresas/tipos.")
    st.stop()

show_ta = tema in ["Ambos", "TA"]
show_ec = tema in ["Ambos", "EC"]

# ====== Tabs ======
tab_dash, tab_persona, tab_empresa = st.tabs(["📊 Dashboard", "🔎 Buscar persona", "🏢 Por empresa"])

# ======================
# TAB 1: DASHBOARD
# ======================
with tab_dash:
    st.markdown("## Tablero de avance")

    colA, colB = st.columns(2)

    if show_ta:
        base, cert, pend, pct = avance_sobre_teoria(df_f, "TA_Teoria_OK", "TA_Practica_OK")
        with colA:
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
        with colB:
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

# ======================
# TAB 2: BUSCAR PERSONA
# ======================
with tab_persona:
    st.markdown("## Buscar una persona")
    st.caption("Seleccioná por DNI o por Apellido y Nombre para ver su estado en TA y EC.")

    modo_busqueda = st.radio("Buscar por", ["DNI", "Nombre y Apellido"], horizontal=True)

    # ... (selección de persona)
    # row = ...

    if row is None:
        st.info("Elegí un DNI o un Nombre para comenzar.")
    else:
        st.markdown(f"### {row['Apellido y Nombre']}  —  DNI {row['DNI']}")
        st.caption(f"{row['Tipo de personal']} · {row['Empresa']} · {row['Puesto']} · {row['Especialidad']}")

        cta, cec = st.columns(2)   # <-- ESTA LÍNEA

        with cta:
            st.markdown("#### TA – Trabajo en Altura")
            st.write(f"Teoría: **{fmt_fecha(row['TA - TEORÍA'])}**")
            st.write(f"Práctica: **{fmt_fecha(row['TA - PRÁCTICA'])}**")
            # ...

        with cec:
            st.markdown("#### EC – Espacios Confinados")
            st.write(f"Teoría: **{fmt_fecha(row['EC - TEORÍA'])}**")
            st.write(f"Práctica: **{fmt_fecha(row['EC - PRÁCTICA'])}**")
            # ...

# ======================
# TAB 3: POR EMPRESA
# ======================
with tab_empresa:
    st.markdown("## Seguimiento por Empresa / Subcontrato")
    empresa = st.selectbox("Elegí una empresa", sorted(df_f["Empresa"].unique()))

    df_emp = df_f[df_f["Empresa"] == empresa].copy()
    st.markdown(f"### {empresa} — Personas: {len(df_emp)}")

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

    st.markdown("### Listado")
    cols = [
        "Apellido y Nombre","DNI","Tipo de personal","Empresa","Puesto","Especialidad",
        "TA_Estado","EC_Estado","TA - TEORÍA","TA - PRÁCTICA","EC - TEORÍA","EC - PRÁCTICA"
    ]
    st.dataframe(df_emp[cols].sort_values("Apellido y Nombre"), use_container_width=True)
