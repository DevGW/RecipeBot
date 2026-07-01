"""Render a static sample recipe to local artifacts."""

from pathlib import Path

from app.config.settings import get_settings
from app.recipes.slug import make_slug
from app.rendering.card_spec import RecipeCardSpec
from app.rendering.renderer import render_card


def build_sample_recipe() -> RecipeCardSpec:
    """Build the deterministic recipe fixture used by the sample renderer."""
    title = "Weeknight Lemon Herb Pasta"
    return RecipeCardSpec(
        title=title,
        slug=make_slug(title),
        description=(
            "A bright, simple pasta with lemon, herbs, and Parmesan that comes together "
            "with pantry staples."
        ),
        source_label="RecipeBot static sample",
        recipe_type="Main course",
        servings="4",
        prep_time="10 minutes",
        cook_time="20 minutes",
        ingredients=[
            "12 ounces spaghetti or linguine",
            "2 tablespoons olive oil",
            "3 cloves garlic, thinly sliced",
            "1 lemon, zested and juiced",
            "1/2 cup finely grated Parmesan, plus more for serving",
            "1/3 cup chopped fresh parsley",
            "Kosher salt and freshly ground black pepper",
        ],
        instructions=[
            "Bring a large pot of salted water to a boil and cook the pasta until al dente.",
            "Reserve one cup of pasta water, then drain the pasta.",
            "Warm the olive oil in the pot over medium heat. Add the garlic and cook until "
            "fragrant, about one minute.",
            "Return the pasta to the pot. Add lemon zest, lemon juice, Parmesan, and a splash "
            "of pasta water; toss until glossy.",
            "Fold in the parsley, season to taste, and serve with additional Parmesan.",
        ],
        notes=[
            "Add pasta water a little at a time; the sauce should cling to the noodles without "
            "becoming watery.",
            "For a richer finish, toss in one tablespoon of butter before serving.",
        ],
        image_paths=[],
    )


def main() -> None:
    """Render the sample recipe and print each generated artifact path."""
    settings = get_settings()
    output_directory = settings.artifact_root / "sample-card"
    paths = render_card(
        build_sample_recipe(),
        output_directory,
        imagemagick_binary=settings.imagemagick_binary,
        rsvg_convert_binary=settings.rsvg_convert_binary,
    )
    for path in (paths.svg, paths.png, paths.pdf):
        print(path.resolve())


if __name__ == "__main__":
    main()
