"""Recipes: the ordered steps that make up a piece of agent work.

A recipe is code, not a row. Each step names an engine it calls, and the engine
call is a Python function — a firm-authored visual builder is a later feature
and would generate these, not replace them.

Ordering follows the practice, not convenience: what the matter is, then what
has happened, then whether the claim is still alive, then what is due, then
what is missing. A deterministic step never depends on an AI step, so the
report keeps its spine when no model is configured.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.agent import AgentRecipe, AgentStepKind
from app.models.ai import AITaskType


@dataclass(frozen=True)
class StepSpec:
    key: str
    label: str
    kind: AgentStepKind
    #: AI steps only. The existing task type that does the work.
    task_type: AITaskType | None = None
    #: AI steps only. A string.Template rendered with the matter's memory to
    #: form the prompt. Placeholders use $name so an unexpected brace in a
    #: matter title cannot break rendering.
    query_template: str | None = None


@dataclass(frozen=True)
class RecipeSpec:
    recipe: AgentRecipe
    title: str
    description: str
    steps: tuple[StepSpec, ...]

    @property
    def deterministic_step_count(self) -> int:
        return sum(1 for step in self.steps if step.kind is AgentStepKind.DETERMINISTIC)


HEARING_PREP = RecipeSpec(
    recipe=AgentRecipe.HEARING_PREP,
    title="Prepare for hearing",
    description=(
        "Assembles what a junior would put in front of the senior before a hearing: "
        "the matter, its procedural history, whether limitation still holds, what is "
        "due, and what is missing from the file."
    ),
    steps=(
        StepSpec(
            key="matter_brief",
            label="Matter and parties",
            kind=AgentStepKind.DETERMINISTIC,
        ),
        StepSpec(
            key="procedural_history",
            label="Procedural history",
            kind=AgentStepKind.DETERMINISTIC,
        ),
        StepSpec(
            key="limitation",
            label="Limitation position",
            kind=AgentStepKind.DETERMINISTIC,
        ),
        StepSpec(
            key="upcoming",
            label="What is due",
            kind=AgentStepKind.DETERMINISTIC,
        ),
        StepSpec(
            key="gaps",
            label="Gaps and unresolved contradictions",
            kind=AgentStepKind.DETERMINISTIC,
        ),
        StepSpec(
            key="issues",
            label="Legal issues in play",
            kind=AgentStepKind.AI,
            task_type=AITaskType.ISSUE_SPOTTING,
            query_template=(
                "Identify the legal issues in play for the hearing in this matter. "
                "Matter: $matter_title. Issues already recorded: $issues. "
                "Open questions: $open_questions."
            ),
        ),
        StepSpec(
            key="counterarguments",
            label="What the other side will say",
            kind=AgentStepKind.AI,
            task_type=AITaskType.COUNTERARGUMENT,
            query_template=(
                "Set out the arguments the opposite party is most likely to make at the "
                "hearing in this matter, and how each should be answered. "
                "Matter: $matter_title. Unresolved contradictions: $contradictions."
            ),
        ),
        StepSpec(
            key="hearing_note",
            label="Hearing note",
            kind=AgentStepKind.AI,
            task_type=AITaskType.MATTER_SUMMARY,
            query_template=(
                "Write a hearing note a senior can read in ninety seconds for this matter. "
                "Lead with what is being asked of the court today. "
                "Matter: $matter_title. Strategy on file: $strategy."
            ),
        ),
    ),
)


RECIPES: dict[AgentRecipe, RecipeSpec] = {AgentRecipe.HEARING_PREP: HEARING_PREP}


def get_recipe(recipe: AgentRecipe) -> RecipeSpec:
    return RECIPES[recipe]
