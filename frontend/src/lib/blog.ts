import matter from "gray-matter";

export type BlogPostMeta = {
  title: string;
  date: string;
  description: string;
  slug: string;
};

export type BlogPost = BlogPostMeta & {
  content: string;
};

const postModules = import.meta.glob("../../content/blog/*.md", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

function slugFromPath(path: string): string {
  const file = path.split("/").pop() ?? path;
  return file.replace(/\.md$/, "");
}

/**
 * Parse a raw Markdown file (with optional YAML frontmatter) into a blog post.
 * Exported for unit tests; production code uses {@link getAllPosts} /
 * {@link getPostBySlug}.
 */
export function parsePost(raw: string, fallbackSlug: string): BlogPost {
  const { data, content } = matter(raw);
  const title = typeof data.title === "string" ? data.title.trim() : "";
  const date = typeof data.date === "string" ? data.date.trim() : "";
  const description =
    typeof data.description === "string" ? data.description.trim() : "";
  const slug =
    typeof data.slug === "string" && data.slug.trim() ? data.slug.trim() : fallbackSlug;

  if (!title || !date || !slug) {
    throw new Error(
      `Blog post "${fallbackSlug}" is missing required frontmatter (title, date, slug)`,
    );
  }

  return {
    title,
    date,
    description,
    slug,
    content: content.trim(),
  };
}

function loadPosts(): BlogPost[] {
  return Object.entries(postModules).map(([path, raw]) =>
    parsePost(raw, slugFromPath(path)),
  );
}

/** All posts newest-first (by `date` frontmatter, ISO YYYY-MM-DD). */
export function getAllPosts(): BlogPostMeta[] {
  return loadPosts()
    .map(({ content: _content, ...meta }) => meta)
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
}

export function getPostBySlug(slug: string): BlogPost | undefined {
  return loadPosts().find((post) => post.slug === slug);
}
