from dataclasses import dataclass, asdict

@dataclass
class Document:
    document_id: str
    document_type: str
    domain: str
    title: str
    version: str
    sensitivity: str
    source: str
    content: str
    recommended_action: str
    raw: dict

@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    parent_id: str
    document_type: str
    domain: str
    title: str
    heading: str
    content: str
    source: str
    version: str
    sensitivity: str
    content_hash: str
    token_estimate: int

    def to_dict(self): return asdict(self)
