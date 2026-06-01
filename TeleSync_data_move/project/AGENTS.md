# Core Principles

Think before coding.

Never silently make assumptions.

State assumptions explicitly.

If requirements are unclear:
stop and ask.

Prefer simple solutions.

Avoid unnecessary abstractions.

------

# Read Before Write

Read existing code first.

Understand:

- architecture
- conventions
- dependencies

before making changes.

------

# Surgical Changes

Only modify what is required.

Do not refactor unrelated code.

Do not rewrite working code.

Match existing project style.

------

# Verification

Never claim success without verification.

Run relevant:

- tests
- lint
- typecheck

Report actual results.

------

# AI Agent Rules

Never assume LLM output is valid.

Handle:

- retries
- timeouts
- malformed responses

Validate structured outputs.

Prefer explicit workflows.

------

# LangGraph

Use graph state.

Avoid global mutable state.

Keep nodes focused.

Make routing explicit.

------

# FastAPI

Use Pydantic schemas.

Keep handlers thin.

Put business logic into services.

------

# Next.js

Prefer Server Components.

Use TypeScript strict mode.

Keep components small.