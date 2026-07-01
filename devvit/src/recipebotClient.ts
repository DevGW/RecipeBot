/** Signed HTTP client for RecipeBot's Devvit ingestion endpoint. */

import { createRecipeBotSignature } from "./hmac.js";
import type { RecipeBotPayload } from "./redditSource.js";

const INGESTION_PATH = "/internal/devvit/recipecard";

export interface RecipeBotClientConfig {
  backendUrl: string;
  webhookSecret: string;
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
    url: `${backendUrl}${INGESTION_PATH}`,
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

/** Send one signed command to RecipeBot and return its durable job response. */
export async function sendRecipeCardRequest(
  payload: RecipeBotPayload,
  config: RecipeBotClientConfig,
  fetcher: typeof fetch = fetch,
): Promise<RecipeBotResponse> {
  const request = buildRecipeBotRequest(payload, config);
  const response = await fetcher(request.url, request.init);
  if (!response.ok) {
    throw new Error(`RecipeBot backend returned HTTP ${response.status}`);
  }
  return (await response.json()) as RecipeBotResponse;
}
