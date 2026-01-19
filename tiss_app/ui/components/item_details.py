
# -*- coding: utf-8 -*-
"""
ui/components/item_details.py
Bloco “Detalhes do Item” (apenas guias com glosa), isolado, com short‑circuit.

Observação:
- Este componente espera que a seleção do item (nome/descrição) já esteja em
  st.session_state["top_itens_editor_selected"] (definido pela view).
- Mantém a mesma lógica de cálculo/ordenação e export do código original.
"""

from __future__ import annotations

import re
import pandas as pd
import streamlit as st

from tiss_app.core.utils import apply_currency, f_currency


def show_item_details(df_view: pd.DataFrame, colmap: dict) -> None:
    """
    Exibe o painel de detalhes para o item selecionado, se houver.
    Respeita filtros já aplicados na view (df_view).
    """
    sel_state_key = "top_itens_editor_selected"
    ver_key = "top_itens_editor_version"
    selected_item_name = st.session_state.get(sel_state_key)

    if not selected_item_name:
        return  # short-circuit: nada a renderizar

    st.markdown("---")
    st.markdown(f"#### 🔎 Detalhes — {selected_item_name}")

    # Botão fechar apenas muda estado e rerun — sem processamento.
    if st.button("❌ Fechar detalhes", key="btn_fechar_detalhes_item"):
        st.session_state[sel_state_key] = None
        st.session_state[ver_key] = int(st.session_state.get(ver_key, 0)) + 1
        st.rerun()

    desc_col_map = colmap.get("descricao")
    if not desc_col_map or desc_col_map not in df_view.columns:
        st.warning("Não foi possível localizar a coluna de descrição original no dataset. Verifique o mapeamento.")
        return

    sel_name_str = str(selected_item_name)
    mask_item = (df_view[desc_col_map].astype(str) == sel_name_str)
    mask_glosa = (mask_item & (df_view["_is_glosa"] == True)) if "_is_glosa" in df_view.columns else mask_item

    amhp_col2 = colmap.get("amhptiss")
    if not amhp_col2:
        for cand in ["Amhptiss", "AMHPTISS", "AMHP TISS", "Nº AMHPTISS", "Numero AMHPTISS", "Número AMHPTISS"]:
            if cand in df_view.columns:
                amhp_col2 = cand
                break

    possiveis = [
        amhp_col2,
        colmap.get("convenio"),
        colmap.get("prestador"),
        colmap.get("data_pagamento"),
        colmap.get("data_realizado"),
        colmap.get("motivo"),
        colmap.get("desc_motivo"),
        colmap.get("cobranca"),
        colmap.get("valor_cobrado"),
        colmap.get("valor_glosa"),
        colmap.get("valor_recursado"),
    ]
    show_cols = [c for c in possiveis if c and c in df_view.columns]
    df_item = df_view.loc[mask_glosa, show_cols]

    vc = colmap.get("valor_cobrado")
    vg = colmap.get("valor_glosa")
    vr = colmap.get("valor_recursado")

    cols_min = [c for c in [vc, vg] if c and c in df_view.columns]
    df_item_all = df_view.loc[mask_item, cols_min] if cols_min else df_view.loc[mask_item, []]

    qtd_itens_cobrados = int(mask_item.sum())
    total_cobrado = float(df_item_all[vc].sum()) if vc in df_item_all.columns else 0.0

    if "_valor_glosa_abs" in df_view.columns:
        total_glosado = float(df_view.loc[mask_glosa, "_valor_glosa_abs"].sum())
    elif vg and vg in df_view.columns:
        total_glosado = float(df_view.loc[mask_glosa, vg].abs().sum())
    else:
        total_glosado = 0.0

    st.markdown("### 📌 Resumo do item")
    st.write(f"**Itens cobrados:** {qtd_itens_cobrados}")
    st.write(f"**Total cobrado:** {f_currency(total_cobrado)}")
    st.write(f"**Total glosado:** {f_currency(total_glosado)}")
    st.markdown("---")

    if "_valor_glosa_abs" in df_view.columns:
        order_series = df_view.loc[mask_glosa, "_valor_glosa_abs"]
    elif vg and vg in df_view.columns:
        order_series = df_view.loc[mask_glosa, vg].abs()
    else:
        order_series = None

    if order_series is not None and not order_series.empty:
        df_item = df_item.loc[order_series.sort_values(ascending=False).index]

    money_cols_fmt = [c for c in [vc, vg, vr] if c in df_item.columns]

    if not df_item.empty:
        st.dataframe(
            apply_currency(df_item, money_cols_fmt),
            use_container_width=True,
            height=420,
        )
    else:
        st.info(
            "Nenhuma **guia com glosa** encontrada para este item no recorte atual. "
            "Se quiser verificar todas as guias cobradas, use a busca por Nº AMHPTISS."
        )

    base_cols = df_item.columns.tolist()
    st.download_button(
        "⬇️ Baixar relação (CSV) — apenas guias com glosa",
        data=df_item[base_cols].to_csv(index=False).encode("utf-8"),
        file_name=f"guias_com_glosa_item_{re.sub(r'[^A-Za-z0-9_-]+','_', selected_item_name)[:40]}.csv",
        mime="text/csv",
    )

