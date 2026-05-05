"""Central pydantic schemas for the teaching harness.

All intermediate artifacts written to the workspace conform to these models.
Keep additions conservative: downstream agents depend on stable field names.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

MaterialType = Literal[
    "slides",
    "textbook",
    "examples",
    "assignment",
    "rubric",
    "past_paper",
    "lab_sheet",
    "other",
]

ChunkType = Literal[
    "title",
    "body",
    "formula",
    "example",
    "figure_caption",
    "table",
    "unknown",
]

Severity = Literal["low", "medium", "high"]

FindingCategory = Literal[
    "coverage",
    "formula",
    "example",
    "hallucination",
    "pedagogy",
    "visual",
    "style",
    "guardrail",
    "source_ref",
    "schema",
]

TargetType = Literal["course", "part", "note", "example", "formula", "visual_plan"]

Difficulty = Literal["intro", "standard", "advanced", "unknown"]

PrereqKind = Literal["must_review", "quick_reminder", "optional_background"]

VisualKind = Literal[
    "concept_map",
    "flowchart",
    "block_diagram",
    "circuit_state_diagram",
    "waveform",
    "derivation_flow",
    "before_after",
    "static_frames",
    "table",
    "mermaid_candidate",
]


class SourceRef(BaseModel):
    """Pointer to a specific location inside a course material."""

    material_id: str
    page: Optional[int] = None
    chunk_id: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    quote: Optional[str] = None


# ---------------------------------------------------------------------------
# Raw + parsed material
# ---------------------------------------------------------------------------


class CourseMaterial(BaseModel):
    id: str
    material_type: MaterialType
    path: str
    title: Optional[str] = None
    source_priority: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ParsedChunk(BaseModel):
    id: str
    material_id: str
    text: str
    heading: Optional[str] = None
    page: Optional[int] = None
    chunk_type: ChunkType = "body"
    source_refs: list[SourceRef] = Field(default_factory=list)
    confidence: float = 1.0


class ParsedDocument(BaseModel):
    material_id: str
    chunks: list[ParsedChunk] = Field(default_factory=list)
    extracted_text: str = ""
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Formulas and examples
# ---------------------------------------------------------------------------


class Formula(BaseModel):
    id: str
    latex: Optional[str] = None
    plain_text: str
    variables: dict[str, str] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    source_refs: list[SourceRef] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    usage_conditions: list[str] = Field(default_factory=list)
    related_concepts: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    needs_review: bool = True


class ExampleProblem(BaseModel):
    id: str
    problem_text: str
    source_refs: list[SourceRef] = Field(default_factory=list)
    related_concepts: list[str] = Field(default_factory=list)
    required_formulas: list[str] = Field(default_factory=list)
    difficulty: Difficulty = "unknown"
    solution_available: bool = False
    parsed_solution: Optional[str] = None
    confidence: float = 0.5
    needs_review: bool = True


# ---------------------------------------------------------------------------
# Curriculum planning
# ---------------------------------------------------------------------------


class CourseModule(BaseModel):
    id: str
    title: str
    summary: str = ""
    part_ids: list[str] = Field(default_factory=list)


class CourseDependency(BaseModel):
    from_id: str
    to_id: str
    reason: str = ""


class CourseMap(BaseModel):
    course_title: str
    core_theme: str
    modules: list[CourseModule] = Field(default_factory=list)
    dependencies: list[CourseDependency] = Field(default_factory=list)
    key_learning_goals: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)


class PrerequisiteConcept(BaseModel):
    concept: str
    kind: PrereqKind
    why: str = ""


class PrerequisiteGraph(BaseModel):
    per_part: dict[str, list[PrerequisiteConcept]] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class LearningPart(BaseModel):
    id: str
    title: str
    core_question: str
    source_refs: list[SourceRef] = Field(default_factory=list)
    prerequisite_concepts: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    formulas: list[str] = Field(default_factory=list)  # Formula ids
    matched_examples: list[str] = Field(default_factory=list)  # ExampleProblem ids
    visual_needs: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    learning_objectives: list[str] = Field(default_factory=list)
    confidence: float = 0.6
    unresolved_issues: list[str] = Field(default_factory=list)


class PartOutline(BaseModel):
    parts: list[LearningPart] = Field(default_factory=list)


class VisualPlanItem(BaseModel):
    part_id: str
    kind: VisualKind
    description: str
    mermaid_draft: Optional[str] = None
    needs_review: bool = True
    # New optional fields for richer visual planning (Task 05).
    source_type: Literal["part", "formula", "example", "concept"] = "part"
    title: str = ""
    reason: str = ""
    source_refs: list[SourceRef] = Field(default_factory=list)
    related_formula_ids: list[str] = Field(default_factory=list)
    related_example_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class VisualNeeds(BaseModel):
    items: list[VisualPlanItem] = Field(default_factory=list)


class ExampleMatch(BaseModel):
    example_id: str
    part_id: str
    score: float
    reason: str
    shared_concepts: list[str] = Field(default_factory=list)
    shared_formulas: list[str] = Field(default_factory=list)


class ExampleMatching(BaseModel):
    matches: list[ExampleMatch] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Teaching plans and notes
# ---------------------------------------------------------------------------


class TeachingPlan(BaseModel):
    part_id: str
    why_this_part_matters: str
    prerequisite_review: list[str] = Field(default_factory=list)
    analogy_needed: bool = False
    analogy: Optional[str] = None
    analogy_boundaries: list[str] = Field(default_factory=list)
    explanation_sequence: list[str] = Field(default_factory=list)
    formula_sequence: list[str] = Field(default_factory=list)
    visual_plan: list[VisualPlanItem] = Field(default_factory=list)
    example_sequence: list[str] = Field(default_factory=list)
    self_check_questions: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)


class PartNote(BaseModel):
    part_id: str
    markdown: str
    source_refs: list[SourceRef] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    needs_review: bool = True


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


class ReviewFinding(BaseModel):
    severity: Severity
    category: FindingCategory
    message: str
    evidence: Optional[str] = None
    suggested_fix: Optional[str] = None
    target_part_id: Optional[str] = None


class ReviewReport(BaseModel):
    target_id: str
    target_type: TargetType
    findings: list[ReviewFinding] = Field(default_factory=list)
    pass_status: bool = False
    required_fixes: list[str] = Field(default_factory=list)
    summary: str = ""

    def highest_severity(self) -> Optional[Severity]:
        order = {"low": 1, "medium": 2, "high": 3}
        best: Optional[Severity] = None
        for f in self.findings:
            if best is None or order[f.severity] > order[best]:
                best = f.severity
        return best


# ---------------------------------------------------------------------------
# Pipeline bookkeeping
# ---------------------------------------------------------------------------


class PipelineStage(BaseModel):
    name: str
    status: Literal["pending", "running", "completed", "failed", "skipped"]
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class PipelineRun(BaseModel):
    run_id: str
    course_path: str
    started_at: str
    completed_at: Optional[str] = None
    status: Literal["initialized", "running", "completed", "failed"] = "initialized"
    stages: list[PipelineStage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


class LearnerPreferences(BaseModel):
    """Slow-moving learner preferences; safe to persist across runs."""

    output_language: str = "zh-en"
    note_style: str = "obsidian"
    prefers_intuition_first: bool = True
    wants_detailed_derivation: bool = False
    extra_notes: list[str] = Field(default_factory=list)


class CoursePreferences(BaseModel):
    """Course-scoped preferences (e.g. depth, terminology)."""

    course_title: Optional[str] = None
    depth: Literal["shallow", "standard", "deep"] = "standard"
    terminology_preferences: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
