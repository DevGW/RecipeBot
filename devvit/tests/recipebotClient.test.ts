import { describe, expect, it } from "vitest";

import { createRecipeBotSignature } from "../src/hmac.js";
import { buildRecipeBotRequest } from "../src/recipebotClient.js";
import type { RecipeBotPayload } from "../src/redditSource.js";

const payload: RecipeBotPayload = {
  command_comment_id: "t1_command",
  requester_username: "example_user",
  subreddit: "recipes",
  source_type: "comment",
  source_fullname: "t1_parent",
  source_title: "Tomato Toast",
  source_body: "Ingredients:\n- bread\nDirections:\n1. Toast.",
  source_permalink: "https://www.reddit.com/r/recipes/comments/example",
  source_url: "https://www.reddit.com/r/recipes/comments/example",
  created_utc: 1780000000,
};

describe("RecipeBot backend request", () => {
  it("constructs the expected URL, raw body, and HMAC headers", () => {
    const timestamp = "1780000000";
    const request = buildRecipeBotRequest(
      payload,
      {
        backendUrl: "https://recipebot.devgw.com/",
        webhookSecret: "test-secret",
      },
      timestamp,
    );

    expect(request.url).toBe(
      "https://recipebot.devgw.com/internal/devvit/recipecard",
    );
    expect(request.rawBody).toBe(JSON.stringify(payload));
    expect(request.init.method).toBe("POST");
    expect(request.init.body).toBe(request.rawBody);
    expect(request.init.headers).toEqual({
      "Content-Type": "application/json",
      "X-RecipeBot-Timestamp": timestamp,
      "X-RecipeBot-Signature": createRecipeBotSignature(
        "test-secret",
        timestamp,
        request.rawBody,
      ),
    });
  });
});
