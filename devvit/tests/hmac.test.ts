import { describe, expect, it } from "vitest";

import { createRecipeBotSignature } from "../src/hmac.js";

describe("RecipeBot HMAC", () => {
  it("signs timestamp dot raw body with lowercase SHA-256 hex", () => {
    const signature = createRecipeBotSignature(
      "test-secret",
      "1780000000",
      '{"command_comment_id":"t1_command"}',
    );

    expect(signature).toMatch(/^[0-9a-f]{64}$/);
    expect(signature).toBe("9710045df21de2ad390dda93b9579e3667122d09819c09b0ae626e45126bbef2");
  });
});
