from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ContractChangeType(str, Enum):
    UNCHANGED = "unchanged"
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class DiffOperation(str, Enum):
    EQUAL = "equal"
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"


class ContractClause(BaseModel):
    clause_id: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=500)
    text: str = Field(min_length=1, max_length=500_000)


class ContractCompareOptions(BaseModel):
    ignore_case: bool = False
    normalize_whitespace: bool = True
    include_unchanged: bool = False
    similarity_threshold: float = Field(default=0.58, ge=0.0, le=1.0)
    max_diff_tokens_per_clause: int = Field(default=20_000, ge=100, le=100_000)


class ContractCompareRequest(BaseModel):
    original_text: str | None = Field(default=None, max_length=2_000_000)
    revised_text: str | None = Field(default=None, max_length=2_000_000)
    original_clauses: list[ContractClause] | None = Field(default=None, max_length=2_000)
    revised_clauses: list[ContractClause] | None = Field(default=None, max_length=2_000)
    options: ContractCompareOptions = Field(default_factory=ContractCompareOptions)

    @model_validator(mode="after")
    def validate_sources(self) -> "ContractCompareRequest":
        original_count = int(bool(self.original_text and self.original_text.strip())) + int(bool(self.original_clauses))
        revised_count = int(bool(self.revised_text and self.revised_text.strip())) + int(bool(self.revised_clauses))
        if original_count != 1:
            raise ValueError("provide exactly one original source: original_text or original_clauses")
        if revised_count != 1:
            raise ValueError("provide exactly one revised source: revised_text or revised_clauses")
        return self


class TokenDiff(BaseModel):
    operation: DiffOperation
    original: str = ""
    revised: str = ""


class ClauseChange(BaseModel):
    change_type: ContractChangeType
    original_index: int | None = None
    revised_index: int | None = None
    original_clause_id: str | None = None
    revised_clause_id: str | None = None
    original_title: str | None = None
    revised_title: str | None = None
    original_text: str | None = None
    revised_text: str | None = None
    similarity: float = Field(ge=0.0, le=1.0)
    token_diff: list[TokenDiff] = Field(default_factory=list)
    redline: str = ""


class ContractCompareSummary(BaseModel):
    original_clause_count: int
    revised_clause_count: int
    added: int
    removed: int
    modified: int
    unchanged: int
    returned_changes: int
    original_word_count: int
    revised_word_count: int
    word_count_delta: int


class ContractCompareResponse(BaseModel):
    summary: ContractCompareSummary
    changes: list[ClauseChange]
    redline_markdown: str
    warnings: list[str]
    disclaimer: str
