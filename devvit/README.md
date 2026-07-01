# RecipeBot Devvit Adapter

RecipeBot's Devvit adapter is a server-only Reddit app that watches comment-created events for the exact `!recipecard` command.

When a user replies to a recipe post or comment with `!recipecard`, the Devvit app resolves the command's parent comment or post, signs a normalized JSON payload, and sends it to RecipeBot's Flask backend.

The Devvit app does not render recipe cards, persist recipes, send DMs, or create public Reddit replies. Rendering, persistence, artifact generation, and artifact hosting are handled by the backend at:

```text
https://recipebot.devgw.com
```

## Current Architecture

```text
Reddit / Devvit
  onCommentCreate trigger
  exact !recipecard detection
  parent post/comment resolution
  signed POST to Flask backend

Hemlock / Docker Compose
  Flask/Gunicorn backend
  Postgres
  worker
  ImageMagick/rsvg renderer
  artifact hosting
```

Devvit does not run on Hemlock. Devvit runs through Reddit's Devvit runtime after upload or playtest. Hemlock only runs the backend services.

## Command Behavior

RecipeBot only accepts the exact standalone command:

```text
!recipecard
```

The adapter ignores:

- extra text
- flags
- malformed commands
- deleted or removed content where detectable
- app-authored comments where detectable

Example valid command:

```text
!recipecard
```

Examples ignored by design:

```text
!recipecard please
!recipecard --pdf
make me a !recipecard
```

## Backend Request

The adapter sends a signed `POST` request to:

```text
https://recipebot.devgw.com/internal/devvit/recipecard
```

The request is signed with HMAC SHA-256.

Signature message:

```text
timestamp + "." + raw JSON body
```

Headers:

```text
X-RecipeBot-Timestamp
X-RecipeBot-Signature
```

The webhook secret is configured through Devvit settings as:

```text
RECIPEBOT_WEBHOOK_SECRET
```

It must match the backend's Flask environment variable:

```text
DEVVIT_WEBHOOK_SECRET
```

The secret must never be committed or logged.

## Payload Sent to Backend

The Devvit adapter sends the minimum data needed to create a RecipeBot job:

```text
command_comment_id
requester_username
subreddit
source_type
source_fullname
source_title
source_body
source_permalink
source_url
created_utc
```

The backend validates the payload, verifies the HMAC signature, deduplicates repeated command events, queues a rendering job, and returns a card URL such as:

```text
https://recipebot.devgw.com/cards/<id>
```

## Fetch Domains

RecipeBot requests access only to this external fetch domain:

```text
recipebot.devgw.com
```

This domain is the RecipeBot backend API. Devvit uses it only to submit signed `!recipecard` jobs to the backend.

RecipeBot does not use this domain for:

- advertising
- tracking
- resale of user data
- credential collection
- Reddit password collection
- OAuth client-secret collection

No Reddit password, OAuth client ID, or OAuth client secret is used by this adapter. Devvit provides the Reddit-side installation context.

### Current Domain Review Status

The domain exception for:

```text
recipebot.devgw.com
```

may show as `Pending` in the Reddit Developer Portal after upload or playtest.

Until Reddit approves the domain, live playtest requests will fail with an error similar to:

```text
HTTP request to domain: recipebot.devgw.com is not allowed
```

That error means the Devvit trigger is working, but Reddit is blocking the outbound fetch before it reaches the RecipeBot backend.

Check status here:

```text
https://developers.reddit.com/apps/recipebot-devgw/developer-settings
```

Look under:

```text
Domain exceptions
```

Expected final status:

```text
Approved
```

## Privacy and Terms Links

Apps that use HTTP fetch should have suitable Terms and Privacy Policy links configured in the Reddit Developer Portal app details.

Recommended hosted pages:

```text
https://recipebot.devgw.com/privacy
https://recipebot.devgw.com/terms
```

These should explain, at minimum:

- what Reddit data is sent to RecipeBot
- why it is sent
- how generated artifacts are hosted
- that RecipeBot does not collect Reddit passwords
- that RecipeBot does not sell user data
- how users or moderators can request removal of generated artifacts

## Devvit Configuration

The app is configured in:

```text
devvit.json
```

The server entry must point to the CommonJS server bundle:

```json
{
  "server": {
    "entry": "dist/server/index.cjs"
  }
}
```

The comment trigger is mapped to an internal server route:

```json
{
  "triggers": {
    "onCommentCreate": "/internal/triggers/comment-create"
  }
}
```

The fetch domain must be the exact hostname only:

```json
{
  "permissions": {
    "http": {
      "enable": true,
      "domains": ["recipebot.devgw.com"]
    },
    "reddit": true
  }
}
```

Do not use:

```text
https://recipebot.devgw.com
recipebot.devgw.com/internal/devvit/recipecard
*.devgw.com
```

## Server Runtime

The Devvit server entry starts a Hono server using Devvit Web's server runtime.

The expected runtime pattern is:

```ts
import { serve } from "@hono/node-server";
import { createServer, getServerPort } from "@devvit/web/server";
import { app } from "./app";

serve({
  fetch: app.fetch,
  createServer,
  port: getServerPort(),
});
```

Tests should import the Hono app directly from the app module. Tests should not start the real Devvit server.

## Local Setup

The repository uses `asdf` for Node.

From the repository root:

```bash
asdf install
asdf current nodejs
```

Then:

```bash
cd devvit
npm install
```

## Devvit Authentication

Authenticate the Devvit CLI:

```bash
npx devvit login
```

On a remote machine such as Hemlock, Devvit login may start a localhost OAuth callback. Use SSH port forwarding if needed:

```bash
ssh -L 65010:127.0.0.1:65010 rogue@hemlock
```

Then run:

```bash
cd /opt/recipebot/devvit
npx devvit login
```

Open the printed Reddit OAuth URL in your local browser. The localhost callback will forward through SSH to Hemlock.

Verify login:

```bash
npx devvit whoami
```

## Settings

Configure the backend URL:

```bash
npx devvit settings set RECIPEBOT_BACKEND_URL
```

Use:

```text
https://recipebot.devgw.com
```

Configure the webhook secret:

```bash
npx devvit settings set RECIPEBOT_WEBHOOK_SECRET
```

Use the same value as the backend's `DEVVIT_WEBHOOK_SECRET`.

Do not paste the secret into chat, commits, screenshots, logs, or README files.

## Test and Build

From `devvit/`:

```bash
npm test
npm run typecheck
npm run build
```

Useful bundle checks:

```bash
grep -R "RecipeBot onCommentCreate handler entered" -n dist/server/index.cjs
grep -R "RecipeBot checking comment command" -n dist/server/index.cjs
grep -R "RecipeBot backend request" -n dist/server/index.cjs
grep -R "serve({" -n dist/server/index.cjs
grep -R "getServerPort" -n dist/server/index.cjs
```

## Upload

From `devvit/`:

```bash
npx devvit upload
```

Do not publish until the fetch domain is approved and the app details include appropriate Terms and Privacy Policy links.

## Playtest

Default playtest subreddit:

```text
r/recipebot_devgw_dev
```

Run:

```bash
npx devvit playtest r/recipebot_devgw_dev
```

Create a recipe post or comment, then reply exactly:

```text
!recipecard
```

Expected Devvit logs when the trigger is working:

```text
RecipeBot onCommentCreate handler entered
RecipeBot checking comment command
RecipeBot backend request
```

If the fetch domain is still pending, the backend request will fail with:

```text
HTTP request to domain: recipebot.devgw.com is not allowed
```

That means the adapter is working, but Reddit has not approved the external fetch domain yet.

## Backend Log Watching

On Hemlock:

```bash
cd /opt/recipebot
sudo docker compose -f docker-compose.prod.yml logs -f web worker
```

Once the fetch domain is approved, a successful command should produce this flow:

```text
Devvit trigger
  -> signed POST to Flask
  -> backend queues job
  -> worker renders artifacts
  -> card page appears under /cards/<id>
```

## Known Current Blockers

### Fetch domain approval

Current blocker:

```text
recipebot.devgw.com is pending domain approval
```

Until Reddit approves the domain, Devvit cannot call the backend.

Check:

```text
https://developers.reddit.com/apps/recipebot-devgw/developer-settings
```

### Playtest dev script warning

If playtest shows:

```text
cp: unrecognized option '--watch'
```

then the npm dev/watch script is passing `--watch` through to `cp`.

Fix by separating build and watch behavior so only `esbuild` receives watch mode, or by using a small Node copy script that runs after build.

This warning is separate from the fetch-domain approval issue.

## What This Adapter Does Not Do

The Devvit adapter does not:

- render recipe cards
- store recipes
- write to Postgres
- send DMs
- post public replies
- upload media
- use Redis
- use PRAW
- use Reddit username/password auth
- use OAuth client ID/client secret auth

Those responsibilities either do not exist yet or belong to the Flask backend.

## Useful Commands

Local Mac commit flow:

```bash
cd /Volumes/MBAEXT/Development/bots/RecipeBot

git status
git add devvit
git commit -m "Update Devvit adapter documentation"
git push
```

Hemlock pull and upload flow:

```bash
cd /opt/recipebot
git pull

cd devvit
npm install
npm test
npm run build
npx devvit upload
```

Hemlock playtest flow:

```bash
cd /opt/recipebot/devvit
npx devvit playtest r/recipebot_devgw_dev
```

Backend logs:

```bash
cd /opt/recipebot
sudo docker compose -f docker-compose.prod.yml logs -f web worker
```
