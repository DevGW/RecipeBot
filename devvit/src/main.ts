/** Devvit trigger entrypoint for RecipeBot command ingestion. */

import { context, reddit, settings } from "@devvit/web/server";
import type { OnCommentCreateRequest, TriggerResponse } from "@devvit/web/shared";
import { Hono } from "hono";

import { isExactRecipeCardCommand, shouldHandleCommand } from "./command.js";
import { sendRecipeCardRequest } from "./recipebotClient.js";
import { buildRecipeBotPayload, isCommentId } from "./redditSource.js";

const app = new Hono();

app.post("/internal/triggers/comment-create", async (c) => {
  const input = await c.req.json<OnCommentCreateRequest>();
  const eventComment = input.comment;
  const eventAuthorName = input.author?.name;
  const eventIsFromApp = eventAuthorName?.toLowerCase() === context.appSlug.toLowerCase();
  if (!eventComment?.id || !isCommentId(eventComment.id) || eventIsFromApp ||
      !isExactRecipeCardCommand(eventComment.body)) {
    return c.json<TriggerResponse>({ status: "ignored" });
  }

  try {
    const command = await reddit.getCommentById(eventComment.id);
    if (!shouldHandleCommand(command, context.appSlug)) {
      return c.json<TriggerResponse>({ status: "ignored" });
    }

    const payload = await buildRecipeBotPayload(command, reddit);
    if (!payload) return c.json<TriggerResponse>({ status: "ignored" });

    const backendUrl = await requiredSetting("RECIPEBOT_BACKEND_URL");
    const webhookSecret = await requiredSetting("RECIPEBOT_WEBHOOK_SECRET");
    const result = await sendRecipeCardRequest(payload, { backendUrl, webhookSecret });
    console.log(`RecipeBot command ${payload.command_comment_id}: ${result.status} job ${result.job_id}`);
    return c.json<TriggerResponse>({ status: "ok" });
  } catch (error) {
    console.error(`RecipeBot command ingestion failed (${errorName(error)})`);
    return c.json({ status: "error" }, 500);
  }
});

async function requiredSetting(name: string): Promise<string> {
  const value = await settings.get(name);
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`Missing required setting: ${name}`);
  }
  return value.trim();
}

function errorName(error: unknown): string {
  return error instanceof Error ? error.name : "UnknownError";
}

export default app;
