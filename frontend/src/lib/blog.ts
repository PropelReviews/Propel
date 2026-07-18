import { parse as parseYaml } from "yaml";

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

const FRONTMATTER_RE = /^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/;

function slugFromPath(path: string): string {
  const file = path.split("/").pop() ?? path;
  return file.replace(/\.md$/, "");
}

function asTrimmedString(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return "";
}

/**
 * Parse a raw Markdown file (with optional YAML frontmatter) into a blog post.
 * Exported for unit tests; production code uses {@link getAllPosts} /
 * {@link getPostBySlug}.
 */
export function parsePost(raw: string, fallbackSlug: string): BlogPost {
  const match = FRONTMATTER_RE.exec(raw);
  const data = match ? (parseYaml(match[1] ?? "") as Record<string, unknown>) : {};
  const body = match ? (match[2] ?? "") : raw;

  const title = asTrimmedString(data.title);
  const date = asTrimmedString(data.date);
  const description = asTrimmedString(data.description);
  const slug = asTrimmedString(data.slug) || fallbackSlug;

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
    content: body.trim(),
  };
}

function loadPosts(): BlogPost[] {
  return Object.entries(postModules)
    .filter(([path]) => !slugFromPath(path).toLowerCase().startsWith("readme"))
    .map(([path, raw]) => parsePost(raw, slugFromPath(path)));
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
