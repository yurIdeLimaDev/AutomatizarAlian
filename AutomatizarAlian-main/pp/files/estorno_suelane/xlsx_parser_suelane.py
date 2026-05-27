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
from decimal import Decimal, InvalidOperation
from numbers import Integral, Real
from typing import List, Optional, Tuple

import pandas as pd


# Permite importar modulos do diretorio pai (files/) sem alterar nada la.
_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)


_APOLICE_EXACT_HEADERS = {
    "APOLICE",
    "N APOLICE",
    "N DA APOLICE",
    "NUM APOLICE",
    "NR APOLICE",
    "NRO APOLICE",
    "NUMERO APOLICE",
    "NUMERO DA APOLICE",
}

_APOLICE_EXCLUDED_TERMS = {
    "ANTERIOR",
    "ANTIGA",
    "CANCELADA",
    "VENCIDA",
}

_CLIENTE_HEADERS = {
    "CLIENTE",
    "SEGURADO",
    "NOME CLIENTE",
    "NOME DO CLIENTE",
    "CLIENTE SEGURADO",
    "SEGURADO CLIENTE",
    "NOME SEGURADO",
    "NOME DO SEGURADO",
}

_VENDEDOR_HEADERS = {
    "VENDEDOR",
    "VEND",
    "VENDEDOR RESPONSAVEL",
    "RESPONSAVEL VENDA",
    "CONSULTOR",
    "CORRETOR",
}

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
    com_corretora_col_found: bool = True
    com_vendedor_col_found: bool = True


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
    return re.sub(r"[\s.,\-/]", "", str(raw).strip())


def _format_decimal_apolice(value: Decimal) -> str:
    fixed = format(value, "f")
    if "." in fixed:
        int_part, frac_part = fixed.split(".", 1)
        if set(frac_part) <= {"0"}:
            return int_part
        return f"{int_part}.{frac_part.rstrip('0')}"
    return fixed


def _stringify_apolice(value) -> str:
    """
    Converte a celula de apolice para texto antes da normalizacao.

    Evita o bug comum em que valores numericos vindos do Excel aparecem como
    "12345.0" ou "1.2345E+5" e viram "123450" apos remover pontuacao.
    """
    if value is None or pd.isna(value):
        return ""

    if isinstance(value, Integral) and not isinstance(value, bool):
        return str(value)

    if isinstance(value, Real) and not isinstance(value, bool):
        numeric = float(value)
        if pd.isna(numeric):
            return ""
        try:
            return _format_decimal_apolice(Decimal(str(numeric)))
        except InvalidOperation:
            return str(value).strip()

    raw = str(value).strip().lstrip("'")
    if not raw:
        return ""

    br_grouped_zero_match = re.fullmatch(r"(\d{1,3}(?:\.\d{3})+),0+", raw)
    if br_grouped_zero_match:
        return br_grouped_zero_match.group(1).replace(".", "")

    us_grouped_zero_match = re.fullmatch(r"(\d{1,3}(?:,\d{3})+)\.0+", raw)
    if us_grouped_zero_match:
        return us_grouped_zero_match.group(1).replace(",", "")

    decimal_zero_match = re.fullmatch(r"(\d+)[.,]0+", raw)
    if decimal_zero_match:
        return decimal_zero_match.group(1)

    sci_match = re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?[Ee][+-]?\d+", raw)
    if sci_match:
        try:
            return _format_decimal_apolice(Decimal(raw.replace(",", ".")))
        except InvalidOperation:
            return raw

    return raw


def _parse_br_money(value) -> Optional[float]:
    """
    Converte um valor de celula (string ou numero) para float.
    Aceita formato brasileiro (1.234,56), americano (1234.56), com R$ etc.
    Retorna None se nao for parseavel.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and pd.isna(value):
            return None
        return float(value)

    raw = str(value).strip()
    if not raw or raw.upper() in {"NAN", "NONE", "-", "--"}:
        return None

    # Remove simbolos comuns de moeda e qualquer espaco unicode.
    cleaned = re.sub(r"[Rr]\$\s*", "", raw)
    cleaned = re.sub(r"\s+", "", cleaned)

    # Detecta negativo entre parenteses (1.234,56) -> -1234.56
    negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        negative = True
        cleaned = cleaned[1:-1]
    elif len(cleaned) > 1 and cleaned.endswith("-"):
        negative = True
        cleaned = cleaned[:-1]

    has_comma = "," in cleaned
    has_dot = "." in cleaned

    if has_comma and has_dot:
        if cleaned.rfind(",") > cleaned.rfind("."):
            # Formato brasileiro: ponto = milhar, virgula = decimal.
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # Formato americano textual: virgula = milhar, ponto = decimal.
            cleaned = cleaned.replace(",", "")
    elif has_comma:
        cleaned = cleaned.replace(",", ".")
    elif has_dot:
        parts = cleaned.split(".")
        if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]):
            # "1.234" em planilha brasileira normalmente eh milhar, nao decimal.
            cleaned = "".join(parts)
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


def _apolice_header_score(cell_norm: str) -> int:
    if "APOLICE" not in cell_norm:
        return 0
    if any(term in cell_norm for term in _APOLICE_EXCLUDED_TERMS):
        return 0
    if cell_norm in _APOLICE_EXACT_HEADERS:
        return 100
    for header in _APOLICE_EXACT_HEADERS:
        if header != "APOLICE" and header in cell_norm:
            return 80
    return 10


def _find_header_col(
    normalized_cells: List[str],
    accepted_headers: set[str],
) -> Optional[int]:
    for col_idx, cell_norm in enumerate(normalized_cells):
        if cell_norm in accepted_headers:
            return col_idx
    return None


def _is_com_corretora_header(cell_norm: str) -> bool:
    if "CORRETORA" not in cell_norm:
        return False
    if any(term in cell_norm for term in ("VEND CORRETORA", "VENDEDOR CORRETORA")):
        return False
    return _match_keyword(cell_norm, _COM_CORRETORA_KEYWORDS)


def _is_com_vendedor_header(cell_norm: str) -> bool:
    if "CORRETORA" in cell_norm:
        return False
    return _match_keyword(cell_norm, _COM_VENDEDOR_KEYWORDS)


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

        cliente_col = _find_header_col(normalized_cells, _CLIENTE_HEADERS)
        vendedor_col = _find_header_col(normalized_cells, _VENDEDOR_HEADERS)

        if cliente_col is None or vendedor_col is None:
            continue

        apolice_col: Optional[int] = None
        apolice_score = 0
        com_corretora_col: Optional[int] = None
        com_vendedor_col: Optional[int] = None

        for col_idx, cell_norm in enumerate(normalized_cells):
            if not cell_norm:
                continue
            if col_idx in (cliente_col, vendedor_col):
                continue

            current_apolice_score = _apolice_header_score(cell_norm)
            if current_apolice_score > apolice_score:
                apolice_col = col_idx
                apolice_score = current_apolice_score

            if com_corretora_col is None and _is_com_corretora_header(cell_norm):
                com_corretora_col = col_idx
                continue

            if com_vendedor_col is None and _is_com_vendedor_header(cell_norm):
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
                apolice_str = _normalize_apolice(_stringify_apolice(apolice_val))

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
                com_corretora_col_found=com_corretora_col is not None,
                com_vendedor_col_found=com_vendedor_col is not None,
            )
        )

    warning_msg = None
    if warnings_extras:
        warning_msg = (
            f"Aba '{sheet_name}': " + ", ".join(warnings_extras) +
            " - linhas que dependerem dessas colunas serao marcadas para verificacao."
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
