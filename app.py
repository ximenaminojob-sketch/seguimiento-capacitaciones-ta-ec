# app.py
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Seguimiento TA/EC", layout="wide")

st.title("Seguimiento de Capacitaciones Teoría–Práctica")
st.caption(
    "Tablero de avance medido sobre personas con TEORÍA realizada. "
    "Certificable = Teoría + Práctica (fecha en ambas celdas). "
    "Aplica para Trabajo en Altura (TA) y Espacios Confinados (EC)."
)

# Archivo fijo dentro del repo
DATA_PATH = "data/registro_ta_ec.xlsx"

PENDING_WORDS = {"PENDIENTE", "S/N", "SN", "NO", "N/A", "NA", ""}

# ---------------- Helpers ----------------
def is_done_date(x) -> bool:
    """True si x parece una fecha válida. False si vacío/PENDIENTE/SN/etc."""
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
    # Excel a veces guarda fechas como número (serial)
    if isinstance(x, (int, float)) and not pd.isna(x):
        return True
    return False

def to_excel_bytes(dataframe: pd.DataFrame, sheet_name="Datos") -> bytes:
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name=sheet_name)
    return out.getvalue()

def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    # Quita columnas "Unnamed" que suelen aparecer con celdas combinadas
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed", regex=True)].copy()

    required = [
        "Apellido y Nombre","DNI","Puesto","Especialidad",
        "TA - TEORÍA","TA - PRÁCTICA","EC - TEORÍA","EC - PRÁCTICA",
        "Tipo de personal","Empresa"
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(
            "Faltan columnas en el Excel: "
            f"{missing}\n\nTip: revisá el nombre exacto de columnas o el parámetro header (header=2 / header=0)."
        )
        st.stop()

    # Limpieza
    df["DNI"] = df["DNI"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    for col in ["Apellido y Nombre","Puesto","Especialidad","Tipo de personal","Empresa"]:
        df[col] = df[col].astype(str).str.strip()

    # Flags
    df["TA_Teoria_OK"] = df["TA - TEORÍA"].apply(is_done_date)
    df["TA_Practica_OK"] = df["TA - PRÁCTICA"].apply(is_done_date)
    df["EC_Teoria_OK"] = df["EC - TEORÍA"].apply(is_done_date)
    df["EC_Practica_OK"] = df["EC - PRÁCTICA"].apply(is_done_date)

    # Estados completos por tema
    df["TA_Estado"] = np.select(
        [
            ~df["TA_Teoria_OK"] & ~df["TA_Practica_OK"],
            df["TA_Teoria_OK"] & ~df["TA_Practica_OK"],
            df["TA_Teoria_OK"] & df["TA_Practica_OK"],
            ~df["TA_Teoria_OK"] & df["TA_Practica_OK"],
        ],
        [
            "Sin teoría ni práctica",
            "Solo teoría",
            "Teoría + práctica (Certificable)",
            "Solo práctica (Inconsistencia)",
        ],
        default="Sin dato"
    )

    df["EC_Estado"] = np.select(
        [
            ~df["EC_Teoria_OK"] & ~df["EC_Practica_OK"],
            df["EC_Teoria_OK"] & ~df["EC_Practica_OK"],
            df["EC_Teoria_OK"] & df["EC_Practica_OK"],
            ~df["EC_Teoria_OK"] & df["EC_Practica_OK"],
        ],
        [
            "Sin teoría ni práctica",
            "Solo teoría",
            "Teoría + práctica (Certificable)",
            "Solo práctica (Inconsistencia)",
        ],
        default="Sin dato"
    )

    return df

def avance_sobre_teoria(dfx: pd.DataFrame, teo_ok_col: str, prac_ok_col: str):
    """Avance medido sobre base de personas con TEORÍA hecha."""
    base_teoria = int(dfx[teo_ok_col].sum())
    certificables = int((dfx[teo_ok_col] & dfx[prac_ok_col]).sum())
    pendientes = int((dfx[teo_ok_col] & ~dfx[prac_ok_col]).sum())
    pct = (certificables / base_teoria * 100) if base_teoria else 0
    return base_teoria, certificables, pendientes, pct

def avance_por_grupo(dfx: pd.DataFrame, group_col: str, teo_ok_col: str, prac_ok_col: str) -> pd.DataFrame:
    """Tabla de avance por grupo (Empresa / Tipo) sobre base con TEORÍA."""
    tmp = dfx.copy()
    tmp["BASE_TEORIA"] = tmp[teo_ok_col].astype(int)
    tmp["CERTIFICABLE"] = (tmp[teo_ok_col] & tmp[prac_ok_col]).astype(int)

    g = tmp.groupby(group_col)[["BASE_TEORIA", "CERTIFICABLE"]].sum()
    g["PENDIENTE_PRACTICA"] = g["BASE_TEORIA"] - g["CERTIFICABLE"]
    g["AVANCE_%"] = np.where(g["BASE_TEORIA"] > 0, (g["CERTIFICABLE"] / g["BASE_TEORIA"] * 100), 0)
    g = g.sort_values(["AVANCE_%", "BASE_TEORIA"], ascending=[False, False]).reset_index()
    return g

# ---------------- Carga desde GitHub (repo) ----------------
st.divider()

try:
    # Si tus encabezados están en la fila 3 (con 2 filas de título arriba), header=2.
    # Si los encabezados están en la fila 1, cambiá a header=0.
    df = pd.read_excel(DATA_PATH, sheet_name=0, header=2)
except FileNotFoundError:
    st.error(f"No se encontró el archivo en: {DATA_PATH}. Revisá que exista data/registro_ta_ec.xlsx en el repo.")
    st.stop()

df = normalize_df(df)

# ---------------- Filtros ----------------
st.markdown("## Filtros")
f1, f2, f3, f4, f5 = st.columns([1.2, 1.2, 1.6, 1.2, 1.2])

tema = f1.selectbox("Tema", ["Ambos", "Trabajo en Altura (TA)", "Espacios Confinados (EC)"])
tipo = f2.multiselect("Tipo de personal", sorted(df["Tipo de personal"].unique()), default=sorted(df["Tipo de personal"].unique()))
empresa = f3.multiselect("Empresa", sorted(df["Empresa"].unique()), default=sorted(df["Empresa"].unique()))
puesto = f4.multiselect("Puesto", sorted(df["Puesto"].unique()), default=sorted(df["Puesto"].unique()))
busqueda = f5.text_input("Buscar (DNI o nombre)", "")

df_f = df[
    df["Tipo de personal"].isin(tipo) &
    df["Empresa"].isin(empresa) &
    df["Puesto"].isin(puesto)
].copy()

if busqueda.strip():
    q = busqueda.strip().lower()
    df_f = df_f[
        df_f["DNI"].astype(str).str.lower().str.contains(q) |
        df_f["Apellido y Nombre"].astype(str).str.lower().str.contains(q)
    ].copy()

show_ta = tema in ["Ambos", "Trabajo en Altura (TA)"]
show_ec = tema in ["Ambos", "Espacios Confinados (EC)"]

st.divider()

# ---------------- Tablero (KPIs + progreso) ----------------
st.markdown("## Tablero de avance (sobre personas con teoría)")

k1, k2 = st.columns(2)

if show_ta:
    base, cert, pend, pct = avance_sobre_teoria(df_f, "TA_Teoria_OK", "TA_Practica_OK")
    with k1:
        st.subheader("Trabajo en Altura (TA)")
        a,b,c = st.columns(3)
        a.metric("Base con teoría", base)
        b.metric("Certificables (Teo+Prac)", cert)
        c.metric("Pendientes de práctica", pend)
        st.metric("% Avance (certificables / base)", f"{pct:.1f}%")
        st.progress(min(int(round(pct)), 100))

if show_ec:
    base, cert, pend, pct = avance_sobre_teoria(df_f, "EC_Teoria_OK", "EC_Practica_OK")
    with k2:
        st.subheader("Espacios Confinados (EC)")
        a,b,c = st.columns(3)
        a.metric("Base con teoría", base)
        b.metric("Certificables (Teo+Prac)", cert)
        c.metric("Pendientes de práctica", pend)
        st.metric("% Avance (certificables / base)", f"{pct:.1f}%")
        st.progress(min(int(round(pct)), 100))

st.divider()

# ---------------- Gráficos ----------------
st.markdown("## Gráficos (sobre base con teoría)")
g1, g2 = st.columns(2)

if show_ta:
    base, cert, pend, pct = avance_sobre_teoria(df_f, "TA_Teoria_OK", "TA_Practica_OK")
    chart_ta = pd.DataFrame(
        {"Estado": ["Certificables", "Pendientes de práctica"], "Personas": [cert, pend]}
    ).set_index("Estado")
    with g1:
        st.markdown("### TA – Certificables vs Pendientes")
        st.bar_chart(chart_ta)

if show_ec:
    base, cert, pend, pct = avance_sobre_teoria(df_f, "EC_Teoria_OK", "EC_Practica_OK")
    chart_ec = pd.DataFrame(
        {"Estado": ["Certificables", "Pendientes de práctica"], "Personas": [cert, pend]}
    ).set_index("Estado")
    with g2:
        st.markdown("### EC – Certificables vs Pendientes")
        st.bar_chart(chart_ec)

st.divider()

# ---------------- Avance por Empresa / Tipo ----------------
st.markdown("## Avance por Empresa y por Tipo de personal (sobre base con teoría)")
t1, t2 = st.columns(2)

if show_ta:
    with t1:
        st.markdown("### TA – Por Empresa")
        ta_emp = avance_por_grupo(df_f[df_f["TA_Teoria_OK"]], "Empresa", "TA_Teoria_OK", "TA_Practica_OK")
        st.dataframe(ta_emp, use_container_width=True)
        if not ta_emp.empty:
            st.bar_chart(ta_emp.set_index("Empresa")[["AVANCE_%"]])

if show_ec:
    with t2:
        st.markdown("### EC – Por Empresa")
        ec_emp = avance_por_grupo(df_f[df_f["EC_Teoria_OK"]], "Empresa", "EC_Teoria_OK", "EC_Practica_OK")
        st.dataframe(ec_emp, use_container_width=True)
        if not ec_emp.empty:
            st.bar_chart(ec_emp.set_index("Empresa")[["AVANCE_%"]])

t3, t4 = st.columns(2)

if show_ta:
    with t3:
        st.markdown("### TA – Por Tipo de personal")
        ta_tipo = avance_por_grupo(df_f[df_f["TA_Teoria_OK"]], "Tipo de personal", "TA_Teoria_OK", "TA_Practica_OK")
        st.dataframe(ta_tipo, use_container_width=True)
        if not ta_tipo.empty:
            st.bar_chart(ta_tipo.set_index("Tipo de personal")[["AVANCE_%"]])

if show_ec:
    with t4:
        st.markdown("### EC – Por Tipo de personal")
        ec_tipo = avance_por_grupo(df_f[df_f["EC_Teoria_OK"]], "Tipo de personal", "EC_Teoria_OK", "EC_Practica_OK")
        st.dataframe(ec_tipo, use_container_width=True)
        if not ec_tipo.empty:
            st.bar_chart(ec_tipo.set_index("Tipo de personal")[["AVANCE_%"]])

st.divider()

# ---------------- Listados + descargas ----------------
st.markdown("## Listados (por estado) + Descargas")

tab1, tab2 = st.columns(2)

if show_ta:
    with tab1:
        st.markdown("### Trabajo en Altura (TA)")
        estados_ta = sorted(df_f["TA_Estado"].unique())
        sel_ta = st.multiselect("Estado TA", estados_ta, default=estados_ta, key="estado_ta")

        df_ta = df_f[df_f["TA_Estado"].isin(sel_ta)].copy()
        st.dataframe(
            df_ta[[
                "Apellido y Nombre","DNI","Puesto","Especialidad",
                "Tipo de personal","Empresa","TA - TEORÍA","TA - PRÁCTICA","TA_Estado"
            ]].sort_values("Apellido y Nombre"),
            use_container_width=True
        )

        df_ta_cert = df_ta[df_ta["TA_Estado"] == "Teoría + práctica (Certificable)"].copy()

        cA, cB = st.columns(2)
        with cA:
            st.download_button(
                "Descargar TA (filtrado)",
                data=to_excel_bytes(df_ta, sheet_name="TA_filtrado"),
                file_name="Listado_TA_filtrado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with cB:
            st.download_button(
                "Descargar TA – Certificables",
                data=to_excel_bytes(df_ta_cert, sheet_name="TA_certificables"),
                file_name="TA_certificables.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

if show_ec:
    with tab2:
        st.markdown("### Espacios Confinados (EC)")
        estados_ec = sorted(df_f["EC_Estado"].unique())
        sel_ec = st.multiselect("Estado EC", estados_ec, default=estados_ec, key="estado_ec")

        df_ec = df_f[df_f["EC_Estado"].isin(sel_ec)].copy()
        st.dataframe(
            df_ec[[
                "Apellido y Nombre","DNI","Puesto","Especialidad",
                "Tipo de personal","Empresa","EC - TEORÍA","EC - PRÁCTICA","EC_Estado"
            ]].sort_values("Apellido y Nombre"),
            use_container_width=True
        )

        df_ec_cert = df_ec[df_ec["EC_Estado"] == "Teoría + práctica (Certificable)"].copy()

        cA, cB = st.columns(2)
        with cA:
            st.download_button(
                "Descargar EC (filtrado)",
                data=to_excel_bytes(df_ec, sheet_name="EC_filtrado"),
                file_name="Listado_EC_filtrado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with cB:
            st.download_button(
                "Descargar EC – Certificables",
                data=to_excel_bytes(df_ec_cert, sheet_name="EC_certificables"),
                file_name="EC_certificables.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

st.caption("Si tus encabezados no se detectan, probá cambiar header=2 por header=0 (según dónde esté la fila de columnas).")
