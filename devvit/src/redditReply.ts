/** Public Reddit replies for successful RecipeBot command handling. */

import type { RecipeBotLogger } from "./recipebotClient.js";
import type { CommentId } from "./redditSource.js";

export interface RedditCommentSubmitter {
  submitComment(options: {
    id: CommentId;
    runAs: "APP";
    text: string;
  }): Promise<unknown>;
}

/** Build the public reply text shown after a card job is queued. */
export function buildRecipeBotReply(
  cardUrl: string,
  status: "queued" | "processing" | "ready" | "existing",
): string {
  if (status === "ready") {
    return [
      "Your RecipeBot card is ready:",
      "",
      cardUrl,
    ].join("\n");
  }
  if (status === "existing") {
    return [
      "RecipeBot already has a card job for this request:",
      "",
      cardUrl,
    ].join("\n");
  }
  return [
    "RecipeBot is generating your card:",
    "",
    cardUrl,
    "",
    "The page will update when the PNG, SVG, and PDF files are ready.",
  ].join("\n");
}

/** Post a public app-authored reply on the original command comment. */
export async function replyToCommandComment(
  commandCommentId: CommentId,
  cardUrl: string,
  status: "queued" | "processing" | "ready" | "existing",
  reddit: RedditCommentSubmitter,
  logger: RecipeBotLogger = console,
): Promise<boolean> {
  try {
    await reddit.submitComment({
      id: commandCommentId,
      text: buildRecipeBotReply(cardUrl, status),
      runAs: "APP",
    });
    logger.log("RecipeBot command reply posted", {
      commandCommentId,
      cardUrl,
    });
    console.log("RecipeBot command reply posted", {
      commandCommentId,
      cardUrl,
    });
    return true;
  } catch (error) {
    const failureDetails = {
      commandCommentId,
      cardUrl,
      errorName: errorName(error),
      errorMessage: errorMessage(error),
    };
    logger.error("RecipeBot command reply failed", failureDetails);
    console.error("RecipeBot command reply failed", failureDetails);
    return false;
  }
}

function errorName(error: unknown): string {
  return error instanceof Error ? error.name : "UnknownError";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
