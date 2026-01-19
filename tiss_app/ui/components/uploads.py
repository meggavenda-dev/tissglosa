
# -*- coding: utf-8 -*-
"""
ui/components/uploads.py
Componentes de upload isolados por contexto (Conciliação / Glosas XLSX).
"""

from __future__ import annotations

from typing import List, Tuple, Optional
import streamlit as st


def uploads_conciliation() -> Tuple[Optional[list], Optional[list]]:
    """
    Renderiza os uploads de XML e Demonstrativo para a aba de Conciliação.
    Retorna (xml_files, demo_files).
    """
    st.subheader("📤 Upload de arquivos")
    xml_files = st.file_uploader(
        "XML TISS (um ou mais):", type=['xml'], accept_multiple_files=True, key="xml_up"
    )
    demo_files = st.file_uploader(
        "Demonstrativos de Pagamento (.xlsx) — itemizado:", type=['xlsx'], accept_multiple_files=True, key="demo_up"
    )
    return xml_files, demo_files


def uploads_glosas() -> Optional[list]:
    """
    Renderiza o upload de relatórios de Faturas Glosadas para a aba específica.
    Retorna a lista de arquivos.
    """
    glosas_files = st.file_uploader(
        "Relatórios de Faturas Glosadas (.xlsx):",
        type=["xlsx"],
        accept_multiple_files=True,
        key="glosas_xlsx_up"
    )
    return glosas_files
