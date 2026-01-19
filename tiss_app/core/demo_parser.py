
# -*- coding: utf-8 -*-
"""
core/demo_parser.py
Leitura do Demonstrativo AMHP (fixo) + mapeamento manual (wizard) + auto-detecção e concat.

Funções copiadas do original (sem alteração de lógica):
- tratar_codigo_glosa
- ler_demo_amhp_fixado
- _COLMAPS
- _match_col
- _apply_manual_map
- _mapping_wizard_for_demo
- build_demo_df
"""

from __future__ import annotations

from typing import List, Dict, Optional
import re
import pandas as pd
import streamlit as st

from .utils import _normtxt, normalize_code, load_demo_mappings, save_demo_mappings
# Leitura cacheada de Excel permanece em state/cache_wrappers (mesmo nome)
# e é importada na execução (evita dependência circular).
# from tiss_app.state.cache_wrappers import _cached_read_excel


def tratar_codigo_glosa(df: pd.DataFrame) -> pd.DataFrame:
    if "Código Glosa" not in df.columns:
        return df
    gl = df["Código Glosa"].astype(str).fillna("")
    df["motivo_glosa_codigo"]    = gl.str.extract(r"^(\d+)")
    df["motivo_glosa_descricao"] = gl.str.extract(r"^\s*\d+\s*-\s*(.*)$")
    df["motivo_glosa_codigo"]    = df["motivo_glosa_codigo"].fillna("").str.strip()
    df["motivo_glosa_descricao"] = df["motivo_glosa_descricao"].fillna("").str.strip()
    return df


def ler_demo_amhp_fixado(path, strip_zeros_codes: bool = False) -> pd.DataFrame:
    try:
        df_raw = pd.read_excel(path, header=None, engine="openpyxl")
    except:
        df_raw = pd.read_csv(path, header=None)

    header_row = None
    for i in range(min(20, len(df_raw))):
        row_values = df_raw.iloc[i].astype(str).tolist()
        if any("CPF/CNPJ" in str(val).upper() for val in row_values):
            header_row = i
            break
    if header_row is None:
        raise ValueError("Não foi possível localizar a linha de cabeçalho 'CPF/CNPJ' no demonstrativo.")

    df = df_raw.iloc[header_row + 1:].copy()
    df.columns = df_raw.iloc[header_row]
    df = df.loc[:, df.columns.notna()]

    ren = {
        "Guia": "numeroGuiaPrestador",
        "Cod. Procedimento": "codigo_procedimento",
        "Descrição": "descricao_procedimento",
        "Valor Apresentado": "valor_apresentado",
        "Valor Apurado": "valor_pago",
        "Valor Glosa": "valor_glosa",
        "Quant. Exec.": "quantidade_apresentada",
        "Código Glosa": "codigo_glosa_bruto",
    }
    df = df.rename(columns=ren)

    df["numeroGuiaPrestador"] = (
        df["numeroGuiaPrestador"]
        .astype(str).str.replace(".0", "", regex=False).str.strip().str.lstrip("0")
    )
    df["codigo_procedimento"] = df["codigo_procedimento"].astype(str).str.strip()

    df["codigo_procedimento_norm"] = df["codigo_procedimento"].map(
        lambda s: normalize_code(s, strip_zeros=strip_zeros_codes)
    )

    for c in ["valor_apresentado", "valor_pago", "valor_glosa", "quantidade_apresentada"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '.'), errors="coerce").fillna(0)

    df["chave_demo"] = df["numeroGuiaPrestador"].astype(str) + "__" + df["codigo_procedimento_norm"].astype(str)

    if "codigo_glosa_bruto" in df.columns:
        df["motivo_glosa_codigo"] = df["codigo_glosa_bruto"].astype(str).str.extract(r"^(\d+)")
        df["motivo_glosa_descricao"] = df["codigo_glosa_bruto"].astype(str).str.extract(r"^\d+\s*-\s*(.*)")
        df["motivo_glosa_codigo"] = df["motivo_glosa_codigo"].fillna("").str.strip()
        df["motivo_glosa_descricao"] = df["motivo_glosa_descricao"].fillna("").str.strip()

    return df.reset_index(drop=True)


# Auto-detecção genérica (fallback)
_COLMAPS = {
    "lote": [r"\blote\b"],
    "competencia": [r"compet|m[eê]s|refer"],
    "guia_prest": [r"\bguia\b"],
    "guia_oper": [r"^\bguia\b"],
    "cod_proc": [r"cod.*proced|proced.*cod|tuss"],
    "desc_proc": [r"descr"],
    "qtd_apres": [r"quant|qtd"],
    "qtd_paga": [r"quant|qtd"],
    "val_apres": [r"apres|cobrado"],
    "val_glosa": [r"glosa"],
    "val_pago": [r"pago|liberado|apurado"],
    "motivo_cod": [r"glosa"],
    "motivo_desc": [r"glosa"],
}


def _match_col(cols, pats):
    norm = {c: _normtxt(c) for c in cols}
    for c, cn in norm.items():
        if all(re.search(p, cn) for p in pats):
            return c
    return None


def _apply_manual_map(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    def pick(k):
        c = mapping.get(k)
        if not c or c == "(não usar)" or c not in df.columns:
            return None
        return df[c]
    out = pd.DataFrame({
        "numero_lote": pick("lote"),
        "competencia": pick("competencia"),
        "numeroGuiaPrestador": pick("guia_prest"),
        "numeroGuiaOperadora": pick("guia_oper"),
        "codigo_procedimento": pick("cod_proc"),
        "descricao_procedimento": pick("desc_proc"),
        "quantidade_apresentada": pd.to_numeric(pick("qtd_apres"), errors="coerce") if pick("qtd_apres") is not None else 0,
        "quantidade_paga": pd.to_numeric(pick("qtd_paga"), errors="coerce") if pick("qtd_paga") is not None else 0,
        "valor_apresentado": pd.to_numeric(pick("val_apres"), errors="coerce") if pick("val_apres") is not None else 0,
        "valor_glosa": pd.to_numeric(pick("val_glosa"), errors="coerce") if pick("val_glosa") is not None else 0,
        "valor_pago": pd.to_numeric(pick("val_pago"), errors="coerce") if pick("val_pago") is not None else 0,
        "motivo_glosa_codigo": pick("motivo_cod"),
        "motivo_glosa_descricao": pick("motivo_desc"),
    })
    for c in ["numero_lote","numeroGuiaPrestador","numeroGuiaOperadora","codigo_procedimento"]:
        out[c] = out[c].astype(str).str.strip()
    for c in ["valor_apresentado","valor_glosa","valor_pago","quantidade_apresentada","quantidade_paga"]:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0)
    out["codigo_procedimento_norm"] = out["codigo_procedimento"].map(lambda s: normalize_code(s))
    out["chave_prest"] = out["numeroGuiaPrestador"] + "__" + out["codigo_procedimento_norm"]
    out["chave_oper"]  = out["numeroGuiaOperadora"] + "__" + out["codigo_procedimento_norm"]
    return out


def _mapping_wizard_for_demo(uploaded_file):
    st.warning(f"Mapeamento manual pode ser necessário para: **{uploaded_file.name}**")
    try:
        # Importa leitura cacheada (mesmo nome), se disponível
        try:
            from tiss_app.state.cache_wrappers import _cached_read_excel
        except Exception:
            _cached_read_excel = None

        xls = pd.ExcelFile(uploaded_file, engine="openpyxl")
    except Exception as e:
        st.error(f"Erro abrindo arquivo: {e}")
        return None
    sheet = st.selectbox(
        f"Aba (sheet) do demonstrativo {uploaded_file.name}",
        xls.sheet_names,
        key=f"map_sheet_{uploaded_file.name}"
    )
    if _cached_read_excel:
        df_raw = _cached_read_excel(uploaded_file, sheet)
    else:
        df_raw = pd.read_excel(uploaded_file, sheet_name=sheet, engine="openpyxl")

    st.dataframe(df_raw.head(15), use_container_width=True)
    cols = [str(c) for c in df_raw.columns]
    fields = [
        ("lote", "Lote"), ("competencia", "Competência"),
        ("guia_prest", "Guia Prestador"), ("guia_oper", "Guia Operadora"),
        ("cod_proc", "Código Procedimento"), ("desc_proc", "Descrição Procedimento"),
        ("qtd_apres", "Quantidade Apresentada"), ("qtd_paga", "Quantidade Paga"),
        ("val_apres", "Valor Apresentado"), ("val_glosa", "Valor Glosa"), ("val_pago", "Valor Pago"),
        ("motivo_cod", "Código Glosa"), ("motivo_desc", "Descrição Motivo Glosa"),
    ]
    def _default(k):
        pats = _COLMAPS.get(k, [])
        for i, c in enumerate(cols):
            if any(re.search(p, _normtxt(c)) for p in pats):
                return i + 1
        return 0
    mapping = {}
    for k, label in fields:
        opt = ["(não usar)"] + cols
        sel = st.selectbox(label, opt, index=_default(k), key=f"{uploaded_file.name}_{k}")
        mapping[k] = None if sel == "(não usar)" else sel

    if st.button(f"Salvar mapeamento de {uploaded_file.name}", type="primary"):
        st.session_state["demo_mappings"][uploaded_file.name] = {
            "sheet": sheet,
            "columns": mapping
        }
        save_demo_mappings(st.session_state["demo_mappings"])
        try:
            df = _apply_manual_map(df_raw, mapping)
            df = tratar_codigo_glosa(df)
            st.success("Mapeamento salvo com sucesso!")
            return df
        except Exception as e:
            st.error(f"Erro aplicando mapeamento: {e}")
            return None
    return None


def build_demo_df(demo_files, strip_zeros_codes=False) -> pd.DataFrame:
    if not demo_files:
        return pd.DataFrame()

    # Carrega mapeamentos persistidos
    st.session_state.setdefault("demo_mappings", load_demo_mappings())

    # Importa leitura cacheada (mesmo nome) se disponível
    try:
        from tiss_app.state.cache_wrappers import _cached_read_excel
    except Exception:
        _cached_read_excel = None

    parts: List[pd.DataFrame] = []
    for f in demo_files:
        fname = f.name
        # 1) leitor AMHP automático
        try:
            df_demo = ler_demo_amhp_fixado(f, strip_zeros_codes=strip_zeros_codes)
            parts.append(df_demo)
            continue
        except Exception:
            pass
        # 2) mapeamento persistido
        mapping_info = st.session_state["demo_mappings"].get(fname)
        if mapping_info:
            try:
                df_demo = ler_demo_amhp_fixado(f, strip_zeros_codes=strip_zeros_codes)
            except:
                if _cached_read_excel:
                    df_raw = _cached_read_excel(f, mapping_info["sheet"])
                else:
                    df_raw = pd.read_excel(f, sheet_name=mapping_info["sheet"], engine="openpyxl")
                df_demo = _apply_manual_map(df_raw, mapping_info["columns"])
            df_demo = tratar_codigo_glosa(df_demo)
            parts.append(df_demo)
            continue
        # 3) auto-detecção suave
        try:
            xls = pd.ExcelFile(f, engine="openpyxl")
            sheet = xls.sheet_names[0]
            if _cached_read_excel:
                df_raw = _cached_read_excel(f, sheet)
            else:
                df_raw = pd.read_excel(f, sheet_name=sheet, engine="openpyxl")
            cols = [str(c) for c in df_raw.columns]
            pick = {k: _match_col(cols, v) for k, v in _COLMAPS.items()}
            if pick.get("cod_proc"):
                df_demo = _apply_manual_map(df_raw, pick)
                df_demo = tratar_codigo_glosa(df_demo)
                parts.append(df_demo)
                continue
        except:
            pass
        # 4) wizard
        with st.expander(f"⚙️ Mapear manualmente: {fname}", expanded=True):
            df_manual = _mapping_wizard_for_demo(f)
            if df_manual is not None:
                parts.append(df_manual)
            else:
                st.error(f"Não foi possível mapear o demonstrativo '{fname}'.")
    if parts:
        return pd.concat(parts, ignore_index=True)
    return pd.DataFrame()

