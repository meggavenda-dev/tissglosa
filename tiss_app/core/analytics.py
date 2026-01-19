
# -*- coding: utf-8 -*-
"""
core/analytics.py
Métricas e análises (KPIs, rankings, motivos, outliers, simulador).

Funções copiadas do original (sem alteração de lógica):
- kpis_por_competencia
- ranking_itens_glosa
- motivos_glosa
- outliers_por_procedimento
- simulador_glosa
"""

from __future__ import annotations

from typing import Optional, Tuple, Dict
import pandas as pd

from .utils import categorizar_motivo_ans


def kpis_por_competencia(df_conc: pd.DataFrame) -> pd.DataFrame:
    base = df_conc.copy()
    if base.empty:
        return base
    if 'competencia' not in base.columns and 'Competência' in base.columns:
        base['competencia'] = base['Competência'].astype(str)
    elif 'competencia' not in base.columns:
        base['competencia'] = ""
    grp = (base.groupby('competencia', dropna=False, as_index=False)
           .agg(valor_apresentado=('valor_apresentado','sum'),
                valor_pago=('valor_pago','sum'),
                valor_glosa=('valor_glosa','sum')))
    grp['glosa_pct'] = grp.apply(
        lambda r: (r['valor_glosa']/r['valor_apresentado']) if r['valor_apresentado']>0 else 0, axis=1
    )
    return grp.sort_values('competencia')


def ranking_itens_glosa(df_conc: pd.DataFrame, min_apresentado: float = 0.0, topn: int = 20) -> Tuple[pd.DataFrame, pd.DataFrame]:
    base = df_conc.copy()
    if base.empty:
        return base, base
    grp = (base.groupby(['codigo_procedimento','descricao_procedimento'], dropna=False, as_index=False)
           .agg(valor_apresentado=('valor_apresentado','sum'),
                valor_glosa=('valor_glosa','sum'),
                valor_pago=('valor_pago','sum'),
                qtd_glosada=('valor_glosa', lambda x: (x > 0).sum())))
    grp_com_glosa = grp[grp['valor_glosa'] > 0].copy()
    if grp_com_glosa.empty:
        return pd.DataFrame(), pd.DataFrame()
    grp_com_glosa['glosa_pct'] = (grp_com_glosa['valor_glosa'] / grp_com_glosa['valor_apresentado']) * 100
    top_valor = grp_com_glosa.sort_values('valor_glosa', ascending=False).head(topn)
    top_pct = grp_com_glosa[grp_com_glosa['valor_apresentado'] >= min_apresentado].sort_values('glosa_pct', ascending=False).head(topn)
    return top_valor, top_pct


def motivos_glosa(df_conc: pd.DataFrame, competencia: Optional[str] = None) -> pd.DataFrame:
    base = df_conc.copy()
    if base.empty:
        return base
    base = base[base['valor_glosa'] > 0]
    if competencia and 'competencia' in base.columns:
        base = base[base['competencia'] == competencia]
    if base.empty: return pd.DataFrame()
    mot = (base.groupby(['motivo_glosa_codigo','motivo_glosa_descricao'], dropna=False, as_index=False)
           .agg(valor_glosa=('valor_glosa','sum'),
                itens=('codigo_procedimento','count')))
    mot['categoria'] = mot['motivo_glosa_codigo'].apply(categorizar_motivo_ans)
    total_glosa = mot['valor_glosa'].sum()
    mot['glosa_pct'] = (mot['valor_glosa'] / total_glosa) * 100 if total_glosa > 0 else 0
    return mot.sort_values('valor_glosa', ascending=False)


def outliers_por_procedimento(df_conc: pd.DataFrame, k: float = 1.5) -> pd.DataFrame:
    base = df_conc[['codigo_procedimento','descricao_procedimento','valor_apresentado']].dropna().copy()
    if base.empty:
        return base
    stats = (base.groupby(['codigo_procedimento','descricao_procedimento'])
             .agg(p50=('valor_apresentado','median'),
                  q1=('valor_apresentado', lambda x: x.quantile(0.25)),
                  q3=('valor_apresentado', lambda x: x.quantile(0.75))))
    stats['iqr'] = stats['q3'] - stats['q1']
    base = base.merge(stats.reset_index(), on=['codigo_procedimento','descricao_procedimento'], how='left')
    base['is_outlier'] = (base['valor_apresentado'] > base['q3'] + k*base['iqr']) | (base['valor_apresentado'] < base['q1'] - k*base['iqr'])
    return base[base['is_outlier']].copy()


def simulador_glosa(df_conc: pd.DataFrame, ajustes: Dict[str, float]) -> pd.DataFrame:
    sim = df_conc.copy()
    if sim.empty or 'motivo_glosa_codigo' not in sim.columns:
        return sim
    sim['valor_glosa_sim'] = sim['valor_glosa']
    for cod, fator in ajustes.items():
        mask = sim['motivo_glosa_codigo'].astype(str) == str(cod)
        sim.loc[mask, 'valor_glosa_sim'] = sim.loc[mask, 'valor_glosa'] * float(fator)
    sim['valor_glosa_sim'] = sim['valor_glosa_sim'].clip(lower=0)
    sim['valor_pago_sim'] = sim['valor_apresentado'] - sim['valor_glosa_sim']
    sim['valor_pago_sim'] = sim['valor_pago_sim'].clip(lower=0)
    sim['glosa_pct_sim'] = sim.apply(
        lambda r: (r['valor_glosa_sim']/r['valor_apresentado']) if r['valor_apresentado']>0 else 0, axis=1
    )
    return sim

