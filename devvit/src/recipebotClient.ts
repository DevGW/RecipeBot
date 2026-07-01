/** Signed HTTP client for RecipeBot's Devvit ingestion endpoint. */

import { createRecipeBotSignature } from "./hmac.js";
import type { RecipeBotPayload } from "./redditSource.js";

export const RECIPEBOT_INGESTION_PATH = "/internal/devvit/recipecard";

export interface RecipeBotClientConfig {
  backendUrl: string;
  webhookSecret: string;
}

export interface RecipeBotLogger {
  error(message: string, details?: Record<string, unknown>): void;
  log(message: string, details?: Record<string, unknown>): void;
}

export interface RecipeBotRequest {
  init: RequestInit;
  rawBody: string;
  url: string;
}

export interface RecipeBotResponse {
  card_url: string;
  job_id: number;
  status: "queued" | "existing";
}

export type RecipeBotSendResult =
  | { ok: true; response: RecipeBotResponse }
  | { ok: false; reason: "fetch" | "http" | "response" };

/** Build a deterministic signed backend request without sending it. */
export function buildRecipeBotRequest(
  payload: RecipeBotPayload,
  config: RecipeBotClientConfig,
  timestamp = Math.floor(Date.now() / 1000).toString(),
): RecipeBotRequest {
  const backendUrl = config.backendUrl.replace(/\/+$/, "");
  const rawBody = JSON.stringify(payload);
  const signature = createRecipeBotSignature(config.webhookSecret, timestamp, rawBody);
  return {
    url: `${backendUrl}${RECIPEBOT_INGESTION_PATH}`,
    rawBody,
    init: {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-RecipeBot-Timestamp": timestamp,
        "X-RecipeBot-Signature": signature,
      },
      body: rawBody,
    },
  };
}

/** Send one signed command without allowing fetch or response errors to escape. */
export async function sendRecipeCardRequest(
  payload: RecipeBotPayload,
  config: RecipeBotClientConfig,
  logger: RecipeBotLogger = console,
  fetcher: typeof fetch = fetch,
): Promise<RecipeBotSendResult> {
  const request = buildRecipeBotRequest(payload, config);
  const diagnosticContext = {
    backendUrl: config.backendUrl,
    finalPostUrl: request.url,
    endpointPath: RECIPEBOT_INGESTION_PATH,
    webhookSecretPresent: Boolean(config.webhookSecret),
    commandCommentId: payload.command_comment_id,
    subreddit: payload.subreddit,
  };
  logger.log("RecipeBot backend request", diagnosticContext);
  console.log("RecipeBot backend request", diagnosticContext);

  let response: Response;
  try {
    response = await fetcher(request.url, request.init);
  } catch (error) {
    const fetchFailureDetails = {
      ...diagnosticContext,
      errorName: errorName(error),
      errorMessage: errorMessage(error),
      hint: "Check Devvit HTTP fetch domain approval, DNS/IPv6, and TLS reachability.",
    };
    logger.error("RecipeBot backend fetch failed", fetchFailureDetails);
    console.error("RecipeBot backend fetch failed", fetchFailureDetails);
    return { ok: false, reason: "fetch" };
  }

  let responseBody: string;
  try {
    responseBody = await response.text();
  } catch (error) {
    logger.error("RecipeBot backend response read failed", {
      ...diagnosticContext,
      httpStatus: response.status,
      errorName: errorName(error),
      errorMessage: errorMessage(error),
    });
    return { ok: false, reason: "response" };
  }

  const responseDetails = {
    ...diagnosticContext,
    httpStatus: response.status,
    responseBody,
  };
  logger.log("RecipeBot backend response", responseDetails);
  if (!response.ok) {
    console.error("RecipeBot backend non-2xx response", responseDetails);
    return { ok: false, reason: "http" };
  }

  try {
    const parsed = JSON.parse(responseBody) as RecipeBotResponse;
    console.log("RecipeBot backend request succeeded", {
      ...diagnosticContext,
      httpStatus: response.status,
      jobId: parsed.job_id,
      cardUrl: parsed.card_url,
      status: parsed.status,
    });
    return {
      ok: true,
      response: parsed,
    };
  } catch (error) {
    logger.error("RecipeBot backend response was not valid JSON", {
      ...diagnosticContext,
      errorName: errorName(error),
      errorMessage: errorMessage(error),
    });
    return { ok: false, reason: "response" };
  }
}

function errorName(error: unknown): string {
  return error instanceof Error ? error.name : "UnknownError";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
