RecipeBot Devvit Adapter

RecipeBot responds only to the exact standalone comment command:

!recipecard

When triggered, the app reads the parent post or comment and sends a minimal signed request to:

https://recipebot.devgw.com/internal/devvit/recipecard

The external domain is required because the Devvit app does not render cards itself. The backend generates PNG, SVG, and PDF recipe cards and returns a hosted card URL.

Data sent:
- command comment id
- requester username
- subreddit
- parent post/comment fullname
- parent title/body
- parent permalink
- parent URL
- created timestamp

RecipeBot does not collect Reddit passwords, OAuth client secrets, private messages, advertising identifiers, or payment information.

RecipeBot does not sell user data and does not use Reddit content for model training.

The backend stores job metadata and generated card artifacts only so the requester can retrieve the result. Users or moderators can request removal through the Privacy Policy page.

External domain requested:
recipebot.devgw.com

This domain is used only for signed RecipeBot job creation and card hosting.