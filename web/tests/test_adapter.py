"""Behavioral checks for changes that intentionally live only in the web adapter."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pp/files'))
sys.path.insert(0, str(ROOT / 'web/python'))
import openpyxl
from browser_pipeline import deduplicate, protect_spreadsheet_text, process
from pdf_parser import PDFRecord
from matcher import MatchedRecord
from report_builder import build_report
import json
import pytest


def test_cross_file_dedupe_prefers_policy_and_preserves_distinct_policies():
    records = [PDFRecord('José', '01/04/2026', '')]
    deduplicate(records, [PDFRecord('JOSÉ', '01/04/2026', '12345'), PDFRecord('José', '01/04/2026', '67890'), PDFRecord('José', '01/04/2026', '')])
    assert [r.apolice for r in records] == ['12345', '67890']


def test_report_injection_is_literal_and_total_remains_a_formula(tmp_path):
    out = tmp_path / 'report.xlsx'
    record = MatchedRecord('=1+1', '01/04/2026', '=2+2', 'EXATO', '=3+3', '3', 'ABR 26')
    build_report([record], str(out))
    protect_spreadsheet_text(out, 'old')
    wb = openpyxl.load_workbook(out)
    assert wb.active['A3'].value == '=1+1'
    assert wb.active['A3'].data_type == 's'
    assert wb.active['D3'].data_type == 's'
    assert wb.active['E3'].data_type == 's'
    assert wb.active['F4'].value == '=SUM(F3:F3)'
    assert wb.active['F4'].data_type == 'f'


def test_corrupted_pdf_does_not_generate_partial_report(tmp_path):
    bad = tmp_path / 'bad.pdf'; bad.write_bytes(b'not a PDF')
    manifest = dict(mode='old', output_dir=str(tmp_path), pdfs=[dict(path=str(bad), name='corrompido.pdf')], sheets=[dict(path='unused.xlsx', name='planilha.xlsx')])
    with pytest.raises(ValueError, match='corrompido.pdf'):
        process(json.dumps(manifest))
    assert not list(tmp_path.glob('*.xlsx'))
