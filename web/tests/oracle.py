"""Independent native-Python reference using unchanged upstream modules.

Fixtures and snapshots stay outside the deployed site. Real client records must
never be printed to CI logs or committed in generated snapshots.
"""
import ast
import importlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pp/files'))
sys.path.insert(0, str(ROOT / 'web/python'))
from pdf_parser import extract_negative_commission_records
from xlsx_parser import extract_client_vendor_pairs
from matcher import match_records
from vendor_sales_counter import count_sales_per_vendor_month
from report_builder import build_report, _calculate_vendor_values
from estorno_suelane.xlsx_parser_suelane import extract_client_vendor_pairs_suelane
from estorno_suelane.matcher_suelane import match_records_suelane, get_valor_estorno
from estorno_suelane.report_builder_suelane import build_report_suelane, analyze_record_suelane

OUT = ROOT / 'web/tests/generated'
OUT.mkdir(parents=True, exist_ok=True)


def workbook_snapshot(path):
    import openpyxl
    wb = openpyxl.load_workbook(path)
    result = []
    for ws in wb:
        result.append({
            'name': ws.title, 'rows': ws.max_row, 'cols': ws.max_column,
            'widths': {k: d.width for k, d in ws.column_dimensions.items()},
            'cells': [{'coordinate': c.coordinate, 'value': c.value, 'type': c.data_type,
                       'format': c.number_format, 'font': str(c.font), 'fill': str(c.fill),
                       'alignment': str(c.alignment)} for row in ws for c in row],
        })
    wb.close()
    return result


def core_cases():
    from name_normalizer import normalize_name, names_match
    from matcher import _compare_apolice, _eval_match_type
    from estorno_suelane.xlsx_parser_suelane import _parse_br_money, _stringify_apolice, _normalize_apolice
    from thefuzz import fuzz
    names = ['José  da Conceição', 'JOSE DA CONCEICAO', 'Ana-Maria', 'ANA MARIA', 'MÁRCIA ÇÉLIA',
             'Marcia Celia', '', 'João', 'JOAO', 'A\u0301lvaro', 'MÜLLER', 'SUELANE J.', 'Suélane.',
             'MARIA SILVA SANTOS', 'MARIA SANTOS SILVA', 'MARIA SILVE SANTOS', 'MARIA SILVEIRA SANTOS',
             'FRANCISCO DE ASSIS OLIVEIRA', 'FRANCISCO ASSIS OLIVEIRA', 'ABCDEFG', 'ABCDEFH']
    policies = ['', '12345', '0012345', '99999', '123', '00123', '12A34', '00012A34']
    money = ['1.234,56', '1234,56', '1234.56', 'R$ 1.234,56', '(1.234,56)', '1234,56-',
             '1.234', '1,234.56', '0', '-10', '--', '', None, True, 0, -10, 1234.56]
    apolices = [12345, 12345.0, '12345.0', "'12345", '1.234,56', '1234.56', '1.234',
                '1.2345E+5', '00012345', '12.345,00', '12,345.00', '', None]
    norm = [normalize_name(n) for n in names]
    boundary_scores = [fuzz.token_sort_ratio('A' * n, 'A' * (n - k) + 'B' * k)
                       for n in range(10, 41) for k in range(1, 7)]
    assert all(threshold in boundary_scores for threshold in (85, 86, 92, 93))
    return {
        'boundaryScores': boundary_scores,
        'normalized': norm,
        'nameMatches': [[names_match(a, b) for b in norm] for a in norm],
        'scores': [[fuzz.token_sort_ratio(a, b) for b in norm] for a in norm],
        'policyMatches': [[_compare_apolice(a, b) for b in policies] for a in policies],
        'matchTypes': [_eval_match_type('', a, '', b, exact) for a in policies for b in policies for exact in [True, False]],
        'money': [_parse_br_money(m) for m in money],
        'policies': [_normalize_apolice(_stringify_apolice(a)) for a in apolices],
    }


def make_edge_fixtures():
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    import openpyxl
    import xlwt
    records = [
        ('JOSE DA CONCEICAO', '0012345', 'SUÉLANE.', 200, 30),
        ('MARIA SILVA SANTOS', '9000002', 'ELIDA', 150, -20),
        ('ANA LIMA', '9000003', 'ELIDA', 100, 0),
        ('PAULO SOUZA', '9000004', 'JOAO', 75, None),
        ('CARLA MELO', '9000005', 'JOAO', 60, 45),
        ('RICARDO SILVA', '9000006', 'MARIA', 30, 80),
        ('JOANA SILVA', '9000007', 'MARIA', 40, 90),
        ('CLIENTE INEXISTENTE', '9000008', 'ELIDA', 20, 50),
    ]
    pdf = OUT / 'edge.pdf'
    c = canvas.Canvas(str(pdf), pagesize=(900, 600))
    data = [['P/E', 'INICIO VIG', 'SEGURADO', 'APOLICE', 'COMISSAO']]
    data += [['P', '01/04/2026', n, a, '-10,00'] for n, a, *_ in records]
    data += [['P', '01/04/2026', records[0][0], records[0][1], '-10,00'], ['E', '01/04/2026', 'IGNORAR POSITIVO', '123', '10,00']]
    t = Table(data, colWidths=[35, 85, 250, 100, 80], rowHeights=24)
    t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('FONTNAME', (0, 0), (-1, -1), 'Helvetica')]))
    t.wrapOn(c, 600, 550); t.drawOn(c, 25, 200); c.save()
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'ABR 26'
    rows = [['CLIENTE', 'VENDEDOR', 'APOLICE ANTERIOR', 'Nº APOLICE', 'COM CORRETORA', 'COMISSAO VENDEDOR']]
    for n, a, v, corretora, vend in records[:-1]:
        n = 'JOSE DA CONCEIÇÃO' if n.startswith('JOSE') else n
        if n == 'MARIA SILVA SANTOS': n = 'MARIA SILVA SANTO'
        if n == 'CARLA MELO': a = '77777'
        if n == 'RICARDO SILVA': a = None
        rows.append([n, v, '11111', a, corretora, vend])
    rows.append(rows[1].copy()); conflict = rows[1].copy(); conflict[4] = 999; rows.append(conflict)
    # Numeric policy, missing commission column, same person in another vendor/sheet.
    rows.append(['JOSE DA CONCEICAO', 'SUELANE', '11111', 12345.0, 'R$ 1.234,56', 50])
    rows.append(['=HYPERLINK("https://example.invalid")', 'ELIDA', '', '999', 1, 1])
    for row in rows: ws.append(row)
    ws2 = wb.create_sheet('ABR 26 OUTRA'); ws2.append(['CLIENTE', 'VENDEDOR', 'APOLICE', 'COM CORRETORA']); ws2.append(['JOANA SILVA', 'MARIA', '9000007', 90])
    wb.create_sheet('SEM CABECALHO').append(['DADOS', 'OUTROS'])
    wb.save(OUT / 'edge.xlsx')
    old = xlwt.Workbook()
    for sheet in wb:
        target = old.add_sheet(sheet.title)
        for ri, row in enumerate(sheet.values):
            for ci, value in enumerate(row):
                if value is not None: target.write(ri, ci, value)
    old.save(str(OUT / 'edge.xls'))


def generate():
    make_edge_fixtures()
    # Read the actual Streamlit cross-file dedupe rather than importing its UI.
    source = ast.parse((ROOT / 'pp/files/estorno_suelane/new_view.py').read_text(encoding='utf-8'))
    nodes = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in ('_safe_upper', '_dedupe_pdf_records')]
    scope = {}; exec(compile(ast.Module(body=nodes, type_ignores=[]), 'original_view', 'exec'), scope)
    cases = [(f'cenario{i}', [ROOT / f'pp/tabelas teste/cenario{i}_pdf.pdf'], [ROOT / f'pp/tabelas teste/cenario{i}_xlsx.xlsx']) for i in range(1, 7)]
    cases += [('real', list((ROOT / 'pp/exemplo 2').glob('*.pdf')), list((ROOT / 'pp/exemplo 2').glob('*.xlsx'))),
              ('edge_xlsx', [OUT / 'edge.pdf'], [OUT / 'edge.xlsx']),
              ('edge_xls', [OUT / 'edge.pdf'], [OUT / 'edge.xls']),
              ('multiple', [OUT / 'edge.pdf', OUT / 'edge.pdf'], [OUT / 'edge.xlsx', OUT / 'edge.xls'])]
    all_results = []
    for name, pdfs, sheets in cases:
        for mode in ('old', 'suelane'):
            pdf_records, xlsx_records, warnings = [], [], []
            for path in pdfs: scope['_dedupe_pdf_records'](pdf_records, extract_negative_commission_records(str(path)))
            parser = extract_client_vendor_pairs if mode == 'old' else extract_client_vendor_pairs_suelane
            for path in sheets:
                records, messages = parser(str(path)); xlsx_records.extend(records); warnings.extend(messages)
            matched, missing = (match_records if mode == 'old' else match_records_suelane)(pdf_records, xlsx_records)
            counts = count_sales_per_vendor_month(xlsx_records) if mode == 'old' else {}
            values = _calculate_vendor_values(matched, counts) if mode == 'old' else [get_valor_estorno(r) for r in matched]
            report = OUT / f'{name}_{mode}.xlsx'
            if matched:
                if mode == 'old': build_report(matched, str(report), missing, counts)
                else: build_report_suelane(matched, str(report), missing)
            all_results.append({
                'name': name, 'mode': mode,
                'pdfs': [str(p.relative_to(ROOT)).replace('\\', '/') for p in pdfs],
                'sheets': [str(p.relative_to(ROOT)).replace('\\', '/') for p in sheets],
                'expected': {'pdfRecords': [asdict(r) for r in pdf_records], 'spreadsheetRecords': [asdict(r) for r in xlsx_records],
                             'matchedRecords': [asdict(r) for r in matched], 'notFound': [asdict(r) for r in missing],
                             'warnings': warnings, 'total': sum(v for v in values if v is not None),
                             'anomalies': sum(r.match_type != 'EXATO' for r in matched) if mode == 'old' else sum(analyze_record_suelane(r)[1] for r in matched)},
                'workbook': workbook_snapshot(report) if matched else None,
            })
            print(f'{name}/{mode}: pdf={len(pdf_records)} xlsx={len(xlsx_records)} matched={len(matched)} missing={len(missing)}')
    (OUT / 'oracle.json').write_text(json.dumps(all_results, ensure_ascii=False), encoding='utf-8')
    (OUT / 'core.json').write_text(json.dumps(core_cases(), ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__': generate()
