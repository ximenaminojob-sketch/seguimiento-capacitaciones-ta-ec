# app.py
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Seguimiento TA/EC", layout="wide")

# ====== CONFIG ======
DATA_PATH = "data/registro_ta_ec.xlsx"   # Excel dentro del repo
HEADER_ROW = 2  # si tus encabezados están en la fila 3 (con 2 filas arriba de título)
PENDING_WORDS = {"PENDIENTE", "S/N", "SN", "NO", "N/A", "NA", ""}

# ====== HELPERS ======
def is_done_date(x) -> bool:
    """True si parece una fecha válida; False si vacío o valores tipo PENDIENTE/SN."""
    if pd.isna(x):
        return False
    if isinstance(x, pd.Timestamp):
        return True
    if isinstance(x, str):
        s = x.strip().upper()
        if s in PENDING_WORDS:
            return False
        try:
            pd.to_datetime(x, errors="raise")
            return True
        except Exception:
            return False
    # A veces Excel guarda fechas como serial numérico
    if isinstance(x, (int, float)) and not pd.isna(x):
        return True
    return False

def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    # Quita columnas basura "Unnamed"
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
            f"Tip: si los nombres existen pero igual falla, puede ser el header incorrecto. "
            f"Probá cambiar HEADER_ROW (header=2 -> header=0) en el código."
        )
        st.stop()

    df["DNI"] = df["DNI"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    for col in ["Apellido y Nombre","Puesto","Especialidad","Tipo de personal","Empresa"]:
        df[col] = df[col].astype(str).str.strip()

    # Flags de cumplimiento por tema
    df["TA_Teoria_OK"] = df["TA - TEORÍA"].apply(is_done_date)
    df["TA_Practica_OK"] = df["TA - PRÁCTICA"].apply(is_done_date)
    df["EC_Teoria_OK"] = df["EC - TEORÍA"].apply(is_done_date)
    df["EC_Practica_OK"] = df["EC - PRÁCTICA"].apply(is_done_date)

    # Estados (lo que querés ver en la app)
    def estado(teo_ok, prac_ok):
        if not teo_ok and not prac_ok:
            return "Sin teoría ni práctica"
        if teo_ok and not prac_ok:
            return "Solo teoría"
        if teo_ok and prac_ok:
            return "Teoría + práctica (Certificable)"
        return "Solo práctica (Inconsistencia)"

    df["TA_Estado"] = [estado(t, p) for t, p in zip(df["TA_Teoria_OK"], df["TA_Practica_OK"])]
    df["EC_Estado"] = [estado(t, p) for t, p in zip(df["EC_Teoria_OK"], df["EC_Practica_OK"])]

    return df

def avance_sobre_teoria(dfx: pd.DataFrame, teo_ok_col: str, prac_ok_col: str):
    """Avance = certificables / base con teoría."""
    base = int(dfx[teo_ok_col].sum())
    cert = int((dfx[teo_ok_col] & dfx[prac_ok_col]).sum())
    pend = int((dfx[teo_ok_col] & ~dfx[prac_ok_col]).sum())
    pct = (cert / base * 100) if base else 0
    return base, cert, pend, pct

# ====== CARGA ======
st.title("App de Seguimiento – Capacitaciones Teoría/Práctica (TA y EC)")
st.caption("Base con teoría = personas con fecha en TEORÍA. Certificable = fecha en TEORÍA y PRÁCTICA.")

try:
    df_raw = pd.read_excel(DATA_PATH, sheet_name=0, header=HEADER_ROW)
except FileNotFoundError:
    st.error(f"No se encontró el archivo: {DATA_PATH}. Revisá que exista en el repo.")
    st.stop()

df = normalize_df(df_raw)

# ====== SIDEBAR (FILTROS GENERALES) ======
st.sidebar.header("Filtros")
tema = st.sidebar.selectbox("Tema", ["Ambos", "TA (Trabajo en Altura)", "EC (Espacios Confinados)"])

tipo_opts = sorted(df["Tipo de personal"].unique())
empresa_opts = sorted(df["Empresa"].unique())

tipo_sel = st.sidebar.multiselect("Tipo de personal", tipo_opts, default=tipo_opts)
empresa_sel = st.sidebar.multiselect("Empresa / Subcontrato", empresa_opts, default=empresa_opts)

df_f = df[df["Tipo de personal"].isin(tipo_sel) & df["Empresa"].isin(empresa_sel)].copy()

show_ta = tema in ["Ambos", "TA (Trabajo en Altura)"]
show_ec = tema in ["Ambos", "EC (Espacios Confinados)"]

# =========================
# 1) TABLERO + GRAFICOS
# =========================
st.markdown("## 1) Tablero de avance y gráficos")

c1, c2 = st.columns(2)

if show_ta:
    base, cert, pend, pct = avance_sobre_teoria(df_f, "TA_Teoria_OK", "TA_Practica_OK")
    with c1:
        st.subheader("TA – Trabajo en Altura")
        a,b,c = st.columns(3)
        a.metric("Base con teoría", base)
        b.metric("Certificables", cert)
        c.metric("Pendientes práctica", pend)
        st.metric("% Avance (cert/base)", f"{pct:.1f}%")
        st.progress(min(int(round(pct)), 100))
        chart = pd.DataFrame({"Personas": [cert, pend]}, index=["Certificables", "Pendientes práctica"])
        st.bar_chart(chart)

if show_ec:
    base, cert, pend, pct = avance_sobre_teoria(df_f, "EC_Teoria_OK", "EC_Practica_OK")
    with c2:
        st.subheader("EC – Espacios Confinados")
        a,b,c = st.columns(3)
        a.metric("Base con teoría", base)
        b.metric("Certificables", cert)
        c.metric("Pendientes práctica", pend)
        st.metric("% Avance (cert/base)", f"{pct:.1f}%")
        st.progress(min(int(round(pct)), 100))
        chart = pd.DataFrame({"Personas": [cert, pend]}, index=["Certificables", "Pendientes práctica"])
        st.bar_chart(chart)

st.divider()

# =========================
# 2) BUSCAR PERSONA
# =========================
st.markdown("## 2) Buscar persona (ver qué capacitaciones tiene hechas)")

q = st.text_input("Buscar por DNI o Apellido y Nombre", "")

if q.strip():
    qq = q.strip().lower()
    df_persona = df_f[
        df_f["DNI"].astype(str).str.lower().str.contains(qq) |
        df_f["Apellido y Nombre"].astype(str).str.lower().str.contains(qq)
    ].copy()

    if df_persona.empty:
        st.warning("No se encontraron personas con esa búsqueda (con los filtros actuales).")
    else:
        # Mostramos "ficha" resumida
        for _, r in df_persona.head(10).iterrows():
            st.markdown(f"### {r['Apellido y Nombre']} — DNI {r['DNI']}")
            cols = st.columns(4)
            cols[0].write(f"**Tipo:** {r['Tipo de personal']}")
            cols[1].write(f"**Empresa:** {r['Empresa']}")
            cols[2].write(f"**Puesto:** {r['Puesto']}")
            cols[3].write(f"**Especialidad:** {r['Especialidad']}")

            t1, t2 = st.columns(2)
            with t1:
                st.markdown("**TA (Trabajo en Altura)**")
                st.write(f"Teoría: {r['TA - TEORÍA']}")
                st.write(f"Práctica: {r['TA - PRÁCTICA']}")
                st.success(r["TA_Estado"]) if "Certificable" in r["TA_Estado"] else st.info(r["TA_Estado"])
            with t2:
                st.markdown("**EC (Espacios Confinados)**")
                st.write(f"Teoría: {r['EC - TEORÍA']}")
                st.write(f"Práctica: {r['EC - PRÁCTICA']}")
                st.success(r["EC_Estado"]) if "Certificable" in r["EC_Estado"] else st.info(r["EC_Estado"])

            st.markdown("---")
else:
    st.info("Escribí un DNI o un nombre para ver el detalle de esa persona.")

st.divider()

# =========================
# 3) LISTADO POR EMPRESA / SUBCONTRATO
# =========================
st.markdown("## 3) Listar por Empresa/Subcontrato (ver quién tiene o no hechas las capacitaciones)")

empresa_list = st.selectbox("Elegí una Empresa/Subcontrato para listar", ["(Seleccionar)"] + empresa_opts)

if empresa_list != "(Seleccionar)":
    df_emp = df_f[df_f["Empresa"] == empresa_list].copy()

    st.write(f"Personas encontradas: **{len(df_emp)}**")

    # Resumen rápido por tema dentro de esa empresa
    s1, s2 = st.columns(2)

    if show_ta:
        base, cert, pend, pct = avance_sobre_teoria(df_emp, "TA_Teoria_OK", "TA_Practica_OK")
        with s1:
            st.subheader("Resumen TA en la empresa")
            st.write(f"- Base con teoría: **{base}**")
            st.write(f"- Certificables: **{cert}**")
            st.write(f"- Pendientes práctica: **{pend}**")
            st.write(f"- % Avance: **{pct:.1f}%**")

    if show_ec:
        base, cert, pend, pct = avance_sobre_teoria(df_emp, "EC_Teoria_OK", "EC_Practica_OK")
        with s2:
            st.subheader("Resumen EC en la empresa")
            st.write(f"- Base con teoría: **{base}**")
            st.write(f"- Certificables: **{cert}**")
            st.write(f"- Pendientes práctica: **{pend}**")
            st.write(f"- % Avance: **{pct:.1f}%**")

    # Tabla operativa: ver estados por persona
    st.markdown("### Listado de personas (con estados TA y EC)")
    st.dataframe(
        df_emp[[
            "Apellido y Nombre","DNI","Tipo de personal","Empresa","Puesto","Especialidad",
            "TA_Estado","EC_Estado","TA - TEORÍA","TA - PRÁCTICA","EC - TEORÍA","EC - PRÁCTICA"
        ]].sort_values("Apellido y Nombre"),
        use_container_width=True
    )
else:
    st.info("Elegí una Empresa/Subcontrato para listar a su personal.")
