"""
Responsabilidade: cruzar PDFRecords (com comissao negativa) com os
XLSXRecordSuelane lidos do XLSX.

O fluxo reaproveita a logica de matching do sistema antigo, mas preserva a
referencia direta ao registro XLSX encontrado. Isso evita lookups/fallbacks por
chaves incompletas que podem copiar valores de comissao de outro cliente.
"""

import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Tuple


_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

from matcher import _build_xlsx_index, _compare_apolice, _eval_match_type  # noqa: E402
from name_normalizer import names_match, normalize_name  # noqa: E402
from pdf_parser import PDFRecord  # noqa: E402
from thefuzz import fuzz  # noqa: E402

from estorno_suelane.xlsx_parser_suelane import XLSXRecordSuelane


@dataclass(frozen=True)
class MatchedRecordSuelane:
    segurado: str
    inicio_vig: str
    vendedor: str
    match_type: str
    apolice_pdf: str
    apolice_xlsx: str
    sheet_name: str
    com_corretora: Optional[float]
    com_vendedor: Optional[float]
    com_corretora_col_found: bool = True
    com_vendedor_col_found: bool = True
    cliente_xlsx: str = ""
    xlsx_duplicate_count: int = 1
    xlsx_duplicate_value_conflict: bool = False


def _normalize_text_key(value: str) -> str:
    if value is None:
        return ""
    decomposed = unicodedata.normalize("NFD", str(value))
    no_diac = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    cleaned = re.sub(r"[^A-Za-z0-9\s]", " ", no_diac)
    return " ".join(cleaned.upper().split())


def _is_suelane(vendedor: str) -> bool:
    """
    Verdadeiro quando o vendedor eh exatamente SUELANE apos normalizacao.

    Permite caixa diferente, acento acidental, pontuacao final e espacos extras,
    mas nao considera variacoes como "SUELANE J" como a vendedora Suelane.
    """
    return _normalize_text_key(vendedor) == "SUELANE"


def get_valor_estorno(record: MatchedRecordSuelane) -> Optional[float]:
    """
    Retorna o valor de estorno aplicavel: COM CORRETORA se vendedor for
    SUELANE, caso contrario COMISSAO VENDEDOR. Pode ser None se nao havia
    valor extraivel na planilha.
    """
    if _is_suelane(record.vendedor):
        return record.com_corretora
    return record.com_vendedor


def get_coluna_origem(record: MatchedRecordSuelane) -> str:
    """Nome amigavel da coluna usada como fonte do valor."""
    if _is_suelane(record.vendedor):
        return "COM CORRETORA"
    return "COMISSAO VENDEDOR"


def is_coluna_origem_encontrada(record: MatchedRecordSuelane) -> bool:
    """Indica se a coluna fonte do valor existia na aba de origem."""
    if _is_suelane(record.vendedor):
        return record.com_corretora_col_found
    return record.com_vendedor_col_found


def _match_source_key(rec: XLSXRecordSuelane) -> tuple[str, str, str, str]:
    return (
        normalize_name(rec.cliente or ""),
        _normalize_text_key(rec.vendedor or ""),
        rec.sheet_name or "",
        rec.apolice or "",
    )


def _value_signature(rec: XLSXRecordSuelane) -> tuple:
    return (
        rec.com_corretora,
        rec.com_vendedor,
        rec.com_corretora_col_found,
        rec.com_vendedor_col_found,
    )


def _duplicate_info(
    xlsx_records: List[XLSXRecordSuelane],
    target: XLSXRecordSuelane,
) -> tuple[int, bool]:
    target_key = _match_source_key(target)
    count = 0
    value_signatures = set()

    for rec in xlsx_records:
        if _match_source_key(rec) != target_key:
            continue
        count += 1
        value_signatures.add(_value_signature(rec))

    return count, len(value_signatures) > 1


def _dedupe_matches(
    matches: List[Tuple[XLSXRecordSuelane, str]],
) -> List[Tuple[XLSXRecordSuelane, str]]:
    """
    Remove apenas duplicatas identicas de origem.

    Mantem linhas distintas por vendedor/aba/apolice, que no fluxo Suelane
    precisam virar linhas separadas no relatorio.
    """
    deduped: List[Tuple[XLSXRecordSuelane, str]] = []
    seen = set()
    for rec, match_type in matches:
        key = (*_match_source_key(rec), match_type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((rec, match_type))
    return deduped


def _filter_best_matches_suelane(
    matches: List[Tuple[XLSXRecordSuelane, str]],
) -> List[Tuple[XLSXRecordSuelane, str]]:
    """
    Mantem a logica do matcher antigo, com uma diferenca importante:
    multiplos matches EXATO ou FUZZY com apolice batendo nao sao descartados
    no fluxo Suelane.
    """
    if len(matches) <= 1:
        return matches

    exact_matches = [m for m in matches if m[1] == "EXATO"]
    if exact_matches:
        return _dedupe_matches(exact_matches)

    fuzzy_exact_apolice_matches = [m for m in matches if m[1] == "FUZZY"]
    if fuzzy_exact_apolice_matches:
        out = _dedupe_matches(fuzzy_exact_apolice_matches)
        out.extend(
            _dedupe_matches(
                [m for m in matches if m[1] not in ("EXATO", "FUZZY")]
            )
        )
        return out

    return _dedupe_matches(matches)


def _find_matches_for_segurado_suelane(
    pdf_rec: PDFRecord,
    normalized_segurado: str,
    index,
    all_xlsx_records: List[XLSXRecordSuelane],
) -> List[Tuple[XLSXRecordSuelane, str]]:
    """
    Replica o matcher antigo, mas usa o desempate seguro para o fluxo Suelane.
    """
    matches: List[Tuple[XLSXRecordSuelane, str]] = []

    exact = index.get(normalized_segurado)
    if exact:
        for rec in exact:
            match_type = _eval_match_type(
                normalized_segurado,
                pdf_rec.apolice,
                normalize_name(rec.cliente),
                rec.apolice,
                True,
            )
            matches.append((rec, match_type))
        return _filter_best_matches_suelane(matches)

    for normalized_client, records in index.items():
        if names_match(normalized_segurado, normalized_client):
            for rec in records:
                match_type = _eval_match_type(
                    normalized_segurado,
                    pdf_rec.apolice,
                    normalized_client,
                    rec.apolice,
                    True,
                )
                matches.append((rec, match_type))
            return _filter_best_matches_suelane(matches)

    best_score_apolice_match = 0
    best_records_apolice_match: List[XLSXRecordSuelane] = []

    best_score_no_apolice = 0
    best_records_no_apolice: List[XLSXRecordSuelane] = []

    for rec in all_xlsx_records:
        norm_client = normalize_name(rec.cliente)
        score = fuzz.token_sort_ratio(normalized_segurado, norm_client)

        if score > 85:
            apolice_matches = _compare_apolice(pdf_rec.apolice, rec.apolice)
            if apolice_matches:
                if score > best_score_apolice_match:
                    best_score_apolice_match = score
                    best_records_apolice_match = [rec]
                elif score == best_score_apolice_match:
                    best_records_apolice_match.append(rec)
            elif score > 92:
                if score > best_score_no_apolice:
                    best_score_no_apolice = score
                    best_records_no_apolice = [rec]
                elif score == best_score_no_apolice:
                    best_records_no_apolice.append(rec)

    for rec in best_records_apolice_match:
        match_type = _eval_match_type(
            normalized_segurado,
            pdf_rec.apolice,
            normalize_name(rec.cliente),
            rec.apolice,
            False,
        )
        matches.append((rec, match_type))

    for rec in best_records_no_apolice:
        match_type = _eval_match_type(
            normalized_segurado,
            pdf_rec.apolice,
            normalize_name(rec.cliente),
            rec.apolice,
            False,
        )
        matches.append((rec, match_type))

    if matches:
        return _filter_best_matches_suelane(matches)

    return matches


def match_records_suelane(
    pdf_records: List[PDFRecord],
    xlsx_records: List[XLSXRecordSuelane],
) -> tuple[List[MatchedRecordSuelane], List[PDFRecord]]:
    """
    Cruza PDF x XLSX usando a mesma logica do matcher antigo e enriquece
    cada match com os valores de comissao corretora/vendedor.

    O XLSXRecordSuelane encontrado pela logica de match eh usado diretamente.
    Portanto, nao ha fallback por sheet/vendedor/apolice sem cliente.
    """
    index = _build_xlsx_index(xlsx_records)

    enriched: List[MatchedRecordSuelane] = []
    not_found: List[PDFRecord] = []

    for pdf_rec in pdf_records:
        normalized = normalize_name(pdf_rec.segurado or "")
        xlsx_matches = _find_matches_for_segurado_suelane(
            pdf_rec,
            normalized,
            index,
            xlsx_records,
        )

        if not xlsx_matches:
            not_found.append(pdf_rec)
            continue

        for xlsx_rec, match_type in xlsx_matches:
            duplicate_count, duplicate_value_conflict = _duplicate_info(
                xlsx_records,
                xlsx_rec,
            )
            enriched.append(
                MatchedRecordSuelane(
                    segurado=pdf_rec.segurado or "",
                    inicio_vig=pdf_rec.inicio_vig or "",
                    vendedor=xlsx_rec.vendedor or "",
                    match_type=match_type,
                    apolice_pdf=pdf_rec.apolice or "",
                    apolice_xlsx=xlsx_rec.apolice or "",
                    sheet_name=xlsx_rec.sheet_name or "",
                    com_corretora=xlsx_rec.com_corretora,
                    com_vendedor=xlsx_rec.com_vendedor,
                    com_corretora_col_found=xlsx_rec.com_corretora_col_found,
                    com_vendedor_col_found=xlsx_rec.com_vendedor_col_found,
                    cliente_xlsx=xlsx_rec.cliente or "",
                    xlsx_duplicate_count=duplicate_count,
                    xlsx_duplicate_value_conflict=duplicate_value_conflict,
                )
            )

    return enriched, not_found
