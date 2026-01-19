
# -*- coding: utf-8 -*-
"""
app.py
Orquestrador principal do aplicativo TISS.

Funções:
- Configura página (layout.setup_page)
- Inicializa estado (ui_state.init_ui_state)
- Carrega parâmetros e cria abas
- Direciona cada aba para sua respectiva view
- Sem lógica pesada aqui — apenas UI reativa

A arquitetura completa está modularizada em:
  core/    → lógica de negócio e parsing
  state/   → caches e estado da interface
  ui/      → views e componentes visuais
"""

from __future__ import annotations

import streamlit as st

# Layout global (título, caption, sidebar, abas)
from tiss_app.ui.layout import setup_page, sidebar_params, build_tabs

# Inicialização de estado da UI
from tiss_app.state.ui_state import init_ui_state

# Views completas
from tiss_app.ui.conciliation_view import render_conciliation_tab
from tiss_app.ui.glosas_view import render_glosas_tab


# ---------------------------------------------------------
# INÍCIO DO APLICATIVO
# ---------------------------------------------------------

# 1. Configura página
setup_page()

# 2. Inicializa todos os estados de UI (idempotente)
init_ui_state()

# 3. Parâmetros da sidebar
params = sidebar_params()

# 4. Constrói abas principais
tab_conc, tab_glosas = build_tabs()


# ---------------------------------------------------------
# ABA 1 — CONCILIAÇÃO TISS
# ---------------------------------------------------------
with tab_conc:
    render_conciliation_tab(params)


# ---------------------------------------------------------
# ABA 2 — FATURAS GLOSADAS (XLSX)
# ---------------------------------------------------------
with tab_glosas:
    render_glosas_tab()

