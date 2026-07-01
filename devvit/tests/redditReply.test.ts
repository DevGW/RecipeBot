import { describe, expect, it } from "vitest";

import { buildQueuedReply } from "../src/redditReply.js";

describe("buildQueuedReply", () => {
  it("returns the expected queued card message with the card URL", () => {
    const cardUrl = "https://recipebot.devgw.com/cards/123";

    expect(buildQueuedReply(cardUrl)).toBe(
      [
        "RecipeBot queued your card:",
        "",
        cardUrl,
        "",
        "It may take a moment for all downloads to appear.",
      ].join("\n"),
    );
  });
});
