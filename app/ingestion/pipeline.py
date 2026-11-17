import json
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from app.chunking.strategies import chunk_record,digest
from app.ingestion.loaders import load_path
from app.repository.metadata import initialize,save_run
CHUNKS=Path("data/chunks.json"); MANIFEST=Path("data/chunk_manifest.json")

def ingest(paths,max_words=220,overlap=1):
    initialize(); records=[]
    for path in paths: records.extend(load_path(path))
    chunks=[chunk.to_dict() for record in records for chunk in chunk_record(record,max_words,overlap)]
    previous=json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    current={x["chunk_id"]:x["content_hash"] for x in chunks}
    added=set(current)-set(previous); removed=set(previous)-set(current); shared=set(current)&set(previous)
    changed={x for x in shared if current[x]!=previous[x]}; unchanged=shared-changed
    CHUNKS.parent.mkdir(parents=True,exist_ok=True); CHUNKS.write_text(json.dumps(chunks,indent=2),encoding="utf-8"); MANIFEST.write_text(json.dumps(current,indent=2),encoding="utf-8")
    result={"run_id":str(uuid4()),"started_at":datetime.now(timezone.utc).isoformat(),"documents":len(records),"chunks":len(chunks),"added":len(added),"changed":len(changed),"removed":len(removed),"unchanged":len(unchanged),"status":"COMPLETED","chunk_records":chunks}
    save_run(result); return result
