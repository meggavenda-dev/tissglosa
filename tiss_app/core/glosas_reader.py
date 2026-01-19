
# -*- coding: utf-8 -*-
"""
analisedeglosa/core/glosas_reader.py
Leitura e pré-processamento de Faturas Glosadas (.xlsx) e métricas específicas.

Correções aplicadas:
- Motivo de glosa sempre como TEXTO limpo (apenas dígitos) → evita "2,012" / "1,702".
- Datas de Realizado/Pagamento exibidas sem horário (dd/mm/yyyy).
- Mantém _pagto_dt (datetime) e _pagto_ym (Period) para cálculos mensais.
"""

from __future__ import annotations

from typing import Tuple, Dict
import re
import pandas as pd
import streamlit as st


def _pick_col(df: pd.DataFrame, *candidates):
    """Retorna o primeiro nome de coluna que existir no DF dentre os candidatos."""
    for cand in candidates:
        for c in df.columns:
            if str(c).strip().lower() == str(cand).strip().lower():
                return c
            lc = str(c).lower()
            if isinstance(cand, str) and all(w in lc for w in cand.lower().split()):
                return c
    return None


@st.cache_data(show_spinner=False)
def read_glosas_xlsx(files) -> tuple[pd.DataFrame, dict]:
    """
    Lê 1..N arquivos .xlsx de Faturas Glosadas (AMHP ou similar),
    concatena e retorna (df, colmap) com mapeamento de colunas.
    Cria sempre colunas de Pagamento derivadas (_pagto_dt/_ym/_mes_br).

    Correções:
      • "Valor Cobrado" passa a usar "Valor Original" (override)
      • "Realizado": exibe apenas DATA (dd/mm/yyyy), sem "00:00:00"
      • "Pagamento": exibe apenas DATA (dd/mm/yyyy), sem "00:00:00"
      • "Motivo Glosa": sempre TEXTO com dígitos, sem vírgula/ponto
    """
    if not files:
        return pd.DataFrame(), {}

    parts = []
    for f in files:
        df = pd.read_excel(f, engine="openpyxl")
        df.columns = [str(c).strip() for c in df.columns]
        parts.append(df)

    df = pd.concat(parts, ignore_index=True)
    cols = df.columns

    # ---------- Mapeamento inicial ----------
    colmap = {
        "valor_cobrado": next((c for c in cols if "Valor Cobrado" in str(c)), None),
        "valor_glosa": next((c for c in cols if "Valor Glosa" in str(c)), None),
        "valor_recursado": next((c for c in cols if "Valor Recursado" in str(c)), None),
        "data_pagamento": next((c for c in cols if "Pagamento" in str(c)), None),
        "data_realizado": None,  # será definido com critério robusto abaixo
        "motivo": next((c for c in cols if "Motivo Glosa" in str(c)), None),
        "desc_motivo": next((c for c in cols if "Descricao Glosa" in str(c) or "Descrição Glosa" in str(c)), None),
        "tipo_glosa": next((c for c in cols if "Tipo de Glosa" in str(c)), None),
        "descricao": _pick_col(df, "descrição", "descricao", "descrição do item", "descricao do item"),
        "procedimento": _pick_col(
            df,
            "procedimento",
            "código",
            "codigo",
            "cód procedimento",
            "cod procedimento",
            "cod. procedimento",
            "procedimento tuss",
            "tuss",
            "cod tuss",
            "codigo tuss",
            "item",
            "codigo item",
            "código item"
        ),
        "convenio": next((c for c in cols if "Convênio" in str(c) or "Convenio" in str(c)), None),
        "prestador": next((c for c in cols if "Nome Clínica" in str(c) or "Nome Clinica" in str(c) or "Prestador" in str(c)), None),
        "amhptiss": next((
            c for c in cols
            if str(c).strip().lower() in {
                "amhptiss", "amhp tiss", "nº amhptiss", "numero amhptiss", "número amhptiss"
            } or "amhptiss" in str(c).strip().lower() or str(c).strip() == "Amhptiss"
        ), None),
        "cobranca": next((c for c in cols if str(c).strip().lower() == "cobrança" or "cobranca" in str(c).lower()), None),
    }

    # ---------- "Realizado" robusto (sem "Horário") ----------
    norm_cols = [(c, re.sub(r"\s+", " ", str(c)).strip().lower()) for c in cols]
    realizado_exact = [c for c, n in norm_cols if n == "realizado"]
    if not realizado_exact:
        realizado_contains = [c for c, n in norm_cols if ("realizado" in n) and ("horar" not in n)]
    else:
        realizado_contains = []
    if realizado_exact:
        col_data_realizado = realizado_exact[-1]
    elif realizado_contains:
        col_data_realizado = realizado_contains[-1]
    else:
        col_data_realizado = None
    colmap["data_realizado"] = col_data_realizado

    # ---------- "Valor Cobrado" ← "Valor Original" ----------
    col_valor_original = next((c for c in cols if str(c).strip().lower() == "valor original"), None)
    if col_valor_original:
        colmap["valor_original"] = col_valor_original
        if colmap["valor_cobrado"] and colmap["valor_cobrado"] in df.columns:
            df[colmap["valor_cobrado"]] = df[col_valor_original]
        else:
            colmap["valor_cobrado"] = col_valor_original

    # ---------- Normalização AMHPTISS ----------
    amhp_col = colmap.get("amhptiss")
    if amhp_col and amhp_col in df.columns:
        df[amhp_col] = (
            df[amhp_col]
            .astype(str)
            .str.replace(r"[^\d]", "", regex=True)
            .str.strip()
        )

    # ---------- Números ----------
    for c in [colmap.get("valor_cobrado"), colmap.get("valor_glosa"), colmap.get("valor_recursado")]:
        if c and c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # ---------- Motivo de Glosa (sempre TEXTO limpo, sem vírgula) ----------
    if colmap.get("motivo") and colmap["motivo"] in df.columns:
        df[colmap["motivo"]] = (
            df[colmap["motivo"]]
            .astype(str)
            .str.replace(r"[^\d]", "", regex=True)
            .str.strip()
        )
    if colmap.get("desc_motivo") and colmap["desc_motivo"] in df.columns:
        df[colmap["desc_motivo"]] = df[colmap["desc_motivo"]].astype(str)

    # ---------- Datas ----------
    # Realizado: exibir APENAS DATA
    if colmap.get("data_realizado") and colmap["data_realizado"] in df.columns:
        _realizado_dt = pd.to_datetime(df[colmap["data_realizado"]], errors="coerce", dayfirst=True)
        df[colmap["data_realizado"]] = _realizado_dt.dt.strftime("%d/%m/%Y")

    # Pagamento: manter datetime para métricas (_pagto_dt/_ym) e exibir coluna formatada
    if colmap.get("data_pagamento") and colmap["data_pagamento"] in df.columns:
        _pagto_dt = pd.to_datetime(df[colmap["data_pagamento"]], errors="coerce", dayfirst=True)
        df["_pagto_dt"] = _pagto_dt
        if df["_pagto_dt"].notna().any():
            df["_pagto_ym"] = df["_pagto_dt"].dt.to_period("M")
            df["_pagto_mes_br"] = df["_pagto_dt"].dt.strftime("%m/%Y")
        else:
            df["_pagto_ym"] = pd.NaT
            df["_pagto_mes_br"] = ""
        # coluna exibida na UI
        df[colmap["data_pagamento"]] = _pagto_dt.dt.strftime("%d/%m/%Y")
    else:
        df["_pagto_dt"] = pd.NaT
        df["_pagto_ym"] = pd.NaT
        df["_pagto_mes_br"] = ""

    # ---------- Flags de glosa ----------
    if colmap.get("valor_glosa") in df.columns:
        df["_is_glosa"] = df[colmap["valor_glosa"]] < 0
        df["_valor_glosa_abs"] = df[colmap["valor_glosa"]].abs()
    else:
        df["_is_glosa"] = False
        df["_valor_glosa_abs"] = 0.0

    return df, colmap


def build_glosas_analytics(df: pd.DataFrame, colmap: dict) -> dict:
    """
    KPIs e agrupamentos para a aba de glosas (respeita filtros aplicados previamente).
    """
    if df.empty or not colmap:
        return {}

    cm = colmap
    m = df["_is_glosa"].fillna(False)

    total_linhas = len(df)
    # 'data_realizado' está formatada como string dd/mm/yyyy (apenas para exibição),
    # mas aqui usamos apenas para min/max de apresentação, não para cálculo.
    periodo_ini = df[cm["data_realizado"]].min() if cm.get("data_realizado") in df.columns else None
    periodo_fim = df[cm["data_realizado"]].max() if cm.get("data_realizado") in df.columns else None
    valor_cobrado = float(df[cm["valor_cobrado"]].fillna(0).sum()) if cm.get("valor_cobrado") in df.columns else 0.0
    valor_glosado = float(df.loc[m, "_valor_glosa_abs"].sum())
    taxa_glosa = (valor_glosado / valor_cobrado) if valor_cobrado else 0.0
    convenios = int(df[cm["convenio"]].nunique()) if cm.get("convenio") in df.columns else 0
    prestadores = int(df[cm["prestador"]].nunique()) if cm.get("prestador") in df.columns else 0

    base = df.loc[m].copy()

    def _agg(df_, keys):
        if df_.empty:
            return df_
        out = (df_.groupby(keys, dropna=False, as_index=False)
               .agg(Qtd=('_is_glosa', 'size'),
                    Valor_Glosado=('_valor_glosa_abs', 'sum')))
        return out.sort_values(["Valor_Glosado","Qtd"], ascending=False)

    top_motivos = _agg(base, [cm["motivo"], cm["desc_motivo"]]) if cm.get("motivo") and cm.get("desc_motivo") else pd.DataFrame()
    by_tipo     = _agg(base, [cm["tipo_glosa"]]) if cm.get("tipo_glosa") else pd.DataFrame()
    top_itens   = _agg(base, [cm["descricao"]]) if cm.get("descricao") else pd.DataFrame()
    by_convenio = _agg(base, [cm["convenio"]]) if cm.get("convenio") else pd.DataFrame()

    if not top_motivos.empty:
        top_motivos = top_motivos.rename(columns={
            cm["motivo"]: "Motivo",
            cm["desc_motivo"]: "Descrição do Motivo",
            "Valor_Glosado": "Valor Glosado (R$)"
        })
    if not by_tipo.empty:
        by_tipo = by_tipo.rename(columns={cm["tipo_glosa"]: "Tipo de Glosa", "Valor_Glosado":"Valor Glosado (R$)"})
    if not top_itens.empty:
        top_itens = top_itens.rename(columns={cm["descricao"]:"Descrição do Item", "Valor Glosado":"Valor Glosado (R$)"})
    if not by_convenio.empty:
        by_convenio = by_convenio.rename(columns={cm["convenio"]:"Convênio", "Valor Glosado":"Valor Glosado (R$)"})

    return dict(
        kpis=dict(
            linhas=total_linhas,
            periodo_ini=periodo_ini,
            periodo_fim=periodo_fim,
            convenios=convenios,
            prestadores=prestadores,
            valor_cobrado=valor_cobrado,
            valor_glosado=valor_glosado,
            taxa_glosa=taxa_glosa
        ),
        top_motivos=top_motivos,
        by_tipo=by_tipo,
        top_itens=top_itens,
        by_convenio=by_convenio
    )
