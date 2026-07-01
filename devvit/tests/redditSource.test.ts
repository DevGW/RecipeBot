import { describe, expect, it } from "vitest";

import {
  buildRecipeBotPayload,
  type RedditCommentSource,
  type RedditPostSource,
  type RedditSourceReader,
} from "../src/redditSource.js";

const command: RedditCommentSource = {
  id: "t1_command",
  parentId: "t1_parent",
  postId: "t3_post",
  authorName: "example_user",
  body: "!recipecard",
  subredditName: "recipes",
  permalink: "/r/recipes/comments/post/title/command/",
  createdAt: new Date("2026-05-29T00:00:00Z"),
};

const parent: RedditCommentSource = {
  id: "t1_parent",
  parentId: "t3_post",
  postId: "t3_post",
  authorName: "cook",
  body: "Ingredients:\n- bread\nDirections:\n1. Toast.",
  subredditName: "recipes",
  permalink: "/r/recipes/comments/post/title/parent/",
  createdAt: new Date("2026-05-28T12:00:00Z"),
};

const post: RedditPostSource = {
  id: "t3_post",
  title: "Tomato Toast",
  body: "Post body",
  subredditName: "recipes",
  permalink: "/r/recipes/comments/post/title/",
  url: "https://www.reddit.com/r/recipes/comments/post/title/",
  createdAt: new Date("2026-05-28T10:00:00Z"),
};

function reader(): RedditSourceReader {
  return {
    async getCommentById() { return parent; },
    async getPostById() { return post; },
  };
}

describe("Reddit source payload", () => {
  it("builds a parent-comment payload", async () => {
    const payload = await buildRecipeBotPayload(command, reader());

    expect(payload).toEqual({
      command_comment_id: "t1_command",
      requester_username: "example_user",
      subreddit: "recipes",
      source_type: "comment",
      source_fullname: "t1_parent",
      source_title: "Tomato Toast",
      source_body: "Ingredients:\n- bread\nDirections:\n1. Toast.",
      source_permalink: "https://www.reddit.com/r/recipes/comments/post/title/parent/",
      source_url: "https://www.reddit.com/r/recipes/comments/post/title/parent/",
      created_utc: 1779969600,
    });
  });

  it("builds a parent-post payload", async () => {
    const postCommand = { ...command, parentId: "t3_post" as const };
    const payload = await buildRecipeBotPayload(postCommand, reader());

    expect(payload?.source_type).toBe("submission");
    expect(payload?.source_fullname).toBe("t3_post");
    expect(payload?.source_body).toBe("Post body");
    expect(payload?.source_url).toBe(post.url);
  });
});
