/** RecipeBot webhook HMAC helpers. */

import { createHmac } from "node:crypto";

/** Create the lowercase HMAC SHA-256 signature expected by RecipeBot. */
export function createRecipeBotSignature(
  secret: string,
  timestamp: string,
  rawBody: string,
): string {
  return createHmac("sha256", secret).update(`${timestamp}.${rawBody}`, "utf8").digest("hex");
}
