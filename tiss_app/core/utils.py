
# -*- coding: utf-8 -*-
"""
core/utils.py
Utilitários e constantes compartilhadas por todo o app.

ATENÇÃO:
- As funções aqui foram copiadas do app original, sem alterar lógica interna.
- Inclui helpers de moeda, normalização, datas e persistência de mapeamentos.
"""

from __future__ import annotations

import os
import re
import json
import unicodedata
from pathlib import Path
from typing import Optional, Union, List, Dict
from decimal import Decimal
from datetime import datetime

import pandas as pd
import streamlit as st

# =========================================================
# Constantes e utilitários gerais (copiados do arquivo original)
# =========================================================
ANS_NS = {'ans': 'http://www.ans.gov.br/padroes/tiss/schemas'}
DEC_ZERO = Decimal('0')

MAP_FILE = "demo_mappings.json"


def dec(txt: Optional[str]) -> Decimal:
    if txt is None:
        return DEC_ZERO
    s = str(txt).strip().replace(',', '.')
    return Decimal(s) if s else DEC_ZERO


def tx(el) -> str:
    return (el.text or '').strip() if (el is not None and getattr(el, "text", None)) else ''


def f_currency(v: Union[int, float, Decimal, str]) -> str:
    try:
        v = float(v)
    except Exception:
        v = 0.0
    neg = v < 0
    v = abs(v)
    inteiro = int(v)
    cent = int(round((v - inteiro) * 100))
    s = f"R$ {inteiro:,}".replace(",", ".") + f",{cent:02d}"
    return f"-{s}" if neg else s


def apply_currency(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    d = df.copy()
    for c in cols:
        if c in d.columns:
            d[c] = d[c].apply(f_currency)
    return d


def parse_date_flex(s: str) -> Optional[datetime]:
    if s is None or not isinstance(s, str):
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def normalize_code(s: str, strip_zeros: bool = False) -> str:
    if s is None:
        return ""
    s2 = re.sub(r'[\.\-_/ \t]', '', str(s)).strip()
    return s2.lstrip('0') if strip_zeros else s2


def _normtxt(s: str) -> str:
    s = str(s or "")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower().strip()
    return re.sub(r"\s+", " ", s)


def categorizar_motivo_ans(codigo: str) -> str:
    codigo = str(codigo).strip()
    if codigo in ['1001','1002','1003','1006','1009']: return "Cadastro/Elegibilidade"
    if codigo in ['1201','1202','1205','1209']: return "Autorização/SADT"
    if codigo in ['1801','1802','1805','1806']: return "Tabela/Preços"
    if codigo.startswith('20') or codigo.startswith('22'): return "Auditoria Médica/Técnica"
    if codigo in ['2501','2505','2509']: return "Documentação/Físico"
    return "Outros/Administrativa"


def load_demo_mappings() -> dict:
    if os.path.exists(MAP_FILE):
        try:
            with open(MAP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_demo_mappings(mappings: dict):
    try:
        with open(MAP_FILE, "w", encoding="utf-8") as f:
            json.dump(mappings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        # Mantido do código original
        st.error(f"Erro ao salvar mapeamentos: {e}")

