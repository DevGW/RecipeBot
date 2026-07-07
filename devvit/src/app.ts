/** RecipeBot Hono app and onCommentCreate trigger handlers. */

import type { OnCommentCreateRequest, TriggerResponse } from "@devvit/web/shared";
import { Hono } from "hono";

import { isExactRecipeCardCommand, shouldHandleCommand } from "./command.js";
import {
  type RecipeBotClientConfig,
  type RecipeBotLogger,
  type RecipeBotSendResult,
} from "./recipebotClient.js";
import {
  replyToCommandComment,
  type RedditCommentSubmitter,
} from "./redditReply.js";
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
  redditReplier: RedditCommentSubmitter;
  sendRequest(
    payload: RecipeBotPayload,
    config: RecipeBotClientConfig,
    logger: RecipeBotLogger,
  ): Promise<RecipeBotSendResult>;
}

export type CommentTriggerStatus = "error" | "ignored" | "ok";

/** Serialize a caught error for outer trigger-handler diagnostics. */
export function serializeTriggerError(error: unknown): {
  message: string;
  name: string;
  stack: string | undefined;
} {
  return {
    name: errorName(error),
    message: errorMessage(error),
    stack: error instanceof Error ? error.stack : undefined,
  };
}

/** Run the onCommentCreate trigger after the request body is parsed. */
export async function handleOnCommentCreateTrigger(
  input: CommentCreateEvent,
  dependencies: CommentTriggerDependencies,
): Promise<TriggerResponse> {
  try {
    const status = await handleCommentCreate(input, dependencies);
    return { status };
  } catch (error) {
    console.error("RecipeBot outer trigger handler failed", serializeTriggerError(error));
    return { status: "error" };
  }
}

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
    console.log("RecipeBot checking comment command");
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
    await replyToCommandComment(
      payload.command_comment_id,
      result.response.card_url,
      result.response.status,
      dependencies.redditReplier,
      dependencies.logger,
    );
    return "ok";
  } catch (error) {
    dependencies.logger.error("RecipeBot comment trigger failed safely", {
      errorName: errorName(error),
      errorMessage: errorMessage(error),
    });
    return "error";
  }
}

/** Create the RecipeBot Hono app with injectable trigger dependencies. */
export function createRecipeBotApp(
  triggerDependencies: CommentTriggerDependencies,
): Hono {
  const app = new Hono();

  app.post("/internal/triggers/comment-create", async (c) => {
    console.log("RecipeBot onCommentCreate handler entered");
    try {
      const input = await c.req.json<OnCommentCreateRequest>();
      const response = await handleOnCommentCreateTrigger(input, triggerDependencies);
      return c.json<TriggerResponse>(response);
    } catch (error) {
      console.error("RecipeBot outer trigger handler failed", serializeTriggerError(error));
      return c.json<TriggerResponse>({ status: "error" });
    }
  });

  return app;
}

function errorName(error: unknown): string {
  return error instanceof Error ? error.name : "UnknownError";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
