# Landing blog content

Markdown posts for the marketing site (`/blog`). Each file needs YAML
frontmatter:

```yaml
---
title: Post title
date: YYYY-MM-DD
description: One-line summary for the index.
slug: url-slug
---
```

Add a new `.md` file here, then rebuild the landing site
(`npm run build:landing` / `npm run dev:landing`). The blog is gated by the
PostHog flag `landing-blog` (env fallback `VITE_LANDING_BLOG_ENABLED`).
