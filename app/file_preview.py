"""Shared "submitted files" preview widget for admin and applicant views.

Fetches the raw-file manifest + bytes through the backend (never touches
disk/src directly - see app/api_client.py module docstring) and renders an
inline preview for images/text/PDF, with a download button for everything else.
"""
from __future__ import annotations

import base64

import streamlit as st
import streamlit.components.v1 as components

from app.api_client import BackendClient, BackendError

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
_TEXT_EXTENSIONS = {".txt", ".csv"}


def _extension(filename: str) -> str:
    return f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else ""


def render_submitted_files(client: BackendClient, submission_id: int) -> None:
    """Renders a "Submitted files" expander with previews for a submission's raw uploads."""
    try:
        files = client.list_submission_files(submission_id)
    except BackendError as exc:
        st.caption(f"Could not load submitted files: {exc}")
        return
    if not files:
        return

    with st.expander(f"📎 Submitted files ({len(files)})"):
        for entry in files:
            index, filename, size = entry["index"], entry["filename"], entry.get("size", 0)
            ext = _extension(filename)
            st.markdown(f"**{filename}** ({size:,} bytes)")

            auto_preview = ext in _IMAGE_EXTENSIONS or ext in _TEXT_EXTENSIONS
            want_pdf_preview = ext == ".pdf" and st.toggle(
                "Preview PDF", key=f"pdf_preview_{submission_id}_{index}"
            )
            loaded_key = f"loaded_{submission_id}_{index}"
            if not (auto_preview or want_pdf_preview):
                if st.button("👁️ Load / download", key=f"load_{submission_id}_{index}"):
                    st.session_state[loaded_key] = True
                if not st.session_state.get(loaded_key):
                    continue

            try:
                content = client.get_submission_file(submission_id, index)
            except BackendError as exc:
                st.caption(f"Could not load file: {exc}")
                continue

            if ext in _IMAGE_EXTENSIONS:
                st.image(content)
            elif ext in _TEXT_EXTENSIONS:
                st.text(content.decode("utf-8", errors="replace"))
            elif want_pdf_preview:
                b64 = base64.b64encode(content).decode()
                components.html(
                    f'<embed src="data:application/pdf;base64,{b64}" '
                    'width="100%" height="600" type="application/pdf" />',
                    height=620,
                )
            st.download_button(
                "⬇️ Download",
                content,
                file_name=filename,
                key=f"dl_{submission_id}_{index}",
            )

