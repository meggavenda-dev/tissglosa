
# -*- coding: utf-8 -*-
"""
ui/conciliation_view.py
Aba 1 — Conciliação TISS: uploads, processamento cacheado, conciliação e analytics.

Regras:
- Sem lógica pesada fora de blocos condicionados por botões/estados.
- Todo processamento usa wrappers cacheados em state/cache_wrappers.py
- Mantém textos/labels do app original.
"""

from __future__ import annotations

import io
import pandas as pd
import streamlit as st

from tiss_app.ui.components.uploads import uploads_conciliation
from tiss_app.core.utils import apply_currency, f_currency
from tiss_app.state.cache_wrappers import (
    cached_build_demo_df, cached_build_xml_df, cached_conciliar
)
from tiss_app.core.analytics import (
    kpis_por_competencia, ranking_itens_glosa, motivos_glosa,
    outliers_por_procedimento, simulador_glosa
)


def render_conciliation_tab(params: dict) -> None:
    """
    Render da aba de Conciliação.
    - params: dict retornado de layout.sidebar_params()
    """
    xml_files, demo_files = uploads_conciliation()

    # PROCESSAMENTO DO DEMONSTRATIVO (sempre) — permite wizard
    df_demo = cached_build_demo_df(demo_files or [], strip_zeros_codes=params["strip_zeros_codes"])
    if not df_demo.empty:
        st.info("Demonstrativo carregado e mapeado. A conciliação considerará **somente** os itens presentes nos XMLs. "
                "Itens presentes apenas no demonstrativo serão **ignorados**.")
    else:
        if demo_files:
            st.info("Carregue um Demonstrativo válido ou conclua o mapeamento manual.")

    st.markdown("---")
    # Botão dispara processamento pesado — mas tudo cacheado.
    if st.button("🚀 Processar Conciliação & Analytics", type="primary", key="btn_conc"):
        # XML → itens
        df_xml = cached_build_xml_df(xml_files or [], strip_zeros_codes=params["strip_zeros_codes"])
        if df_xml.empty:
            st.warning("Nenhum item extraído do(s) XML(s). Verifique os arquivos.")
            st.stop()

        st.subheader("📄 Itens extraídos dos XML (Consulta / SADT)")
        st.dataframe(apply_currency(df_xml, ['valor_unitario','valor_total']), use_container_width=True, height=360)

        if df_demo.empty:
            st.warning("Nenhum demonstrativo válido para conciliar.")
            st.stop()

        # Conciliação (cache)
        result = cached_conciliar(
            df_xml=df_xml,
            df_demo=df_demo,
            tolerance_valor=float(params["tolerance_valor"]),
            fallback_por_descricao=params["fallback_desc"]
        )
        conc = result["conciliacao"]
        unmatch = result["nao_casados"]

        st.subheader("🔗 Conciliação Item a Item (XML × Demonstrativo)")
        conc_disp = apply_currency(
            conc.copy(),
            ['valor_unitario','valor_total','valor_apresentado','valor_glosa','valor_pago','apresentado_diff']
        )
        st.dataframe(conc_disp, use_container_width=True, height=460)

        c1, c2 = st.columns(2)
        c1.metric("Itens conciliados", len(conc))
        c2.metric("Itens não conciliados (somente XML)", len(unmatch))

        if not unmatch.empty:
            st.subheader("❗ Itens (do XML) não conciliados")
            st.dataframe(apply_currency(unmatch.copy(), ['valor_unitario','valor_total']), use_container_width=True, height=300)
            st.download_button("Baixar Não Conciliados (CSV)", data=unmatch.to_csv(index=False).encode("utf-8"),
                               file_name="nao_conciliados.csv", mime="text/csv")

        # Analytics (conciliado)
        st.markdown("---")
        st.subheader("📊 Analytics de Glosa (apenas itens conciliados)")

        st.markdown("### 📈 Tendência por competência")
        kpi_comp = kpis_por_competencia(conc)
        st.dataframe(apply_currency(kpi_comp, ['valor_apresentado','valor_pago','valor_glosa']), use_container_width=True)
        try:
            st.line_chart(kpi_comp.set_index('competencia')[['valor_apresentado','valor_pago','valor_glosa']])
        except Exception:
            pass

        st.markdown("### 🏆 TOP itens glosados (valor e %)")
        min_apres = st.number_input(
            "Corte mínimo de Apresentado para ranking por % (R$)", min_value=0.0, value=500.0, step=50.0, key="min_apres_pct"
        )
        top_valor, top_pct = ranking_itens_glosa(conc, min_apresentado=min_apres, topn=20)
        t1, t2 = st.columns(2)
        with t1:
            st.markdown("**Por valor de glosa (TOP 20)**")
            st.dataframe(apply_currency(top_valor, ['valor_apresentado','valor_glosa','valor_pago']), use_container_width=True)
        with t2:
            st.markdown("**Por % de glosa (TOP 20)**")
            st.dataframe(apply_currency(top_pct, ['valor_apresentado','valor_glosa','valor_pago']), use_container_width=True)

        st.markdown("### 🧩 Motivos de glosa — análise")
        comp_opts = ['(todas)']
        if 'competencia' in conc.columns:
            comp_opts += sorted(conc['competencia'].dropna().astype(str).unique().tolist())
        comp_sel = st.selectbox("Filtrar por competência", comp_opts, key="comp_mot")
        motdf = motivos_glosa(conc, None if comp_sel=='(todas)' else comp_sel)
        st.dataframe(apply_currency(motdf, ['valor_glosa','valor_apresentado']), use_container_width=True)

        st.markdown("### 👩‍⚕️ Médicos — ranking por glosa")
        if 'competencia' in conc.columns:
            comp_med = st.selectbox("Competência (médicos)",
                                    ['(todas)'] + sorted(conc['competencia'].dropna().astype(str).unique().tolist()),
                                    key="comp_med")
            med_base = conc if comp_med == '(todas)' else conc[conc['competencia'] == comp_med]
        else:
            med_base = conc
        med_rank = (med_base.groupby(['medico'], dropna=False, as_index=False)
                    .agg(valor_apresentado=('valor_apresentado','sum'),
                         valor_glosa=('valor_glosa','sum'),
                         valor_pago=('valor_pago','sum'),
                         itens=('arquivo','count')))
        med_rank['glosa_pct'] = med_rank.apply(lambda r: (r['valor_glosa']/r['valor_apresentado']) if r['valor_apresentado']>0 else 0, axis=1)
        st.dataframe(apply_currency(med_rank.sort_values(['glosa_pct','valor_glosa'], ascending=[False,False]),
                                    ['valor_apresentado','valor_glosa','valor_pago']), use_container_width=True)

        st.markdown("### 🧾 Glosa por Tabela (22/19)")
        if 'Tabela' in conc.columns:
            tab = (conc.groupby('Tabela', as_index=False)
                   .agg(valor_apresentado=('valor_apresentado','sum'),
                        valor_glosa=('valor_glosa','sum'),
                        valor_pago=('valor_pago','sum')))
            tab['glosa_pct'] = tab.apply(lambda r: (r['valor_glosa']/r['valor_apresentado']) if r['valor_apresentado']>0 else 0, axis=1)
            st.dataframe(apply_currency(tab, ['valor_apresentado','valor_glosa','valor_pago']), use_container_width=True)
        else:
            st.info("Coluna 'Tabela' não encontrada nos itens conciliados (opcional no demonstrativo).")

        if 'matched_on' in conc.columns:
            st.markdown("### 🧪 Qualidade da conciliação (origem do match)")
            match_dist = conc['matched_on'].value_counts(dropna=False).rename_axis('origem').reset_index(name='itens')
            st.bar_chart(match_dist.set_index('origem'))
            st.dataframe(match_dist, use_container_width=True)

        st.markdown("### 🚩 Outliers em valor apresentado (por procedimento)")
        out_df = outliers_por_procedimento(conc, k=1.5)
        if out_df.empty:
            st.info("Nenhum outlier identificado com o critério atual (IQR).")
        else:
            st.dataframe(out_df, use_container_width=True, height=280)
            st.download_button("Baixar Outliers (CSV)", data=out_df.to_csv(index=False).encode("utf-8"),
                               file_name="outliers_valor_apresentado.csv", mime="text/csv")

        st.markdown("### 🧮 Simulador de faturamento (what‑if por motivo de glosa)")
        motivos_disponiveis = sorted(conc['motivo_glosa_codigo'].dropna().astype(str).unique().tolist()) if 'motivo_glosa_codigo' in conc.columns else []
        if motivos_disponiveis:
            cols_sim = st.columns(min(4, max(1, len(motivos_disponiveis))))
            ajustes = {}
            for i, cod in enumerate(motivos_disponiveis):
                col = cols_sim[i % len(cols_sim)]
                with col:
                    fator = st.slider(f"Motivo {cod} → fator (0–1)", 0.0, 1.0, 1.0, 0.05,
                                      help="Ex.: 0,8 reduz a glosa em 20% para esse motivo.", key=f"sim_{cod}")
                    ajustes[cod] = fator
            sim = simulador_glosa(conc, ajustes)
            st.write("**Resumo do cenário simulado:**")
            res = (sim.agg(
                total_apres=('valor_apresentado','sum'),
                glosa=('valor_glosa','sum'),
                glosa_sim=('valor_glosa_sim','sum'),
                pago=('valor_pago','sum'),
                pago_sim=('valor_pago_sim','sum')
            ))
            st.json({k: f_currency(v) for k, v in res.to_dict().items()})

        # Export Excel consolidado
        st.markdown("---")
        st.subheader("📥 Exportar Excel Consolidado")

        demo_cols_for_export = [c for c in [
            'numero_lote','competencia','numeroGuiaPrestador','numeroGuiaOperadora',
            'codigo_procedimento','descricao_procedimento',
            'quantidade_apresentada','valor_apresentado','valor_glosa','valor_pago',
            'motivo_glosa_codigo','motivo_glosa_descricao','Tabela'
        ] if c in conc.columns]
        itens_demo_match = pd.DataFrame()
        if demo_cols_for_export:
            itens_demo_match = conc[demo_cols_for_export].drop_duplicates().copy()

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as wr:
            df_xml.to_excel(wr, index=False, sheet_name='Itens_XML')
            if not itens_demo_match.empty:
                itens_demo_match.to_excel(wr, index=False, sheet_name='Itens_Demo')
            conc.to_excel(wr, index=False, sheet_name='Conciliação')
            unmatch.to_excel(wr, index=False, sheet_name='Nao_Casados')

            mot_x = motivos_glosa(conc, None)
            mot_x.to_excel(wr, index=False, sheet_name='Motivos_Glosa')

            proc_x = (conc.groupby(['codigo_procedimento','descricao_procedimento'], dropna=False, as_index=False)
                      .agg(valor_apresentado=('valor_apresentado','sum'),
                           valor_glosa=('valor_glosa','sum'),
                           valor_pago=('valor_pago','sum'),
                           itens=('arquivo','count')))
            proc_x['glosa_pct'] = proc_x.apply(lambda r: (r['valor_glosa']/r['valor_apresentado']) if r['valor_apresentado']>0 else 0, axis=1)
            proc_x.to_excel(wr, index=False, sheet_name='Procedimentos_Glosa')

            med_x = (conc.groupby(['medico'], dropna=False, as_index=False)
                     .agg(valor_apresentado=('valor_apresentado','sum'),
                          valor_glosa=('valor_glosa','sum'),
                          valor_pago=('valor_pago','sum'),
                          itens=('arquivo','count')))
            med_x['glosa_pct'] = med_x.apply(lambda r: (r['valor_glosa']/r['valor_apresentado']) if r['valor_apresentado']>0 else 0, axis=1)
            med_x.to_excel(wr, index=False, sheet_name='Medicos')

            if 'numero_lote' in conc.columns:
                lot_x = (conc.groupby(['numero_lote'], dropna=False, as_index=False)
                         .agg(valor_apresentado=('valor_apresentado','sum'),
                              valor_glosa=('valor_glosa','sum'),
                              valor_pago=('valor_pago','sum'),
                              itens=('arquivo','count')))
                lot_x['glosa_pct'] = lot_x.apply(lambda r: (r['valor_glosa']/r['valor_apresentado']) if r['valor_apresentado']>0 else 0, axis=1)
                lot_x.to_excel(wr, index=False, sheet_name='Lotes')

            kpi_comp.to_excel(wr, index=False, sheet_name='KPIs_Competencia')

        st.download_button(
            "⬇️ Baixar Excel consolidado",
            data=buf.getvalue(),
            file_name="tiss_conciliacao_analytics.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

