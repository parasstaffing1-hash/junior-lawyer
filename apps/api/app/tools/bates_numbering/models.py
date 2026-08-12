from enum import Enum

from pydantic import BaseModel, Field, model_validator


class BatesPosition(str, Enum):
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


class CollisionPolicy(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    ERROR = "error"


class BatesNumberingOptions(BaseModel):
    prefix: str = Field(default="BATES-", max_length=100)
    suffix: str = Field(default="", max_length=100)
    start_number: int = Field(default=1, ge=0, le=999_999_999_999)
    digits: int = Field(default=6, ge=1, le=12)
    increment: int = Field(default=1, ge=1, le=1_000_000)
    position: BatesPosition = BatesPosition.BOTTOM_RIGHT
    margin_x: float = Field(default=36.0, ge=0, le=500)
    margin_y: float = Field(default=24.0, ge=0, le=500)
    font_size: float = Field(default=9.0, ge=5.0, le=36.0)
    page_numbers: list[int] | None = Field(default=None, max_length=20_000)
    collision_policy: CollisionPolicy = CollisionPolicy.WARN

    @model_validator(mode="after")
    def validate_page_numbers(self) -> "BatesNumberingOptions":
        if self.page_numbers is not None:
            if not self.page_numbers:
                raise ValueError("page_numbers cannot be an empty list; use null to stamp every page")
            if any(number < 1 for number in self.page_numbers):
                raise ValueError("page_numbers are 1-based and must all be >= 1")
            if len(set(self.page_numbers)) != len(self.page_numbers):
                raise ValueError("page_numbers cannot contain duplicates")
        return self


class BatesAssignment(BaseModel):
    page_number: int
    bates_number: str
    collision_detected: bool


class BatesPreviewResponse(BaseModel):
    original_filename: str | None
    page_count: int
    stamped_page_count: int
    skipped_page_count: int
    first_bates_number: str | None
    last_bates_number: str | None
    assignments: list[BatesAssignment]
    collision_pages: list[int]
    warnings: list[str]
    disclaimer: str
