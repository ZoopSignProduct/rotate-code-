import io
import base64
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
#  Custom CSS
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
h2 { font-family: 'Space Mono', monospace !important; color: #e8e4dc !important; font-size: 1.1rem !important; letter-spacing: 0.05em !important; text-transform: uppercase; }
h3 { font-family: 'DM Sans', sans-serif !important; color: #a8a39a !important; font-weight: 400 !important; font-size: 0.9rem !important; }

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
.stWarning { background: #2b1a0d !important; border-left: 3px solid #e67e22 !important; }
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
    font-size: 0.72rem;
    color: #a8a39a;
    line-height: 1.8;
}
.flow-box span.highlight { color: #f0c040; font-weight: 700; }
.rot-tag {
    display: inline-block;
    background: #f0c040;
    color: #0f0f0f;
    font-family: 'Space Mono', monospace;
    font-size: 0.6rem;
    font-weight: 700;
    padding: 1px 5px;
    border-radius: 2px;
    margin-left: 4px;
    vertical-align: middle;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────
def pdf_page_to_image(pdf_bytes: bytes, page_index: int, width: int = 400):
    """Render a single PDF page to a PIL-compatible bytes object."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_index]
    zoom = width / page.rect.width
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes


def rotate_pdf_bytes(pdf_bytes: bytes, rotation_map: dict) -> bytes:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        deg = rotation_map.get(i, 0)
        if deg:
            page.rotate(deg)
        writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def merge_pdfs(
    folder1_files: dict,
    folder2_bytes: bytes,
    page_ranges: dict = None,
    interleave_after: int = 4,
) -> bytes:
    """
    Merge pattern:
      - First `interleave_after` pages of F1 go straight through
      - From page (interleave_after + 1) onwards: each F1 page is followed by F2's single page

    Example with interleave_after=4:
      F1p1, F1p2, F1p3, F1p4, F2p1, F1p5, F2p1, F1p6, F2p1, ...
    """
    writer = PdfWriter()
    for fname, f1_bytes in folder1_files.items():
        r1 = PdfReader(io.BytesIO(f1_bytes))
        all_pages = list(r1.pages)
        if page_ranges and fname in page_ranges:
            start, end = page_ranges[fname]
            pages = all_pages[start:end]
        else:
            pages = all_pages
        for i, p in enumerate(pages):
            writer.add_page(p)
            if i >= interleave_after - 1:
                f2_r = PdfReader(io.BytesIO(folder2_bytes))
                writer.add_page(f2_r.pages[0])
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
    ("folder2_bytes", None),
    ("folder2_name", ""),
    ("rotations_f1", {}),
    ("rotations_f2", {}),
    ("page_ranges_f1", {}),
    ("interleave_after", 4),
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

    # Folder 1
    st.markdown("### Folder 1")
    f1_uploads = st.file_uploader(
        "folder1",
        type="pdf",
        accept_multiple_files=True,
        key="f1_upload",
        label_visibility="collapsed",
    )
    if f1_uploads:
        for uf in f1_uploads:
            if uf.name not in st.session_state.folder1_files:
                st.session_state.folder1_files[uf.name] = uf.read()
                st.session_state.rotations_f1[uf.name] = {}
    if st.session_state.folder1_files:
        n_f1 = len(st.session_state.folder1_files)
        st.caption(f"✅ {n_f1} file(s) loaded")
        if st.button("🗑 Clear Folder 1", use_container_width=True, key="clear_f1"):
            st.session_state.folder1_files = {}
            st.session_state.rotations_f1 = {}
            st.session_state.page_ranges_f1 = {}
            st.rerun()

    st.markdown("---")

    # Folder 2
    st.markdown("### Folder 2 — single page")
    f2_upload = st.file_uploader(
        "folder2",
        type="pdf",
        key="f2_upload",
        label_visibility="collapsed",
    )
    if f2_upload:
        st.session_state.folder2_bytes = f2_upload.read()
        st.session_state.folder2_name = f2_upload.name
        st.session_state.rotations_f2 = {}
    if st.session_state.folder2_bytes:
        st.caption(f"✅ {st.session_state.folder2_name}")
        if st.button("🗑 Clear Folder 2", use_container_width=True, key="clear_f2"):
            st.session_state.folder2_bytes = None
            st.session_state.folder2_name = ""
            st.session_state.rotations_f2 = {}
            st.rerun()

    st.markdown("---")

    # Merge settings
    st.markdown("### Merge Settings")
    st.session_state.interleave_after = st.number_input(
        "Insert Folder 2 page after every N pages from Folder 1",
        min_value=1,
        value=st.session_state.interleave_after,
        step=1,
        key="interleave_input",
        help="First N pages of each Folder 1 file go straight through, then Folder 2 page is inserted after every subsequent Folder 1 page.",
    )

    # Live flow preview
    n = st.session_state.interleave_after
    flow_pages = [f"F1·p{i+1}" for i in range(n)] + ["<span class='highlight'>F2</span>", f"F1·p{n+1}", "<span class='highlight'>F2</span>", f"F1·p{n+2}", "<span class='highlight'>F2</span>", "…"]
    st.markdown(
        "<div class='flow-box'>" + " → ".join(flow_pages) + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    ready = bool(st.session_state.folder1_files) and bool(st.session_state.folder2_bytes)
    if ready:
        if st.button("⚡ MERGE NOW", use_container_width=True, key="merge_btn"):
            with st.spinner("Merging…"):
                processed_f1 = {}
                for fname, fbytes in st.session_state.folder1_files.items():
                    rmap = st.session_state.rotations_f1.get(fname, {})
                    processed_f1[fname] = rotate_pdf_bytes(fbytes, rmap)
                f2 = rotate_pdf_bytes(
                    st.session_state.folder2_bytes,
                    st.session_state.rotations_f2,
                )
                st.session_state.merged_bytes = merge_pdfs(
                    processed_f1,
                    f2,
                    st.session_state.page_ranges_f1,
                    st.session_state.interleave_after,
                )
            st.success("Done!")
    else:
        st.info("Upload files in both folders to merge.")


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
    if not st.session_state.folder1_files and not st.session_state.folder2_bytes:
        st.markdown(
            "<div style='text-align:center;padding:80px 0;color:#3a3a3a;"
            "font-family:Space Mono,monospace;font-size:0.9rem;letter-spacing:0.1em;'>"
            "📄<br><br>UPLOAD PDFs IN THE SIDEBAR TO BEGIN</div>",
            unsafe_allow_html=True,
        )
    else:
        subtab_labels = []
        if st.session_state.folder1_files:
            subtab_labels.append("📂 Folder 1")
        if st.session_state.folder2_bytes:
            subtab_labels.append("📂 Folder 2")

        subtabs = st.tabs(subtab_labels)
        idx = 0

        # ── Folder 1 ──
        if st.session_state.folder1_files:
            with subtabs[idx]:
                idx += 1
                file_list = sorted(st.session_state.folder1_files.keys())
                selected_file = st.selectbox(
                    "Select PDF",
                    file_list,
                    key="f1_select",
                    label_visibility="collapsed",
                )

                if selected_file:
                    pdf_bytes = st.session_state.folder1_files[selected_file]
                    n_pages = get_page_count(pdf_bytes)
                    rmap = st.session_state.rotations_f1.get(selected_file, {})

                    # File info + page range row
                    info_col, range_col = st.columns([2, 3])
                    with info_col:
                        st.markdown(f"**{selected_file}** — {n_pages} page(s)")
                        cur_range = st.session_state.page_ranges_f1.get(selected_file)
                        if cur_range:
                            st.caption(f"Merge range: pages {cur_range[0]+1}–{cur_range[1]}")
                        else:
                            st.caption("Merge range: all pages")

                    with range_col:
                        pr_default_start = cur_range[0] + 1 if cur_range else 1
                        pr_default_end = cur_range[1] if cur_range else n_pages
                        rc1, rc2, rc3, rc4 = st.columns([1, 1, 1, 1])
                        pr_start = rc1.number_input("From", 1, n_pages, pr_default_start, key=f"pr_s_{selected_file}", label_visibility="visible")
                        pr_end   = rc2.number_input("To",   1, n_pages, pr_default_end,   key=f"pr_e_{selected_file}", label_visibility="visible")
                        rc3.markdown("&nbsp;", unsafe_allow_html=True)
                        if rc3.button("Set range", key=f"pr_set_{selected_file}"):
                            if pr_start <= pr_end:
                                st.session_state.page_ranges_f1[selected_file] = (pr_start - 1, pr_end)
                                st.rerun()
                            else:
                                st.error("From must be ≤ To")
                        if rc4.button("All pages", key=f"pr_rst_{selected_file}"):
                            st.session_state.page_ranges_f1.pop(selected_file, None)
                            st.rerun()

                    st.markdown("---")

                    # Preview + controls
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
                        if rmap:
                            for pg, deg in sorted(rmap.items()):
                                if deg:
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
                        img = pdf_page_to_image(preview_bytes, page_num, width=480)
                        caption = f"Page {page_num+1} of {n_pages}"
                        if cur_rot:
                            caption += f"  ·  {cur_rot}° rotated"
                        st.image(img, caption=caption, use_container_width=True)

        # ── Folder 2 ──
        if st.session_state.folder2_bytes:
            with subtabs[idx]:
                pdf_bytes = st.session_state.folder2_bytes
                n_pages = get_page_count(pdf_bytes)
                rmap = st.session_state.rotations_f2

                st.markdown(f"**{st.session_state.folder2_name}** — {n_pages} page(s)")
                st.markdown("---")

                col_img, col_ctrl = st.columns([3, 2])

                with col_ctrl:
                    page_num = st.number_input(
                        "Page to preview",
                        min_value=1, max_value=n_pages, value=1, key="f2_page"
                    ) - 1

                    rotate_by = st.selectbox(
                        "Rotation",
                        [0, 90, 180, 270],
                        key="f2_rot_sel",
                        format_func=lambda x: f"{x}°",
                    )

                    b1, b2 = st.columns(2)
                    if b1.button("✓ Apply", key="f2_apply", use_container_width=True):
                        st.session_state.rotations_f2[page_num] = rotate_by
                        st.rerun()
                    if b2.button("↺ Reset", key="f2_reset", use_container_width=True):
                        st.session_state.rotations_f2.pop(page_num, None)
                        st.rerun()

                    st.markdown("---")
                    st.markdown("**Rotation map**")
                    if rmap:
                        for pg, deg in sorted(rmap.items()):
                            if deg:
                                st.markdown(
                                    f"<span style='font-family:Space Mono,monospace;font-size:0.8rem;'>"
                                    f"P{pg+1} → {deg}°</span>",
                                    unsafe_allow_html=True,
                                )
                        if st.button("🗑 Clear rotations", key="f2_clear_all", use_container_width=True):
                            st.session_state.rotations_f2 = {}
                            st.rerun()
                    else:
                        st.caption("No rotations applied.")

                with col_img:
                    cur_rot = rmap.get(page_num, 0)
                    preview_bytes = rotate_pdf_bytes(pdf_bytes, {page_num: cur_rot})
                    img = pdf_page_to_image(preview_bytes, page_num, width=480)
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
            file_name="final_output.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="download_btn",
        )

        st.markdown("---")
        st.markdown("#### Preview")

        page_preview = st.number_input(
            "Jump to page", min_value=1, max_value=total_pages, value=1, key="merged_page"
        ) - 1

        img = pdf_page_to_image(merged, page_preview, width=560)
        st.image(img, caption=f"Page {page_preview+1} of {total_pages}", use_container_width=False)
