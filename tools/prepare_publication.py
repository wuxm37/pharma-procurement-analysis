"""准备可审阅的 GitHub / Pages 发布副本；不调用 Git、不上传文件。"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'publication/repository'
STATIC_FILES = [
    'index.html', 'project.html', 'report.html', 'ANALYSIS_REPORT.md',
    'results.json', 'procurement_analysis.xlsx', 'test_results.txt',
    'cleaned_demand.csv', 'forecast_validation.csv', 'forecast_test.csv',
    'simulation_ledger.csv', 'stress_lead2_ledger.csv', 'inventory_risks.csv',
]


def main():
    # 先核对已有结果与工作簿，防止发布混用不同运行批次的文件。
    subprocess.run([sys.executable, str(ROOT/'tools/verify_outputs.py')], check=True)
    names = [
        '.gitignore', '.gitattributes', 'README.md', 'LOCAL_RUN.md',
        'PUBLISHING.md', 'NOTICE.md', 'DESIGN.md', 'BUSINESS_FLOW.md',
        'DATA_DICTIONARY.md', 'BEGINNER_GUIDE.md', 'requirements.txt',
        'config.json', 'run_project.py', '打开看板.cmd', '重新生成.ps1',
        'web/dashboard.html', 'web/assets/dashboard-preview.png',
        'tools/export_workbook.mjs', 'tools/verify_outputs.py',
        'tools/prepare_publication.py', 'research/zenodo_metadata.json',
        'research/zenodo_audited_source.zip', 'data/source/AUTHOR_README.md',
        'data/source/source_manifest.json', 'data/source/monthly_demand_long.csv',
        'data/source/empirical_inputs.csv', 'data/source/data_dictionary.csv',
        'outputs/demo/run_manifest.json',
    ]
    names += [p.relative_to(ROOT).as_posix() for folder in ['analysis', 'tests']
              for p in sorted((ROOT/folder).glob('*.py'))]
    names += ['outputs/demo/'+name for name in STATIC_FILES]
    copies = {name: ROOT/name for name in names}
    copies.update({'docs/'+name: ROOT/'outputs/demo'/name for name in STATIC_FILES})
    copies['docs/assets/dashboard-preview.png'] = ROOT/'web/assets/dashboard-preview.png'
    if STAGE.is_symlink() or STAGE.is_junction() or not STAGE.resolve().is_relative_to(ROOT):
        raise RuntimeError('发布目录不在项目内或存在目录重定向')
    for destination, source in copies.items():
        if not source.is_file():
            raise FileNotFoundError(f'发布内容缺失：{source.relative_to(ROOT)}')
        target = STAGE/destination
        if not target.resolve().is_relative_to(STAGE.resolve()):
            raise RuntimeError('目标路径超出发布目录')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (STAGE/'docs/.nojekyll').write_text('', encoding='utf-8')
    public_names = sorted([*copies, 'docs/.nojekyll'])
    manifest = {
        'status': 'prepared_locally_not_published',
        'pages_source': 'main:/docs',
        'files': {name: {'bytes': (STAGE/name).stat().st_size,
                         'sha256': hashlib.sha256((STAGE/name).read_bytes()).hexdigest()}
                  for name in public_names},
    }
    (STAGE/'PUBLICATION_MANIFEST.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    archive_path = ROOT/'publication/github_release.zip'
    with ZipFile(archive_path, 'w', ZIP_DEFLATED) as archive:
        for name in [*public_names, 'PUBLICATION_MANIFEST.json']:
            archive.write(STAGE/name, name)
    with ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(public_names)+1
    print(json.dumps({'status': manifest['status'], 'files': len(public_names)+1,
                      'archive_mb': round(archive_path.stat().st_size/1024**2, 2),
                      'repository_directory': str(STAGE), 'archive': str(archive_path)},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
