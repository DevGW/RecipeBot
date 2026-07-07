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
  ok?: boolean;
  status: "queued" | "processing" | "ready" | "existing";
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
    ...(response.ok
      ? { responseBody }
      : sanitizedBackendResponseDetails(responseBody)),
  };
  logger.log("RecipeBot backend response", responseDetails);
  if (!response.ok) {
    console.error("RecipeBot backend non-2xx response", responseDetails);
    return { ok: false, reason: "http" };
  }

  try {
    const parsed = parseRecipeBotResponse(responseBody);
    if (!parsed) {
      logger.error("RecipeBot backend response was missing a usable card URL", {
        ...diagnosticContext,
        httpStatus: response.status,
      });
      return { ok: false, reason: "response" };
    }
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

function parseRecipeBotResponse(responseBody: string): RecipeBotResponse | null {
  const parsed = JSON.parse(responseBody) as {
    card_url?: unknown;
    job_id?: unknown;
    ok?: unknown;
    status?: unknown;
    status_url?: unknown;
  };
  if (parsed.ok === false) return null;
  const cardUrl = typeof parsed.card_url === "string" && parsed.card_url.trim()
    ? parsed.card_url
    : typeof parsed.status_url === "string" && parsed.status_url.trim()
      ? parsed.status_url
      : null;
  const jobId = parseJobId(parsed.job_id);
  if (!cardUrl || jobId === null) return null;
  return {
    card_url: cardUrl,
    job_id: jobId,
    status: parseRecipeBotStatus(parsed.status),
    ...(typeof parsed.ok === "boolean" ? { ok: parsed.ok } : {}),
  };
}

function parseJobId(jobId: unknown): number | null {
  if (typeof jobId === "number" && Number.isInteger(jobId) && jobId > 0) return jobId;
  if (typeof jobId !== "string" || !/^[1-9]\d*$/.test(jobId)) return null;
  return Number(jobId);
}

function parseRecipeBotStatus(status: unknown): RecipeBotResponse["status"] {
  return status === "processing" || status === "ready" || status === "existing"
    ? status
    : "queued";
}

function sanitizedBackendResponseDetails(responseBody: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(responseBody) as { error?: unknown; ok?: unknown };
    return {
      backendError: typeof parsed.error === "string" ? parsed.error : "unknown",
      responseBodyLength: responseBody.length,
    };
  } catch {
    return { responseBodyLength: responseBody.length };
  }
}

function errorName(error: unknown): string {
  return error instanceof Error ? error.name : "UnknownError";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
