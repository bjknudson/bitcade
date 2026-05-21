# Bitcade Resource Files

These files define the current Bitcade product direction and the implementation contract for the first build.

## Documents

- [Bitcade Game Package Standard](bitcade-game-package-standard.md): required package structure, `bitcade.json`, supported file types, player metadata, controls, validation, statuses, and adapter expectations.
- [Bitcade Implementation Guide](bitcade-implementation-guide.md): local arcade/admin architecture, URLs, upload flow, security model, kiosk behavior, and interface scope.
- [Bitcade SQLite Data Model](bitcade-database-schema.md): starter database tables and suggested SQL for games, files, play sessions, and high scores.
- [Bitcade Development Roadmap](bitcade-development-roadmap.md): phased plan from browser arcade MVP through future adapters.

## Current first-build rule

To appear in Bitcade, a game must run from an `index.html` file without internet access.
