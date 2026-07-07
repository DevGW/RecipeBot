import { describe, expect, it } from "vitest";

import { buildRecipeBotReply } from "../src/redditReply.js";

describe("buildRecipeBotReply", () => {
  it("returns the expected queued card message with the card URL", () => {
    const cardUrl = "https://recipebot.devgw.com/cards/123";

    expect(buildRecipeBotReply(cardUrl, "queued")).toBe(
      [
        "RecipeBot is generating your card:",
        "",
        cardUrl,
        "",
        "The page will update when the PNG, SVG, and PDF files are ready.",
      ].join("\n"),
    );
  });

  it("returns the ready card message with the card URL", () => {
    const cardUrl = "https://recipebot.devgw.com/cards/123";

    expect(buildRecipeBotReply(cardUrl, "ready")).toBe(
      [
        "Your RecipeBot card is ready:",
        "",
        cardUrl,
      ].join("\n"),
    );
  });

  it("returns the existing job message with the card URL", () => {
    const cardUrl = "https://recipebot.devgw.com/cards/123";

    expect(buildRecipeBotReply(cardUrl, "existing")).toBe(
      [
        "RecipeBot already has a card job for this request:",
        "",
        cardUrl,
      ].join("\n"),
    );
  });
});
