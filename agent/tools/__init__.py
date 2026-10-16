"""ChemAI Tools — collected from domain sub-modules and re-exported.

TOOL_META maps tool function → {"personas": [...], "call_limit": N}.
Used by langgraph_agent_v2 to filter tools per persona.
"""

# ── Exam bank & search ──
from agent.tools.exam_bank import (
    search_exam_bank,
    web_search,
    show_exam_workbench,
    save_to_bank,
    list_banks,
    delete_bank,
)

# ── Tutoring ──
from agent.tools.tutoring import (
    chemistry_tutor,
    balance_equation,
    ionic_equation_tutor,
    stoichiometry_tutor,
    redox_tutor,
    equilibrium_tutor,
    periodic_law_tutor,
    organic_tutor,
    _normalize_chem_formulas,
)

# ── Diagnosis ──
from agent.tools.diagnosis import (
    diagnose_barrier,
    show_diagnosis,
    show_students,
    weekly_report,
    assign_adaptive_practice,
)

# ── Question generation ──
from agent.tools.generation import generate_questions

# ── Experiment simulation ──
from agent.tools.simulation import simulate_experiment

# ── OCR & grading ──
from agent.tools.ocr_grading import (
    query_ocr_progress,
    grade_answer_sheets,
    save_grading_results,
)

# ── Long-term memory ──
from agent.tools.memory import (
    memory_student_get,
    memory_teacher_get,
)

# ── Learning plan ──
from agent.tools.diagnosis import (
    generate_learning_plan,
    send_learning_plan,
    generate_parent_report,
    send_report_to_parent,
)

# ── All tools (flat list for agent factories) ──

TOOLS = [
    search_exam_bank,
    web_search,
    show_exam_workbench,
    show_diagnosis,
    show_students,
    diagnose_barrier,
    chemistry_tutor,
    simulate_experiment,
    balance_equation,
    query_ocr_progress,
    grade_answer_sheets,
    save_grading_results,
    ionic_equation_tutor,
    stoichiometry_tutor,
    redox_tutor,
    equilibrium_tutor,
    periodic_law_tutor,
    organic_tutor,
    weekly_report,
    assign_adaptive_practice,
    save_to_bank,
    list_banks,
    delete_bank,
    generate_questions,
    memory_student_get,
    memory_teacher_get,
    generate_learning_plan,
    send_learning_plan,
    generate_parent_report,
    send_report_to_parent,
]

# ── Per-tool metadata for persona filtering & call limits ──

TOOL_META = {
    search_exam_bank:         {"personas": ["tutor", "teacher"], "call_limit": 3},
    web_search:               {"personas": ["student", "tutor", "teacher", "parent"], "call_limit": 2},
    show_exam_workbench:      {"personas": ["tutor", "teacher"], "call_limit": 3},
    show_diagnosis:           {"personas": ["teacher"], "call_limit": 1},
    show_students:            {"personas": ["teacher"], "call_limit": 1},
    diagnose_barrier:         {"personas": ["teacher", "parent"], "call_limit": 2},
    chemistry_tutor:          {"personas": ["student", "tutor", "teacher"], "call_limit": 3},
    simulate_experiment:      {"personas": ["student", "tutor"], "call_limit": 2},
    balance_equation:         {"personas": ["tutor", "teacher"], "call_limit": 3},
    query_ocr_progress:       {"personas": ["teacher"], "call_limit": 3},
    grade_answer_sheets:      {"personas": ["teacher"], "call_limit": 2},
    save_grading_results:     {"personas": ["teacher"], "call_limit": 2},
    ionic_equation_tutor:     {"personas": ["student"], "call_limit": 5},
    stoichiometry_tutor:      {"personas": ["student"], "call_limit": 5},
    redox_tutor:              {"personas": ["student"], "call_limit": 5},
    equilibrium_tutor:        {"personas": ["student"], "call_limit": 5},
    periodic_law_tutor:       {"personas": ["student"], "call_limit": 5},
    organic_tutor:            {"personas": ["student"], "call_limit": 5},
    weekly_report:            {"personas": ["teacher", "parent"], "call_limit": 2},
    assign_adaptive_practice: {"personas": ["teacher"], "call_limit": 1},
    save_to_bank:             {"personas": ["tutor", "teacher"], "call_limit": 1},
    list_banks:               {"personas": ["tutor", "teacher"], "call_limit": 1},
    delete_bank:              {"personas": ["tutor", "teacher"], "call_limit": 1},
    generate_questions:       {"personas": ["tutor", "teacher"], "call_limit": 5},
    memory_student_get:       {"personas": ["student", "tutor", "teacher", "parent"], "call_limit": 1},
    memory_teacher_get:       {"personas": ["teacher"], "call_limit": 1},
    generate_learning_plan:  {"personas": ["teacher"], "call_limit": 5},
    send_learning_plan:      {"personas": ["teacher"], "call_limit": 2},
    generate_parent_report: {"personas": ["teacher"], "call_limit": 5},
    send_report_to_parent:  {"personas": ["teacher"], "call_limit": 3},
}

# verify all TOOLS are in TOOL_META
assert set(TOOLS) == set(TOOL_META.keys()), f"TOOL_META missing: {set(TOOLS) - set(TOOL_META.keys())}"
