import hashlib
import re
from app.ingestion.models import Chunk

def digest(text): return hashlib.sha256(text.encode("utf-8")).hexdigest()
def tokens(text): return max(1, round(len(text.split())*1.3))
def sentences(text): return [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]

def windows(items, max_words, overlap=1):
    out=[]; start=0
    while start < len(items):
        end=start; words=0
        while end<len(items) and words+len(items[end].split())<=max_words:
            words+=len(items[end].split()); end+=1
        if end==start: end+=1
        out.append(" ".join(items[start:end]))
        if end>=len(items): break
        start=max(start+1,end-overlap)
    return out

def chunk_record(record,max_words=220,overlap=1):
    doc_id=record["document_id"]; dtype=record["document_type"]
    if dtype=="incident_runbook":
        sections=[("Symptom",record.get("symptom","")),("Possible Causes","; ".join(record.get("possible_causes",[]))),("Resolution Steps","; ".join(record.get("resolution_steps",[]))),("Overview",record["content"])]
    else:
        sections=[(record["title"],record["content"]+" Recommended action: "+record["recommended_action"])]
    chunks=[]; number=0
    for heading,text in sections:
        if not text.strip(): continue
        for content in windows(sentences(text),max_words,overlap):
            number+=1
            chunks.append(Chunk(f"{doc_id}::chunk::{number:03d}",doc_id,f"parent::{doc_id}",dtype,record["domain"],record["title"],heading,content,record["source"],record["version"],record["sensitivity"],digest(content),tokens(content)))
    return chunks
