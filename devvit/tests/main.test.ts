import { describe, expect, it } from "vitest";

import {
  handleCommentCreate,
  type CommentTriggerDependencies,
} from "../src/main.js";
import type { RecipeBotLogger } from "../src/recipebotClient.js";
import type {
  RedditCommentSource,
  RedditPostSource,
  RedditSourceReader,
} from "../src/redditSource.js";

class TestLogger implements RecipeBotLogger {
  readonly entries: Array<{ details?: Record<string, unknown>; message: string }> = [];

  error(message: string, details?: Record<string, unknown>): void {
    this.entries.push({ message, ...(details ? { details } : {}) });
  }

  log(message: string, details?: Record<string, unknown>): void {
    this.entries.push({ message, ...(details ? { details } : {}) });
  }
}

const command: RedditCommentSource = {
  id: "t1_command",
  parentId: "t1_parent",
  postId: "t3_post",
  authorName: "example_user",
  body: "!recipecard",
  subredditName: "recipes",
  permalink: "/r/recipes/comments/post/title/command/",
  createdAt: new Date("2026-05-29T00:00:00Z"),
};

const parent: RedditCommentSource = {
  id: "t1_parent",
  parentId: "t3_post",
  postId: "t3_post",
  authorName: "cook",
  body: "Ingredients:\n- bread\nDirections:\n1. Toast.",
  subredditName: "recipes",
  permalink: "/r/recipes/comments/post/title/parent/",
  createdAt: new Date("2026-05-28T12:00:00Z"),
};

const post: RedditPostSource = {
  id: "t3_post",
  title: "Tomato Toast",
  body: "Post body",
  subredditName: "recipes",
  permalink: "/r/recipes/comments/post/title/",
  url: "https://www.reddit.com/r/recipes/comments/post/title/",
  createdAt: new Date("2026-05-28T10:00:00Z"),
};

function redditReader(): RedditSourceReader {
  return {
    async getCommentById(id) { return id === command.id ? command : parent; },
    async getPostById() { return post; },
  };
}

function dependencies(
  settings: Record<string, unknown>,
  logger = new TestLogger(),
  sendRequest: CommentTriggerDependencies["sendRequest"] = async () => ({
    ok: true,
    response: {
      status: "queued",
      job_id: 123,
      card_url: "https://recipebot.devgw.com/cards/123",
    },
  }),
): CommentTriggerDependencies & { logger: TestLogger } {
  return {
    appSlug: "recipebot-devgw",
    getSetting: async (name) => settings[name],
    logger,
    reddit: redditReader(),
    sendRequest,
  };
}

const event = {
  author: { name: "example_user" },
  comment: { id: "t1_command", body: "!recipecard" },
};

describe("comment-created trigger", () => {
  it("returns safely when the backend URL is missing", async () => {
    const deps = dependencies({ RECIPEBOT_WEBHOOK_SECRET: "secret" });

    await expect(handleCommentCreate(event, deps)).resolves.toBe("error");
    expect(deps.logger.entries).toContainEqual({
      message: "RecipeBot backend URL setting is missing",
    });
  });

  it("returns safely when the webhook secret is missing", async () => {
    const deps = dependencies({
      RECIPEBOT_BACKEND_URL: "https://recipebot.devgw.com",
    });

    await expect(handleCommentCreate(event, deps)).resolves.toBe("error");
    expect(deps.logger.entries).toContainEqual({
      message: "RecipeBot webhook secret setting is missing",
    });
  });

  it("returns safely when the backend fetch reports failure", async () => {
    const deps = dependencies(
      {
        RECIPEBOT_BACKEND_URL: "https://recipebot.devgw.com",
        RECIPEBOT_WEBHOOK_SECRET: "secret",
      },
      new TestLogger(),
      async () => ({ ok: false, reason: "fetch" }),
    );

    await expect(handleCommentCreate(event, deps)).resolves.toBe("error");
  });

  it("logs the accepted job id and card URL", async () => {
    const deps = dependencies({
      RECIPEBOT_BACKEND_URL: "https://recipebot.devgw.com",
      RECIPEBOT_WEBHOOK_SECRET: "secret",
    });

    await expect(handleCommentCreate(event, deps)).resolves.toBe("ok");
    expect(deps.logger.entries).toContainEqual({
      message: "RecipeBot backend job accepted",
      details: expect.objectContaining({
        jobId: 123,
        cardUrl: "https://recipebot.devgw.com/cards/123",
      }),
    });
  });
});
