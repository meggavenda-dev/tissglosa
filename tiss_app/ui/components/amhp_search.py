
# -*- coding: utf-8 -*-
"""
ui/components/amhp_search.py
Busca por Nº AMHPTISS desacoplada, com index normalizado e short‑circuit.
"""

from __future__ import annotations

import re
import pandas as pd
import streamlit as st

from tiss_app.core.utils import apply_currency, f_currency


@st.cache_data(show_spinner=False)
def _normalize_and_index(df: pd.DataFrame, col: str):
    """
    Gera uma coluna auxiliar com apenas dígitos e um índice {amhp_digits: [indices]}.
    """
    df2 = df.copy()
    df2["_amhp_digits"] = (
        df2[col].astype(str).str.replace(r"[^\d]", "", regex=True).str.strip()
    )
    index = {}
    for i, v in df2["_amhp_digits"].items():
        if v not in index:
            index[v] = []
        index[v].append(i)
    return df2, index


def _digits(s): 
    return re.sub(r"\D+", "", str(s or ""))


def render_amhp_search(df_g: pd.DataFrame, df_view: pd.DataFrame, colmap: dict) -> None:
    """
    Renderiza o painel de busca por Nº AMHPTISS, respeitando filtros se desejado.
    - df_g: dataset completo processado
    - df_view: dataset com filtros aplicados (convênio / mês), se houver
    - colmap: mapeamento de colunas detectado
    """
    amhp_col = colmap.get("amhptiss")
    if not amhp_col or amhp_col not in df_g.columns:
        st.info("Não foi possível identificar a coluna de **AMHPTISS** nos arquivos enviados.")
        return

    # Index do AMHPTISS (normalizado) no dataset completo
    df_g_idx, amhp_index = _normalize_and_index(df_g, amhp_col)

    st.session_state.setdefault("amhp_query", "")
    st.session_state.setdefault("amhp_result", None)

    st.markdown("## 🔎 Buscar por **Nº AMHPTISS**")
    st.markdown("---")

    col1, col2 = st.columns([0.65, 0.35])
    with col1:
        numero_input = st.text_input(
            "Informe o Nº AMHPTISS",
            value=st.session_state.amhp_query,
            placeholder="Ex.: 61916098"
        )
        cbt1, cbt2 = st.columns(2)
        with cbt1:
            clique_buscar = st.button("🔍 Buscar", key="btn_buscar_amhp")
        with cbt2:
            clique_fechar = st.button("❌ Fechar resultados", key="btn_fechar_amhp")
    with col2:
        ignorar_filtros = st.checkbox(
            "Ignorar filtros de Convênio/Mês",
            False,
            help="Busca no dataset completo, ignorando filtros ativos."
        )

    if clique_fechar:
        st.session_state.amhp_query = ""
        st.session_state.amhp_result = None
        st.rerun()   # short-circuit via rerun

    if clique_buscar:
        num = _digits(numero_input)
        if not num:
            st.warning("Digite um Nº AMHPTISS válido.")
        else:
            st.session_state.amhp_query = num
            base = df_g if ignorar_filtros else df_view
            if num in amhp_index:
                idx = amhp_index[num]
                # mantém só os índices existentes no DF base (evita KeyError)
                idx_validos = [i for i in idx if i in base.index]
                if idx_validos:
                    result = base.loc[idx_validos]
                else:
                    result = pd.DataFrame()
            else:
                result = pd.DataFrame()

            st.session_state.amhp_result = result

    result = st.session_state.amhp_result
    numero_alvo = st.session_state.amhp_query
    if result is None:
        return

    st.markdown("---")
    st.subheader(f"🧾 Itens da guia — AMHPTISS **{numero_alvo}**")

    if result.empty:
        msg = "" if ignorar_filtros else " com os filtros atuais"
        st.info(f"Nenhuma linha encontrada para esse AMHPTISS{msg}.")
        return

    motivo_col = colmap.get("motivo")
    if motivo_col and motivo_col in result.columns:
        result = result.assign(
            **{motivo_col: result[motivo_col].astype(str).str.replace(r"[^\d]", "", regex=True).str.strip()}
        )

    col_vc = colmap.get("valor_cobrado")
    col_vg = colmap.get("valor_glosa")
    qtd_cobrados = len(result)
    total_cobrado = float(pd.to_numeric(result[col_vc], errors="coerce").fillna(0).sum()) if col_vc in result else 0.0
    total_glosado = float(pd.to_numeric(result[col_vg], errors="coerce").abs().fillna(0).sum()) if col_vg in result else 0.0
    qtd_glosados = int((result["_is_glosa"] == True).sum()) if "_is_glosa" in result.columns else 0

    st.markdown("### 📌 Resumo da guia")
    st.write(f"**Total Cobrado:** {f_currency(total_cobrado)}")
    st.write(f"**Total Glosado:** {f_currency(total_glosado)}")
    st.write(f"**Itens cobrados:** {qtd_cobrados}")
    st.write(f"**Itens glosados:** {qtd_glosados}")
    st.markdown("---")

    ren = {}
    if col_vc and col_vc in result.columns: ren[col_vc] = "Valor Cobrado (R$)"
    if col_vg and col_vg in result.columns: ren[col_vg] = "Valor Glosado (R$)"
    col_vr = colmap.get("valor_recursado")
    if col_vr and col_vr in result.columns: ren[col_vr] = "Valor Recursado (R$)"
    result_show = result.rename(columns=ren)

    
    # LIMPAR colunas indesejadas antes de exibir
    colunas_para_remover = [
        colmap.get("tipo_glosa"),
        colmap.get("guia_prest"),  # se existir no colmap
        "Guia Prestador",
        "numeroGuiaPrestador",
        "Guia_Prestador",
    ]
    
    for c in colunas_para_remover:
        if c in result_show.columns:
            result_show = result_show.drop(columns=[c])
    
    # Agora definimos apenas as colunas que você quer exibir
    exibir_cols = [
        amhp_col,
        colmap.get("convenio"),
        colmap.get("prestador"),
        colmap.get("descricao"),
        motivo_col,
        colmap.get("desc_motivo"),
        colmap.get("data_realizado"),
        colmap.get("data_pagamento"),
        colmap.get("cobranca"),
        "Valor Cobrado (R$)",
        "Valor Glosado (R$)",
        "Valor Recursado (R$)",
    ]
    
    # Mantém apenas as que realmente existem
    exibir_cols = [c for c in exibir_cols if c in result_show.columns]


    st.dataframe(
        apply_currency(result_show[exibir_cols], ["Valor Cobrado (R$)", "Valor Glosado (R$)", "Valor Recursado (R$)"]),
        use_container_width=True,
        height=420
    )

    st.download_button(
        "⬇️ Baixar resultado (CSV)",
        result_show[exibir_cols].to_csv(index=False).encode("utf-8"),
        file_name=f"itens_AMHPTISS_{numero_alvo}.csv",
        mime="text/csv"
    )

    if not ignorar_filtros:
        st.caption("Dica: se algum item não aparecer, marque **“Ignorar filtros de Convênio/Mês”**.")
