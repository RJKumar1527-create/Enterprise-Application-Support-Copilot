import csv
import json
from pathlib import Path

REQUIRED = {"document_id","document_type","domain","title","version","sensitivity","source","content","recommended_action"}

def validate(record):
    missing = REQUIRED - set(record)
    if missing: raise ValueError(f"Missing fields {sorted(missing)}")
    if record["sensitivity"] != "SYNTHETIC": raise ValueError(f"Blocked non-synthetic document {record['document_id']}")
    return record

def load_json(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = value if isinstance(value, list) else [value]
    return [validate(row) for row in rows]

def load_txt(path):
    p=Path(path); text=p.read_text(encoding="utf-8")
    return [validate({"document_id":p.stem.upper(),"document_type":"reference","domain":"general","title":p.stem,"version":"1.0","sensitivity":"SYNTHETIC","source":p.name,"content":text,"recommended_action":"Use the cited source."})]

def load_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f: return [validate(dict(row)) for row in csv.DictReader(f)]

def load_path(path):
    suffix=Path(path).suffix.lower()
    if suffix==".json": return load_json(path)
    if suffix in {".txt",".md"}: return load_txt(path)
    if suffix==".csv": return load_csv(path)
    raise ValueError(f"Unsupported file type: {suffix}")
