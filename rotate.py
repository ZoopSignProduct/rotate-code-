import io
import streamlit as st
from pypdf import PdfReader, PdfWriter
import fitz  # PyMuPDF

# ─────────────────────────────────────────────
#  Page Config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="PDF Merge Studio",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: #0f0f0f;
    color: #e8e4dc;
}
[data-testid="stSidebar"] {
    background: #161616;
    border-right: 1px solid #2a2a2a;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-family: 'Space Mono', monospace;
    color: #f0c040;
    letter-spacing: -0.02em;
}
h1 { font-family: 'Space Mono', monospace !important; color: #f0c040 !important; letter-spacing: -0.04em !important; }
h2 { font-family: 'Space Mono', monospace !important; color: #e8e4dc !important; font-size: 1.1rem !important; text-transform: uppercase; }

.stButton > button {
    background: #f0c040 !important;
    color: #0f0f0f !important;
    border: none !important;
    border-radius: 3px !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.06em !important;
    padding: 0.55rem 1.2rem !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover {
    background: #ffd060 !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(240,192,64,0.3) !important;
}
[data-testid="stFileUploader"] {
    border: 1px dashed #3a3a3a !important;
    border-radius: 6px !important;
    background: #161616 !important;
}
[data-testid="stMetricValue"] {
    font-family: 'Space Mono', monospace !important;
    color: #f0c040 !important;
}
[data-baseweb="tab-list"] {
    background: #161616 !important;
    border-bottom: 1px solid #2a2a2a !important;
    gap: 0 !important;
}
[data-baseweb="tab"] {
    font-family: 'Space Mono', monospace !important;
    font-size: 0.72rem !important;
    letter-spacing: 0.08em !important;
    color: #5a5a5a !important;
    border-bottom: 2px solid transparent !important;
    padding: 0.7rem 1.4rem !important;
}
[aria-selected="true"] {
    color: #f0c040 !important;
    border-bottom: 2px solid #f0c040 !important;
    background: transparent !important;
}
[data-baseweb="select"] > div,
[data-baseweb="input"] > div input {
    background: #1e1e1e !important;
    border-color: #2a2a2a !important;
    color: #e8e4dc !important;
    border-radius: 4px !important;
}
.stSuccess { background: #0d2b1a !important; border-left: 3px solid #2ea44f !important; }
.stInfo    { background: #0d1f2b !important; border-left: 3px solid #2980b9 !important; }
hr { border-color: #2a2a2a !important; }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0f0f0f; }
::-webkit-scrollbar-thumb { background: #3a3a3a; border-radius: 3px; }

.flow-box {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 12px 16px;
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    color: #a8a39a;
    line-height: 2;
}
.flow-box .sep { color: #f0c040; font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────
def render_page(pdf_bytes: bytes, page_idx: int, width: int = 460) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_idx]
    zoom = width / page.rect.width
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = pix.tobytes("png")
    doc.close()
    return img


def rotate_pdf_bytes(pdf_bytes: bytes, rotation_map: dict) -> bytes:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if rotation_map.get(i, 0):
            page.rotate(rotation_map[i])
        writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def extract_single_page(pdf_bytes: bytes, page_idx: int) -> bytes:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    writer.add_page(reader.pages[page_idx])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def merge_pdfs(
    folder1_files: dict,
    separator_bytes: bytes,
    page_ranges: dict = None,
    sep_file: str = None,
    sep_page_idx: int = None,
) -> bytes:
    """
    Strict 1:1 interleave, skipping the separator page itself from the F1 sequence:
      F1_p1 → SEP → F1_p2 → SEP → F1_p3 → SEP → …
    """
    writer = PdfWriter()
    for fname, f1_bytes in folder1_files.items():
        r1 = PdfReader(io.BytesIO(f1_bytes))
        all_pages = list(enumerate(r1.pages))
        if page_ranges and fname in page_ranges:
            start, end = page_ranges[fname]
            all_pages = [(i, p) for i, p in all_pages if start <= i < end]
        for i, p in all_pages:
            # Skip the page that was chosen as the separator
            if fname == sep_file and i == sep_page_idx:
                continue
            writer.add_page(p)
            sep_reader = PdfReader(io.BytesIO(separator_bytes))
            writer.add_page(sep_reader.pages[0])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def get_page_count(pdf_bytes: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)


# ─────────────────────────────────────────────
#  Session state
# ─────────────────────────────────────────────
for key, default in [
    ("folder1_files", {}),
    ("rotations_f1", {}),
    ("page_ranges_f1", {}),
    ("sep_file", None),
    ("sep_page_idx", 0),
    ("merged_bytes", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ─────────────────────────────────────────────
#  Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📁 PDF Merge Studio")
    st.markdown("---")

    # ── Folder 1 upload ──
    st.markdown("### Folder 1")
    uploads = st.file_uploader(
        "folder1",
        type="pdf",
        accept_multiple_files=True,
        key="f1_upload",
        label_visibility="collapsed",
    )
    if uploads:
        for uf in uploads:
            if uf.name not in st.session_state.folder1_files:
                st.session_state.folder1_files[uf.name] = uf.read()
                st.session_state.rotations_f1[uf.name] = {}

    if st.session_state.folder1_files:
        st.caption(f"✅ {len(st.session_state.folder1_files)} file(s) loaded")
        if st.button("🗑 Clear all", use_container_width=True, key="clear_f1"):
            for k in ("folder1_files", "rotations_f1", "page_ranges_f1"):
                st.session_state[k] = {}
            st.session_state.sep_file = None
            st.session_state.sep_page_idx = 0
            st.session_state.merged_bytes = None
            st.rerun()

    st.markdown("---")

    # ── Separator page picker ──
    st.markdown("### Separator Page")
    st.caption("This page will be inserted after every Folder 1 page in the merged PDF.")

    if st.session_state.folder1_files:
        file_list = sorted(st.session_state.folder1_files.keys())

        sep_file = st.selectbox(
            "File",
            file_list,
            index=file_list.index(st.session_state.sep_file)
                  if st.session_state.sep_file in file_list else 0,
            key="sep_file_sel",
        )
        sep_n_pages = get_page_count(st.session_state.folder1_files[sep_file])
        sep_page_num = st.number_input(
            "Page number",
            min_value=1,
            max_value=sep_n_pages,
            value=min(st.session_state.sep_page_idx + 1, sep_n_pages),
            key="sep_page_input",
        )
        st.session_state.sep_file = sep_file
        st.session_state.sep_page_idx = sep_page_num - 1

        # Preview of separator page
        sep_img = render_page(
            st.session_state.folder1_files[sep_file],
            st.session_state.sep_page_idx,
            width=220,
        )
        st.image(sep_img, caption=f"{sep_file} · page {sep_page_num}", use_container_width=True)

        st.markdown("---")
        st.markdown("**Merge pattern**")
        st.markdown(
            "<div class='flow-box'>"
            "F1·p1 → <span class='sep'>SEP</span> → "
            "F1·p2 → <span class='sep'>SEP</span> → "
            "F1·p3 → <span class='sep'>SEP</span> → …"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown("---")
        if st.button("⚡ MERGE NOW", use_container_width=True, key="merge_btn"):
            with st.spinner("Merging…"):
                processed_f1 = {}
                for fname, fbytes in st.session_state.folder1_files.items():
                    rmap = st.session_state.rotations_f1.get(fname, {})
                    processed_f1[fname] = rotate_pdf_bytes(fbytes, rmap)

                sep_bytes = extract_single_page(
                    processed_f1[st.session_state.sep_file],
                    st.session_state.sep_page_idx,
                )
                st.session_state.merged_bytes = merge_pdfs(
                    processed_f1,
                    sep_bytes,
                    st.session_state.page_ranges_f1,
                    sep_file=st.session_state.sep_file,
                    sep_page_idx=st.session_state.sep_page_idx,
                )
            st.success("Done!")
    else:
        st.info("Upload files in Folder 1 first.")


# ─────────────────────────────────────────────
#  Main area
# ─────────────────────────────────────────────
st.markdown("# PDF Merge Studio")
st.markdown("---")

TAB_PREVIEW, TAB_MERGE = st.tabs(["🔍  PREVIEW & ROTATE", "📦  MERGED OUTPUT"])

# ═══════════════════════════════════════════════
#  TAB 1 – Preview & Rotate
# ═══════════════════════════════════════════════
with TAB_PREVIEW:
    if not st.session_state.folder1_files:
        st.markdown(
            "<div style='text-align:center;padding:80px 0;color:#3a3a3a;"
            "font-family:Space Mono,monospace;font-size:0.9rem;letter-spacing:0.1em;'>"
            "📄<br><br>UPLOAD PDFs IN THE SIDEBAR TO BEGIN</div>",
            unsafe_allow_html=True,
        )
    else:
        file_list = sorted(st.session_state.folder1_files.keys())
        selected_file = st.selectbox(
            "Select PDF to preview / rotate",
            file_list,
            key="f1_select",
        )

        if selected_file:
            pdf_bytes = st.session_state.folder1_files[selected_file]
            n_pages = get_page_count(pdf_bytes)
            rmap = st.session_state.rotations_f1.get(selected_file, {})

            # File info + page range
            info_col, range_col = st.columns([2, 3])
            with info_col:
                st.markdown(f"**{selected_file}** — {n_pages} page(s)")
                cur_range = st.session_state.page_ranges_f1.get(selected_file)
                if cur_range:
                    st.caption(f"Merge range: pages {cur_range[0]+1}–{cur_range[1]}")
                else:
                    st.caption("Merge range: all pages")

            with range_col:
                pr_s = cur_range[0] + 1 if cur_range else 1
                pr_e = cur_range[1]     if cur_range else n_pages
                rc1, rc2, rc3, rc4 = st.columns(4)
                pr_start = rc1.number_input("From", 1, n_pages, pr_s, key=f"pr_s_{selected_file}")
                pr_end   = rc2.number_input("To",   1, n_pages, pr_e, key=f"pr_e_{selected_file}")
                if rc3.button("Set", key=f"pr_set_{selected_file}", use_container_width=True):
                    if pr_start <= pr_end:
                        st.session_state.page_ranges_f1[selected_file] = (pr_start - 1, pr_end)
                        st.rerun()
                    else:
                        st.error("From must be ≤ To")
                if rc4.button("Reset", key=f"pr_rst_{selected_file}", use_container_width=True):
                    st.session_state.page_ranges_f1.pop(selected_file, None)
                    st.rerun()

            st.markdown("---")

            col_img, col_ctrl = st.columns([3, 2])

            with col_ctrl:
                page_num = st.number_input(
                    "Page to preview",
                    min_value=1, max_value=n_pages, value=1, key="f1_page"
                ) - 1

                rotate_by = st.selectbox(
                    "Rotation",
                    [0, 90, 180, 270],
                    key="f1_rot_sel",
                    format_func=lambda x: f"{x}°",
                )

                b1, b2 = st.columns(2)
                if b1.button("✓ Apply", key="f1_apply", use_container_width=True):
                    st.session_state.rotations_f1[selected_file][page_num] = rotate_by
                    st.rerun()
                if b2.button("↺ Reset", key="f1_reset", use_container_width=True):
                    st.session_state.rotations_f1[selected_file].pop(page_num, None)
                    st.rerun()

                st.markdown("---")
                st.markdown("**Rotation map**")
                applied = {pg: deg for pg, deg in rmap.items() if deg}
                if applied:
                    for pg, deg in sorted(applied.items()):
                        st.markdown(
                            f"<span style='font-family:Space Mono,monospace;font-size:0.8rem;'>"
                            f"P{pg+1} → {deg}°</span>",
                            unsafe_allow_html=True,
                        )
                    if st.button("🗑 Clear rotations", key="f1_clear_all", use_container_width=True):
                        st.session_state.rotations_f1[selected_file] = {}
                        st.rerun()
                else:
                    st.caption("No rotations applied.")

            with col_img:
                cur_rot = rmap.get(page_num, 0)
                preview_bytes = rotate_pdf_bytes(pdf_bytes, {page_num: cur_rot})
                img = render_page(preview_bytes, page_num)
                caption = f"Page {page_num+1} of {n_pages}"
                if cur_rot:
                    caption += f"  ·  {cur_rot}° rotated"
                st.image(img, caption=caption, use_container_width=True)


# ═══════════════════════════════════════════════
#  TAB 2 – Merged Output
# ═══════════════════════════════════════════════
with TAB_MERGE:
    if st.session_state.merged_bytes is None:
        st.markdown(
            "<div style='text-align:center;padding:80px 0;color:#3a3a3a;"
            "font-family:Space Mono,monospace;font-size:0.9rem;letter-spacing:0.1em;'>"
            "⚡<br><br>HIT \"MERGE NOW\" IN THE SIDEBAR</div>",
            unsafe_allow_html=True,
        )
    else:
        merged = st.session_state.merged_bytes
        total_pages = get_page_count(merged)

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Total Pages", total_pages)
        mc2.metric("File Size", f"{len(merged)/1024:.1f} KB")
        mc3.metric("Source PDFs", len(st.session_state.folder1_files))

        st.markdown("---")

        st.download_button(
            label="⬇ DOWNLOAD MERGED PDF",
            data=merged,
            file_name="merged_output.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="download_btn",
        )

        st.markdown("---")
        st.markdown("#### Preview merged pages")

        page_preview = st.number_input(
            "Jump to page", min_value=1, max_value=total_pages, value=1, key="merged_page"
        ) - 1

        img = render_page(merged, page_preview, width=560)
        st.image(img, caption=f"Page {page_preview+1} of {total_pages}")
