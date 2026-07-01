/** Devvit trigger entrypoint for RecipeBot command ingestion. */

import { context, reddit, settings } from "@devvit/web/server";
import type { OnCommentCreateRequest, TriggerResponse } from "@devvit/web/shared";
import { Hono } from "hono";

import { isExactRecipeCardCommand, shouldHandleCommand } from "./command.js";
import {
  sendRecipeCardRequest,
  type RecipeBotClientConfig,
  type RecipeBotLogger,
  type RecipeBotSendResult,
} from "./recipebotClient.js";
import {
  buildRecipeBotPayload,
  isCommentId,
  type RedditSourceReader,
  type RecipeBotPayload,
} from "./redditSource.js";

export interface CommentCreateEvent {
  author?: { name?: string | undefined } | undefined;
  comment?: { body?: string | undefined; id?: string | undefined } | undefined;
}

export interface CommentTriggerDependencies {
  appSlug: string;
  getSetting(name: string): Promise<unknown>;
  logger: RecipeBotLogger;
  reddit: RedditSourceReader;
  sendRequest(
    payload: RecipeBotPayload,
    config: RecipeBotClientConfig,
    logger: RecipeBotLogger,
  ): Promise<RecipeBotSendResult>;
}

export type CommentTriggerStatus = "error" | "ignored" | "ok";

/** Process one comment-created event and always resolve with a trigger status. */
export async function handleCommentCreate(
  input: CommentCreateEvent,
  dependencies: CommentTriggerDependencies,
): Promise<CommentTriggerStatus> {
  try {
    const eventComment = input.comment;
    const eventAuthorName = input.author?.name;
    const eventIsFromApp =
      eventAuthorName?.toLowerCase() === dependencies.appSlug.toLowerCase();
    if (
      !eventComment?.id ||
      !isCommentId(eventComment.id) ||
      eventIsFromApp ||
      !isExactRecipeCardCommand(eventComment.body)
    ) {
      return "ignored";
    }

    const backendUrl = await dependencies.getSetting("RECIPEBOT_BACKEND_URL");
    if (typeof backendUrl !== "string" || !backendUrl.trim()) {
      dependencies.logger.error("RecipeBot backend URL setting is missing");
      return "error";
    }
    const webhookSecret = await dependencies.getSetting("RECIPEBOT_WEBHOOK_SECRET");
    if (typeof webhookSecret !== "string" || !webhookSecret.trim()) {
      dependencies.logger.error("RecipeBot webhook secret setting is missing");
      return "error";
    }

    const command = await dependencies.reddit.getCommentById(eventComment.id);
    if (!shouldHandleCommand(command, dependencies.appSlug)) return "ignored";

    const payload = await buildRecipeBotPayload(command, dependencies.reddit);
    if (!payload) return "ignored";

    const result = await dependencies.sendRequest(
      payload,
      {
        backendUrl: backendUrl.trim(),
        webhookSecret: webhookSecret.trim(),
      },
      dependencies.logger,
    );
    if (!result.ok) return "error";

    dependencies.logger.log("RecipeBot backend job accepted", {
      status: result.response.status,
      jobId: result.response.job_id,
      cardUrl: result.response.card_url,
      commandCommentId: payload.command_comment_id,
      subreddit: payload.subreddit,
    });
    return "ok";
  } catch (error) {
    dependencies.logger.error("RecipeBot comment trigger failed safely", {
      errorName: errorName(error),
      errorMessage: errorMessage(error),
    });
    return "error";
  }
}

const app = new Hono();

app.post("/internal/triggers/comment-create", async (c) => {
  try {
    const input = await c.req.json<OnCommentCreateRequest>();
    const status = await handleCommentCreate(input, {
      appSlug: context.appSlug,
      getSetting: (name) => settings.get(name),
      logger: console,
      reddit,
      sendRequest: sendRecipeCardRequest,
    });
    return c.json<TriggerResponse>({ status });
  } catch (error) {
    console.error("RecipeBot comment-created endpoint failed safely", {
      errorName: errorName(error),
      errorMessage: errorMessage(error),
    });
    return c.json({ status: "error" });
  }
});

function errorName(error: unknown): string {
  return error instanceof Error ? error.name : "UnknownError";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default app;
