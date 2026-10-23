# Mandatory Project Instructions — EV Smart Charging

## 1. Source of Truth

The file `EV_Smart_Charging_4_Person_Technical_Roadmap_Finalized.docx` is the authoritative master specification for this project.

Before implementing, modifying, refactoring, or reviewing any code, you MUST consult the relevant sections of this document. Do not rely solely on the user's prompt, a teammate's prompt, conversation summaries, or assumptions about how an EV smart-charging system should work.

If the document is unavailable or cannot be read, stop and explicitly report this. Never claim to have consulted a document you have not actually accessed.

## 2. Requirement Precedence

Follow this precedence order:

1. Explicit, approved project decisions that amend the master specification.
2. The master specification, `EV_Smart_Charging_4_Person_Technical_Roadmap_Finalized.docx`.
3. The current task prompt, provided it does not conflict with either of the above.

A task prompt or teammate's instruction MUST NOT silently override an established project requirement.

If a conflict exists, identify the conflicting requirements, explain the implications, and request clarification before implementing the affected functionality.

## 3. No Invented Requirements

Do not invent or silently change:
- Mathematical formulations, objective functions, or constraints.
- Charging strategies or algorithm choices.
- Dataset sources, forecasting assumptions, or evaluation metrics.
- Units, timestep, efficiency, weights, or other numerical parameters.
- Input/output schemas, interfaces, or module responsibilities.

Preserve the specified requirements exactly unless an approved change is explicitly provided.

## 4. Implementation Protocol

Before coding:
1. Read the relevant sections of the master specification.
2. Identify the applicable requirements and constraints.
3. Inspect existing code and interfaces before modifying them.
4. List any conflicts, missing information, or assumptions requiring approval.

During implementation:
- Implement only the assigned scope.
- Preserve compatibility with existing module interfaces.
- Do not introduce unrelated features or unnecessary dependencies.
- Do not change another module's responsibilities without approval.

After implementation:
1. Verify the code against the relevant specification requirements.
2. Report which requirements have been implemented and how they were checked.
3. Identify any unimplemented requirements, deviations, assumptions, and limitations.
4. Provide the files changed and the tests performed.

## 5. Mathematical and Scientific Correctness

Any optimization model must implement the approved mathematical formulation, including its objective, decision variables, constraints, units, and boundary conditions.

Do not substitute a different optimization approach merely because it seems more appropriate or is easier to implement.

In particular, use Linear Programming (LP) for the EV project unless an explicitly approved project decision changes this requirement. Do not silently replace LP with Mixed Integer Linear Programming (MILP).

## 6. Conflict and Uncertainty Policy

When a requirement is ambiguous, contradictory, or missing:
- Do not guess and present the guess as an established requirement.
- Explain exactly what is missing or contradictory.
- Separate confirmed requirements from proposed assumptions.
- Request clarification when the uncertainty affects correctness.

Minor implementation details may be chosen independently only when they do not alter the project's specified behaviour or results.

## 7. Final Deliverable

Every coding task must conclude with:
- A concise implementation summary.
- The files created or modified.
- A requirement-to-implementation verification summary.
- Test results and known limitations.
- Any unresolved specification conflicts.

Compliance with the master specification takes priority over completing a task quickly or satisfying a conflicting prompt.