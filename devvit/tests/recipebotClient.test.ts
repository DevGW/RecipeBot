import { describe, expect, it } from "vitest";

import { createRecipeBotSignature } from "../src/hmac.js";
import {
  buildRecipeBotRequest,
  sendRecipeCardRequest,
  type RecipeBotLogger,
} from "../src/recipebotClient.js";
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

class TestLogger implements RecipeBotLogger {
  readonly entries: Array<{ details?: Record<string, unknown>; message: string }> = [];

  error(message: string, details?: Record<string, unknown>): void {
    this.entries.push({ message, ...(details ? { details } : {}) });
  }

  log(message: string, details?: Record<string, unknown>): void {
    this.entries.push({ message, ...(details ? { details } : {}) });
  }
}

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

  it("contains fetch failures and logs actionable diagnostics", async () => {
    const logger = new TestLogger();
    const result = await sendRecipeCardRequest(
      payload,
      {
        backendUrl: "https://recipebot.devgw.com",
        webhookSecret: "never-log-this-secret",
      },
      logger,
      async () => { throw new TypeError("fetch failed"); },
    );

    expect(result).toEqual({ ok: false, reason: "fetch" });
    expect(logger.entries).toContainEqual({
      message: "RecipeBot backend fetch failed",
      details: expect.objectContaining({
        errorName: "TypeError",
        errorMessage: "fetch failed",
        backendUrl: "https://recipebot.devgw.com",
        finalPostUrl: "https://recipebot.devgw.com/internal/devvit/recipecard",
        endpointPath: "/internal/devvit/recipecard",
        commandCommentId: "t1_command",
        subreddit: "recipes",
        hint: "Check Devvit HTTP fetch domain approval, DNS/IPv6, and TLS reachability.",
      }),
    });
    expect(JSON.stringify(logger.entries)).not.toContain("never-log-this-secret");
    expect(JSON.stringify(logger.entries)).not.toContain("X-RecipeBot-Signature");
  });

  it("logs the HTTP status and body for a non-2xx response", async () => {
    const logger = new TestLogger();
    const result = await sendRecipeCardRequest(
      payload,
      {
        backendUrl: "https://recipebot.devgw.com",
        webhookSecret: "test-secret",
      },
      logger,
      async () => new Response('{"error":"unauthorized"}', { status: 401 }),
    );

    expect(result).toEqual({ ok: false, reason: "http" });
    expect(logger.entries).toContainEqual({
      message: "RecipeBot backend response",
      details: expect.objectContaining({
        httpStatus: 401,
        responseBody: '{"error":"unauthorized"}',
      }),
    });
  });
});
