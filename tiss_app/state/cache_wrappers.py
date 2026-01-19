
# -*- coding: utf-8 -*-
"""
state/cache_wrappers.py
Wrappers cacheados (@st.cache_data) para centralizar e isolar recomputações.

Objetivos:
- Manter nomes já usados no app original (e.g. _cached_read_excel, _cached_xml_bytes).
- Oferecer funções cacheadas de alto nível para build_demo_df, build_xml_df e conciliar_itens,
  SEM alterar nenhuma lógica do core. Apenas delegamos a chamada.

Observações:
- Evitamos dependências circulares importando funções do core DENTRO dos wrappers, quando necessário.
- Mesmo que algum core já tenha cache interno (ex.: read_glosas_xlsx), manter um wrapper unifica a chamada.
"""

from __future__ import annotations

from typing import List, Dict, Tuple
from io import BytesIO

import pandas as pd
import streamlit as st


# -----------------------------------------
# Caches básicos (mesmos nomes do app original)
# -----------------------------------------
@st.cache_data(show_spinner=False)
def _cached_read_excel(file, sheet_name=0) -> pd.DataFrame:
    """
    Leitura cacheada de planilhas Excel.
    Mantém o NOME original usado no app para máxima compatibilidade.
    """
    return pd.read_excel(file, sheet_name=sheet_name, engine="openpyxl")


@st.cache_data(show_spinner=False)
def _cached_xml_bytes(b: bytes) -> List[Dict]:
    """
    Converte bytes de XML → lista de itens (via parse_itens_tiss_xml), com cache.
    Mantém o NOME original usado no app para máxima compatibilidade.
    """
    from tiss_app.core.xml_parser import parse_itens_tiss_xml
    return parse_itens_tiss_xml(BytesIO(b))


# -----------------------------------------
# Caches de alto nível (domínio)
# -----------------------------------------
@st.cache_data(show_spinner=False)
def cached_build_demo_df(demo_files, strip_zeros_codes: bool = False) -> pd.DataFrame:
    """
    Wrapper cacheado para build_demo_df (core.demo_parser).
    Não altera lógica interna; apenas evita recomputação em reruns.
    """
    from tiss_app.core.demo_parser import build_demo_df
    return build_demo_df(demo_files, strip_zeros_codes=strip_zeros_codes)


@st.cache_data(show_spinner=False)
def cached_build_xml_df(xml_files, strip_zeros_codes: bool = False) -> pd.DataFrame:
    """
    Wrapper cacheado para build_xml_df (core.conciliation_engine).
    Não altera lógica interna; apenas evita recomputação em reruns.
    """
    from tiss_app.core.conciliation_engine import build_xml_df
    return build_xml_df(xml_files, strip_zeros_codes=strip_zeros_codes)


@st.cache_data(show_spinner=False)
def cached_conciliar(df_xml: pd.DataFrame,
                     df_demo: pd.DataFrame,
                     tolerance_valor: float = 0.02,
                     fallback_por_descricao: bool = False) -> Dict[str, pd.DataFrame]:
    """
    Wrapper cacheado para conciliar_itens (core.conciliation_engine).
    Não altera lógica interna; apenas evita recomputação em reruns.
    """
    from tiss_app.core.conciliation_engine import conciliar_itens
    return conciliar_itens(
        df_xml=df_xml,
        df_demo=df_demo,
        tolerance_valor=float(tolerance_valor),
        fallback_por_descricao=bool(fallback_por_descricao),
    )


@st.cache_data(show_spinner=False)
def cached_read_glosas_xlsx(files) -> Tuple[pd.DataFrame, dict]:
    """
    Wrapper cacheado para read_glosas_xlsx (core.glosas_reader).
    Observação: a função no core já possui @st.cache_data, mas manter este wrapper
    padroniza o consumo na camada de UI e centraliza políticas de cache.
    """
    from tiss_app.core.glosas_reader import read_glosas_xlsx
    return read_glosas_xlsx(files)

