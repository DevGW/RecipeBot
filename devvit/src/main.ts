/** Devvit server entrypoint that wires Reddit runtime dependencies into the Hono app. */

import { context, reddit, settings } from "@devvit/web/server";

import { createRecipeBotApp } from "./serverApp.js";
import { sendRecipeCardRequest } from "./recipebotClient.js";

const app = createRecipeBotApp({
  get appSlug() {
    return context.appSlug;
  },
  getSetting: async (name) => await settings.get(name),
  logger: console,
  reddit,
  sendRequest: sendRecipeCardRequest,
});

export default app;
