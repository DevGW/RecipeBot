# Foundation architecture

RecipeBot currently has three local boundaries:

- Pydantic settings and render contracts validate input.
- SQLAlchemy models describe Postgres persistence, managed through Alembic.
- The renderer creates deterministic SVG and delegates PNG/PDF conversion to ImageMagick.

Reddit API access, asynchronous queues, and an HTTP application are intentionally outside this foundation.
