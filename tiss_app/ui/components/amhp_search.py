
# -*- coding: utf-8 -*-
"""
ui/components/amhp_search.py
Busca por Nº AMHPTISS desacoplada, com index normalizado e short‑circuit.

Ajustes (Guilherme):
- Tabela da tela "Itens da guia — AMHPTISS" agora exibe SOMENTE:
  [Código do procedimento, Descrição do procedimento, Data do atendimento,
   Valor cobrado, Valor glosado, Valor recursado, Código de glosa, Descrição da glosa]
- Código do procedimento sanitizado (remove vírgulas).
- Resumo em layout vertical (Paciente, Convênio, Totais e Contagens).
- Sem "ignorar filtros" e sem "mostrar todas as colunas": respeita sempre df_view.
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
    Renderiza o painel de busca por Nº AMHPTISS, respeitando filtros da VIEW (df_view).
    - df_g: dataset completo processado
    - df_view: dataset com filtros aplicados (Convênio / mês), se houver
    - colmap: mapeamento de colunas detectado
    """
    amhp_col = colmap.get("amhptiss")
    if not amhp_col or amhp_col not in df_g.columns:
        st.info("Não foi possível identificar a coluna de **AMHPTISS** nos arquivos enviados.")
        return

    # Index do AMHPTISS (normalizado) no dataset completo (para lookup rápido)
    df_g_idx, amhp_index = _normalize_and_index(df_g, amhp_col)

    st.session_state.setdefault("amhp_query", "")
    st.session_state.setdefault("amhp_result", None)

    st.markdown("## 🔎 Buscar por **Nº AMHPTISS**")
    st.markdown("---")

    col1, col2 = st.columns([0.70, 0.30])
    with col1:
        numero_input = st.text_input(
            "Informe o Nº AMHPTISS",
            value=st.session_state.amhp_query,
            placeholder="Ex.: 62977972"
        )
    with col2:
        clique_buscar = st.button("🔍 Buscar", key="btn_buscar_amhp")
        clique_fechar = st.button("❌ Fechar resultados", key="btn_fechar_amhp")

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
            # SEM "ignorar filtros": usa SEMPRE o df_view (respeita filtros da aba)
            base = df_view
            if num in amhp_index:
                idx = amhp_index[num]
                # mantém só os índices existentes no DF base (evita KeyError)
                idx_validos = [i for i in idx if i in base.index]
                result = base.loc[idx_validos] if idx_validos else pd.DataFrame()
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
        st.info("Nenhuma linha encontrada para esse AMHPTISS no recorte atual.")
        return

    # ---------- Normalizações idempotentes ----------
    # Motivo em dígitos (sem separadores)
    motivo_col = colmap.get("motivo")
    if motivo_col and motivo_col in result.columns:
        result = result.assign(
            **{motivo_col: result[motivo_col].astype(str).str.replace(r"[^\d]", "", regex=True).str.strip()}
        )

    # Mapeamentos de colunas relevantes
    col_proc  = colmap.get("procedimento")      # Código do procedimento
    col_desc  = colmap.get("descricao")         # Descrição do procedimento
    col_data  = colmap.get("data_realizado")    # Data do atendimento (no glosas_reader)
    col_vc    = colmap.get("valor_cobrado")
    col_vg    = colmap.get("valor_glosa")
    col_vr    = colmap.get("valor_recursado")
    col_mcod  = colmap.get("motivo")            # Código de glosa
    col_mdesc = colmap.get("desc_motivo")       # Descrição da glosa

    # Remover vírgulas do CÓDIGO do procedimento (se existir)
    if col_proc and col_proc in result.columns:
        result[col_proc] = result[col_proc].astype(str).str.replace(",", "", regex=False).str.strip()

    # KPIs do resumo (mantidos)
    qtd_cobrados = len(result)
    total_cobrado = float(pd.to_numeric(result[col_vc], errors="coerce").fillna(0).sum()) if col_vc in result else 0.0
    total_glosado = float(pd.to_numeric(result[col_vg], errors="coerce").abs().fillna(0).sum()) if col_vg in result else 0.0
    qtd_glosados = int((result["_is_glosa"] == True).sum()) if "_is_glosa" in result.columns else 0

    # ----------------------- Paciente & Convênio no Resumo (vertical) -----------------------
    # Heurística para localizar "Paciente/Beneficiário" caso não haja mapeamento dedicado
    pac_col = None
    pac_candidates = [
        "paciente", "nome do paciente", "nome paciente",
        "beneficiario", "beneficiário", "nome do beneficiario", "nome do beneficiário"
    ]
    for c in result.columns:
        lc = str(c).strip().lower()
        if any(tok in lc for tok in pac_candidates):
            pac_col = c
            break
    nome_paciente = (
        str(result[pac_col].iloc[0]).strip()
        if pac_col and pac_col in result.columns and not result[pac_col].empty
        else "—"
    )

    conv_col = colmap.get("convenio")
    convenio_val = (
        str(result[conv_col].iloc[0]).strip()
        if conv_col and conv_col in result.columns and not result[conv_col].empty
        else "—"
    )

    st.markdown("### 📌 Resumo da guia")
    # Tudo EM LINHA VERTICAL (um abaixo do outro)
    st.write(f"**Paciente:** {nome_paciente}")
    st.write(f"**Convênio:** {convenio_val}")
    st.write(f"**Total Cobrado:** {f_currency(total_cobrado)}")
    st.write(f"**Total Glosado:** {f_currency(total_glosado)}")
    st.write(f"**Itens cobrados:** {qtd_cobrados}")
    st.write(f"**Itens glosados:** {qtd_glosados}")
    st.markdown("---")

    # ---------- Exibição: APENAS as colunas solicitadas ----------
    # Renomeia as colunas de valores para exibição
    result_show = result.copy()
    ren = {}
    if col_vc and col_vc in result_show.columns: ren[col_vc] = "Valor Cobrado (R$)"
    if col_vg and col_vg in result_show.columns: ren[col_vg] = "Valor Glosado (R$)"
    if col_vr and col_vr in result_show.columns: ren[col_vr] = "Valor Recursado (R$)"
    if ren:
        result_show = result_show.rename(columns=ren)

    # Seleção e ordem final das colunas
    # Obs.: se alguma coluna não existir no resultado, é simplesmente desconsiderada.
    exibir_cols = [
        col_proc,                 # Código do procedimento
        col_desc,                 # Descrição do procedimento
        col_data,                 # Data do atendimento (Realizado)
        "Valor Cobrado (R$)",     # Valor cobrado
        "Valor Glosado (R$)",     # Valor glosado
        "Valor Recursado (R$)",   # Valor recursado
        col_mcod,                 # Código de glosa
        col_mdesc,                # Descrição da glosa
    ]
    exibir_cols = [c for c in exibir_cols if c and c in result_show.columns]

    # Formatar apenas as colunas monetárias renomeadas
    money_cols = [c for c in ["Valor Cobrado (R$)", "Valor Glosado (R$)", "Valor Recursado (R$)"] if c in exibir_cols]

    if not exibir_cols:
        st.warning("Nenhuma das colunas solicitadas foi encontrada no resultado. Verifique o mapeamento das colunas.")
        return

    st.dataframe(
        apply_currency(result_show[exibir_cols], money_cols),
        use_container_width=True,
        height=420
    )

    st.download_button(
        "⬇️ Baixar resultado (CSV)",
        result_show[exibir_cols].to_csv(index=False).encode("utf-8"),
        file_name=f"itens_AMHPTISS_{numero_alvo}.csv",
        mime="text/csv"
    )
