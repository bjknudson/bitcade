# Bitcade

Arcade platform to test student-made games.

Bitcade is planned as a local classroom arcade manager: upload a student game package, validate it, store it locally, approve it, show it in a kiosk arcade menu, and play it locally in Chromium.

## Resource files

The project direction and first implementation contract live in [`docs/resources/`](docs/resources/):

- [Bitcade Game Package Standard](docs/resources/bitcade-game-package-standard.md)
- [Bitcade Implementation Guide](docs/resources/bitcade-implementation-guide.md)
- [Bitcade SQLite Data Model](docs/resources/bitcade-database-schema.md)
- [Bitcade Development Roadmap](docs/resources/bitcade-development-roadmap.md)

## First-build rule

To appear in Bitcade, a game must run from an `index.html` file without internet access.
