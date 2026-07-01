# RecipeBot Devvit adapter

This server-only Devvit app watches comment-created events for the exact `!recipecard` command. It resolves the command's parent comment or post, signs a normalized JSON payload, and sends it to RecipeBot's Flask backend. It does not render cards, persist recipes, send messages, or post replies.

## Fetch Domains

The app requests access only to `recipebot.devgw.com`. It sends the command fullname and requester username plus the parent recipe's subreddit, fullname, title, body, permalink, URL, type, and creation timestamp to create a RecipeBot job. No Reddit password, OAuth client id, or client secret is used; Devvit provides installation-scoped Reddit access.

Public distribution of an app using HTTP fetch also requires suitable terms and privacy-policy links in its Developer Portal app details. Playtesting in a subreddit you moderate does not require public app review.

## Setup

The repository's `.tool-versions` pins Node for asdf:

```bash
asdf install
asdf current nodejs
cd devvit
npm install
```

Authenticate the Devvit CLI:

```bash
npx devvit login
```

Configure the backend URL and the same HMAC secret used by Flask's `DEVVIT_WEBHOOK_SECRET`:

```bash
npx devvit settings set RECIPEBOT_BACKEND_URL
npx devvit settings set RECIPEBOT_WEBHOOK_SECRET
```

Use `https://recipebot.devgw.com` for `RECIPEBOT_BACKEND_URL`. The webhook secret is declared as a global secret setting and must never be committed or logged.

## Test and build

```bash
npm test
npm run typecheck
npm run build
```

## Playtest

Create a small subreddit named `RecipeBotTest`, ensure your Reddit account is a moderator, and run:

```bash
npx devvit playtest r/RecipeBotTest
```

In the playtest subreddit, reply to a recipe comment or text post with exactly `!recipecard`. Extra text and flags are ignored. The adapter queues silently: it sends no DM and creates no public reply.
