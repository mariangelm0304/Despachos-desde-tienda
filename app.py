# -*- coding: utf-8 -*-
"""
Dashboard Interactivo de Despachos por Almacén — Muebles Jamar Colombia 2026
=============================================================================
Tiendas físicas que despachan producto directamente desde su inventario local
(sin pasar por CENDIS). Objetivo: entender QUÉ se vende desde cada tienda, con
qué margen, cómo evoluciona mes a mes, y detectar márgenes negativos.

Ejecutar:  streamlit run app.py
"""

import os
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# CONFIGURACIÓN GENERAL Y PALETA CORPORATIVA
# ---------------------------------------------------------------------------
AZUL_MARINO = "#1B3A5C"
NARANJA = "#F5A623"
BLANCO = "#FFFFFF"
FONDO = "#0E1B29"          # azul marino muy oscuro para el tema
FONDO_PANEL = "#16293D"
VERDE = "#2ECC71"
AMARILLO = "#F5C518"
ROJO = "#E74C3C"
GRIS_TEXTO = "#B8C4D0"

MESES = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio"}
MESES_INV = {v: k for k, v in MESES.items()}

st.set_page_config(
    page_title="Despachos por Almacén · Jamar 2026",
    page_icon="🛋️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS — TEMA OSCURO PROFESIONAL
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
        .stApp {{ background-color: {FONDO}; color: {BLANCO}; }}
        section[data-testid="stSidebar"] {{ background-color: {FONDO_PANEL}; }}
        section[data-testid="stSidebar"] * {{ color: {BLANCO}; }}
        h1, h2, h3, h4 {{ color: {BLANCO}; font-family: "Segoe UI", sans-serif; }}
        .block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; }}

        /* Tarjetas KPI */
        .kpi-card {{
            background: {FONDO_PANEL};
            border: 1px solid #24405c;
            border-left: 4px solid {NARANJA};
            border-radius: 12px;
            padding: 16px 18px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.35);
            height: 100%;
        }}
        .kpi-label {{
            font-size: 0.74rem; color: {GRIS_TEXTO};
            text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;
        }}
        .kpi-value {{ font-size: 1.55rem; font-weight: 700; color: {BLANCO}; line-height: 1.1; }}
        .kpi-sub {{ font-size: 0.72rem; color: {GRIS_TEXTO}; margin-top: 2px; }}

        .seccion {{
            border-left: 4px solid {NARANJA};
            padding-left: 10px; margin: 8px 0 2px 0;
        }}
        .stDataFrame {{ background-color: {FONDO_PANEL}; }}
        div[data-baseweb="select"] > div {{ background-color: {FONDO}; }}
        hr {{ border-color: #24405c; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# CARGA DE DATOS
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Cargando datos de despachos…")
def cargar_datos() -> pd.DataFrame:
    base = os.path.dirname(os.path.abspath(__file__))
    candidatos = [
        os.path.join(base, "datos_despachos_almacen_2026.csv"),
        os.path.join(base, "Data Completa Dashboard - Despachos ALMACEN 2026 (Ene-Jun).csv"),
    ]
    ruta = next((c for c in candidatos if os.path.exists(c)), None)
    if ruta is None:
        st.error(
            "No se encontró el archivo de datos. Coloca el CSV junto a app.py "
            "con el nombre 'datos_despachos_almacen_2026.csv'."
        )
        st.stop()
    import snowflake.connector

@st.cache_data(ttl=900)
def cargar_datos():
    conn = snowflake.connector.connect(
        user=st.secrets["snowflake"]["user"],
        password=st.secrets["snowflake"]["password"],
        account=st.secrets["snowflake"]["account"],
        warehouse=st.secrets["snowflake"]["warehouse"],
        database=st.secrets["snowflake"]["database"],
        role=st.secrets["snowflake"]["role"]
    )
    
    query = """
    SELECT 
        b.DESCRIPCION AS ALMACEN_ORIGEN,
        t.MES,
        p.ESTADO_GRUPO AS CICLO_VIDA,
        ac.LINEA,
        ac.SUBLINEA,
        ac.CATEGORIA,
        SUM(f.VALOR_VENTA_OFERTA) AS VENTA_COP,
        SUM(f.UNIDADES_VENDIDAS) AS UNIDADES,
        SUM(f.MARGEN_BRUTO) AS MARGEN_BRUTO_COP,
        SUM(f.CONTRIBUCION) AS MARGEN_CONTRIB_COP,
        SUM(f.COSTO_MERC_VENDIDA) AS COSTO_MERCANCIA_COP,
        SUM(f.FLETES) AS FLETES_COP,
        SUM(f.ARMADO) AS ARMADO_COP,
        COUNT(DISTINCT f.FACTURA) AS NUM_FACTURAS
    FROM JM_SILVER_PRD_DB.JM_VENTAS_LEGACY.FACT_FACTURACION f
    LEFT JOIN JM_SILVER_PRD_DB.JM_CORE_LEGACY.DIM_BODEGAS b 
        ON f.CENTRO_LOGISTICO_ID = b.ID
    LEFT JOIN JM_SILVER_PRD_DB.JM_CORE_LEGACY.DIM_UNIDAD_TIEMPO t 
        ON f.UNIDAD_TIEMPO_ID = t.ID
    LEFT JOIN JM_SILVER_PRD_DB.JM_CORE_LEGACY.DIM_PRODUCTOS p 
        ON f.PRODUCTO_ID = p.ID
    LEFT JOIN JM_SILVER_PRD_DB.JM_CORE_LEGACY.DIM_ARBOL_CAT ac 
        ON p.CATEGORIA_ID = ac.ID
    WHERE t.ANO = YEAR(CURRENT_DATE)
      AND b.CODIGO_SAP LIKE '3%%'
    GROUP BY 1,2,3,4,5,6
    HAVING SUM(f.VALOR_VENTA_OFERTA) <> 0
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    return df

df = cargar_datos()

# ---------------------------------------------------------------------------
# UTILIDADES DE FORMATO
# ---------------------------------------------------------------------------
def fmt_millones(valor: float, decimales: int = 1) -> str:
    if pd.isna(valor):
        return "—"
    return f"${valor / 1_000_000:,.{decimales}f}M"

def fmt_pct(valor: float, decimales: int = 1) -> str:
    if pd.isna(valor):
        return "—"
    return f"{valor:,.{decimales}f}%"

def fmt_entero(valor: float) -> str:
    if pd.isna(valor):
        return "—"
    return f"{valor:,.0f}"

def color_por_margen(pct: float) -> str:
    """Verde >40%, amarillo 20-40%, rojo <20%."""
    if pct is None or pd.isna(pct):
        return GRIS_TEXTO
    if pct > 40:
        return VERDE
    if pct >= 20:
        return AMARILLO
    return ROJO

PLOT_LAYOUT = dict(
    paper_bgcolor=FONDO,
    plot_bgcolor=FONDO_PANEL,
    font=dict(color=BLANCO, family="Segoe UI, sans-serif"),
    margin=dict(l=10, r=10, t=50, b=10),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
    title=dict(font=dict(size=15, color=BLANCO)),
)

def estilizar(fig, alto=None):
    fig.update_layout(**PLOT_LAYOUT)
    fig.update_xaxes(gridcolor="#24405c", zerolinecolor="#24405c")
    fig.update_yaxes(gridcolor="#24405c", zerolinecolor="#24405c")
    if alto:
        fig.update_layout(height=alto)
    return fig

# ---------------------------------------------------------------------------
# SIDEBAR — FILTROS
# ---------------------------------------------------------------------------
st.sidebar.markdown("## 🛋️ Filtros")
st.sidebar.caption("Muebles Jamar Colombia · Despachos de Almacén 2026")

def multiselect_todos(label, opciones, key, ayuda=None):
    """Multiselect que inicia con todas las opciones seleccionadas."""
    return st.sidebar.multiselect(label, options=opciones, default=opciones, key=key, help=ayuda)

# 1. MES
meses_disp = [MESES[m] for m in sorted(df["MES"].unique())]
sel_meses = multiselect_todos("📅 Mes", meses_disp, "f_mes")
sel_meses_num = [MESES_INV[m] for m in sel_meses]

# 2. ALMACEN
almacenes_disp = sorted(df["ALMACEN_ORIGEN"].unique())
sel_almacenes = multiselect_todos("🏬 Almacén origen", almacenes_disp, "f_alm")

# 3. LINEA
lineas_disp = sorted(df["LINEA"].unique())
sel_lineas = multiselect_todos("📦 Línea", lineas_disp, "f_lin")

# 4. SUBLINEA (dependiente de LINEA)
sublineas_disp = sorted(df.loc[df["LINEA"].isin(sel_lineas), "SUBLINEA"].unique()) if sel_lineas else []
sel_sublineas = st.sidebar.multiselect(
    "🔖 Sublínea", options=sublineas_disp, default=sublineas_disp, key="f_sub",
    help="Las opciones dependen de las líneas seleccionadas.",
)

# 5. CATEGORIA
categorias_disp = sorted(df["CATEGORIA"].unique())
sel_categorias = multiselect_todos("🗂️ Categoría", categorias_disp, "f_cat")

st.sidebar.markdown("---")

# Aplicar filtros
dff = df[
    df["MES"].isin(sel_meses_num)
    & df["ALMACEN_ORIGEN"].isin(sel_almacenes)
    & df["LINEA"].isin(sel_lineas)
    & df["SUBLINEA"].isin(sel_sublineas)
    & df["CATEGORIA"].isin(sel_categorias)
].copy()

st.sidebar.metric("Registros filtrados", f"{len(dff):,}", f"de {len(df):,} totales")

# ---------------------------------------------------------------------------
# CABECERA
# ---------------------------------------------------------------------------
st.markdown(
    f"<h1 style='margin-bottom:0'>Despachos por Almacén "
    f"<span style='color:{NARANJA}'>· Jamar 2026</span></h1>"
    f"<p style='color:{GRIS_TEXTO};margin-top:4px'>"
    f"Análisis de ventas y márgenes de tiendas que despachan desde inventario local "
    f"(sin CENDIS) · Enero–Junio 2026</p>",
    unsafe_allow_html=True,
)

if dff.empty:
    st.warning("⚠️ No hay datos para la combinación de filtros seleccionada. Ajusta los filtros en la barra lateral.")
    st.stop()

# ---------------------------------------------------------------------------
# FILA 1 — KPIs
# ---------------------------------------------------------------------------
total_venta = dff["VENTA_COP"].sum()
total_mb = dff["MARGEN_BRUTO_COP"].sum()
total_mc = dff["MARGEN_CONTRIB_COP"].sum()
total_und = dff["UNIDADES"].sum()
total_fact = dff["NUM_FACTURAS"].sum()
pct_mb_pond = (total_mb / total_venta * 100) if total_venta else np.nan
pct_mc_pond = (total_mc / total_venta * 100) if total_venta else np.nan
ticket_prom = (total_venta / total_fact) if total_fact else np.nan

def kpi(col, label, value, sub="", value_color=BLANCO):
    col.markdown(
        f"""<div class="kpi-card">
              <div class="kpi-label">{label}</div>
              <div class="kpi-value" style="color:{value_color}">{value}</div>
              <div class="kpi-sub">{sub}</div>
            </div>""",
        unsafe_allow_html=True,
    )

st.markdown("<div class='seccion'><h3>Indicadores clave</h3></div>", unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
kpi(c1, "Total Venta", fmt_millones(total_venta), "Ventas acumuladas", NARANJA)
kpi(c2, "Margen Bruto", fmt_millones(total_mb), "MB acumulado",
    VERDE if total_mb >= 0 else ROJO)
kpi(c3, "% Margen Bruto", fmt_pct(pct_mb_pond), "Promedio ponderado",
    color_por_margen(pct_mb_pond))
kpi(c4, "% Margen Contrib.", fmt_pct(pct_mc_pond), "Promedio ponderado",
    VERDE if pct_mc_pond >= 0 else ROJO)

c5, c6, c7 = st.columns(3)
kpi(c5, "Total Unidades", fmt_entero(total_und), "Unidades despachadas")
kpi(c6, "N.º Facturas", fmt_entero(total_fact), "Facturas emitidas")
kpi(c7, "Ticket Promedio", fmt_millones(ticket_prom, 2), "Venta / Factura", NARANJA)

st.markdown("---")

# ---------------------------------------------------------------------------
# FILA 2 — EVOLUCIÓN TEMPORAL
# ---------------------------------------------------------------------------
st.markdown("<div class='seccion'><h3>Evolución temporal por almacén</h3></div>", unsafe_allow_html=True)
g1, g2 = st.columns(2)

evol = (
    dff.groupby(["MES", "MES_NOMBRE", "ALMACEN_ORIGEN"])
    .agg(VENTA_COP=("VENTA_COP", "sum"),
         MARGEN_BRUTO_COP=("MARGEN_BRUTO_COP", "sum"))
    .reset_index()
)
evol["PCT_MB"] = np.where(evol["VENTA_COP"] != 0,
                          evol["MARGEN_BRUTO_COP"] / evol["VENTA_COP"] * 100, np.nan)
evol["VENTA_M"] = evol["VENTA_COP"] / 1_000_000
orden_meses = [MESES[m] for m in sorted(evol["MES"].unique())]

with g1:
    fig = px.line(
        evol.sort_values("MES"), x="MES_NOMBRE", y="VENTA_M", color="ALMACEN_ORIGEN",
        markers=True, category_orders={"MES_NOMBRE": orden_meses},
        labels={"VENTA_M": "Venta (M COP)", "MES_NOMBRE": "Mes", "ALMACEN_ORIGEN": "Almacén"},
        title="Venta mensual por almacén",
    )
    fig.update_traces(hovertemplate="%{fullData.name}<br>%{x}: $%{y:.1f}M<extra></extra>")
    st.plotly_chart(estilizar(fig, 430), use_container_width=True)

with g2:
    fig = px.line(
        evol.sort_values("MES"), x="MES_NOMBRE", y="PCT_MB", color="ALMACEN_ORIGEN",
        markers=True, category_orders={"MES_NOMBRE": orden_meses},
        labels={"PCT_MB": "% Margen Bruto", "MES_NOMBRE": "Mes", "ALMACEN_ORIGEN": "Almacén"},
        title="% Margen Bruto mensual por almacén",
    )
    fig.add_hline(y=0, line_dash="dot", line_color=GRIS_TEXTO)
    fig.update_traces(hovertemplate="%{fullData.name}<br>%{x}: %{y:.1f}%<extra></extra>")
    st.plotly_chart(estilizar(fig, 430), use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# FILA 3 — RANKINGS (Top 15 con color por % MB)
# ---------------------------------------------------------------------------
st.markdown("<div class='seccion'><h3>Rankings · Top 15 por venta</h3></div>", unsafe_allow_html=True)
r1, r2 = st.columns(2)

def ranking(df_in, dim, titulo, n=15):
    g = (df_in.groupby(dim)
         .agg(VENTA_COP=("VENTA_COP", "sum"),
              MARGEN_BRUTO_COP=("MARGEN_BRUTO_COP", "sum"))
         .reset_index())
    g["PCT_MB"] = np.where(g["VENTA_COP"] != 0,
                           g["MARGEN_BRUTO_COP"] / g["VENTA_COP"] * 100, np.nan)
    g = g.sort_values("VENTA_COP", ascending=False).head(n).sort_values("VENTA_COP")
    g["VENTA_M"] = g["VENTA_COP"] / 1_000_000
    g["color"] = g["PCT_MB"].apply(color_por_margen)
    fig = go.Figure(go.Bar(
        x=g["VENTA_M"], y=g[dim], orientation="h",
        marker=dict(color=g["color"]),
        text=[f"${v:.1f}M · {p:.1f}%" for v, p in zip(g["VENTA_M"], g["PCT_MB"])],
        textposition="auto", insidetextanchor="end",
        customdata=g["PCT_MB"],
        hovertemplate="%{y}<br>Venta: $%{x:.1f}M<br>% MB: %{customdata:.1f}%<extra></extra>",
    ))
    fig.update_layout(title=titulo, xaxis_title="Venta (M COP)", yaxis_title="")
    return estilizar(fig, 480)

with r1:
    st.plotly_chart(ranking(dff, "ALMACEN_ORIGEN", "Top 15 almacenes por venta"),
                    use_container_width=True)
with r2:
    st.plotly_chart(ranking(dff, "LINEA", "Top 15 líneas por venta"),
                    use_container_width=True)

st.markdown(
    f"<p style='color:{GRIS_TEXTO};font-size:0.8rem'>"
    f"<span style='color:{VERDE}'>■</span> % MB &gt; 40% &nbsp;&nbsp;"
    f"<span style='color:{AMARILLO}'>■</span> 20%–40% &nbsp;&nbsp;"
    f"<span style='color:{ROJO}'>■</span> &lt; 20%</p>",
    unsafe_allow_html=True,
)
st.markdown("---")

# ---------------------------------------------------------------------------
# FILA 4 — COMPOSICIÓN
# ---------------------------------------------------------------------------
st.markdown("<div class='seccion'><h3>Composición de portafolio</h3></div>", unsafe_allow_html=True)
co1, co2 = st.columns(2)

# Treemap LINEA > SUBLINEA, tamaño = VENTA, color = PCT_MARGEN_BRUTO (divergente)
with co1:
    tre = (dff.groupby(["LINEA", "SUBLINEA"])
           .agg(VENTA_COP=("VENTA_COP", "sum"),
                MARGEN_BRUTO_COP=("MARGEN_BRUTO_COP", "sum"))
           .reset_index())
    tre = tre[tre["VENTA_COP"] > 0]
    tre["PCT_MB"] = np.where(tre["VENTA_COP"] != 0,
                             tre["MARGEN_BRUTO_COP"] / tre["VENTA_COP"] * 100, 0)
    lim = max(40, float(np.nanpercentile(np.abs(tre["PCT_MB"]), 95))) if not tre.empty else 40
    fig = px.treemap(
        tre, path=[px.Constant("Todas las líneas"), "LINEA", "SUBLINEA"],
        values="VENTA_COP", color="PCT_MB",
        color_continuous_scale=[(0, ROJO), (0.5, "#F2F2F2"), (1, VERDE)],
        color_continuous_midpoint=0, range_color=[-lim, lim],
        title="Línea › Sublínea · tamaño = venta, color = % MB",
    )
    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>Venta: %{value:,.0f} COP<br>% MB: %{color:.1f}%<extra></extra>",
        marker_line_width=1, marker_line_color=FONDO,
    )
    fig.update_layout(coloraxis_colorbar=dict(title="% MB"))
    st.plotly_chart(estilizar(fig, 480), use_container_width=True)

# Stacked bar 100% por ALMACEN, composición por LINEA
with co2:
    comp = (dff.groupby(["ALMACEN_ORIGEN", "LINEA"])["VENTA_COP"].sum().reset_index())
    tot_alm = comp.groupby("ALMACEN_ORIGEN")["VENTA_COP"].transform("sum")
    comp["PCT"] = np.where(tot_alm != 0, comp["VENTA_COP"] / tot_alm * 100, 0)
    orden_alm = (comp.groupby("ALMACEN_ORIGEN")["VENTA_COP"].sum()
                 .sort_values(ascending=True).index.tolist())
    fig = px.bar(
        comp, x="PCT", y="ALMACEN_ORIGEN", color="LINEA", orientation="h",
        category_orders={"ALMACEN_ORIGEN": orden_alm},
        labels={"PCT": "% del almacén", "ALMACEN_ORIGEN": "", "LINEA": "Línea"},
        title="Composición de venta por línea (100% por almacén)",
    )
    fig.update_layout(barmode="stack", xaxis=dict(ticksuffix="%"))
    fig.update_traces(hovertemplate="%{fullData.name}<br>%{y}: %{x:.1f}%<extra></extra>")
    st.plotly_chart(estilizar(fig, 480), use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# FILA 5 — ANÁLISIS DE MARGEN
# ---------------------------------------------------------------------------
st.markdown("<div class='seccion'><h3>Análisis de margen</h3></div>", unsafe_allow_html=True)
m1, m2 = st.columns([3, 2])

with m1:
    sc = dff[dff["VENTA_COP"] > 0].copy()
    sc["VENTA_M"] = sc["VENTA_COP"] / 1_000_000
    sc["UNIDADES_ABS"] = sc["UNIDADES"].abs()  # tamaño no admite negativos (devoluciones)
    fig = px.scatter(
        sc, x="VENTA_M", y="PCT_MARGEN_BRUTO", size="UNIDADES_ABS", color="CATEGORIA",
        size_max=38, opacity=0.75,
        custom_data=["ALMACEN_ORIGEN", "SUBLINEA", "LINEA", "UNIDADES"],
        labels={"VENTA_M": "Venta (M COP)", "PCT_MARGEN_BRUTO": "% Margen Bruto",
                "CATEGORIA": "Categoría"},
        title="Venta vs. % Margen Bruto (tamaño = unidades)",
    )
    fig.add_hline(y=0, line_dash="dot", line_color=ROJO)
    fig.update_traces(hovertemplate=(
        "<b>%{customdata[0]}</b><br>%{customdata[2]} › %{customdata[1]}"
        "<br>Venta: $%{x:.1f}M<br>% MB: %{y:.1f}%<br>Unidades: %{customdata[3]}<extra></extra>"
    ))
    st.plotly_chart(estilizar(fig, 470), use_container_width=True)

with m2:
    st.markdown("**🚨 Alertas · Márgenes brutos negativos**")
    alertas = dff[dff["PCT_MARGEN_BRUTO"] < 0].sort_values("PCT_MARGEN_BRUTO").copy()
    if alertas.empty:
        st.success("Sin márgenes negativos en la selección actual. 🎉")
    else:
        st.caption(f"{len(alertas):,} combinaciones con margen bruto negativo "
                   f"(venta afectada: {fmt_millones(alertas['VENTA_COP'].sum())}).")
        tabla = alertas[["ALMACEN_ORIGEN", "MES_NOMBRE", "LINEA", "SUBLINEA",
                         "VENTA_COP", "MARGEN_BRUTO_COP", "PCT_MARGEN_BRUTO"]].copy()
        tabla["VENTA_COP"] = tabla["VENTA_COP"] / 1_000_000
        tabla["MARGEN_BRUTO_COP"] = tabla["MARGEN_BRUTO_COP"] / 1_000_000
        tabla = tabla.rename(columns={
            "ALMACEN_ORIGEN": "Almacén", "MES_NOMBRE": "Mes", "LINEA": "Línea",
            "SUBLINEA": "Sublínea", "VENTA_COP": "Venta (M)",
            "MARGEN_BRUTO_COP": "MB (M)", "PCT_MARGEN_BRUTO": "% MB"})
        st.dataframe(
            tabla.style
            .format({"Venta (M)": "${:,.2f}M", "MB (M)": "${:,.2f}M", "% MB": "{:,.1f}%"})
            .applymap(lambda v: f"color: {ROJO}", subset=["MB (M)", "% MB"]),
            use_container_width=True, height=420, hide_index=True,
        )

st.markdown("---")

# ---------------------------------------------------------------------------
# FILA 6 — TABLA DE DETALLE
# ---------------------------------------------------------------------------
st.markdown("<div class='seccion'><h3>Detalle completo</h3></div>", unsafe_allow_html=True)

busq = st.text_input("🔍 Buscar (almacén, línea, sublínea, categoría)", "")
det = dff.copy()
if busq.strip():
    patron = busq.strip()
    mask = (
        det["ALMACEN_ORIGEN"].str.contains(patron, case=False, na=False)
        | det["LINEA"].str.contains(patron, case=False, na=False)
        | det["SUBLINEA"].str.contains(patron, case=False, na=False)
        | det["CATEGORIA"].str.contains(patron, case=False, na=False)
    )
    det = det[mask]

# Pasar a millones las columnas monetarias para visualización
cols_money = ["VENTA_COP", "MARGEN_BRUTO_COP", "MARGEN_CONTRIB_COP",
              "COSTO_MERCANCIA_COP", "FLETES_COP", "ARMADO_COP"]
vista = det[[
    "ALMACEN_ORIGEN", "MES_NOMBRE", "LINEA", "SUBLINEA", "CATEGORIA",
    *cols_money, "UNIDADES", "NUM_FACTURAS",
    "PCT_DE_TIENDA_MES", "PCT_MARGEN_BRUTO", "PCT_MARGEN_CONTRIB",
]].copy()
for c in cols_money:
    vista[c] = vista[c] / 1_000_000

vista = vista.rename(columns={
    "ALMACEN_ORIGEN": "Almacén", "MES_NOMBRE": "Mes", "LINEA": "Línea",
    "SUBLINEA": "Sublínea", "CATEGORIA": "Categoría",
    "VENTA_COP": "Venta (M)", "MARGEN_BRUTO_COP": "MB (M)",
    "MARGEN_CONTRIB_COP": "MC (M)", "COSTO_MERCANCIA_COP": "Costo (M)",
    "FLETES_COP": "Fletes (M)", "ARMADO_COP": "Armado (M)",
    "UNIDADES": "Unidades", "NUM_FACTURAS": "Facturas",
    "PCT_DE_TIENDA_MES": "% Tienda-Mes", "PCT_MARGEN_BRUTO": "% MB",
    "PCT_MARGEN_CONTRIB": "% MC",
})

cols_margen = ["MB (M)", "MC (M)", "% MB", "% MC"]
def color_neg_pos(v):
    if pd.isna(v):
        return ""
    return f"color: {ROJO}" if v < 0 else f"color: {VERDE}"

fmt_dict = {
    "Venta (M)": "${:,.2f}M", "MB (M)": "${:,.2f}M", "MC (M)": "${:,.2f}M",
    "Costo (M)": "${:,.2f}M", "Fletes (M)": "${:,.3f}M", "Armado (M)": "${:,.3f}M",
    "Unidades": "{:,.0f}", "Facturas": "{:,.0f}",
    "% Tienda-Mes": "{:,.1f}%", "% MB": "{:,.1f}%", "% MC": "{:,.1f}%",
}

st.caption(f"{len(vista):,} filas · ordena haciendo clic en cualquier encabezado de columna.")
st.dataframe(
    vista.style.format(fmt_dict).applymap(color_neg_pos, subset=cols_margen),
    use_container_width=True, height=460, hide_index=True,
)

# Descarga
csv_out = det.to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ Descargar datos filtrados (CSV)", csv_out,
                   file_name="despachos_filtrado.csv", mime="text/csv")

st.markdown(
    f"<p style='color:{GRIS_TEXTO};font-size:0.78rem;text-align:center;margin-top:20px'>"
    f"Muebles Jamar Colombia &middot; Dashboard de Despachos de Almac&eacute;n &middot; Datos Ene&ndash;Jun 2026"
    f"</p>", unsafe_allow_html=True,
)
