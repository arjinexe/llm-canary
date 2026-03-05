# universal-v1

The core canary suite. These tests cover fundamental behaviors that *all* capable LLMs should pass consistently.

If these start failing, something significant changed in the model.

## Philosophy

Tests in this suite must be:
- **Deterministic** — the correct answer never changes
- **Unambiguous** — no reasonable interpretation leads to a different answer
- **Fast** — each test should complete in under 2 seconds
- **Model-agnostic** — should pass on GPT-4, Claude, and Gemini

## Tests

| File | Category | Count |
|------|----------|-------|
| `01_basic_consistency.yml` | Math, geography, counting | 8 |
| `02_instruction_following.yml` | Format, language, constraints | 7 |

## Contributing

Add a test to this suite only if it meets all four criteria above.
A test that GPT-4o passes but Claude fails is interesting but belongs in a model-comparison suite, not here.
