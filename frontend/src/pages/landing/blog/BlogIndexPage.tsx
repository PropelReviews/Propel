import { Link } from "react-router-dom";

import { MarketingLayout } from "@/components/landing/marketing-layout";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";
import { getAllPosts } from "@/lib/blog";

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

export function BlogIndexPage() {
  const posts = getAllPosts();

  return (
    <MarketingLayout>
      <Section bordered={false} containerClassName="py-16 sm:py-24">
        <SectionHeading
          align="left"
          title="Blog"
          description="Notes on engineering metrics, shipping, and building Propel in the open."
          className="mb-12"
        />

        {posts.length === 0 ? (
          <p className="text-muted-foreground">No posts yet. Check back soon.</p>
        ) : (
          <ul className="divide-border/60 divide-y">
            {posts.map((post) => (
              <li key={post.slug} className="py-8 first:pt-0">
                <article>
                  <time dateTime={post.date} className="text-muted-foreground text-sm">
                    {formatDate(post.date)}
                  </time>
                  <h3 className="mt-2 text-xl font-semibold tracking-tight">
                    <Link
                      to={`/blog/${post.slug}`}
                      className="hover:text-primary transition-colors"
                    >
                      {post.title}
                    </Link>
                  </h3>
                  {post.description && (
                    <p className="text-muted-foreground mt-2 max-w-2xl text-base">
                      {post.description}
                    </p>
                  )}
                  <Link
                    to={`/blog/${post.slug}`}
                    className="text-primary mt-3 inline-block text-sm font-medium underline-offset-4 hover:underline"
                  >
                    Read more
                  </Link>
                </article>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </MarketingLayout>
  );
}
