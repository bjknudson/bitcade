# Next Development Step for Bitcade

Based on the current implementation and the project roadmap, the next development step is to start **Phase 5: High scores and leaderboards**.

Why this is next:

1. Phase 4 input support is implemented: admin display settings, controller detection, saved player mappings, a system exit/menu combo, browser gamepad-to-key translation, and install profile exports are present.
2. Phase 5 is the next roadmap milestone after better input support.
3. The existing SQLite-backed game/session model gives the high-score work a local place to attach score submissions, moderation, and leaderboard views.

Immediate Phase 5 priorities:

- Add score metadata validation for games that opt into leaderboards.
- Add SQLite tables for score entries and moderation state.
- Add a browser score submission bridge for static web games.
- Add native Python/Pygame score event capture from process output.
- Show per-game leaderboards on game detail pages.
- Add a local player tag prompt and basic admin moderation workflow.
