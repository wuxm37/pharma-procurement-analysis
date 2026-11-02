"""交付核查：输出一致性、导出公式、文件链接与运行哈希。只读已有成品。"""
import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/demo"
N = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def main():
    data = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    page = (OUT / "index.html").read_text(encoding="utf-8")
    embedded = re.search(r'<script id="analysis-data" type="application/json">(.*?)</script>', page, re.S)
    assert embedded and json.loads(embedded[1]) == data, "网页数据与本次结果不一致"
    assert "__RESULTS_JSON__" not in page
    for filename in ['index.html', 'project.html', 'report.html']:
        html = (OUT / filename).read_text(encoding='utf-8')
        assert '采购更有依据，库存更有分寸' not in html
        for href in re.findall(r'href="([^"#]+)"', html):
            if not href.startswith(('https://', 'data:')):
                assert (OUT / href).is_file(), f"页面链接缺失：{filename} -> {href}"
    manifest = json.loads((OUT / "run_manifest.json").read_text(encoding="utf-8"))
    for group in ["inputs", "outputs"]:
        for name, expected in manifest[group].items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected, f"运行后文件改变：{name}"
    with ZipFile(OUT / "procurement_analysis.xlsx") as archive:
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared = [''.join(x.itertext()) for x in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('m:si', N)]
        sheets = [ET.fromstring(archive.read(f'xl/worksheets/sheet{i}.xml')) for i in range(1, 5)]
        assert len(ET.fromstring(archive.read('xl/workbook.xml')).findall('m:sheets/m:sheet', N)) == 4
        def value(sheet, addr):
            cell = sheet.find(f'.//m:c[@r="{addr}"]', N)
            if cell is None:
                return None
            v = cell.find('m:v', N)
            if v is None:
                return ''.join(cell.find('m:is', N).itertext()) if cell.find('m:is', N) is not None else None
            if cell.get('t') == 's':
                return shared[int(v.text)]
            if cell.get('t') in ['str', 'd']:
                return v.text
            return float(v.text) if v.text else None
        for sheet in sheets:
            errors = [cell.get('r') for cell in sheet.findall('.//m:c', N) if cell.get('t') == 'e']
            assert not errors, f"Excel 有公式错误：{errors}"
        def close(got, want):
            assert isinstance(got, (int, float)) and abs(got-want) <= 1e-7*max(1, abs(want)), (got, want)
        close(value(sheets[0], 'E6'), data['simulation']['changes']['turnover_improvement_pct']/100)
        close(value(sheets[0], 'D10'), data['simulation']['summaries']['optimized']['operating_cost'])
        close(value(sheets[0], 'E11'), data['simulation']['changes']['fill_rate_change_pp'])
        close(value(sheets[3], 'D21'), data['benchmark']['time_reduction_pct']/100)
        assert value(sheets[1], 'A6') == 'M13' and value(sheets[1], 'G6') is None
        close(value(sheets[1], 'E6'), 170/15)
        close(value(sheets[3], 'B25'), data['tests']['run'])
        for i in [0, len(data['forecast_rows'])//2, len(data['forecast_rows'])-1]:
            record, row = data['forecast_rows'][i], i+6
            assert value(sheets[2], f'A{row}') == record['Medication']
            close(value(sheets[2], f'G{row}'), abs(record['baseline_forecast']-record['actual']))
            close(value(sheets[2], f'H{row}'), abs(record['selected_forecast']-record['actual']))
    result = {"core_tests_passed": data['tests']['run'], "html_matches_results": True,
              "download_links_exist": True, "run_hashes_match": True, "xlsx_error_cells": 0,
              "xlsx_sheets": 4, "xlsx_key_values_match": True,
              "xlsx_sha256": hashlib.sha256((OUT/'procurement_analysis.xlsx').read_bytes()).hexdigest()}
    (OUT / "verification").mkdir(exist_ok=True)
    (OUT / "verification/output_checks.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
