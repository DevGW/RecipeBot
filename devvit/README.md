# RecipeBot Devvit Adapter

RecipeBot is a Devvit app that responds only to the exact standalone comment command:

`!recipecard`

When a Reddit user replies to a recipe post or comment with `!recipecard`, the app reads the parent post or comment, creates a minimal signed job request, and sends that request to RecipeBot's backend.

The backend accepts the job and returns a public card URL.

The Devvit app replies to the user's `!recipecard` command comment with that URL so the requester can retrieve the generated recipe card.

## External Fetch Domain

RecipeBot requests access to one external domain:

`recipebot.devgw.com`

The Devvit app sends signed job requests to:

`https://recipebot.devgw.com/internal/devvit/recipecard`

Public documentation for this endpoint is available at:

`https://recipebot.devgw.com/devvit-api`

## Why This Domain Is Needed

The Devvit app does not render recipe cards itself.

RecipeBot's backend is required because the card-generation workflow creates PNG, SVG, and PDF artifacts using a native rendering pipeline. The backend also handles job deduplication, artifact hosting, and removal requests.

## Command Behavior

RecipeBot only accepts the exact standalone command:

`!recipecard`

The app ignores malformed commands, commands with extra text, deleted or removed content where detectable, and app-authored comments where detectable.

Examples ignored by design:

`!recipecard please`

`!recipecard --pdf`

`make me a !recipecard`

## Data Sent to Backend

The Devvit app sends only the data needed to create the requested recipe card job:

- command comment id
- requester username
- subreddit
- parent post/comment fullname
- parent title/body
- parent permalink
- parent URL
- created timestamp

The backend uses this data only to create the requested recipe card job and return a hosted card URL.

## User Delivery

After the backend accepts the job, it returns a public card URL.

The Devvit app replies to the user's `!recipecard` command comment with that URL.

If the card is still rendering, the card page shows the current processing state and updates when the PNG, SVG, and PDF artifacts are ready.

## Security

Requests are signed with HMAC SHA-256.

The signature is calculated from:

`timestamp + "." + raw JSON body`

The backend validates the timestamp and signature before accepting the request.

The webhook secret is configured through Devvit settings and is never committed, logged, or exposed to users.

## What RecipeBot Does Not Collect

RecipeBot does not collect:

- Reddit passwords
- OAuth client secrets
- private messages
- payment information
- advertising identifiers
- unrelated profile data

RecipeBot does not independently scrape Reddit. The backend only receives the parent post/comment data that the Devvit app sends after a user intentionally invokes `!recipecard`.

## Data Practices

RecipeBot does not sell user data.

RecipeBot does not use Reddit content for advertising.

RecipeBot does not use Reddit content for model training.

Generated card artifacts and job metadata are retained only so the requester can retrieve the generated card URL and so users or moderators can request removal.

## Terms and Privacy

Terms:

`https://recipebot.devgw.com/terms`

Privacy Policy:

`https://recipebot.devgw.com/privacy`

Public Devvit API documentation:

`https://recipebot.devgw.com/devvit-api`

## Summary

External domain requested:

`recipebot.devgw.com`

This domain is used only for signed RecipeBot job creation, recipe card generation, card hosting, user delivery, and removal support.
