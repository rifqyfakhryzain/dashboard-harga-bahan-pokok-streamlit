# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from streamlit_option_menu import option_menu

DATA_PATH = "data/fpma_indonesia_monthly_clean_long_with_oil.csv"

st.set_page_config(
    page_title="Dashboard Harga Bahan Pokok Indonesia",
    layout="wide"
)

# =========================
# LOAD & PREP DATA
# =========================
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    required = {"date", "commodity", "price"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Kolom wajib tidak ditemukan: {missing}. Kolom tersedia: {list(df.columns)}"
        )

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["price"])

    df["commodity"] = df["commodity"].astype(str).str.strip()

    if "currency" not in df.columns:
        df["currency"] = "IDR"
    else:
        df["currency"] = df["currency"].astype(str).str.strip()

    if "unit" not in df.columns:
        df["unit"] = ""
    else:
        df["unit"] = df["unit"].astype(str).str.strip()

    df = df.sort_values(["commodity", "date"]).reset_index(drop=True)
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return df


def add_changes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values(["commodity", "date"]).copy()
    out["mom_pct"] = out.groupby("commodity")["price"].pct_change(1) * 100
    out["yoy_pct"] = out.groupby("commodity")["price"].pct_change(12) * 100
    return out


def filter_data(df: pd.DataFrame, selected_commodities, start_date, end_date) -> pd.DataFrame:
    return df[
        (df["commodity"].isin(selected_commodities)) &
        (df["date"] >= start_date) &
        (df["date"] <= end_date)
    ].copy()


# =========================
# APP START
# =========================
df = load_data(DATA_PATH)

# =========================
# SIDEBAR MENU (MODERN)
# Urutan: Stabilitas -> YoY -> MoM -> dst.
# =========================
with st.sidebar:
    st.markdown("### Informasi Strategis ")

    info_choice = option_menu(
        menu_title=None,
        options=[
            "Stabilitas (Naik-Turun)",      # 1
            "Lonjakan Bulanan (MoM)",       # 3
            "Harga Terbaru (Saat Ini)",
            "Sebelum vs Sesudah Periode",
        ],
        icons=[
            "activity",                     # Stabilitas
            "exclamation-triangle",         # MoM
            "currency-dollar",
            "shuffle",
        ],
        default_index=0,
        styles={
            "container": {"padding": "0!important"},
            "icon": {"font-size": "16px"},
            "nav-link": {"font-size": "14px", "padding": "10px 12px", "border-radius": "10px"},
            "nav-link-selected": {"background-color": "#2b2b2b", "font-weight": "600"},
        }
    )

    st.divider()
    st.caption("Filter komoditas & tanggal ada di bagian utama halaman.")


# =========================
# HEADER
# =========================
st.title("Dashboard Harga Bahan Pokok Indonesia (FAO FPMA)")

with st.expander("Sumber Data & Catatan", expanded=False):
    st.write(
        "Dataset berasal dari FAO GIEWS FPMA (Domestic Prices). "
        "Satuan tiap komoditas bisa berbeda (contoh: Rice = IDR/Kg, Vegetable oil = IDR/Liter, Wheat(Flour) = IDR/Kg). "
        "Untuk perbandingan lintas komoditas yang lebih adil, gunakan perubahan (%) atau indeks."
    )

# =========================
# FILTER UTAMA (MAIN)
# =========================
commodities = sorted(df["commodity"].unique().tolist())
min_date = df["date"].min()
max_date = df["date"].max()

with st.expander("Filter Data (Komoditas & Rentang Waktu)", expanded=True):
    c1, c2 = st.columns([2, 2])

    with c1:
        selected_commodities = st.multiselect(
            "Pilih komoditas",
            options=commodities,
            default=commodities
        )

    with c2:
        date_range = st.date_input(
            "Rentang tanggal",
            value=(min_date.date(), max_date.date()),
            min_value=min_date.date(),
            max_value=max_date.date()
        )

start_date = pd.to_datetime(date_range[0])
end_date = pd.to_datetime(date_range[1])

df_f = filter_data(df, selected_commodities, start_date, end_date)
if df_f.empty:
    st.warning("Tidak ada data pada filter yang dipilih. Pilih komoditas atau ubah rentang tanggal.")
    st.stop()

dfx = add_changes(df_f)

# =========================
# TABS
# =========================
tab1, tab2 = st.tabs(["📌 Informasi Strategis", "🗃️ Data"])

# -------------------------
# TAB 1: INFORMASI STRATEGIS
# -------------------------
with tab1:
    st.subheader("Informasi Strategis")

    # 1) Stabilitas (naik-turun) - LINE CHART MoM 12 bulan
    if info_choice == "Stabilitas (Naik-Turun)":
        st.write("Menunjukkan seberapa sering harga **naik-turun (MoM)** dalam 12 bulan terakhir.")
        st.caption("Semakin zig-zag garisnya, semakin tidak stabil harganya.")

        # Ambil 12 bulan terakhir per komoditas
        recent = (
            dfx.sort_values("date")
            .groupby("commodity")
            .tail(12)
            .dropna(subset=["mom_pct"])
        )

        if recent.empty:
            st.warning("Data MoM belum cukup (butuh minimal 2 bulan data).")
            st.stop()

        # ===== LINE CHART =====
        fig = px.line(
            recent,
            x="date",
            y="mom_pct",
            color="commodity",
            markers=True,
            title="Stabilitas Harga (Naik-Turun MoM 12 Bulan Terakhir)"
        )

        fig.add_hline(y=0, line_dash="dash")

        fig.update_layout(
            xaxis_title="Tanggal",
            yaxis_title="Perubahan MoM (%)"
        )

        st.plotly_chart(fig, use_container_width=True)

        # ===== Ringkasan Stabilitas =====
        vol = (
            recent.groupby("commodity")["mom_pct"]
            .std()
            .reset_index(name="volatilitas")
            .sort_values("volatilitas", ascending=False)
        )

        if not vol.empty:
            top = vol.iloc[0]

            st.markdown("### 📌 Ringkasan")
            st.write(
                f"Komoditas paling **tidak stabil** dalam 12 bulan terakhir adalah "
                f"**{top['commodity']}**, karena memiliki naik-turun bulanan paling besar."
            )


    # 2) Lonjakan Bulanan (MoM) - puncak kenaikan per komoditas
    elif info_choice == "Lonjakan Bulanan (MoM)":
        st.write("Mencari bulan dengan **lonjakan terbesar dibanding bulan sebelumnya (MoM)** untuk tiap komoditas.")
        st.caption("MoM = perubahan dibanding bulan sebelumnya.")

        peak_list = []
        for c, grp in dfx.groupby("commodity"):
            g = grp.dropna(subset=["mom_pct"]).sort_values("mom_pct", ascending=False)
            if g.empty:
                continue
            peak = g.iloc[0]
            peak_list.append([c, peak["date"].strftime("%Y-%m"), float(peak["mom_pct"]), float(peak["price"])])

        peak_df = pd.DataFrame(peak_list, columns=["Komoditas", "Bulan", "Lonjakan MoM (%)", "Harga saat itu"])
        peak_df = peak_df.sort_values("Lonjakan MoM (%)", ascending=False)

        fig = px.bar(peak_df, x="Komoditas", y="Lonjakan MoM (%)", title="Lonjakan Bulanan Terbesar per Komoditas")
        fig.add_hline(y=0)
        fig.update_layout(xaxis_title="Komoditas", yaxis_title="MoM (%)")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Detail (tabel):**")
        st.dataframe(peak_df, use_container_width=True)

        if not peak_df.empty:
            top = peak_df.iloc[0]
            st.markdown("### 📌 Ringkasan")
            st.write(
                f"Lonjakan bulanan terbesar terjadi pada **{top['Komoditas']}** di **{top['Bulan']}** "
                f"sebesar **{top['Lonjakan MoM (%)']:.2f}%**. Bulan ini bisa menjadi titik fokus untuk menelusuri penyebabnya."
            )

    # 3) Harga Terbaru
    elif info_choice == "Harga Terbaru (Saat Ini)":
        st.write("Menampilkan **harga terakhir** untuk tiap komoditas (mengikuti satuan masing-masing).")

        latest_idx = df_f.groupby("commodity")["date"].idxmax()
        last = df_f.loc[latest_idx, ["commodity", "date", "price", "currency", "unit"]].copy()
        last = last.sort_values("price", ascending=False)

        colA, colB = st.columns([2, 1])
        with colA:
            fig = px.bar(last, x="commodity", y="price", title="Harga Terbaru per Komoditas")
            fig.update_layout(xaxis_title="Komoditas", yaxis_title="Harga (sesuai satuan)")
            st.plotly_chart(fig, use_container_width=True)

        with colB:
            if not last.empty:
                top = last.iloc[0]
                st.metric("Harga Tertinggi Saat Ini", top["commodity"])
                st.metric("Harga", f"{top['price']:,.0f} {top['currency']}/{top['unit']}")
                st.caption(f"Periode: {top['date'].strftime('%Y-%m')}")

    # 4) Sebelum vs Sesudah Periode
    elif info_choice == "Sebelum vs Sesudah Periode":
        st.write("Membandingkan **rata-rata harga** sebelum dan sesudah tahun tertentu.")
        st.caption("Catatan: fokus per komoditas yang sama. Satuan antar komoditas bisa berbeda.")

        years = sorted(df_f["year"].unique().tolist())
        default_idx = years.index(2021) if 2020 in years else 0
        pivot_year = st.selectbox("Pilih tahun pemisah", options=years, index=default_idx)

        tmp = df_f.copy()
        tmp["fase"] = np.where(tmp["year"] < pivot_year, f"Sebelum {pivot_year}", f"Sesudah {pivot_year}")
        tmp = tmp[tmp["year"] != pivot_year]

        counts = tmp.groupby("fase")["price"].count().reset_index(name="jumlah_data")
        st.caption("Cek ketersediaan data (biar jelas kalau salah satu bar tidak muncul):")
        st.dataframe(counts, use_container_width=True)

        agg = tmp.groupby(["commodity", "fase"], as_index=False)["price"].mean()

        all_comms = sorted(tmp["commodity"].unique().tolist())
        fases = [f"Sebelum {pivot_year}", f"Sesudah {pivot_year}"]
        grid = pd.MultiIndex.from_product([all_comms, fases], names=["commodity", "fase"]).to_frame(index=False)
        agg_full = grid.merge(agg, on=["commodity", "fase"], how="left")

        fig = px.bar(
            agg_full,
            x="commodity",
            y="price",
            color="fase",
            barmode="group",
            title=f"Rata-rata Harga: Sebelum vs Sesudah {pivot_year}"
        )
        fig.update_layout(xaxis_title="Komoditas", yaxis_title="Rata-rata Harga (sesuai satuan)")
        st.plotly_chart(fig, use_container_width=True)

        pivot_tbl = agg_full.pivot(index="commodity", columns="fase", values="price")
        if set(fases).issubset(pivot_tbl.columns):
            denom = pivot_tbl[fases[0]].replace({0: np.nan})
            pivot_tbl["Perubahan (%)"] = ((pivot_tbl[fases[1]] - pivot_tbl[fases[0]]) / denom) * 100
            pivot_tbl["Perubahan (%)"] = pivot_tbl["Perubahan (%)"].round(2)

        st.markdown("**Detail (tabel):**")
        st.dataframe(pivot_tbl.reset_index(), use_container_width=True)

        st.markdown("### 📌 Ringkasan")
        st.write(
            "Indikator ini membantu melihat apakah rata-rata harga setelah tahun pemisah cenderung lebih tinggi atau lebih rendah "
            "dibanding sebelum tahun tersebut, untuk setiap komoditas."
        )

# -------------------------
# TAB 2: DATA
# -------------------------
with tab2:
    st.subheader("Data (Setelah Filter)")
    st.dataframe(df_f, use_container_width=True)

    csv_out = df_f.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download data hasil filter (CSV)",
        data=csv_out,
        file_name="fpma_filtered.csv",
        mime="text/csv"
    )

