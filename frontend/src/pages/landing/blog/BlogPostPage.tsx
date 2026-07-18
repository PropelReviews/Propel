import { Link, Navigate, useParams } from "react-router-dom";

import { MarketingLayout } from "@/components/landing/marketing-layout";
import { MarkdownContent } from "@/components/landing/markdown-content";
import { Section } from "@/components/ui/section";
import { getPostBySlug } from "@/lib/blog";

function formatDate(isoDate: string): string {
  const parsed = new Date(`${isoDate}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return isoDate;
  return parsed.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function BlogPostPage() {
  const { slug } = useParams<{ slug: string }>();
  const post = slug ? getPostBySlug(slug) : undefined;

  if (!post) {
    return <Navigate to="/blog" replace />;
  }

  return (
    <MarketingLayout>
      <Section bordered={false} containerClassName="py-16 sm:py-24">
        <div className="mx-auto max-w-2xl">
          <Link
            to="/blog"
            className="text-muted-foreground hover:text-foreground text-sm transition-colors"
          >
            ← Back to blog
          </Link>
          <header className="mt-6 mb-10">
            <time dateTime={post.date} className="text-muted-foreground text-sm">
              {formatDate(post.date)}
            </time>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              {post.title}
            </h1>
            {post.description && (
              <p className="text-muted-foreground mt-4 text-lg">{post.description}</p>
            )}
          </header>
          <MarkdownContent content={post.content} />
        </div>
      </Section>
    </MarketingLayout>
  );
}
