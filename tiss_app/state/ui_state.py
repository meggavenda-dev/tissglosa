
# -*- coding: utf-8 -*-
"""
state/ui_state.py
Inicialização, utilitários e operações de estado da UI (session_state).

Objetivo:
- Centralizar a criação de chaves de UI (toggles/flags) com valores padrão,
  sem executar processamento.
- Fornecer funções helper para abrir/fechar seções (short-circuit),
  limpar estados e gerar assinaturas estáveis de uploads.

IMPORTANTE:
- Não há lógica de negócio/processamento aqui.
- Use estes helpers nas views para evitar recomputações desnecessárias.
"""

from __future__ import annotations

from typing import Optional, Iterable, Tuple
import streamlit as st


# -----------------------------
# Inicialização de estado
# -----------------------------
def init_ui_state() -> None:
    """
    Garante que todas as chaves de UI existam no session_state.
    Chame isso no início do app (após set_page_config).
    """
    # Seções/visibilidade
    st.session_state.setdefault("ui_amhptiss_aberto", False)
    st.session_state.setdefault("ui_detalhes_aberto", False)

    # Seleção de item (Top Itens com glosa)
    st.session_state.setdefault("top_itens_editor_selected", None)   # string com a descrição
    st.session_state.setdefault("top_itens_editor_version", 0)       # bump para forçar rerender do editor

    # AMHP busca
    st.session_state.setdefault("amhp_query", "")
    st.session_state.setdefault("amhp_result", None)

    # Glosas (leitura XLSX) — processamento/diagnóstico
    st.session_state.setdefault("glosas_ready", False)
    st.session_state.setdefault("glosas_data", None)
    st.session_state.setdefault("glosas_colmap", None)
    st.session_state.setdefault("glosas_files_sig", None)

    # Wizard/mapeamentos de demonstrativo são tratados em core/demo_parser.build_demo_df
    # (lá fazemos .setdefault("demo_mappings", load_demo_mappings()))


# -----------------------------
# Helpers de visibilidade (short-circuit)
# -----------------------------
def open_amhptiss() -> None:
    """Abre a seção de busca AMHPTISS (somente altera estado)."""
    st.session_state["ui_amhptiss_aberto"] = True


def close_amhptiss() -> None:
    """Fecha a seção de busca AMHPTISS (somente altera estado)."""
    st.session_state["ui_amhptiss_aberto"] = False


def is_amhptiss_open() -> bool:
    """Retorna True se a seção AMHPTISS estiver visível."""
    return bool(st.session_state.get("ui_amhptiss_aberto", False))


def open_detalhes() -> None:
    """Abre a seção de detalhes de item."""
    st.session_state["ui_detalhes_aberto"] = True


def close_detalhes() -> None:
    """Fecha a seção de detalhes de item."""
    st.session_state["ui_detalhes_aberto"] = False


def is_detalhes_open() -> bool:
    """Retorna True se a seção de detalhes estiver visível."""
    return bool(st.session_state.get("ui_detalhes_aberto", False))


# -----------------------------
# Helpers específicos (Glosas XLSX)
# -----------------------------
def files_signature(files: Optional[Iterable]) -> Optional[Tuple]:
    """
    Gera uma assinatura estável (nome, tamanho) para uma lista de arquivos de upload.
    Útil para detectar se os arquivos mudaram.
    """
    if not files:
        return None
    return tuple(sorted((getattr(f, "name", ""), getattr(f, "size", 0)) for f in files))


def clear_glosas_state() -> None:
    """
    Reseta completamente o estado do bloco 'Faturas Glosadas'.
    Use em botões do tipo 'Limpar/Resetar'.
    """
    st.session_state["glosas_ready"] = False
    st.session_state["glosas_data"] = None
    st.session_state["glosas_colmap"] = None
    st.session_state["glosas_files_sig"] = None


# -----------------------------
# Helpers genéricos
# -----------------------------
def set_flag(key: str, value: bool) -> None:
    """Define uma flag booleana arbitrária no session_state."""
    st.session_state[key] = bool(value)


def bump_key(key: str) -> None:
    """
    Incrementa um contador (útil para forçar rerender de componentes com 'key').
    """
    st.session_state[key] = int(st.session_state.get(key, 0)) + 1

