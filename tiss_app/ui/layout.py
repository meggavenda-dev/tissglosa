
# -*- coding: utf-8 -*-
"""
ui/layout.py
Layout global (config da página, título/caption), sidebar de parâmetros
e criação das abas.

A UI não processa dados aqui — somente coleta parâmetros e retorna objetos
para as views consumirem.
"""

from __future__ import annotations

from typing import Tuple
import streamlit as st


def setup_page() -> None:
    """Configura a página e exibe título/caption."""
    st.set_page_config(page_title="TISS • Conciliação & Analytics", layout="wide")
    st.title("TISS — Itens por Guia (XML) + Conciliação com Demonstrativo + Analytics")
    st.caption(
        "Lê XML TISS (Consulta / SADT), concilia com Demonstrativo itemizado (AMHP), "
        "gera rankings e analytics — sem editor de XML. Auditoria mantida no código, porém desativada."
    )


def sidebar_params() -> dict:
    """
    Cria a seção de parâmetros na sidebar e retorna um dicionário com valores selecionados.
    Nada pesado aqui; apenas inputs.
    """
    params = {}
    with st.sidebar:
        with st.expander("⚙️ Parâmetros", expanded=False):
            params["prazo_retorno"] = st.number_input(
                "Prazo de retorno (dias) — (auditoria desativada)",
                min_value=0, value=30, step=1
            )
            params["tolerance_valor"] = st.number_input(
                "Tolerância p/ fallback por descrição (R$)",
                min_value=0.00, value=0.02, step=0.01, format="%.2f"
            )
            params["fallback_desc"] = st.toggle(
                "Fallback por descrição + valor (quando código não casar)", value=False
            )
            params["strip_zeros_codes"] = st.toggle(
                "Normalizar códigos removendo zeros à esquerda", value=True
            )
    return params


def build_tabs() -> Tuple:
    """Cria as abas principais e as retorna para que as views façam o render."""
    return st.tabs(["🔗 Conciliação TISS", "📑 Faturas Glosadas (XLSX)"])

