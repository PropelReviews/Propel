import { describe, expect, it } from "vitest";

import { getAllPosts, getPostBySlug, parsePost } from "./blog";

const SAMPLE = `---
title: Sample Post
date: 2026-06-01
description: A short description.
slug: sample-post
---

Hello **world**.
`;

describe("parsePost", () => {
  it("parses frontmatter and body", () => {
    const post = parsePost(SAMPLE, "fallback-slug");
    expect(post).toEqual({
      title: "Sample Post",
      date: "2026-06-01",
      description: "A short description.",
      slug: "sample-post",
      content: "Hello **world**.",
    });
  });

  it("falls back to the filename slug when frontmatter omits slug", () => {
    const raw = `---
title: No Slug
date: 2026-01-01
description: Desc
---

Body
`;
    expect(parsePost(raw, "from-filename").slug).toBe("from-filename");
  });

  it("throws when required frontmatter is missing", () => {
    expect(() => parsePost("---\ndescription: only\n---\n\nHi", "x")).toThrow(
      /missing required frontmatter/,
    );
  });
});

describe("blog content modules", () => {
  it("loads seeded posts newest-first", () => {
    const posts = getAllPosts();
    expect(posts.length).toBeGreaterThanOrEqual(2);
    expect(posts.map((p) => p.slug)).toContain("hello-propel");
    expect(posts.map((p) => p.slug)).toContain("measuring-what-matters");

    for (let i = 0; i < posts.length - 1; i++) {
      expect(posts[i]!.date >= posts[i + 1]!.date).toBe(true);
    }
  });

  it("resolves a post by slug", () => {
    const post = getPostBySlug("hello-propel");
    expect(post?.title).toBe("Hello from Propel");
    expect(post?.content.length).toBeGreaterThan(0);
  });

  it("returns undefined for unknown slugs", () => {
    expect(getPostBySlug("does-not-exist")).toBeUndefined();
  });
});
