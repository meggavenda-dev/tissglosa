
# -*- coding: utf-8 -*-
"""
core/audit.py
Funções de auditoria de guias (mantidas mesmo desativadas na UI principal).

Funções copiadas do original (sem alteração de lógica):
- build_chave_guia
- _parse_dt_series
- auditar_guias
"""

from __future__ import annotations

from typing import Optional
import pandas as pd


def build_chave_guia(tipo: str, numeroGuiaPrestador: str, numeroGuiaOperadora: str) -> Optional[str]:
    tipo = (tipo or "").upper()
    if tipo not in ("CONSULTA", "SADT"):
        return None
    guia = (numeroGuiaPrestador or "").strip() or (numeroGuiaOperadora or "").strip()
    return guia if guia else None


def _parse_dt_series(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def auditar_guias(df_xml_itens: pd.DataFrame, prazo_retorno: int = 30) -> pd.DataFrame:
    if df_xml_itens is None or df_xml_itens.empty:
        return pd.DataFrame()
    req = ["arquivo","numero_lote","tipo_guia","numeroGuiaPrestador","numeroGuiaOperadora","paciente","medico","data_atendimento","valor_total"]
    for c in req:
        if c not in df_xml_itens.columns:
            df_xml_itens[c] = None
    df = df_xml_itens.copy()
    df["data_atendimento_dt"] = _parse_dt_series(df["data_atendimento"])
    agg = (df.groupby(["tipo_guia","numeroGuiaPrestador","numeroGuiaOperadora","paciente","medico"], dropna=False, as_index=False)
           .agg(arquivo=("arquivo", lambda x: sorted(set(str(a) for a in x if str(a).strip()))),
                numero_lote=("numero_lote", lambda x: sorted(set(str(a) for a in x if str(a).strip()))),
                data_atendimento=("data_atendimento_dt","min"),
                itens_na_guia=("valor_total","count"),
                valor_total_xml=("valor_total","sum")))
    agg["arquivo(s)"] = agg["arquivo"].apply(lambda L: ", ".join(L))
    agg["numero_lote(s)"] = agg["numero_lote"].apply(lambda L: ", ".join(L))
    agg.drop(columns=["arquivo","numero_lote"], inplace=True)
    agg["chave_guia"] = agg.apply(lambda r: build_chave_guia(r["tipo_guia"], r["numeroGuiaPrestador"], r["numeroGuiaOperadora"]), axis=1)
    return agg


