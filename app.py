import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Seguimiento TA/EC", layout="wide")

st.title("Seguimiento de Capacitaciones Teoría–Práctica")
st.caption("Trabajo en Altura (TA) y Espacios Confinados (EC) — estados operativos (sin reprobados).")

PENDING_WORDS = {"PENDIENTE", "S/N", "SN", "NO", "N/A", "NA", ""}

def is_done_date(x) -> bool:
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
    return False

def to_excel_bytes(dataframe: pd.DataFrame) -> bytes:
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Datos")
    return out.getvalue()

def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed", regex=True)].copy()

    required = [
        "Apellido y Nombre","DNI","Puesto","Especialidad",
        "TA - TEORÍA","TA - PRÁCTICA","EC - TEORÍA","EC - PRÁCTICA",
        "Tipo de personal","Empresa"
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"Faltan columnas en el Excel: {missing}")
        st.stop()

    df["DNI"] = df["DNI"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    df["Apellido y Nombre"] = df["Apellido y Nombre"].astype(str).str.strip()
    df["Tipo de personal"] = df["Tipo de personal"].astype(str).str.strip()
    df["Empresa"] = df["Empresa"].astype(str).str.strip()

    df["TA_Teoria_OK"] = df["TA - TEORÍA"].apply(is_done_date)
    df["TA_Practica_OK"] = df["TA - PRÁCTICA"].apply(is_done_date)
    df["EC_Teoria_OK"] = df["EC - TEORÍA"].apply(is_done_date)
    df["EC_Practica_OK"] = df["EC - PRÁCTICA"].apply(is_done_date)

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

uploaded = st.file_uploader("Subí el Excel base (.xlsx)", type=["xlsx"])
st.divider()

if not uploaded:
    st.info("Subí un Excel para comenzar.")
    st.stop()

# Tu plantilla tiene 2 filas de título y encabezados en la fila 3:
df = pd.read_excel(uploaded, sheet_name=0, header=2)
df = normalize_df(df)

# -------- Filtros --------
c1, c2, c3, c4 = st.columns(4)
tema = c1.selectbox("Tema", ["Ambos", "Trabajo en Altura (TA)", "Espacios Confinados (EC)"])
tipo = c2.multiselect("Tipo de personal", sorted(df["Tipo de personal"].unique()), default=sorted(df["Tipo de personal"].unique()))
empresa = c3.multiselect("Empresa", sorted(df["Empresa"].unique()), default=sorted(df["Empresa"].unique()))
busqueda = c4.text_input("Buscar (DNI o nombre)", "")

df_f = df[df["Tipo de personal"].isin(tipo) & df["Empresa"].isin(empresa)].copy()

if busqueda.strip():
    q = busqueda.strip().lower()
    df_f = df_f[
        df_f["DNI"].astype(str).str.lower().str.contains(q) |
        df_f["Apellido y Nombre"].astype(str).str.lower().str.contains(q)
    ].copy()

show_ta = tema in ["Ambos", "Trabajo en Altura (TA)"]
show_ec = tema in ["Ambos", "Espacios Confinados (EC)"]

# -------- KPIs --------
def kpis_for(prefix: str, dfx: pd.DataFrame):
    total = len(dfx)
    teo = int(dfx[f"{prefix}_Teoria_OK"].sum())
    prac = int(dfx[f"{prefix}_Practica_OK"].sum())
    habil = int((dfx[f"{prefix}_Teoria_OK"] & ~dfx[f"{prefix}_Practica_OK"]).sum())
    pct_teo = (teo / total * 100) if total else 0
    pct_prac_total = (prac / total * 100) if total else 0
    pct_prac_teo = (prac / teo * 100) if teo else 0
    return total, teo, habil, prac, pct_teo, pct_prac_total, pct_prac_teo

kcol1, kcol2 = st.columns(2)

if show_ta:
    total, teo, habil, prac, pct_teo, pct_prac_total, pct_prac_teo = kpis_for("TA", df_f)
    with kcol1:
        st.subheader("Trabajo en Altura (TA)")
        a,b,c,d = st.columns(4)
        a.metric("Total nómina", total)
        b.metric("Con teoría", teo, f"{pct_teo:.1f}%")
        c.metric("Habilitados práctica", habil)
        d.metric("Práctica realizada", prac, f"{pct_prac_total:.1f}% vs total | {pct_prac_teo:.1f}% vs teoría")

if show_ec:
    total, teo, habil, prac, pct_teo, pct_prac_total, pct_prac_teo = kpis_for("EC", df_f)
    with kcol2:
        st.subheader("Espacios Confinados (EC)")
        a,b,c,d = st.columns(4)
        a.metric("Total nómina", total)
        b.metric("Con teoría", teo, f"{pct_teo:.1f}%")
        c.metric("Habilitados práctica", habil)
        d.metric("Práctica realizada", prac, f"{pct_prac_total:.1f}% vs total | {pct_prac_teo:.1f}% vs teoría")

st.divider()

# -------- Tablas operativas --------
tab1, tab2 = st.columns(2)

if show_ta:
    with tab1:
        st.markdown("### Operativo TA")
        estados = sorted(df_f["TA_Estado"].unique())
        sel = st.multiselect("Estado TA", estados, default=estados)
        df_ta = df_f[df_f["TA_Estado"].isin(sel)].copy()

        st.dataframe(
            df_ta[["Apellido y Nombre","DNI","Puesto","Especialidad","Tipo de personal","Empresa","TA - TEORÍA","TA - PRÁCTICA","TA_Estado"]]
            .sort_values("Apellido y Nombre"),
            use_container_width=True
        )

        st.download_button(
            "Descargar TA (filtrado)",
            data=to_excel_bytes(df_ta),
            file_name="Listado_TA_filtrado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

if show_ec:
    with tab2:
        st.markdown("### Operativo EC")
        estados = sorted(df_f["EC_Estado"].unique())
        sel = st.multiselect("Estado EC", estados, default=estados)
        df_ec = df_f[df_f["EC_Estado"].isin(sel)].copy()

        st.dataframe(
            df_ec[["Apellido y Nombre","DNI","Puesto","Especialidad","Tipo de personal","Empresa","EC - TEORÍA","EC - PRÁCTICA","EC_Estado"]]
            .sort_values("Apellido y Nombre"),
            use_container_width=True
        )

        st.download_button(
            "Descargar EC (filtrado)",
            data=to_excel_bytes(df_ec),
            file_name="Listado_EC_filtrado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
