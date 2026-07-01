/** Devvit server entrypoint that starts the RecipeBot Hono app. */

import { serve } from "@hono/node-server";
import { context, createServer, getServerPort, reddit, settings } from "@devvit/web/server";

import { createRecipeBotApp } from "./app.js";
import { sendRecipeCardRequest } from "./recipebotClient.js";

const app = createRecipeBotApp({
  get appSlug() {
    return context.appSlug;
  },
  getSetting: async (name) => await settings.get(name),
  logger: console,
  reddit,
  redditReplier: reddit,
  sendRequest: sendRecipeCardRequest,
});

serve({
  fetch: app.fetch,
  createServer,
  port: getServerPort(),
});
