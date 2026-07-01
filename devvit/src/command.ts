/** Exact RecipeBot command recognition. */

export const RECIPE_CARD_COMMAND = "!recipecard";

export interface CommandComment {
  authorName?: string | null | undefined;
  body?: string | null | undefined;
  removed?: boolean | undefined;
  spam?: boolean | undefined;
}

/** Return true only for a standalone RecipeBot command. */
export function isExactRecipeCardCommand(body: string | null | undefined): boolean {
  if (body === null || body === undefined) return false;
  const normalized = body.trim();
  return normalized === RECIPE_CARD_COMMAND;
}

/** Determine whether a comment is an actionable command from a non-app user. */
export function shouldHandleCommand(
  comment: CommandComment,
  appAccountName?: string | null,
): boolean {
  const authorName = comment.authorName?.trim();
  if (!authorName || authorName === "[deleted]") return false;
  if (comment.removed || comment.spam) return false;
  if (appAccountName && authorName.toLowerCase() === appAccountName.toLowerCase()) return false;
  return isExactRecipeCardCommand(comment.body);
}
