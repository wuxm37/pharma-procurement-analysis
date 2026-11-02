"""仅提取公开数据包中白名单数据文件；不执行作者代码。"""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

SOURCE_URL = "https://zenodo.org/records/22286723"
PREFIX = "healthcare-4503243_ZENODO_AUDITED_UPDATE/"
FILES = ["monthly_demand_long.csv", "empirical_inputs.csv", "data_dictionary.csv"]
EXPECTED_MD5 = "ef1ee4be3a21a07a4df37694690b12cc"


def prepare_source(root):
    root = Path(root)
    archive = root/"research/zenodo_audited_source.zip"
    if not archive.exists():
        raise FileNotFoundError("缺少已核查的公开数据包。下载说明见 README，不会自动生成冒充真实记录的数据。")
    raw = archive.read_bytes()
    if hashlib.md5(raw).hexdigest() != EXPECTED_MD5:
        raise ValueError("数据包与已核查版本校验值不符，请重新核对来源。")
    directory = root/"data/source"
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"doi": "10.5281/zenodo.22286723", "url": SOURCE_URL, "license": "CC BY 4.0", "author": "Fernando Rojas", "archive_md5": EXPECTED_MD5, "archive_sha256": hashlib.sha256(raw).hexdigest(), "files": {}}
    with ZipFile(archive) as z:
        for name in FILES:
            payload = z.read(PREFIX+"data/source_zenodo/"+name)
            target = directory/name
            if target.exists() and target.read_bytes() != payload:
                raise ValueError(f"原始数据 {name} 已改变；不自动覆盖，请核对原件。")
            if not target.exists():
                target.write_bytes(payload)
            manifest["files"][name] = {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
        (directory/"AUTHOR_README.md").write_bytes(z.read(PREFIX+"README.md"))
    (directory/"source_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return directory, manifest
