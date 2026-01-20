
# -*- coding: utf-8 -*-
"""
tiss_app/ui/glosas_view.py
Aba 2 — Faturas Glosadas (XLSX), sem gráficos, com filtros e componentes
de seleção de item e busca AMHPTISS isolados.

Correções aplicadas:
- Motivo de glosa sempre limpo (apenas dígitos) em todas as exibições (inclui Top 20).
- Datas Realizado/Pagamento exibidas sem horário (dd/mm/yyyy) na view.
- Mantém _pagto_dt/_pagto_ym para série mensal.
- Coluna "% Glosa" (Glosa/Cobrado) na tabela "Glosa por mês de pagamento".
- Bloco "🔧 Diagnóstico (debug rápido)" removido.
- Linha horizontal acima do filtro e label alterado para "Filtrar por convênio:".
- [NOVO] Filtro "Filtrar por associado:" logo abaixo do filtro de convênio.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tiss_app.ui.components.uploads import uploads_glosas
from tiss_app.ui.components.item_details import show_item_details
from tiss_app.ui.components.amhp_search import render_amhp_search
from tiss_app.state.ui_state import (
    files_signature, clear_glosas_state
)
from tiss_app.state.cache_wrappers import cached_read_glosas_xlsx
from tiss_app.core.glosas_reader import build_glosas_analytics
from tiss_app.core.utils import apply_currency


def render_glosas_tab() -> None:
    """Render da aba de Faturas Glosadas, com short‑circuit e cache."""
    st.subheader("Leitor de Faturas Glosadas (XLSX) — independente do XML/Demonstrativo")
    st.caption("A análise respeita filtros por **Convênio** e por **mês de Pagamento**. O processamento é persistido com session_state.")

    # Estado inicial (se vier de app.py, fica idempotente)
    if "glosas_ready" not in st.session_state:
        st.session_state.glosas_ready = False
        st.session_state.glosas_data = None
        st.session_state.glosas_colmap = None
        st.session_state.glosas_files_sig = None

    glosas_files = uploads_glosas()
    a1, a2 = st.columns(2)
    with a1:
        proc_click = st.button("📊 Processar Faturas Glosadas", type="primary", key="proc_glosas_btn")
    with a2:
        clear_click = st.button("🧹 Limpar / Resetar", key="clear_glosas_btn")

    if clear_click:
        clear_glosas_state()
        st.rerun()

    if proc_click:
        if not glosas_files:
            st.warning("Selecione pelo menos um arquivo .xlsx antes de processar.")
        else:
            files_sig = files_signature(glosas_files)
            df_g, colmap = cached_read_glosas_xlsx(glosas_files)
            st.session_state.glosas_data = df_g
            st.session_state.glosas_colmap = colmap
            st.session_state.glosas_ready = True
            st.session_state.glosas_files_sig = files_sig
            st.rerun()

    if not st.session_state.glosas_ready or st.session_state.glosas_data is None:
        st.info("Envie os arquivos e clique em **Processar Faturas Glosadas**.")
        return  # short-circuit

    # Arquivos mudaram?
    current_sig = files_signature(glosas_files)
    if (glosas_files and current_sig != st.session_state.glosas_files_sig):
        st.info("Os arquivos enviados mudaram desde o último processamento. Clique em **Processar Faturas Glosadas** para atualizar.")

    df_g   = st.session_state.glosas_data
    colmap = st.session_state.glosas_colmap

    # =========================
    # Filtros
    # =========================
    has_pagto = ("_pagto_dt" in df_g.columns) and df_g["_pagto_dt"].notna().any()
    if not has_pagto:
        st.warning("Coluna 'Pagamento' não encontrada ou sem dados válidos. Recursos mensais ficarão limitados.")

    # Opções de Convênio
    conv_opts = ["(todos)"]
    if colmap.get("convenio") and colmap["convenio"] in df_g.columns:
        conv_unique = sorted(df_g[colmap["convenio"]].dropna().astype(str).unique().tolist())
        conv_opts += conv_unique

    # Linha horizontal + filtro de Convênio
    st.markdown("---")
    conv_sel = st.selectbox("Filtrar por convênio:", conv_opts, index=0, key="conv_glosas")

    # [NOVO] Filtro por Associado (usa a coluna literal 'Associado' do XLSX)
    assoc_col = "Associado"
    assoc_opts = ["(todos)"]
    if assoc_col in df_g.columns:
        assoc_unique = sorted(df_g[assoc_col].dropna().astype(str).unique().tolist())
        assoc_opts += assoc_unique
    assoc_sel = st.selectbox("Filtrar por associado:", assoc_opts, index=0, key="assoc_glosas")

    # Período por Pagamento
    if has_pagto:
        meses_df = (df_g.loc[df_g["_pagto_ym"].notna(), ["_pagto_ym","_pagto_mes_br"]]
                        .drop_duplicates().sort_values("_pagto_ym"))
        meses_labels = meses_df["_pagto_mes_br"].tolist()
        modo_periodo = st.radio("Período (por **Pagamento**):",
                                ["Todos os meses (agrupado)", "Um mês"],
                                horizontal=False, key="modo_periodo")
        mes_sel_label = None
        if modo_periodo == "Um mês" and meses_labels:
            mes_sel_label = st.selectbox("Escolha o mês (Pagamento)", meses_labels, key="mes_pagto_sel")
    else:
        modo_periodo = "Todos os meses (agrupado)"
        mes_sel_label = None

    # =========================
    # Aplicar filtros
    # =========================
    df_view = df_g.copy()

    # Limpeza global de Motivo/Desc. Motivo (sem vírgula/ponto)
    mcol = colmap.get("motivo")
    if mcol and mcol in df_view.columns:
        df_view[mcol] = df_view[mcol].astype(str).str.replace(r"[^\d]", "", regex=True).str.strip()
    dcol = colmap.get("desc_motivo")
    if dcol and dcol in df_view.columns:
        df_view[dcol] = df_view[dcol].astype(str)

    # Datas sem horário para exibição
    for dc in ["data_pagamento", "data_realizado"]:
        c = colmap.get(dc)
        if c and c in df_view.columns:
            df_view[c] = pd.to_datetime(df_view[c], errors="coerce", dayfirst=True).dt.strftime("%d/%m/%Y")

    # AMHPTISS normalizado
    amhp_col = colmap.get("amhptiss")
    if amhp_col and amhp_col in df_view.columns:
        df_view[amhp_col] = (
            df_view[amhp_col].astype(str).str.replace(r"[^\d]", "", regex=True).str.strip()
        )

    # Filtro por Convênio
    if conv_sel != "(todos)" and colmap.get("convenio") and colmap["convenio"] in df_view.columns:
        df_view = df_view[df_view[colmap["convenio"]].astype(str) == conv_sel]

    # [NOVO] Filtro por Associado
    if assoc_sel != "(todos)" and assoc_col in df_view.columns:
        df_view = df_view[df_view[assoc_col].astype(str) == assoc_sel]

    # Filtro por mês de pagamento
    if has_pagto and mes_sel_label:
        df_view = df_view[df_view["_pagto_mes_br"] == mes_sel_label]

    # =========================
    # Série mensal (Pagamento) — SEM gráficos
    # =========================
    st.markdown("### 📅 Glosa por **mês de pagamento**")
    has_pagto_view = ("_pagto_dt" in df_view.columns) and df_view["_pagto_dt"].notna().any()
    if has_pagto_view:
        base_m = df_view[df_view["_is_glosa"] == True].copy()
        if base_m.empty:
            st.info("Sem glosas no recorte atual.")
        else:
            mensal = (
                base_m.groupby(["_pagto_ym", "_pagto_mes_br"], as_index=False)
                      .agg(
                          Valor_Glosado=("_valor_glosa_abs", "sum"),
                          Valor_Cobrado=(colmap["valor_cobrado"], "sum"),
                          Valor_Recursado=(colmap["valor_recursado"], "sum")
                            if (colmap.get("valor_recursado") in base_m.columns) else ("_valor_glosa_abs", "size")
                      )
                      .sort_values("_pagto_ym")
            )

            # Rótulos amigáveis
            mensal = mensal.rename(columns={
                "_pagto_mes_br": "Mês de Pagamento",
                "Valor_Glosado": "Valor Glosado (R$)",
                "Valor_Cobrado": "Valor Cobrado (R$)",
                "Valor_Recursado": "Valor Recursado (R$)",
            })

            # Percentual de glosa sobre o total cobrado
            if "Valor Cobrado (R$)" in mensal.columns and "Valor Glosado (R$)" in mensal.columns:
                mensal["% Glosa"] = mensal.apply(
                    lambda r: (r["Valor Glosado (R$)"] / r["Valor Cobrado (R$)"] * 100) if r["Valor Cobrado (R$)"] > 0 else 0.0,
                    axis=1
                )
            else:
                mensal["% Glosa"] = 0.0

            # Seleção/ordem final de colunas
            cols_final = ["Mês de Pagamento", "Valor Cobrado (R$)", "Valor Glosado (R$)", "Valor Recursado (R$)", "% Glosa"]
            mensal = mensal[[c for c in cols_final if c in mensal.columns]]

            # Formatação: moeda para valores e percentual com 2 casas (padrão BR)
            mensal_fmt = apply_currency(mensal.copy(), ["Valor Cobrado (R$)", "Valor Glosado (R$)", "Valor Recursado (R$)"])
            if "% Glosa" in mensal_fmt.columns:
                mensal_fmt["% Glosa"] = mensal["% Glosa"].map(
                    lambda v: f"{v:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
                )

            st.dataframe(mensal_fmt, use_container_width=True, height=260)
    else:
        st.info("Sem 'Pagamento' válido para montar série mensal.")

    # =========================
    # Analytics globais (respeita df_view)
    # =========================
    analytics = build_glosas_analytics(df_view, colmap)

    st.markdown("### 🏥 Convênios com maior valor glosado")
    by_conv = analytics.get("by_convenio") if analytics else pd.DataFrame()
    if by_conv is None or by_conv.empty:
        st.info("Coluna de 'Convênio' não encontrada.")
    else:
        # Base de Valor Cobrado por convênio (no recorte atual: df_view)
        if colmap.get("convenio") in df_view.columns and colmap.get("valor_cobrado") in df_view.columns:
            cob_df = (
                df_view.groupby(colmap["convenio"], as_index=False)
                       .agg(Valor_Cobrado=(colmap["valor_cobrado"], "sum"))
                       .rename(columns={colmap["convenio"]: "Convênio"})
            )
        else:
            cob_df = pd.DataFrame(columns=["Convênio", "Valor_Cobrado"])

        conv_df = by_conv.copy()
        glosa_col = "Valor Glosado (R$)" if "Valor Glosado (R$)" in conv_df.columns else (
            "Valor_Glosado" if "Valor_Glosado" in conv_df.columns else None
        )
        ren_map = {}
        if glosa_col:
            ren_map[glosa_col] = "Valor Glosado"
        conv_df = conv_df.rename(columns=ren_map)

        conv_df = conv_df.merge(cob_df, on="Convênio", how="left")
        conv_df = conv_df.rename(columns={"Valor_Cobrado": "Valor Cobrado"})
        cols_final = ["Convênio", "Qtd", "Valor Cobrado", "Valor Glosado"]
        for c in cols_final:
            if c not in conv_df.columns:
                conv_df[c] = 0
        conv_df = conv_df[cols_final].copy()
        conv_df_fmt = apply_currency(conv_df, ["Valor Cobrado", "Valor Glosado"])
        conv_df_fmt = (
            conv_df_fmt
            .assign(_ord_glosa = conv_df["Valor Glosado"].astype(float),
                    _ord_qtd   = conv_df["Qtd"].astype(int))
            .sort_values(["_ord_glosa", "_ord_qtd"], ascending=[False, False])
            .drop(columns=["_ord_glosa", "_ord_qtd"])
            .head(20)
        )
        st.dataframe(conv_df_fmt, use_container_width=True, height=320)

        # Top 20 — Motivos de glosa por maior valor glosado
        st.markdown("### 🧾 Top 20 — Motivos de glosa por **maior valor glosado**")
        mot_df = analytics.get("top_motivos") if analytics else pd.DataFrame()
        if mot_df is None or mot_df.empty:
            st.info("Não foi possível montar o ranking de motivos (verifique as colunas de 'Motivo Glosa' e 'Descrição Glosa' nos arquivos).")
        else:
            gl_col = "Valor Glosado (R$)" if "Valor Glosado (R$)" in mot_df.columns else (
                "Valor_Glosado" if "Valor_Glosado" in mot_df.columns else None
            )
            if gl_col is None:
                st.info("Coluna de valor glosado não encontrada no ranking de motivos.")
            else:
                mot_view = mot_df.copy()
                if gl_col != "Valor Glosado (R$)":
                    mot_view = mot_view.rename(columns={gl_col: "Valor Glosado (R$)"})
                if "Qtd" in mot_view.columns:
                    mot_view = mot_view.sort_values(["Valor Glosado (R$)", "Qtd"], ascending=[False, False])
                else:
                    mot_view = mot_view.sort_values(["Valor Glosado (R$)"], ascending=[False])
                mot_view = mot_view.head(20)
                cols_show = [c for c in ["Motivo", "Descrição do Motivo", "Valor Glosado (R$)"] if c in mot_view.columns]
                mot_view_fmt = apply_currency(mot_view[cols_show], ["Valor Glosado (R$)"])
                st.dataframe(mot_view_fmt, use_container_width=True, height=260)

    # =========================
    # Itens/descrições com maior valor glosado (Detalhes só com glosa)
    # =========================
    st.markdown("### 🧩 Itens/descrições com maior valor glosado")
    desc_col = colmap.get("descricao")
    proc_col = colmap.get("procedimento")
    vc_col   = colmap.get("valor_cobrado")
    vg_col   = colmap.get("valor_glosa")

    base_glosa = df_view[df_view["_is_glosa"] == True].copy() if "_is_glosa" in df_view.columns else pd.DataFrame()
    if (not desc_col) or (desc_col not in df_view.columns):
        st.info("Coluna de 'Descrição' não encontrada.")
    else:
        if base_glosa.empty:
            st.info("Sem itens glosados no recorte atual.")
        else:
            group_keys = [desc_col]
            if proc_col and (proc_col in df_view.columns):
                group_keys = [proc_col, desc_col]

            agg = (
                base_glosa.groupby(group_keys, dropna=False, as_index=False)
                          .agg(
                              Qtd=("_is_glosa", "size"),
                              Valor_cobrado=(vc_col, "sum") if (vc_col and vc_col in base_glosa.columns) else ("_valor_glosa_abs", "size"),
                              Valor_glosado=("_valor_glosa_abs", "sum")
                          )
            )

            ren_map = {desc_col: "Descrição do Item", "Valor_cobrado": "Valor cobrado", "Valor_glosado": "Valor glosado"}
            if proc_col and (proc_col in agg.columns):
                ren_map[proc_col] = "Código"
            agg = agg.rename(columns=ren_map)

            agg = agg.sort_values(["Valor glosado", "Qtd"], ascending=[False, False]).reset_index(drop=True)

            if "Código" not in agg.columns:
                agg["Código"] = ""
            else:
                agg["Código"] = agg["Código"].astype(str).str.replace(r"[^\dA-Za-z]+", "", regex=True).str.strip()
            agg = agg[["Código", "Descrição do Item", "Qtd", "Valor cobrado", "Valor glosado"]]

            agg_fmt = apply_currency(agg.copy(), ["Valor cobrado", "Valor glosado"])

            # Seleção por checkbox (1 por vez) — estado persistente
            sel_state_key = "top_itens_editor_selected"
            ver_key       = "top_itens_editor_version"
            if ver_key not in st.session_state:
                st.session_state[ver_key] = 0
            if sel_state_key not in st.session_state:
                st.session_state[sel_state_key] = None

            selected_item_name = st.session_state[sel_state_key]
            prev_series = (agg_fmt.get("Descrição do Item", "").astype(str) == str(selected_item_name))
            agg_fmt["Detalhes"] = prev_series

            st.caption("Clique em **Detalhes** para abrir a relação das guias (somente com glosa) deste item.")
            editor_key = f"top_itens_editor__v{st.session_state[ver_key]}"

            edited = st.data_editor(
                agg_fmt,
                use_container_width=True,
                height=420,
                disabled=[c for c in agg_fmt.columns if c != "Detalhes"],
                column_config={
                    "Detalhes": st.column_config.CheckboxColumn(
                        help="Mostrar detalhes deste item logo abaixo",
                        default=False
                    )
                },
                key=editor_key
            )

            # Detecta alteração na seleção
            if "Descrição do Item" not in edited.columns:
                new_selected_item = None
            else:
                curr_series = edited["Detalhes"].astype(bool).reindex(prev_series.index, fill_value=False)
                turned_on  = (curr_series & ~prev_series)
                if turned_on.any():
                    idx = turned_on[turned_on].index[-1]
                    new_selected_item = edited.loc[idx, "Descrição do Item"]
                elif not curr_series.any():
                    new_selected_item = None
                elif curr_series.sum() == 1:
                    idx = curr_series.idxmax()
                    new_selected_item = edited.loc[idx, "Descrição do Item"]
                else:
                    candidates = curr_series[curr_series].index.tolist()
                    prev_idx = prev_series[prev_series].index.tolist()
                    pick = [i for i in candidates if i not in prev_idx]
                    idx = (pick[-1] if pick else candidates[-1])
                    new_selected_item = edited.loc[idx, "Descrição do Item"]

            if new_selected_item != selected_item_name:
                st.session_state[sel_state_key] = new_selected_item
                st.session_state[ver_key] += 1
                st.rerun()

    # === DETALHES DO ITEM SELECIONADO ===
    show_item_details(df_view, colmap)

    # === BUSCA POR Nº AMHPTISS ===
    render_amhp_search(df_g, df_view, colmap)
