import streamlit as st
import pandas as pd
import pickle
import altair as alt
import json

st.title("Dashboard Analitik DJPb")

# Sidebar Filter
st.sidebar.header("Menu Filter")
opsi = st.sidebar.selectbox("Pilih Model:", ["Klasifikasi", "Regresi"])

data = pd.read_csv("data/02_realisasi_anggaran_klasifikasi.csv")


@st.cache_resource
def load_model():
    with open("models/Best_model.pkcls", "rb") as model_file:
        return pickle.load(model_file)


tab_prediksi, tab_visualisasi = st.tabs(["Menu Prediksi", "Visualisasi"])

with tab_visualisasi:
    st.header("Visualisasi Pie Chart")
    st.markdown(
        "Pie chart menunjukkan proporsi satuan kerja berdasarkan kolom `realisasi_tercapai_95persen`."
    )

    pie_data = (
        data["realisasi_tercapai_95persen"]
        .value_counts()
        .rename_axis("Realisasi Tercapai 95%")
        .reset_index(name="Jumlah")
    )

    chart = (
        alt.Chart(pie_data)
        .mark_arc(outerRadius=180)
        .encode(
            theta=alt.Theta("Jumlah:Q"),
            color=alt.Color(
                "Realisasi Tercapai 95%:N",
                title="Realisasi Tercapai 95%",
                scale=alt.Scale(
                    domain=["Ya", "Tidak"],
                    range=["#1976D2", "#D32F2F"],
                ),
            ),
            tooltip=[
                "Realisasi Tercapai 95%:N",
                "Jumlah:Q",
            ],
        )
        .properties(width=900, height=450)
        .interactive()
    )
    st.altair_chart(chart, width=900)
    st.header("Peta Indonesia")
    st.markdown(
        "Warna menunjukkan apakah mayoritas satuan kerja di provinsi mencapai 95%. "
        "Label pada peta menunjukkan rata-rata skor IKPA."
    )

    map_data = data.copy()
    map_data["Provinsi"] = map_data["provinsi"].replace(
        {
            "NTB": "Nusa Tenggara Barat",
            "NTT": "Nusa Tenggara Timur",
        }
    )
    map_data = (
        map_data.groupby("Provinsi", as_index=False)
        .agg(
            **{
                "Rata-rata Skor IKPA": ("skor_ikpa", "mean"),
                "Jumlah Satuan Kerja": ("kode_satker", "count"),
                "Satker Tercapai": (
                    "realisasi_tercapai_95persen",
                    lambda status: status.eq("Ya").sum(),
                ),
                "Satker Tidak Tercapai": (
                    "realisasi_tercapai_95persen",
                    lambda status: status.eq("Tidak").sum(),
                ),
            }
        )
    )
    map_data["Status Capaian 95%"] = (
        map_data["Satker Tercapai"] > map_data["Jumlah Satuan Kerja"] / 2
    ).map({True: "Tercapai", False: "Tidak tercapai"})

    province_geo = (
        alt.Chart(
            alt.Data(
                url="data/indonesia-38-provinces.geojson",
                format=alt.DataFormat(property="features"),
            )
        )
        .mark_geoshape(stroke="white", strokeWidth=0.6)
        .transform_lookup(
            lookup="properties.PROVINSI",
            from_=alt.LookupData(
                map_data,
                key="Provinsi",
                fields=[
                    "Rata-rata Skor IKPA",
                    "Jumlah Satuan Kerja",
                    "Satker Tercapai",
                    "Satker Tidak Tercapai",
                    "Status Capaian 95%",
                ],
            ),
        )
        .encode(
            color=alt.Color(
                "Status Capaian 95%:N",
                title="Status (mayoritas satker)",
                scale=alt.Scale(
                    domain=["Tercapai", "Tidak tercapai"],
                    range=["#1976D2", "#D32F2F"],
                ),
            ),
            tooltip=[
                alt.Tooltip("properties.PROVINSI:N", title="Provinsi"),
                alt.Tooltip("Rata-rata Skor IKPA:Q", format=".2f"),
                alt.Tooltip("Jumlah Satuan Kerja:Q"),
                alt.Tooltip("Satker Tercapai:Q", title="Satker tercapai 95%"),
                alt.Tooltip(
                    "Satker Tidak Tercapai:Q",
                    title="Satker tidak tercapai 95%",
                ),
                alt.Tooltip("Status Capaian 95%:N", title="Status provinsi"),
            ],
        )
        .properties(width=900, height=550)
        .project(type="mercator")
    )

    def geometry_coordinates(coordinates):
        if isinstance(coordinates[0], (int, float)):
            return [coordinates]
        values = []
        for item in coordinates:
            values.extend(geometry_coordinates(item))
        return values

    with open("data/indonesia-38-provinces.geojson", encoding="utf-8") as geo_file:
        indonesia_geo = json.load(geo_file)

    label_rows = []
    for feature in indonesia_geo["features"]:
        province = feature["properties"]["PROVINSI"]
        points = geometry_coordinates(feature["geometry"]["coordinates"])
        province_average = map_data.loc[
            map_data["Provinsi"] == province,
            "Rata-rata Skor IKPA",
        ]
        if province_average.empty:
            continue
        label_rows.append(
            {
                "Provinsi": province,
                "longitude": sum(point[0] for point in points) / len(points),
                "latitude": sum(point[1] for point in points) / len(points),
                "Rata-rata Skor IKPA": float(province_average.iloc[0]),
            }
        )

    map_labels = (
        alt.Chart(pd.DataFrame(label_rows))
        .mark_text(fontSize=11, fontWeight="bold", color="#123A5A")
        .encode(
            longitude="longitude:Q",
            latitude="latitude:Q",
            text=alt.Text("Rata-rata Skor IKPA:Q", format=".1f"),
        )
        .project(type="mercator")
    )

    indonesia_map = province_geo + map_labels
    st.altair_chart(indonesia_map, width=900)

    st.subheader("Sebaran Satker per Provinsi")
    st.markdown(
        "Warna provinsi mengikuti status mayoritas satker. Gelembung merah dan biru "
        "menunjukkan jumlah satker yang tidak tercapai dan tercapai di setiap provinsi. "
        "Titik mewakili provinsi, bukan koordinat satker individual; pasangan status "
        "digeser sedikit agar tidak bertumpuk."
    )

    province_locations = pd.DataFrame(label_rows)[
        ["Provinsi", "longitude", "latitude"]
    ]
    distribution_data = map_data.melt(
        id_vars=["Provinsi"],
        value_vars=["Satker Tercapai", "Satker Tidak Tercapai"],
        var_name="Status",
        value_name="Jumlah Satker",
    )
    distribution_data["Status"] = distribution_data["Status"].map(
        {
            "Satker Tercapai": "Tercapai",
            "Satker Tidak Tercapai": "Tidak tercapai",
        }
    )
    distribution_data = distribution_data.merge(
        province_locations,
        on="Provinsi",
        how="inner",
        validate="many_to_one",
    )
    distribution_data["longitude"] += distribution_data["Status"].map(
        {"Tercapai": 0.25, "Tidak tercapai": -0.25}
    )
    distribution_data = distribution_data[
        distribution_data["Jumlah Satker"] > 0
    ]

    distribution_base = (
        alt.Chart(
            alt.Data(
                url="data/indonesia-38-provinces.geojson",
                format=alt.DataFormat(property="features"),
            )
        )
        .mark_geoshape(stroke="white", strokeWidth=0.6)
        .transform_lookup(
            lookup="properties.PROVINSI",
            from_=alt.LookupData(
                map_data,
                key="Provinsi",
                fields=[
                    "Status Capaian 95%",
                    "Satker Tercapai",
                    "Satker Tidak Tercapai",
                ],
            ),
        )
        .encode(
            color=alt.Color(
                "Status Capaian 95%:N",
                title="Status mayoritas provinsi",
                scale=alt.Scale(
                    domain=["Tercapai", "Tidak tercapai"],
                    range=["#1976D2", "#D32F2F"],
                ),
            ),
            tooltip=[
                alt.Tooltip("properties.PROVINSI:N", title="Provinsi"),
                alt.Tooltip("Status Capaian 95%:N", title="Status mayoritas"),
                alt.Tooltip("Satker Tercapai:Q", title="Satker tercapai 95%"),
                alt.Tooltip(
                    "Satker Tidak Tercapai:Q",
                    title="Satker tidak tercapai 95%",
                ),
            ],
        )
    )
    satker_bubbles = (
        alt.Chart(distribution_data)
        .mark_circle(opacity=0.8, stroke="white", strokeWidth=1)
        .encode(
            longitude="longitude:Q",
            latitude="latitude:Q",
            size=alt.Size(
                "Jumlah Satker:Q",
                title="Jumlah Satker",
                scale=alt.Scale(range=[30, 600]),
            ),
            color=alt.Color(
                "Status:N",
                title="Realisasi 95%",
                scale=alt.Scale(
                    domain=["Tercapai", "Tidak tercapai"],
                    range=["#1976D2", "#D32F2F"],
                ),
            ),
            tooltip=[
                alt.Tooltip("Provinsi:N"),
                alt.Tooltip("Status:N", title="Status realisasi"),
                alt.Tooltip("Jumlah Satker:Q"),
            ],
        )
    )
    satker_distribution_map = (
        alt.layer(distribution_base, satker_bubbles)
        .properties(width=900, height=550)
        .project(type="mercator")
    )
    st.altair_chart(satker_distribution_map, width=900)

    st.subheader("Streamline Sebaran Satker")
    total_satker = len(data)
    satker_tercapai = data["realisasi_tercapai_95persen"].eq("Ya").sum()
    satker_tidak_tercapai = data["realisasi_tercapai_95persen"].eq("Tidak").sum()
    status_columns = st.columns(2)
    status_columns[0].metric(
        "Tercapai",
        f"{satker_tercapai / total_satker * 100:.1f}%",
        help=f"{satker_tercapai} dari {total_satker} satker",
    )
    status_columns[1].metric(
        "Tidak tercapai",
        f"{satker_tidak_tercapai / total_satker * 100:.1f}%",
        help=f"{satker_tidak_tercapai} dari {total_satker} satker",
    )
    st.markdown(
        "Garis menghubungkan Jakarta sebagai titik acuan visual ke tiap provinsi. "
        "Warna menunjukkan status, sedangkan ketebalan menunjukkan persentase satker "
        "dengan status tersebut di provinsi terkait. Garis ini bukan rute atau aliran aktual."
    )

    province_totals = map_data.set_index("Provinsi")["Jumlah Satuan Kerja"]
    distribution_data["Persentase Satker"] = (
        distribution_data["Jumlah Satker"]
        / distribution_data["Provinsi"].map(province_totals)
        * 100
    )
    jakarta_location = province_locations.loc[
        province_locations["Provinsi"] == "DKI Jakarta"
    ].iloc[0]
    flow_rows = []
    for row in distribution_data.to_dict("records"):
        if row["Provinsi"] == "DKI Jakarta":
            continue

        start_lon = float(jakarta_location["longitude"])
        start_lat = float(jakarta_location["latitude"])
        end_lon = float(row["longitude"])
        end_lat = float(row["latitude"])
        control_lon = (start_lon + end_lon) / 2
        control_lat = (start_lat + end_lat) / 2 + 5

        for step in range(21):
            position = step / 20
            inverse = 1 - position
            flow_rows.append(
                {
                    "Rute": f'{row["Provinsi"]}-{row["Status"]}',
                    "Provinsi": row["Provinsi"],
                    "Status": row["Status"],
                    "Jumlah Satker": row["Jumlah Satker"],
                    "Persentase Satker": row["Persentase Satker"],
                    "step": step,
                    "longitude": (
                        inverse**2 * start_lon
                        + 2 * inverse * position * control_lon
                        + position**2 * end_lon
                    ),
                    "latitude": (
                        inverse**2 * start_lat
                        + 2 * inverse * position * control_lat
                        + position**2 * end_lat
                    ),
                }
            )

    streamline_data = pd.DataFrame(flow_rows)
    streamline_lines = (
        alt.Chart(streamline_data)
        .mark_line(opacity=0.7)
        .encode(
            longitude="longitude:Q",
            latitude="latitude:Q",
            detail=alt.Detail("Rute:N"),
            order=alt.Order("step:Q"),
            size=alt.Size(
                "Persentase Satker:Q",
                title="Persentase Satker (%)",
                scale=alt.Scale(domain=[0, 100], range=[1, 7]),
            ),
            color=alt.Color(
                "Status:N",
                title="Realisasi 95%",
                scale=alt.Scale(
                    domain=["Tercapai", "Tidak tercapai"],
                    range=["#1976D2", "#D32F2F"],
                ),
            ),
            tooltip=[
                alt.Tooltip("Provinsi:N"),
                alt.Tooltip("Status:N", title="Status realisasi"),
                alt.Tooltip("Jumlah Satker:Q"),
                alt.Tooltip("Persentase Satker:Q", format=".1f"),
            ],
        )
    )
    streamline_endpoints = (
        alt.Chart(distribution_data)
        .mark_circle(stroke="white", strokeWidth=1)
        .encode(
            longitude="longitude:Q",
            latitude="latitude:Q",
            size=alt.Size(
                "Persentase Satker:Q",
                title="Persentase Satker (%)",
                scale=alt.Scale(range=[30, 400]),
            ),
            color=alt.Color(
                "Status:N",
                title="Realisasi 95%",
                scale=alt.Scale(
                    domain=["Tercapai", "Tidak tercapai"],
                    range=["#1976D2", "#D32F2F"],
                ),
            ),
            tooltip=[
                alt.Tooltip("Provinsi:N"),
                alt.Tooltip("Status:N", title="Status realisasi"),
                alt.Tooltip("Jumlah Satker:Q"),
                alt.Tooltip("Persentase Satker:Q", format=".1f"),
            ],
        )
    )
    jakarta_hub = (
        alt.Chart(
            pd.DataFrame(
                [
                    {
                        "longitude": float(jakarta_location["longitude"]),
                        "latitude": float(jakarta_location["latitude"]),
                        "Label": "Jakarta: titik acuan visual",
                    }
                ]
            )
        )
        .mark_point(shape="diamond", size=120, color="#222222")
        .encode(
            longitude="longitude:Q",
            latitude="latitude:Q",
            tooltip=alt.Tooltip("Label:N"),
        )
    )
    streamline_map = (
        alt.layer(
            distribution_base,
            streamline_lines,
            streamline_endpoints,
            jakarta_hub,
        )
        .properties(width=900, height=550)
        .project(type="mercator")
    )
    st.altair_chart(streamline_map, width=900)
with tab_prediksi:
    st.header("Prediksi Realisasi 95%")
    st.markdown("Masukkan data input berikut dan klik tombol untuk melihat hasil prediksi.")

    col1, col2 = st.columns(2)
    with col1:
        jumlah_spm = st.number_input(
            "Jumlah SPM",
            min_value=1,
            max_value=200,
            value=10,
            step=1,
            format="%d",
        )
        revisi_dipa = st.number_input(
            "Revisi DIPA",
            min_value=0,
            max_value=5,
            value=1,
            step=1,
            format="%d",
        )
        deviasi_rpd_persen = st.number_input(
            "Deviasi RPD (%)",
            min_value=0.00,
            max_value=30.00,
            value=5.50,
            format="%.2f",
        )
    with col2:
        skor_ikpa = st.slider(
            "Skor IKPA",
            min_value=70.00,
            max_value=100.00,
            value=85.00,
            step=0.01,
            format="%.2f",
        )
        tipe_satker = st.selectbox(
            "Tipe Satker",
            ["Dekonsentrasi", "Kantor Daerah", "Kantor Pusat", "Tugas Pembantuan"],
        )

    if st.button("Prediksi", type="primary"):
        try:
            import Orange
        except ModuleNotFoundError as exc:
            if exc.name != "Orange":
                raise
            st.error(
                "Orange3 belum terpasang di interpreter ini. Jalankan `uv sync` "
                "atau `pip install -r requirements.txt`, lalu muat ulang aplikasi."
            )
        else:
            model = load_model()
            tipe_values = [
                "Dekonsentrasi",
                "Kantor Daerah",
                "Kantor Pusat",
                "Tugas Pembantuan",
            ]
            tipe_indicators = [
                1.0 if tipe_satker == tipe_value else 0.0
                for tipe_value in tipe_values
            ]
            input_row = [
                float(jumlah_spm),
                float(revisi_dipa),
                float(deviasi_rpd_persen),
                float(skor_ikpa),
                *tipe_indicators,
            ]

            table = Orange.data.Table.from_list(model.domain, [input_row])
            prediction_index = int(model(table)[0])
            probabilities = model(table, model.Probs)[0]
            class_name = model.domain.class_var.values[prediction_index]
            confidence = float(probabilities[prediction_index])

            if class_name == "Ya":
                st.success(f"Prediksi: {class_name} (keyakinan {confidence:.1%})")
            else:
                st.warning(f"Prediksi: {class_name} (keyakinan {confidence:.1%})")

with tab_visualisasi:
    st.header("Visualisasi Bubble Plot")
    st.markdown(
        "Grafik bubble menunjukkan skor IKPA terhadap deviasi RPD, dengan warna berdasarkan kolom `realisasi_tercapai_95persen`."
    )

    chart = (
        alt.Chart(data)
        .mark_circle(opacity=0.7, size=100)
        .encode(
            x=alt.X(
                "skor_ikpa",
                title="Skor IKPA",
                scale=alt.Scale(domain=[70, 100]),
            ),
            y=alt.Y("deviasi_rpd_persen", title="Deviasi RPD (%)"),
            color=alt.Color(
                "realisasi_tercapai_95persen:N",
                title="Realisasi Tercapai 95%",
                scale=alt.Scale(
                    domain=["Ya", "Tidak"],
                    range=["#1976D2", "#D32F2F"],
                ),
            ),
            tooltip=[
                "kode_satker",
                "tipe_satker",
                "skor_ikpa",
                "deviasi_rpd_persen",
                "realisasi_tercapai_95persen",
            ],
        )
        .properties(width=900, height=550)
        .interactive()
    )
    st.altair_chart(chart, width=900)
