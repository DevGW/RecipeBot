import { describe, expect, it, vi } from "vitest";

import {
  createRecipeBotApp,
  handleCommentCreate,
  handleOnCommentCreateTrigger,
  type CommentTriggerDependencies,
} from "../src/app.js";
import { sendRecipeCardRequest } from "../src/recipebotClient.js";
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
        ok: true,
        status: "queued",
        job_id: 123,
        card_url: "https://recipebot.devgw.com/cards/123",
    },
  }),
  redditReplier: CommentTriggerDependencies["redditReplier"] = {
    submitComment: async () => ({}),
  },
): CommentTriggerDependencies & { logger: TestLogger } {
  return {
    appSlug: "recipebot-devgw",
    getSetting: async (name) => settings[name],
    logger,
    reddit: redditReader(),
    redditReplier,
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
    const submitComment = vi.fn(async () => ({}));
    const deps = dependencies(
      {
        RECIPEBOT_BACKEND_URL: "https://recipebot.devgw.com",
        RECIPEBOT_WEBHOOK_SECRET: "secret",
      },
      new TestLogger(),
      async () => ({ ok: false, reason: "fetch" }),
      { submitComment },
    );

    await expect(handleCommentCreate(event, deps)).resolves.toBe("error");
    expect(submitComment).not.toHaveBeenCalled();
  });

  it("sends the backend request for the exact standalone command", async () => {
    const sendRequest = vi.fn<CommentTriggerDependencies["sendRequest"]>(async () => ({
      ok: true,
      response: {
        ok: true,
        status: "queued",
        job_id: 123,
        card_url: "https://recipebot.devgw.com/cards/123",
      },
    }));
    const deps = dependencies(
      {
        RECIPEBOT_BACKEND_URL: "https://recipebot.devgw.com",
        RECIPEBOT_WEBHOOK_SECRET: "secret",
      },
      new TestLogger(),
      sendRequest,
    );

    await expect(handleCommentCreate(event, deps)).resolves.toBe("ok");
    expect(sendRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        command_comment_id: "t1_command",
        source_fullname: "t1_parent",
      }),
      {
        backendUrl: "https://recipebot.devgw.com",
        webhookSecret: "secret",
      },
      deps.logger,
    );
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

  it("replies to the command comment after a successful backend response", async () => {
    const submitComment = vi.fn(async () => ({}));
    const deps = dependencies(
      {
        RECIPEBOT_BACKEND_URL: "https://recipebot.devgw.com",
        RECIPEBOT_WEBHOOK_SECRET: "secret",
      },
      new TestLogger(),
      async () => ({
        ok: true,
        response: {
          ok: true,
          status: "queued",
          job_id: 123,
          card_url: "https://recipebot.devgw.com/cards/123",
        },
      }),
      { submitComment },
    );

    await expect(handleCommentCreate(event, deps)).resolves.toBe("ok");
    expect(submitComment).toHaveBeenCalledWith({
      id: "t1_command",
      text: [
        "RecipeBot is generating your card:",
        "",
        "https://recipebot.devgw.com/cards/123",
        "",
        "The page will update when the PNG, SVG, and PDF files are ready.",
      ].join("\n"),
      runAs: "APP",
    });
    expect(deps.logger.entries).toContainEqual({
      message: "RecipeBot command reply posted",
      details: expect.objectContaining({
        commandCommentId: "t1_command",
        cardUrl: "https://recipebot.devgw.com/cards/123",
      }),
    });
  });

  it("uses the ready reply when the backend says the card is ready", async () => {
    const submitComment = vi.fn(async () => ({}));
    const deps = dependencies(
      {
        RECIPEBOT_BACKEND_URL: "https://recipebot.devgw.com",
        RECIPEBOT_WEBHOOK_SECRET: "secret",
      },
      new TestLogger(),
      async () => ({
        ok: true,
        response: {
          ok: true,
          status: "ready",
          job_id: 123,
          card_url: "https://recipebot.devgw.com/cards/123",
        },
      }),
      { submitComment },
    );

    await expect(handleCommentCreate(event, deps)).resolves.toBe("ok");
    expect(submitComment).toHaveBeenCalledWith({
      id: "t1_command",
      text: [
        "Your RecipeBot card is ready:",
        "",
        "https://recipebot.devgw.com/cards/123",
      ].join("\n"),
      runAs: "APP",
    });
  });

  it("uses the existing job reply when the backend reports a duplicate job", async () => {
    const submitComment = vi.fn(async () => ({}));
    const deps = dependencies(
      {
        RECIPEBOT_BACKEND_URL: "https://recipebot.devgw.com",
        RECIPEBOT_WEBHOOK_SECRET: "secret",
      },
      new TestLogger(),
      async () => ({
        ok: true,
        response: {
          ok: true,
          status: "existing",
          job_id: 123,
          card_url: "https://recipebot.devgw.com/cards/123",
        },
      }),
      { submitComment },
    );

    await expect(handleCommentCreate(event, deps)).resolves.toBe("ok");
    expect(submitComment).toHaveBeenCalledWith({
      id: "t1_command",
      text: [
        "RecipeBot already has a card job for this request:",
        "",
        "https://recipebot.devgw.com/cards/123",
      ].join("\n"),
      runAs: "APP",
    });
  });

  it("ignores malformed commands without calling backend or replying", async () => {
    const sendRequest = vi.fn<CommentTriggerDependencies["sendRequest"]>();
    const submitComment = vi.fn(async () => ({}));
    const deps = dependencies(
      {
        RECIPEBOT_BACKEND_URL: "https://recipebot.devgw.com",
        RECIPEBOT_WEBHOOK_SECRET: "secret",
      },
      new TestLogger(),
      sendRequest,
      { submitComment },
    );

    await expect(handleCommentCreate({
      author: { name: "example_user" },
      comment: { id: "t1_command", body: "!recipecard please" },
    }, deps)).resolves.toBe("ignored");
    expect(sendRequest).not.toHaveBeenCalled();
    expect(submitComment).not.toHaveBeenCalled();
  });

  it("ignores app-authored comments without calling backend or replying", async () => {
    const sendRequest = vi.fn<CommentTriggerDependencies["sendRequest"]>();
    const submitComment = vi.fn(async () => ({}));
    const deps = dependencies(
      {
        RECIPEBOT_BACKEND_URL: "https://recipebot.devgw.com",
        RECIPEBOT_WEBHOOK_SECRET: "secret",
      },
      new TestLogger(),
      sendRequest,
      { submitComment },
    );

    await expect(handleCommentCreate({
      author: { name: "recipebot-devgw" },
      comment: { id: "t1_command", body: "!recipecard" },
    }, deps)).resolves.toBe("ignored");
    expect(sendRequest).not.toHaveBeenCalled();
    expect(submitComment).not.toHaveBeenCalled();
  });

  it("resolves safely when the Reddit reply call rejects", async () => {
    const deps = dependencies(
      {
        RECIPEBOT_BACKEND_URL: "https://recipebot.devgw.com",
        RECIPEBOT_WEBHOOK_SECRET: "secret",
      },
      new TestLogger(),
      async () => ({
        ok: true,
        response: {
          ok: true,
          status: "queued",
          job_id: 123,
          card_url: "https://recipebot.devgw.com/cards/123",
        },
      }),
      {
        submitComment: async () => {
          throw new Error("reply rejected");
        },
      },
    );

    await expect(handleCommentCreate(event, deps)).resolves.toBe("ok");
    expect(deps.logger.entries).toContainEqual({
      message: "RecipeBot command reply failed",
      details: expect.objectContaining({
        commandCommentId: "t1_command",
        cardUrl: "https://recipebot.devgw.com/cards/123",
        errorMessage: "reply rejected",
      }),
    });
  });
});

describe("Hono app route", () => {
  it("exports a Hono app with fetch from createRecipeBotApp", () => {
    const app = createRecipeBotApp(
      dependencies({
        RECIPEBOT_BACKEND_URL: "https://recipebot.devgw.com",
        RECIPEBOT_WEBHOOK_SECRET: "secret",
      }),
    );

    expect(app).toBeDefined();
    expect(typeof app.fetch).toBe("function");
  });

  it("POST /internal/triggers/comment-create returns 200 for a minimal request", async () => {
    const app = createRecipeBotApp(
      dependencies({
        RECIPEBOT_BACKEND_URL: "https://recipebot.devgw.com",
        RECIPEBOT_WEBHOOK_SECRET: "secret",
      }),
    );

    const response = await app.request("/internal/triggers/comment-create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        author: { name: "example_user" },
        comment: { id: "t1_other", body: "not a command" },
      }),
    });

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ status: "ignored" });
  });
});

describe("onCommentCreate trigger handler", () => {
  it("resolves without throwing when fetch rejects with fetch failed", async () => {
    const fetchError = new Error("fetch failed");
    const sendRequest: CommentTriggerDependencies["sendRequest"] = async (payload, config, logger) =>
      await sendRecipeCardRequest(
        payload,
        config,
        logger,
        async () => { throw fetchError; },
      );

    const deps = dependencies(
      {
        RECIPEBOT_BACKEND_URL: "https://recipebot.devgw.com",
        RECIPEBOT_WEBHOOK_SECRET: "secret",
      },
      new TestLogger(),
      sendRequest,
    );

    await expect(handleOnCommentCreateTrigger(event, deps)).resolves.toEqual({ status: "error" });
  });
});
