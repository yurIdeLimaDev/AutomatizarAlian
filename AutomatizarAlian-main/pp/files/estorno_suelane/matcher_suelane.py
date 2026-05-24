"""
Responsabilidade: cruzar PDFRecords (com comissao negativa) com os
XLSXRecordSuelane lidos do XLSX, reaproveitando integralmente a logica
fuzzy/exata do matcher antigo (matcher.py).

Como XLSXRecordSuelane expoe os mesmos atributos que XLSXRecord
(cliente, vendedor, sheet_name, apolice), passamos os registros estendidos
diretamente para match_records via duck typing. Em seguida, enriquecemos
cada MatchedRecord com os valores de comissao (corretora/vendedor)
encontrados na planilha.
"""

import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

from matcher import MatchedRecord, match_records  # noqa: E402
from pdf_parser import PDFRecord  # noqa: E402

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


def _is_suelane(vendedor: str) -> bool:
    """Verdadeiro quando o vendedor eh exatamente SUELANE (case insensitive)."""
    return vendedor.strip().upper() == "SUELANE"


def _build_lookup(
    xlsx_records: List[XLSXRecordSuelane],
) -> Dict[Tuple[str, str, str, str], XLSXRecordSuelane]:
    """
    Indice para recuperar o XLSXRecordSuelane original a partir dos campos
    presentes no MatchedRecord.
    """
    lookup: Dict[Tuple[str, str, str, str], XLSXRecordSuelane] = {}
    for rec in xlsx_records:
        key = (
            rec.cliente.upper().strip(),
            rec.sheet_name,
            rec.apolice,
            rec.vendedor.upper().strip(),
        )
        # Primeira ocorrencia tem prioridade (consistente com o matcher antigo)
        lookup.setdefault(key, rec)
    return lookup


def get_valor_estorno(record: MatchedRecordSuelane) -> Optional[float]:
    """
    Retorna o valor de estorno aplicavel: COM CORRETORA se vendedor for
    SUELANE, caso contrario COMISSAO VEND. Pode ser None se nao havia
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


def match_records_suelane(
    pdf_records: List[PDFRecord],
    xlsx_records: List[XLSXRecordSuelane],
) -> Tuple[List[MatchedRecordSuelane], List[PDFRecord]]:
    """
    Cruza PDF x XLSX usando o matcher antigo (sem alteracoes) e enriquece
    cada match com os valores de comissao corretora/vendedor.
    """
    matched, not_found = match_records(pdf_records, xlsx_records)

    lookup = _build_lookup(xlsx_records)

    enriched: List[MatchedRecordSuelane] = []
    for m in matched:
        key = (
            m.segurado.upper().strip(),
            m.sheet_name,
            m.apolice_xlsx,
            m.vendedor.upper().strip(),
        )
        xlsx_orig = lookup.get(key)

        if xlsx_orig is None:
            # Fallback: tenta sem apolice (matches fuzzy podem ter normalizacoes diferentes)
            for k, v in lookup.items():
                if (
                    k[1] == m.sheet_name
                    and k[3] == m.vendedor.upper().strip()
                    and v.cliente.upper().strip() == m.segurado.upper().strip()
                ):
                    xlsx_orig = v
                    break

        if xlsx_orig is None:
            # Ultimo fallback: por sheet+vendedor+apolice
            for k, v in lookup.items():
                if (
                    k[1] == m.sheet_name
                    and k[2] == m.apolice_xlsx
                    and k[3] == m.vendedor.upper().strip()
                ):
                    xlsx_orig = v
                    break

        com_corretora = xlsx_orig.com_corretora if xlsx_orig else None
        com_vendedor = xlsx_orig.com_vendedor if xlsx_orig else None

        enriched.append(
            MatchedRecordSuelane(
                segurado=m.segurado,
                inicio_vig=m.inicio_vig,
                vendedor=m.vendedor,
                match_type=m.match_type,
                apolice_pdf=m.apolice_pdf,
                apolice_xlsx=m.apolice_xlsx,
                sheet_name=m.sheet_name,
                com_corretora=com_corretora,
                com_vendedor=com_vendedor,
            )
        )

    return enriched, not_found
