"""
Responsabilidade: extrair registros (cliente, vendedor, apolice, com_corretora,
comissao_vend) do XLSX de comissoes.

Diferencas em relacao ao xlsx_parser do sistema antigo:
  - NAO exclui o vendedor SUELANE (ele eh necessario para o novo fluxo)
  - Tambem captura as colunas:
        * COM CORRETORA / COMISSAO CORRETORA   (varias variantes)
        * COMISSAO VEND / COMISSAO VENDEDOR    (varias variantes)
    Estas colunas sao detectadas no cabecalho com normalizacao para
    aguentar acentuacao diferente e pequenos erros de digitacao.
"""

import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pandas as pd


# Permite importar modulos do diretorio pai (files/) sem alterar nada la.
_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)


_APOLICE_KEYWORDS = [
    "APOLICE",
    "N APOLICE",
    "NUMERO DA APOLICE",
    "N DA APOLICE",
]

# Palavras-chave normalizadas (sem acento, sem pontuacao) para identificar a
# coluna do valor de comissao da CORRETORA.
_COM_CORRETORA_KEYWORDS = [
    "COM CORRETORA",
    "COMISSAO CORRETORA",
    "COMISSAO DA CORRETORA",
    "COM DA CORRETORA",
    "COMIS CORRETORA",
    "VALOR CORRETORA",
    "VLR CORRETORA",
    "CORRETORA",
]

# Palavras-chave normalizadas para identificar a coluna do valor de comissao
# do VENDEDOR.
_COM_VENDEDOR_KEYWORDS = [
    "COMISSAO VEND",
    "COMISSAO VENDEDOR",
    "COMISSAO DO VENDEDOR",
    "COM VEND",
    "COM VENDEDOR",
    "COMIS VEND",
    "COMIS VENDEDOR",
    "VALOR VENDEDOR",
    "VLR VENDEDOR",
    "VALOR VEND",
]


@dataclass(frozen=True)
class XLSXRecordSuelane:
    cliente: str
    vendedor: str
    sheet_name: str
    apolice: str
    com_corretora: Optional[float]
    com_vendedor: Optional[float]


def _strip_accents_upper(text: str) -> str:
    """Remove acentos, converte para maiusculas e colapsa espacos."""
    if text is None:
        return ""
    decomposed = unicodedata.normalize("NFD", str(text))
    no_diac = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    cleaned = re.sub(r"[^A-Za-z0-9\s]", " ", no_diac)
    return " ".join(cleaned.upper().split())


def _normalize_apolice(raw: str) -> str:
    if not raw:
        return ""
    return re.sub(r"[\s.\-/]", "", str(raw).strip())


def _parse_br_money(value) -> Optional[float]:
    """
    Converte um valor de celula (string ou numero) para float.
    Aceita formato brasileiro (1.234,56), americano (1234.56), com R$ etc.
    Retorna None se nao for parseavel.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and pd.isna(value):
            return None
        return float(value)

    raw = str(value).strip()
    if not raw or raw.upper() in {"NAN", "NONE", "-", "--"}:
        return None

    # Remove simbolos comuns de moeda e espacos
    cleaned = re.sub(r"[Rr]\$\s*", "", raw)
    cleaned = cleaned.replace(" ", "")

    # Detecta negativo entre parenteses (1.234,56) -> -1234.56
    negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        negative = True
        cleaned = cleaned[1:-1]

    has_comma = "," in cleaned
    has_dot = "." in cleaned

    if has_comma and has_dot:
        # Assume formato brasileiro: ponto = milhar, virgula = decimal
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif has_comma:
        cleaned = cleaned.replace(",", ".")
    # senao mantem como esta

    try:
        result = float(cleaned)
    except ValueError:
        return None

    return -result if negative else result


def _match_keyword(cell_norm: str, keywords: List[str]) -> bool:
    """Retorna True se alguma keyword aparece em cell_norm."""
    for kw in keywords:
        if kw in cell_norm:
            return True
    return False


def _find_header_row(
    df: pd.DataFrame,
) -> Tuple[
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
]:
    """
    Procura a linha do cabecalho que contem CLIENTE e VENDEDOR.

    Retorna:
        (row_idx, cliente_col, vendedor_col, apolice_col,
         com_corretora_col, com_vendedor_col)
    Colunas opcionais podem ser None.
    """
    for row_idx, row in df.iterrows():
        normalized_cells = [_strip_accents_upper(v) for v in row]

        if "CLIENTE" not in normalized_cells or "VENDEDOR" not in normalized_cells:
            continue

        cliente_col = normalized_cells.index("CLIENTE")
        vendedor_col = normalized_cells.index("VENDEDOR")

        apolice_col: Optional[int] = None
        com_corretora_col: Optional[int] = None
        com_vendedor_col: Optional[int] = None

        for col_idx, cell_norm in enumerate(normalized_cells):
            if not cell_norm:
                continue
            if col_idx in (cliente_col, vendedor_col):
                continue

            if apolice_col is None and _match_keyword(cell_norm, _APOLICE_KEYWORDS):
                apolice_col = col_idx
                continue

            # Para COM CORRETORA: precisa conter CORRETORA (mais especifico que VEND)
            if com_corretora_col is None and _match_keyword(
                cell_norm, _COM_CORRETORA_KEYWORDS
            ):
                com_corretora_col = col_idx
                continue

            if com_vendedor_col is None and _match_keyword(
                cell_norm, _COM_VENDEDOR_KEYWORDS
            ):
                com_vendedor_col = col_idx
                continue

        return (
            row_idx,
            cliente_col,
            vendedor_col,
            apolice_col,
            com_corretora_col,
            com_vendedor_col,
        )

    return None, None, None, None, None, None


def _extract_records_from_sheet(
    df: pd.DataFrame, sheet_name: str
) -> Tuple[List[XLSXRecordSuelane], Optional[str]]:
    (
        header_row_idx,
        cliente_col,
        vendedor_col,
        apolice_col,
        com_corretora_col,
        com_vendedor_col,
    ) = _find_header_row(df)

    if header_row_idx is None:
        return [], (
            f"Aba '{sheet_name}': cabecalho CLIENTE/VENDEDOR nao encontrado "
            f"- aba ignorada."
        )

    warnings_extras = []
    if com_corretora_col is None:
        warnings_extras.append("coluna COM CORRETORA nao encontrada")
    if com_vendedor_col is None:
        warnings_extras.append("coluna COMISSAO VENDEDOR nao encontrada")

    records: List[XLSXRecordSuelane] = []

    for _, row in df.iloc[header_row_idx + 1 :].iterrows():
        cliente_val = row.iloc[cliente_col]
        vendedor_val = row.iloc[vendedor_col]

        if pd.isna(cliente_val) or pd.isna(vendedor_val):
            continue

        cliente_str = str(cliente_val).strip()
        vendedor_str = str(vendedor_val).strip()

        if not cliente_str or not vendedor_str:
            continue

        # NAO excluimos SUELANE aqui (este eh o ponto central da feature).

        apolice_str = ""
        if apolice_col is not None:
            apolice_val = row.iloc[apolice_col]
            if pd.notna(apolice_val):
                if isinstance(apolice_val, float) and apolice_val.is_integer():
                    raw_str = str(int(apolice_val))
                else:
                    raw_str = str(apolice_val).strip()
                apolice_str = _normalize_apolice(raw_str)

        com_corretora_val: Optional[float] = None
        if com_corretora_col is not None:
            com_corretora_val = _parse_br_money(row.iloc[com_corretora_col])

        com_vendedor_val: Optional[float] = None
        if com_vendedor_col is not None:
            com_vendedor_val = _parse_br_money(row.iloc[com_vendedor_col])

        records.append(
            XLSXRecordSuelane(
                cliente=cliente_str,
                vendedor=vendedor_str,
                sheet_name=sheet_name,
                apolice=apolice_str,
                com_corretora=com_corretora_val,
                com_vendedor=com_vendedor_val,
            )
        )

    warning_msg = None
    if warnings_extras:
        warning_msg = (
            f"Aba '{sheet_name}': " + ", ".join(warnings_extras) +
            " - linhas serao marcadas para verificacao."
        )

    return records, warning_msg


def extract_client_vendor_pairs_suelane(
    xlsx_path: str,
) -> Tuple[List[XLSXRecordSuelane], List[str]]:
    """
    Le todas as abas do XLSX e retorna (registros, lista_de_avisos).
    Inclui o vendedor SUELANE e captura colunas de comissao da corretora e
    do vendedor.
    """
    all_records: List[XLSXRecordSuelane] = []
    warnings: List[str] = []

    xl = pd.ExcelFile(xlsx_path)

    for sheet_name in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet_name, header=None, dtype=object)
        records, warning = _extract_records_from_sheet(df, sheet_name)
        all_records.extend(records)
        if warning:
            warnings.append(warning)

    return all_records, warnings
