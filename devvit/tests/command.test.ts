import { describe, expect, it } from "vitest";

import { isExactRecipeCardCommand, shouldHandleCommand } from "../src/command.js";

describe("RecipeBot command detection", () => {
  it("accepts the exact standalone command", () => {
    expect(isExactRecipeCardCommand("!recipecard")).toBe(true);
    expect(isExactRecipeCardCommand("  !recipecard\n")).toBe(true);
  });

  it("rejects extra text, flags, and partial words", () => {
    expect(isExactRecipeCardCommand("!recipecard --images")).toBe(false);
    expect(isExactRecipeCardCommand("please !recipecard")).toBe(false);
    expect(isExactRecipeCardCommand("!recipecards")).toBe(false);
  });

  it("rejects app-authored, deleted, and removed comments", () => {
    expect(shouldHandleCommand(
      { body: "!recipecard", authorName: "recipebot-devvit" },
      "recipebot-devvit",
    )).toBe(false);
    expect(shouldHandleCommand({ body: "!recipecard", authorName: "[deleted]" })).toBe(false);
    expect(shouldHandleCommand({ body: "!recipecard", authorName: "cook", removed: true })).toBe(false);
  });
});
