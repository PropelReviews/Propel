// External destinations for the landing CTAs. Baked at build time by
// vite.landing.config.ts (per environment); the fallbacks cover local dev.
export const appUrl = import.meta.env.VITE_APP_URL ?? "https://app.propel.ninja";
export const githubUrl =
  import.meta.env.VITE_GITHUB_URL ?? "https://github.com/PropelReviews/Propel";
export const docsUrl = `${githubUrl}/tree/main/docs`;
export const contributingUrl = `${githubUrl}/blob/main/CONTRIBUTING.md`;
export const licenseUrl = `${githubUrl}/blob/main/LICENSE`;
