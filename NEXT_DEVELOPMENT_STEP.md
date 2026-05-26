# Next Development Step for Bitcade

Based on the current implementation and the project roadmap, the next development step is to start **Phase 5: High scores and leaderboards**.

Why this is next:

1. Phase 4 input support is implemented: admin display settings, controller detection, saved player mappings, a system exit/menu combo, browser gamepad-to-key translation, and install profile exports are present.
2. Phase 5 is the next roadmap milestone after better input support.
3. The existing SQLite-backed game/session model gives the high-score work a local place to attach score submissions, moderation, and leaderboard views.

Current Phase 5 status:

- The roadmap, database schema notes, package standard, and upload guides already
  describe the high-score direction.
- The app currently records `play_sessions`, `play_count`, and `last_played`,
  which gives Phase 5 a launch/session anchor.
- The app now includes score metadata columns, a `high_scores` table, browser
  and Python/Pygame score capture, local tag prompts, leaderboard views, and
  admin moderation.

Phase 5 to-do list:

- [x] Add score metadata fields to the app database schema:
  `scores_enabled`, `score_label`, `score_order`, `score_unit`,
  `score_precision`, and `score_ties`.
- [x] Add a `high_scores` table using the existing database schema guide as the
  starting point, including moderation fields such as `hidden_at` and
  `hidden_reason`.
- [x] Add migration/backfill handling for existing local SQLite databases so
  current installs gain the new columns and table without losing games.
- [x] Extend `bitcade.json` validation for optional `scores` metadata:
  `enabled`, `label`, `order`, `unit`, `precision`, and `ties`.
- [x] Store score metadata when new games are uploaded or existing metadata is
  edited in admin.
- [x] Add ranking helpers that scope leaderboards by `game_id` and
  `game_version`, respect `asc` versus `desc`, and apply the configured tie
  behavior.
- [x] Add browser score capture for iframe games through a small launcher bridge
  that accepts `bitcade:score` `postMessage` events from the current game
  origin.
- [x] Add a first-party browser helper script or documented `window.Bitcade`
  helper so student games can submit scores without hand-writing raw
  `postMessage` calls.
- [x] Add Python/Pygame score event capture by parsing `BITCADE_SCORE` JSON
  lines from native process stdout and associating them with the current play
  session when possible.
- [x] Decide whether a submitted score qualifies before prompting for a player
  tag, based on max leaderboard size and current rank.
- [x] Add a local tag prompt flow for browser games that did not provide a tag
  in-game.
- [x] Add an after-exit tag prompt or holding state for native games that report
  a qualifying score without a tag.
- [x] Normalize and validate player tags to a short classroom-safe format, then
  store only the public tag, not student identity.
- [x] Show top scores on each approved game detail page.
- [ ] Add a Leaderboards index page with filters for game, version, time
  period, and scoring mode.
- [ ] Add a post-game result view that shows the player's rank and nearby
  scores after a stored score.
- [x] Add admin moderation actions to hide, restore, or annotate score entries
  with a reason.
- [x] Add focused tests for metadata validation, database migration, leaderboard
  ranking, browser score submission, tag validation, and moderation.
