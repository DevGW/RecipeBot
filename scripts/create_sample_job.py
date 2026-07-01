"""Insert a synthetic source recipe and queued job into Postgres."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config.settings import get_settings
from app.db.models import Recipe, SourceItem, Subreddit
from app.db.session import build_session_factory
from app.jobs.service import create_job
from scripts.render_sample import build_sample_recipe


def main() -> None:
    """Create a complete synthetic job fixture and print its database id."""
    settings = get_settings()
    session_factory = build_session_factory(settings.database_url)
    token = uuid4().hex[:16]

    with session_factory.begin() as session:
        session.execute(
            insert(Subreddit)
            .values(name="recipebot_sample", enabled=False)
            .on_conflict_do_nothing(index_elements=[Subreddit.name])
        )
        subreddit = session.scalar(
            select(Subreddit).where(Subreddit.name == "recipebot_sample")
        )
        if subreddit is None:
            raise RuntimeError("sample subreddit could not be loaded")

        source_item = SourceItem(
            reddit_fullname=f"t3_sample_{token}",
            item_type="synthetic",
            permalink=f"local://sample/{token}",
            subreddit_id=subreddit.id,
            raw_data={"fixture": "sample"},
        )
        session.add(source_item)
        session.flush()

        spec = build_sample_recipe()
        recipe = Recipe(
            source_item_id=source_item.id,
            title=spec.title,
            slug=spec.slug,
            spec_data=spec.model_dump(mode="json"),
        )
        session.add(recipe)
        session.flush()

        job = create_job(session, f"t1_sample_{token}", source_item.id)
        job_id = job.id

    print(job_id)


if __name__ == "__main__":
    main()
