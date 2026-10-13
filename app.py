"""Indonesian local browser interface for the notebook-compatible converter."""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from web_workflow import (filters_from_inputs, local_source, plot_data, preview_batch,
                          process_batch, results_zip, scan_folder, selection_signature,
                          sync_session, uploaded_sources)

st.set_page_config(page_title="Ruang GRIB", page_icon="🌦️", layout="wide")
st.markdown("""
<style>
.stApp {background: #f4f7fa; color: #19364a;}
.block-container {max-width: 1200px; padding-top: 2rem; padding-bottom: 3rem;}
h1, h2, h3 {color: #19364a; letter-spacing: -.025em;}
div[data-testid="stVerticalBlockBorderWrapper"] {background: #fff; border-radius: 14px;}
.grib-hero {background: linear-gradient(115deg,#193b55,#205c6b); padding: 2rem;
border-radius: 18px; color: white; margin-bottom: 1.4rem;}
.grib-hero h1 {color:white; font-size:2.2rem; margin:.4rem 0 .7rem;}
.grib-hero p {color:#deebf0; max-width:720px; margin:0; font-size:1.04rem;}
.grib-tag {color:#a4e6db; font-size:.8rem; letter-spacing:.18em; font-weight:700;}
.grib-step {font-size:.9rem; color:#326275; padding:.8rem 0;}
button[kind="primary"] {background-color:#167f80; border-color:#167f80;}
@media(max-width:640px) {.grib-hero{padding:1.2rem}.grib-hero h1{font-size:1.7rem}}
</style>
<div class="grib-hero"><span class="grib-tag">RUANG GRIB · PENGOLAHAN DATA</span>
<h1>Dari GRIB ke tabel yang siap dibaca.</h1>
<p>Pilih berkas atau folder, periksa cuplikan data, lalu unduh CSV dan Excel.
Lihat tren satu variabel melalui grafik yang mengikuti waktu sumber.</p></div>
""", unsafe_allow_html=True)
for column, text in zip(st.columns(4), ("01  Pilih data", "02  Periksa cuplikan",
                                       "03  Proses berkas", "04  Unduh hasil")):
    column.markdown(f'<div class="grib-step">{text}</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Satu alur, dua format")
    st.write("CSV untuk pertukaran data. Excel untuk membaca tabel dengan mudah.")
    st.markdown("**Mulai di sini**\n\n1. Pilih sumber dan berkas.\n2. Lihat cuplikan sebelum memproses.\n3. Unduh hasil yang berhasil.")
    st.divider()
    st.caption("Data dibaca oleh aplikasi pada komputer ini. Berkas sumber tidak ditimpa; hasil siap diunduh selama sesi ini.")
    st.caption("Grafik bersifat opsional. Satuan mengikuti metadata berkas, tanpa konversi atau asumsi zona waktu.")

sources = []
with st.container(border=True):
    st.subheader("1. Pilih sumber data")
    mode = st.radio("Cara memasukkan data", ["Unggah berkas", "Unggah folder", "Folder lokal"],
                    horizontal=True, key="input_mode")
    context = mode
    if mode in ("Unggah berkas", "Unggah folder"):
        directory_mode = mode == "Unggah folder"
        uploads = st.file_uploader("Pilih folder GRIB" if directory_mode else "Pilih berkas GRIB",
                                   type=["grib", "grb", "grib2", "grb2"],
                                   accept_multiple_files="directory" if directory_mode else True,
                                   key="folder_upload" if directory_mode else "file_upload")
        st.caption("Batas unggahan: 200 MB per berkas. Untuk file lebih besar, gunakan Folder lokal. Folder diunggah beserta subfoldernya.")
        try:
            sources = uploaded_sources(uploads or [])
        except ValueError as exc:
            st.error(str(exc))
    else:
        folder = st.text_input("Lokasi folder GRIB", value=str(Path("data").resolve()),
                               help="Alamat folder di komputer yang menjalankan aplikasi, bukan alamat web.")
        recursive = st.checkbox("Sertakan subfolder", value=False)
        context = f"{mode}:{folder}:{recursive}"
        if st.button("Tampilkan berkas"):
            try:
                found = scan_folder(folder, recursive)
                st.session_state["local_listing"] = found
                st.session_state["local_context"] = context
                if not found:
                    st.warning("Tidak ada berkas GRIB pada folder ini. Periksa folder atau sertakan subfolder.")
            except (OSError, ValueError) as exc:
                st.session_state["local_listing"] = []
                st.session_state["local_context"] = context
                st.error(str(exc))
        if st.session_state.get("local_context") == context:
            for previous in st.session_state.get("local_listing", []):
                try:
                    sources.append(local_source(previous.path, previous.label))
                except (OSError, ValueError):
                    st.warning(f"{previous.label} sudah tidak tersedia; tampilkan ulang daftar.")
        st.caption("Folder lokal dibaca dari komputer aplikasi ini. Path dari Windows 'Copy as path' boleh ditempel dengan tanda kutip.")

    if sources:
        by_id = {source.identity: source for source in sources}
        selected_ids = st.multiselect("Berkas yang dipilih", list(by_id), default=list(by_id),
                                      format_func=lambda key: by_id[key].label,
                                      key=f"selected_{mode}")
        selected = [by_id[key] for key in selected_ids]
        st.caption(f"{len(selected)} berkas dipilih · {sum(s.size for s in selected) / (1024**2):.1f} MB")
    else:
        selected = []
    with st.expander("Filter lanjutan (opsional)"):
        st.write("Isi hanya jika Anda mengetahui kunci GRIB yang diperlukan. Kosong berarti membaca tanpa filter.")
        first, second = st.columns(2)
        data_type = first.text_input("dataType", placeholder="Contoh: an, fc, em, es")
        points = second.text_input("numberOfPoints", placeholder="Contoh: 1639")
    filters = {}
    valid_filters = True
    try:
        filters = filters_from_inputs(data_type, points)
    except ValueError as exc:
        valid_filters = False
        st.error(str(exc))
    signature = selection_signature(selected, filters, context + ("" if valid_filters else f":{data_type}:{points}"))
    changed = sync_session(st.session_state, signature)
    if changed and selected:
        st.caption("Pilihan terbaru siap dibaca. Cuplikan dan hasil sebelumnya telah diperbarui sesuai sumber/filter ini.")
    preview_column, process_column = st.columns(2)
    see_preview = preview_column.button("Lihat cuplikan", disabled=not selected or not valid_filters,
                                        width="stretch")
    process = process_column.button("Proses berkas terpilih", type="primary",
                                     disabled=not selected or not valid_filters, width="stretch")

if see_preview or process:
    action = "Membaca cuplikan" if see_preview else "Memproses berkas"
    with st.status(action, expanded=True) as status:
        def report_progress(outcome):
            status.write(f"{'Selesai' if outcome.error is None else 'Perlu diperiksa'} · {outcome.source.label}")
        if see_preview:
            st.session_state["previews"] = preview_batch(selected, filters, report_progress)
        else:
            st.session_state["results"] = process_batch(
                selected, filters, st.session_state.get("previews", []), report_progress)
        status.update(label="Pembacaan cuplikan selesai" if see_preview else "Pemrosesan selesai",
                      state="complete", expanded=False)

outcomes = st.session_state.get("results") or st.session_state.get("previews") or []
for outcome in outcomes:
    if outcome.error:
        st.error(f"{outcome.source.label}: {outcome.error}")
        with st.expander(f"Detail masalah · {outcome.source.label}"):
            st.code(outcome.technical_error, language=None)
successful = [outcome for outcome in outcomes if outcome.error is None]
exported = [outcome for outcome in st.session_state.get("results", []) if outcome.error is None]

if exported:
    with st.container(border=True):
        st.subheader("Unduh hasil")
        st.success(f"{len(exported)} dari {len(st.session_state['results'])} berkas berhasil diproses.")
        for outcome in exported:
            st.markdown(f"**{outcome.source.label}** · {len(outcome.frame):,} baris")
            csv_column, excel_column = st.columns(2)
            csv_column.download_button("Unduh CSV", outcome.csv_bytes, outcome.csv_name,
                                       "text/csv", key=f"csv_{outcome.source.identity}", on_click="ignore")
            excel_column.download_button("Unduh Excel", outcome.xlsx_bytes, outcome.xlsx_name,
                                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                         key=f"xlsx_{outcome.source.identity}", on_click="ignore")
        st.download_button("Unduh semua hasil (ZIP)", results_zip(exported), "hasil-grib.zip",
                           "application/zip", on_click="ignore", type="primary")
        st.caption("ZIP memberi folder unik untuk setiap sumber, termasuk berkas yang memiliki nama sama.")

if successful:
    with st.container(border=True):
        st.subheader("Periksa data")
        available = {outcome.source.identity: outcome for outcome in successful}
        chosen = st.selectbox("Berkas untuk diperiksa", list(available),
                              format_func=lambda key: available[key].source.label)
        outcome = available[chosen]
        frame, metadata = outcome.frame, outcome.metadata
        rows, variables, missing = st.columns(3)
        rows.metric("Baris data", f"{len(frame):,}")
        variables.metric("Variabel", len(metadata["variables"]))
        missing.metric("Nilai kosong", sum(metadata["missing"].values()))
        st.caption(f"Titik terakhir: latitude {metadata['latitude']:g}, longitude {metadata['longitude']:g} · Jalur {metadata['route']}")
        st.write("Cuplikan 20 baris pertama. Nilai variabel ditampilkan dengan notasi ilmiah untuk menjaga angka sangat kecil terbaca.")
        st.dataframe(frame.head(20).style.format({name: "{:.9e}" for name in metadata["variables"]}),
                     hide_index=True, width="stretch")
        if metadata["route"] == "monthly":
            st.info("Tanggal ekspor adalah tanggal referensi. Kolom hour adalah durasi step dalam jam bulat dan bisa lebih dari 23.")
        else:
            st.caption("Tanggal dan hour ekspor berasal dari waktu referensi time. Zona waktu tidak diasumsikan.")
        if st.checkbox("Lihat grafik", key="show_plot"):
            variable = st.selectbox("Variabel grafik", metadata["variables"], key=f"variable_{chosen}")
            reference = None
            count = len(frame)
            if metadata["route"] == "monthly":
                references = list(pd.to_datetime(metadata["time"]).unique())
                reference = st.selectbox("Waktu referensi", references,
                                          format_func=lambda value: str(value), key=f"reference_{chosen}")
                count = int((pd.to_datetime(metadata["reference_time"]) == reference).sum())
            row_range = (0, count - 1)
            if count > 1:
                row_range = st.slider("Rentang baris grafik", 1, count, (1, count), key=f"range_{chosen}_{reference}")
                row_range = (row_range[0] - 1, row_range[1] - 1)
            data, kind, recommendation = plot_data(frame, metadata, variable, reference, row_range)
            st.write(f"**Rekomendasi:** {recommendation}")
            unit = metadata["units"].get(variable)
            st.caption(f"Satuan sumber: {unit or 'tidak tersedia pada metadata'}. Grafik tidak mengubah data unduhan.")
            if len(data) > 5000:
                st.info("Rentang ini memiliki lebih dari 5.000 titik. Persempit rentang baris untuk melihat semua titik tanpa downsampling.")
            else:
                chart = alt.Chart(data)
                x = alt.X("x:Q", title="Durasi step (jam)") if metadata["route"] == "monthly" else alt.X("x:T", title="Waktu referensi")
                encoding = dict(x=x, y=alt.Y("value:Q", title=f"{variable} ({unit})" if unit else variable),
                                tooltip=[x, alt.Tooltip("value:Q", format=".9e")])
                if kind == "line":
                    chart = chart.mark_line(point=True, color="#167f80").encode(
                        **encoding, detail="segment:N", order="order:Q")
                else:
                    chart = chart.mark_circle(color="#167f80", size=45).encode(**encoding)
                st.altair_chart(chart.properties(height=320), width="stretch")
                st.caption(f"{len(data):,} baris/titik pada rentang ini; nilai kosong tidak dihubungkan oleh garis.")
else:
    st.info("Pilih sumber data, lalu klik Lihat cuplikan atau Proses berkas terpilih untuk memulai.")
