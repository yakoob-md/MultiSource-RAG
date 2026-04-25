from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal
import json
import dataclasses

SourceType = Literal["pdf", "web", "youtube", "legal_statute", "legal_judgment", "image"]
ChunkType  = Literal["text", "legal", "image", "transcript"]
DocLanguage = Literal["en", "hi", "te", "es", "fr"]

@dataclass
class UnifiedChunkMetadata:
    source_id     : str
    source_type   : SourceType
    source_title  : str
    chunk_type    : ChunkType
    language      : DocLanguage
    domain        : str                     # "law" | "general" | "medical" | "tech"
    topics        : list[str]               # extracted topic tags
    date_added    : str                     # ISO 8601 format
    section_id    : str | None    = None
    section_title : str | None    = None
    statute_name  : str | None    = None
    chapter       : str | None    = None
    amendments    : list[str]     = field(default_factory=list)
    has_exception : bool          = False
    has_explanation: bool         = False
    case_name     : str | None    = None
    court         : str | None    = None
    judgment_date : str | None    = None
    cited_sections: list[str]     = field(default_factory=list)
    cited_cases   : list[str]     = field(default_factory=list)
    para_range    : str | None    = None
    url           : str | None    = None
    timestamp_s   : int | None    = None
    image_path    : str | None    = None
    caption_model : str | None    = None

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> UnifiedChunkMetadata:
        return cls(**json.loads(s))

    def to_filter_dict(self) -> dict:
        """Returns only the fields useful for source filtering."""
        return {
            "source_id"   : self.source_id,
            "source_type" : self.source_type,
            "chunk_type"  : self.chunk_type,
            "domain"      : self.domain,
            "language"    : self.language,
            "section_id"  : self.section_id,
            "case_name"   : self.case_name,
            "court"       : self.court,
        }
