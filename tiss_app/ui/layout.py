
# -*- coding: utf-8 -*-
"""
ui/layout.py
Layout global (config da página, título/caption), sidebar de parâmetros
e criação das abas.

A UI não processa dados aqui — somente coleta parâmetros e retorna objetos
para as views consumirem.

Ajustes:
- Sidebar sempre colapsada em todo carregamento e a cada rerun (sem desativar o botão "☰").
"""

from __future__ import annotations

from typing import Tuple
import streamlit as st
import streamlit.components.v1 as components


def _force_sidebar_collapsed() -> None:
    """
    Assegura que a sidebar permaneça colapsada em todo rerun.
    Não remove a sidebar; apenas 'clica' no controle de colapsar se ela estiver aberta.
    Isso preserva o comportamento do botão ☰ para o usuário.
    """
    components.html(
        """
        <script>
        (function() {
          const tryCollapse = () => {
            const doc = window.parent.document;
            // Sidebar e botão do header/collapse
            const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
            // Botão de toggle: nas versões recentes do Streamlit, um destes seletores funciona
            const toggleBtn =
              doc.querySelector('[data-testid="collapsedControl"]') ||
              doc.querySelector('button[kind="header"]') ||
              doc.querySelector('button[title="Menu"]');

            if (!sidebar || !toggleBtn) return false;

            // Heurística para detectar se está expandida:
            // 1) largura visível
            // 2) presença/ausência do atributo 'aria-expanded' (varia entre versões)
            const isVisible = sidebar.offsetWidth > 0 && sidebar.getBoundingClientRect().width > 0;
            const aria = sidebar.getAttribute('aria-expanded');
            const expanded = (aria === null) ? isVisible : (aria === "true" || aria === "True");

            if (expanded) {
              toggleBtn.click(); // recolhe
            }
            return true;
          };

          // Tenta por alguns ciclos para pegar o momento em que o DOM do app terminou de montar
          let tries = 0;
          const timer = setInterval(() => {
            const ok = tryCollapse();
            if (ok || ++tries > 40) {
              clearInterval(timer);
            }
          }, 75);
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def setup_page() -> None:
    """Configura a página e exibe título/caption."""
    st.set_page_config(
        page_title="TISS • Conciliação & Analytics",
        layout="wide",
        initial_sidebar_state="collapsed"  # Início sempre colapsado no primeiro load
    )

    # Garante colapso também em todo rerun
    _force_sidebar_collapsed()

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
