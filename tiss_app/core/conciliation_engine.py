
# -*- coding: utf-8 -*-
"""
core/conciliation_engine.py
Construção de DFs a partir de XML e conciliação com Demonstrativo.

Funções copiadas do original (sem alteração de lógica):
- build_xml_df
- _XML_CORE_COLS
- _alias_xml_cols
- conciliar_itens
"""

from __future__ import annotations

from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np

from .utils import normalize_code
from .xml_parser import parse_itens_tiss_xml
# As versões cacheadas de leitura de XML por bytes ficam em state/cache_wrappers.py
# e devem ser importadas pela camada de UI (para evitar dependência circular).


def build_xml_df(xml_files, strip_zeros_codes: bool = False) -> pd.DataFrame:
    linhas: List[Dict] = []
    # Import tardio para evitar dependência direta aqui
    try:
        from tiss_app.state.cache_wrappers import _cached_xml_bytes  # mantém o nome original
        _have_cache = True
    except Exception:
        _have_cache = False
        _cached_xml_bytes = None

    for f in xml_files:
        if hasattr(f, 'seek'):
            f.seek(0)
        try:
            if hasattr(f, 'read'):
                bts = f.read()
                if _have_cache and _cached_xml_bytes is not None:
                    linhas.extend(_cached_xml_bytes(bts))
                else:
                    # fallback sem cache
                    from io import BytesIO
                    linhas.extend(parse_itens_tiss_xml(BytesIO(bts)))
            else:
                linhas.extend(parse_itens_tiss_xml(f))
        except Exception as e:
            linhas.append({'arquivo': getattr(f, 'name', 'upload.xml'), 'erro': str(e)})

    df = pd.DataFrame(linhas)
    if df.empty:
        return df

    for c in ['quantidade', 'valor_unitario', 'valor_total']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    df['codigo_procedimento_norm'] = df['codigo_procedimento'].astype(str).map(
        lambda s: normalize_code(s, strip_zeros=strip_zeros_codes)
    )
    df['chave_prest'] = (df['numeroGuiaPrestador'].fillna('').astype(str).str.strip()
                        + '__' + df['codigo_procedimento_norm'].fillna('').astype(str).str.strip())

    df['chave_oper'] = (
        df['numeroGuiaOperadora'].fillna('').astype(str).str.strip()
        + '__' + df['codigo_procedimento_norm'].fillna('').astype(str).str.strip()
    )

    return df


_XML_CORE_COLS = [
    'arquivo', 'numero_lote', 'tipo_guia',
    'numeroGuiaPrestador', 'numeroGuiaOperadora',
    'paciente', 'medico', 'data_atendimento',
    'tipo_item', 'identificadorDespesa',
    'codigo_tabela', 'codigo_procedimento', 'codigo_procedimento_norm',
    'descricao_procedimento',
    'quantidade', 'valor_unitario', 'valor_total',
    'chave_oper', 'chave_prest',
]


def _alias_xml_cols(df: pd.DataFrame, cols: List[str] = None, prefer_suffix: str = '_xml') -> pd.DataFrame:
    if cols is None:
        cols = _XML_CORE_COLS
    out = df.copy()
    for c in cols:
        if c not in out.columns:
            cand = f'{c}{prefer_suffix}'
            if cand in out.columns:
                out[c] = out[cand]
    return out


def conciliar_itens(
    df_xml: pd.DataFrame,
    df_demo: pd.DataFrame,
    tolerance_valor: float = 0.02,
    fallback_por_descricao: bool = False,
) -> Dict[str, pd.DataFrame]:

    m1 = df_xml.merge(df_demo, left_on="chave_prest", right_on="chave_demo", how="left", suffixes=("_xml", "_demo"))
    m1 = _alias_xml_cols(m1)
    m1["matched_on"] = m1["valor_apresentado"].notna().map({True: "prestador", False: ""})

    restante = m1[m1["matched_on"] == ""].copy()
    restante = _alias_xml_cols(restante)
    cols_xml = df_xml.columns.tolist()
    m2 = restante[cols_xml].merge(df_demo, left_on="chave_oper", right_on="chave_demo", how="left", suffixes=("_xml", "_demo"))
    m2 = _alias_xml_cols(m2)
    m2["matched_on"] = m2["valor_apresentado"].notna().map({True: "operadora", False: ""})

    conc = pd.concat([m1[m1["matched_on"] != ""], m2[m2["matched_on"] != ""]], ignore_index=True)

    fallback_matches = pd.DataFrame()
    if fallback_por_descricao:
        ainda_sem_match = m2[m2["matched_on"] == ""].copy()
        ainda_sem_match = _alias_xml_cols(ainda_sem_match)
        if not ainda_sem_match.empty:
            ainda_sem_match["guia_join"] = ainda_sem_match.apply(
                lambda r: str(r.get("numeroGuiaPrestador", "")).strip() or str(r.get("numeroGuiaOperadora", "")).strip(), axis=1
            )
            df_demo2 = df_demo.copy()
            df_demo2["guia_join"] = df_demo2["numeroGuiaPrestador"].astype(str).str.strip()
            if "descricao_procedimento" in ainda_sem_match.columns and "descricao_procedimento" in df_demo2.columns:
                tmp = ainda_sem_match[cols_xml + ["guia_join"]].merge(
                    df_demo2, on=["guia_join", "descricao_procedimento"], how="left", suffixes=("_xml", "_demo")
                )
                tol = float(tolerance_valor)
                keep = (tmp["valor_apresentado"].notna() & ((tmp["valor_total"] - tmp["valor_apresentado"]).abs() <= tol))
                fallback_matches = tmp[keep].copy()
                if not fallback_matches.empty:
                    fallback_matches["matched_on"] = "descricao+valor"
                    conc = pd.concat([conc, fallback_matches], ignore_index=True)

    if not fallback_matches.empty:
        chaves_resolvidas = fallback_matches["chave_prest"].unique()
        unmatch = m2[(m2["matched_on"] == "") & (~m2["chave_prest"].isin(chaves_resolvidas))].copy()
    else:
        unmatch = m2[m2["matched_on"] == ""].copy()
    unmatch = _alias_xml_cols(unmatch)
    if not unmatch.empty:
        subset_cols = [c for c in ["arquivo", "numeroGuiaPrestador", "codigo_procedimento", "valor_total"] if c in unmatch.columns]
        if subset_cols:
            unmatch = unmatch.drop_duplicates(subset=subset_cols)

    if not conc.empty:
        conc = _alias_xml_cols(conc)
        conc["apresentado_diff"] = conc["valor_total"] - conc["valor_apresentado"]
        conc["glosa_pct"] = conc.apply(
            lambda r: (r["valor_glosa"] / r["valor_apresentado"]) if r.get("valor_apresentado", 0) > 0 else 0.0,
            axis=1
        )

    return {"conciliacao": conc, "nao_casados": unmatch}

