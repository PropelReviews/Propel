import { buttonVariants } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { GithubIcon } from "./github-icon";
import { contributingUrl, docsUrl, githubUrl, licenseUrl } from "./links";

const footerLinkClass = cn(
  buttonVariants({ variant: "link", size: "sm" }),
  "text-muted-foreground hover:text-foreground h-auto p-0",
);

const footerLinks = [
  { href: docsUrl, label: "Docs", external: false },
  { href: contributingUrl, label: "Contributing", external: false },
  { href: licenseUrl, label: "License", external: false },
];

export function Footer() {
  return (
    <footer>
      <Separator />
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-6 py-12 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-2">
          <div className="text-lg font-semibold tracking-tight">Propel</div>
          <p className="text-muted-foreground max-w-xs text-sm">
            Open source developer analytics for teams that want to trust their
            metrics.
          </p>
        </div>

        <nav className="flex flex-wrap items-center gap-x-6 gap-y-3">
          {footerLinks.map((link) => (
            <a key={link.label} href={link.href} className={footerLinkClass}>
              {link.label}
            </a>
          ))}
          <a
            href={githubUrl}
            target="_blank"
            rel="noreferrer"
            className={cn(footerLinkClass, "gap-1.5")}
          >
            <GithubIcon className="size-4" />
            GitHub
          </a>
        </nav>
      </div>

      <Separator />
      <div className="text-muted-foreground px-6 py-6 text-center text-xs">
        MIT licensed. Built in the open.
      </div>
    </footer>
  );
}
