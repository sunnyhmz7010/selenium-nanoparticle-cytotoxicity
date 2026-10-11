"""仅用标准库转换归档 XLSX；保留原始数值文本和未确认的浓度单位。"""
import csv
import hashlib
import io
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'data' / 'prospective'
SOURCE = DIRECTORY / 'experimental_huvec_original.xlsx'
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
FIELDS = ['nanoparticle', 'size_nm', 'zeta_mV', 'cell_type',
          'concentration_reported', 'time_h', 'viability_percent']


def main():
    with ZipFile(SOURCE) as archive:
        strings = [''.join(si.itertext()) for si in
                   ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        sheets = []
        for index in range(1, 4):
            xml = ET.fromstring(archive.read(f'xl/worksheets/sheet{index}.xml'))
            rows = []
            for row in xml.findall('m:sheetData/m:row', NS):
                values = [''] * 7
                for cell in row.findall('m:c', NS):
                    column = ''.join(c for c in cell.attrib['r'] if c.isalpha())
                    if column not in 'ABCDEFG' or len(column) != 1:
                        raise ValueError(f'Unexpected column: {column}')
                    if cell.find('m:f', NS) is not None:
                        raise ValueError('Formula found; manual review required')
                    value = cell.findtext('m:v', '', NS)
                    if cell.attrib.get('t') == 's':
                        value = strings[int(value)]
                    values[ord(column) - ord('A')] = value
                rows.append(values)
            sheets.append(rows)
    headers, *rows = sheets[0]
    assert len(rows) == 351 and not sheets[1] and not sheets[2]
    assert all(all(row) for row in rows)
    keys = {(r[0], r[3], r[4], r[5]) for r in rows}
    assert len(keys) == len(rows)
    materials = sorted({r[0] for r in rows})
    doses = sorted({r[4] for r in rows}, key=float)
    assert len(materials) == 9 and len(doses) == 13
    assert {r[3] for r in rows} == {'HUVEC'}
    assert {r[5] for r in rows} == {'24', '48', '72'}
    for material in materials:
        for time in ['24', '48', '72']:
            assert {r[4] for r in rows if r[0] == material and r[5] == time} == set(doses)
    for row in rows:
        for index in [1, 2, 4, 5, 6]:
            float(row[index])
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerow(FIELDS)
    writer.writerows(rows)
    csv_path = DIRECTORY / 'experimental_huvec_dose_time.csv'
    csv_path.write_bytes(buffer.getvalue().encode('utf-8'))
    audit = {
        'source': SOURCE.name,
        'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'csv': csv_path.name,
        'csv_sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        'source_headers': headers,
        'csv_fields': FIELDS,
        'rows': len(rows),
        'materials': materials,
        'concentrations_reported': doses,
        'times_h': [24, 48, 72],
        'empty_sheets': ['Sheet2', 'Sheet3'],
        'missing_cells': 0,
        'duplicate_condition_keys': len(rows) - len(keys),
        'concentration_unit_status': '原表为μm，含义与计量基准待确认；未换算为μM或μg/mL',
        'replicate_status': '每条件一个报告值；原始重复孔数量和汇总方式未提供',
    }
    (DIRECTORY / 'audit.json').write_bytes(
        (json.dumps(audit, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(f'Validated and archived {len(rows)} rows, {len(materials)} materials.')


if __name__ == '__main__':
    main()
