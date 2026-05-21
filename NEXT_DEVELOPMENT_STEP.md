# Next Development Step for Bitcade

Based on the current implementation and the project roadmap, the next development step is to complete **Phase 4: Better input support**.

Why this is next:

1. The Phase 1 browser arcade MVP and substantial Phase 2/3 capabilities are already present in the codebase.
2. The roadmap defines Phase 4 as the next milestone after adding browser uploads/approval and the Python/Pygame adapter.
3. Core data structures for cabinet input profiles already exist (`DEFAULT_CABINET_PROFILE`, key mapping options), so implementation can continue from existing foundations.

Immediate Phase 4 priorities:

- Add an admin controller detection and mapping page (Gamepad API).
- Save cabinet mappings for player 1 and player 2.
- Implement a configurable system exit/menu combo.
- Export the install profile (JSON/Markdown/prompt block) for students.

