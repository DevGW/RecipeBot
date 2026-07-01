"""Process at most one queued RecipeBot job."""

from app.jobs.worker import build_worker


def main() -> None:
    """Run one worker iteration and print whether a job was processed."""
    processed = build_worker().run_once()
    print("Processed one job." if processed else "No queued jobs.")


if __name__ == "__main__":
    main()
