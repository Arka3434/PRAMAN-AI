# Copilot instructions for PRAMAN AI

## Core operating rules
- Understand the existing code and project phase before making any change.
- Make the smallest possible, scoped change that addresses the requested task.
- Preserve the working inspection workflow, architecture, and verified test/build behavior.
- Do not redesign the app or replace the approved stack without explicit direction.
- Do not invent legal requirements, legal interpretations, or regulatory conclusions.
- LLM output is not the final authority for legal or compliance decisions.
- Deterministic, versioned legal rules and source documents determine compliance.
- Keep legal source PDFs traceable to their source documents and inventory entries.
- Do not add unrelated architectures, services, or dependencies.
- Follow the current phase and do not jump ahead into later phases unless explicitly requested.
- Do not implement future phases or unrelated features without explicit instruction.
- Follow the current phase and only advance when explicitly instructed.

## Change discipline
- Read the relevant code before editing it.
- Reuse existing models, APIs, and services when possible.
- Avoid duplicate models, duplicate flows, or architecture drift.
- Keep OCR output clearly separated from legal/compliance verdicts.
- Preserve existing migrations and database schema changes only when required by the task.

## Verification requirements
- Run the smallest relevant backend test, frontend build, or browser check for the change.
- Do not assume a change works without verification.
- Prefer the project’s existing validation commands and environment.
- For backend tests, use the project working directory or configure `PYTHONPATH` correctly.

## Legal and evidence rules
- Treat OCR and package-image extraction as evidence, not legal truth.
- Legal sources must remain documented and traceable to the source PDF set.
- Candidate legal provisions must remain clearly marked as provisional and require human/legal verification.
- Do not implement compliance logic or rule execution without an explicit legal-source and rule-catalog workflow.

## Scope guardrails
- Do not implement Phase 6+ features without explicit instruction.
- Do not add mock legal compliance logic in place of deterministic rule execution.
- Do not add unrelated infrastructure, analytics, or consumer workflows.
- Maintain a clean separation between evidence capture, OCR, review, and legal rules.
