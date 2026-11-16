from enum import Enum

from pydantic import BaseModel, Field, model_validator


class IssueType(str, Enum):
    spelling = "spelling"
    grammar = "grammar"
    punctuation = "punctuation"
    style = "style"
    readability = "readability"


class Severity(str, Enum):
    error = "error"
    warning = "warning"
    suggestion = "suggestion"

    @property
    def rank(self) -> int:
        return {"suggestion": 1, "warning": 2, "error": 3}[self.value]


class IssueSource(str, Enum):
    language_tool = "language_tool"
    spellcheck = "spellcheck"
    rule = "rule"


class Issue(BaseModel):
    id: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str
    type: IssueType
    severity: Severity
    message: str
    suggestions: list[str] = Field(default_factory=list)
    rule_id: str
    source: IssueSource

    @model_validator(mode="after")
    def validate_span(self) -> "Issue":
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class DocumentStats(BaseModel):
    words: int
    sentences: int
    characters: int
    paragraphs: int
    average_sentence_length: float
    long_sentences: int
    lexical_diversity: float
    passive_ratio: float
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    gunning_fog: float
    reading_time_seconds: int


class AnalyzeOptions(BaseModel):
    language: str | None = None
    categories: list[IssueType] | None = None
    min_severity: Severity = Severity.suggestion
    include_stats: bool = True
    use_remote: bool = True


class AnalyzeRequest(AnalyzeOptions):
    text: str = Field(max_length=60000)


class AnalyzeResponse(BaseModel):
    issues: list[Issue]
    stats: DocumentStats | None = None
    text_length: int
    timing_ms: dict[str, float]
    degraded: list[str] = Field(default_factory=list)


class RewriteRequest(BaseModel):
    text: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    replacement: str

    @model_validator(mode="after")
    def validate_span(self) -> "RewriteRequest":
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        if self.end > len(self.text):
            raise ValueError("span is outside of the text")
        return self


class RewriteResponse(BaseModel):
    text: str


class DictionaryRequest(BaseModel):
    word: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def normalize(self) -> "DictionaryRequest":
        self.word = self.word.strip().lower()
        if not self.word or not self.word.replace("-", "").replace("'", "").isalpha():
            raise ValueError("word must contain letters only")
        return self


class DictionaryResponse(BaseModel):
    words: list[str]
