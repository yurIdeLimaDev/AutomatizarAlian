"""Browser adapter. Business modules under pp/files remain unchanged.

Only orchestration from the two Streamlit views lives here; the browser's
in-memory filesystem replaces TemporaryDirectory on the server.
"""
import gc
import json
from dataclasses import asdict
from pathlib import Path

from pdf_parser import extract_negative_commission_records
from xlsx_parser import extract_client_vendor_pairs
from matcher import match_records
from vendor_sales_counter import count_sales_per_vendor_month
from report_builder import build_report, _calculate_vendor_values
from estorno_suelane.xlsx_parser_suelane import extract_client_vendor_pairs_suelane
from estorno_suelane.matcher_suelane import match_records_suelane, get_valor_estorno
from estorno_suelane.report_builder_suelane import build_report_suelane, analyze_record_suelane


def deduplicate(existing, incoming):
    """Same cross-file policy as old_view.render / new_view._dedupe_pdf_records."""
    for rec in incoming:
        index = next((i for i, old in enumerate(existing)
                      if old.segurado.upper() == rec.segurado.upper()
                      and old.inicio_vig == rec.inicio_vig
                      and (old.apolice == rec.apolice or not old.apolice or not rec.apolice)), -1)
        if index < 0:
            existing.append(rec)
        elif not existing[index].apolice and rec.apolice:
            existing[index] = rec


def protect_spreadsheet_text(path, mode):
    """Untrusted strings beginning '=' must stay text; preserve the TOTAL formula."""
    import openpyxl
    wb = openpyxl.load_workbook(path)
    main = wb.worksheets[0]
    total = (main.title, main.max_row, 7 if mode == 'suelane' else 6)
    changed = False
    for sheet in wb:
        for row in sheet:
            for cell in row:
                if cell.data_type == 'f' and (sheet.title, cell.row, cell.column) != total:
                    cell.data_type = 's'
                    changed = True
    if changed:
        wb.save(path)
    wb.close()


def process(manifest_json, progress=lambda message: None):
    manifest = json.loads(manifest_json)
    mode = manifest['mode']
    if mode not in ('old', 'suelane'):
        raise ValueError('Fluxo inválido.')
    pdfs, sheets = manifest['pdfs'], manifest['sheets']
    if not pdfs or not sheets:
        raise ValueError('Selecione ao menos um PDF e uma planilha.')
    pdf_records, xlsx_records, warnings = [], [], []
    for index, file in enumerate(pdfs):
        progress(f"Lendo PDF {index + 1} de {len(pdfs)}: {file['name']}")
        try:
            records = extract_negative_commission_records(file['path'])
        except Exception as exc:
            raise ValueError(f"Não foi possível ler o PDF '{file['name']}'. Verifique se está íntegro e sem senha.") from exc
        deduplicate(pdf_records, records)
        if not records:
            warnings.append(f"PDF '{file['name']}': nenhum registro com comissão negativa identificado. PDFs digitalizados como imagem precisam de texto pesquisável.")
        gc.collect()
    parser = extract_client_vendor_pairs_suelane if mode == 'suelane' else extract_client_vendor_pairs
    for index, file in enumerate(sheets):
        progress(f"Lendo planilha {index + 1} de {len(sheets)}: {file['name']}")
        try:
            records, messages = parser(file['path'])
        except Exception as exc:
            raise ValueError(f"Não foi possível ler a planilha '{file['name']}'. Verifique o formato XLS/XLSX, a integridade e a proteção por senha.") from exc
        xlsx_records.extend(records)
        warnings.extend(messages)
        gc.collect()
    progress('Cruzando nomes e apólices…')
    matcher = match_records_suelane if mode == 'suelane' else match_records
    matched, not_found = matcher(pdf_records, xlsx_records)
    counts = count_sales_per_vendor_month(xlsx_records) if mode == 'old' else {}
    anomalies = sum(analyze_record_suelane(r)[1] for r in matched) if mode == 'suelane' else sum(r.match_type != 'EXATO' for r in matched)
    values = [get_valor_estorno(r) for r in matched] if mode == 'suelane' else _calculate_vendor_values(matched, counts)
    filename = 'estornos_suelane.xlsx' if mode == 'suelane' else 'controle_estornos.xlsx'
    output = str(Path(manifest['output_dir']) / filename)
    if matched:
        progress('Gerando e conferindo a planilha…')
        if mode == 'suelane':
            build_report_suelane(matched, output, not_found=not_found)
        else:
            build_report(matched, output, not_found=not_found, vendor_sales_counts=counts)
        protect_spreadsheet_text(output, mode)
    return json.dumps({
        'filename': filename, 'output': output if matched else None,
        'pdfCount': len(pdf_records), 'spreadsheetCount': len(xlsx_records),
        'matchedCount': len(matched), 'anomalies': anomalies,
        'total': sum(v for v in values if v is not None),
        'warnings': warnings, 'notFound': [asdict(r) for r in not_found],
        'pdfRecords': [asdict(r) for r in pdf_records],
        'spreadsheetRecords': [asdict(r) for r in xlsx_records],
        'matchedRecords': [asdict(r) for r in matched],
    }, ensure_ascii=False, allow_nan=False)
