/** Resolve Reddit parent content into RecipeBot's normalized webhook payload. */

export type CommentId = `t1_${string}`;
export type PostId = `t3_${string}`;

export interface RedditCommentSource {
  authorName: string;
  body: string;
  createdAt: Date;
  id: CommentId;
  parentId: CommentId | PostId;
  permalink: string;
  postId: PostId;
  removed?: boolean | undefined;
  spam?: boolean | undefined;
  subredditName: string;
}

export interface RedditPostSource {
  body?: string | undefined;
  createdAt: Date;
  id: PostId;
  permalink: string;
  removed?: boolean | undefined;
  spam?: boolean | undefined;
  subredditName: string;
  title: string;
  url: string;
}

export interface RedditSourceReader {
  getCommentById(id: CommentId): Promise<RedditCommentSource>;
  getPostById(id: PostId): Promise<RedditPostSource>;
}

export interface RecipeBotPayload {
  command_comment_id: CommentId;
  requester_username: string;
  subreddit: string;
  source_type: "comment" | "submission";
  source_fullname: CommentId | PostId;
  source_title: string;
  source_body: string;
  source_permalink: string;
  source_url: string;
  created_utc: number;
}

/** Return true when a value is a Reddit comment fullname. */
export function isCommentId(value: string): value is CommentId {
  return value.startsWith("t1_");
}

/** Return true when a value is a Reddit post fullname. */
export function isPostId(value: string): value is PostId {
  return value.startsWith("t3_");
}

/** Convert a Reddit permalink into an absolute HTTPS URL. */
export function absoluteRedditUrl(permalink: string): string {
  if (permalink.startsWith("https://") || permalink.startsWith("http://")) return permalink;
  return `https://www.reddit.com${permalink.startsWith("/") ? "" : "/"}${permalink}`;
}

/** Resolve the command's parent comment or post into a RecipeBot payload. */
export async function buildRecipeBotPayload(
  command: RedditCommentSource,
  reddit: RedditSourceReader,
): Promise<RecipeBotPayload | null> {
  const requester = command.authorName.trim();
  if (!requester || requester === "[deleted]") return null;

  if (isCommentId(command.parentId)) {
    const parent = await reddit.getCommentById(command.parentId);
    if (!usableSource(parent.body, parent.removed, parent.spam)) return null;
    const post = await reddit.getPostById(parent.postId);
    return {
      command_comment_id: command.id,
      requester_username: requester,
      subreddit: parent.subredditName,
      source_type: "comment",
      source_fullname: parent.id,
      source_title: post.title,
      source_body: parent.body.trim(),
      source_permalink: absoluteRedditUrl(parent.permalink),
      source_url: absoluteRedditUrl(parent.permalink),
      created_utc: toUnixSeconds(parent.createdAt),
    };
  }

  if (!isPostId(command.parentId)) return null;
  const post = await reddit.getPostById(command.parentId);
  const body = post.body ?? "";
  if (!usableSource(body, post.removed, post.spam)) return null;
  return {
    command_comment_id: command.id,
    requester_username: requester,
    subreddit: post.subredditName,
    source_type: "submission",
    source_fullname: post.id,
    source_title: post.title,
    source_body: body.trim(),
    source_permalink: absoluteRedditUrl(post.permalink),
    source_url: post.url || absoluteRedditUrl(post.permalink),
    created_utc: toUnixSeconds(post.createdAt),
  };
}

function usableSource(body: string, removed?: boolean, spam?: boolean): boolean {
  const normalized = body.trim().toLowerCase();
  return Boolean(normalized && normalized !== "[deleted]" && normalized !== "[removed]") &&
    !removed && !spam;
}

function toUnixSeconds(value: Date): number {
  return Math.floor(value.getTime() / 1000);
}
