# Foundation architecture

RecipeBot currently has three local boundaries:

- Pydantic settings and render contracts validate input.
- SQLAlchemy models describe Postgres persistence, managed through Alembic.
- The renderer creates deterministic SVG and delegates PNG/PDF conversion to ImageMagick.
- The artifact service validates renderer output, writes metadata, and builds ZIP bundles.
- The FastAPI service safely resolves completed card paths and delivers fixed artifact names.
- The PRAW listener watches an explicit subreddit allowlist and ingests only exact commands.
- The deterministic extractor turns Reddit source text into the existing renderer contract.
- The delivery service durably records DM attempts and only uses public fallback when opted in.

Recipe listing commands, per-command flags, web authentication, and external queue systems remain intentionally unimplemented.
