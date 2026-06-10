import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ApiError,
  getGithubAppInstallUrl,
  getGithubLinkUrl,
  syncGithubInstallations,
} from "@/lib/api";
import { listTenants } from "@/lib/tenants";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";

const COMING_SOON_TOOLS = [
  { name: "Linear", description: "Issues, cycles and project velocity." },
  { name: "Jira", description: "Sprint and ticket activity." },
  { name: "Slack", description: "Team communication signals." },
  { name: "Cursor", description: "AI-assisted development metrics." },
];

type CheckState =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "not-found" }
  | { status: "error"; message: string };

/**
 * Onboarding empty state: shown when the signed-in user has no workspace yet.
 * Installing the GitHub App is the only step — the backend discovers the
 * installation, provisions the workspace, imports the org roster and assigns
 * roles from the GitHub org structure.
 */
export function ConnectTools({ onConnected }: { onConnected: () => void }) {
  const { token, user } = useAuth();
  const { tenant, permissions } = useTenant();
  const [check, setCheck] = useState<CheckState>({ status: "idle" });
  const githubLinked = user?.github?.connected ?? false;
  // Pre-tenant onboarding is open to anyone (installing the app provisions
  // the workspace); inside an existing workspace, installs are admin-only.
  const canInstall = !tenant || permissions.includes("connections:manage");

  async function openInstallPage() {
    if (!token) return;
    try {
      const url = await getGithubAppInstallUrl(token);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "Could not load the GitHub install page.";
      setCheck({ status: "error", message });
    }
  }

  async function connectGithubAccount() {
    if (!token) return;
    try {
      const url = await getGithubLinkUrl(token);
      window.location.href = url;
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "Could not start the GitHub connection.";
      setCheck({ status: "error", message });
    }
  }

  async function checkConnection() {
    if (!token) return;
    setCheck({ status: "checking" });
    try {
      await syncGithubInstallations(token);
      // The roster import may have just linked this user to a workspace —
      // re-check membership before deciding what to show.
      const tenants = await listTenants(token);
      if (tenants.length > 0) {
        onConnected();
        setCheck({ status: "idle" });
      } else {
        setCheck({ status: "not-found" });
      }
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Could not check the connection.";
      setCheck({ status: "error", message });
    }
  }

  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-lg font-medium">Connect your tools</h2>
        <p className="text-muted-foreground mt-1 max-w-2xl text-sm">
          You&apos;re not part of a workspace yet. Connect a tool your team uses and
          Propel will set up your workspace, import your teammates and assign roles from
          your org automatically.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card className="border-primary/40">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>GitHub</CardTitle>
              <Badge variant="secondary">Available</Badge>
            </div>
            <CardDescription>
              Commits, pull requests, reviews and Copilot usage. Roles are assigned from
              your GitHub org (owners become admins).
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {canInstall && (
                <Button onClick={openInstallPage}>Install GitHub App</Button>
              )}
              <Button
                variant="outline"
                onClick={checkConnection}
                disabled={check.status === "checking"}
              >
                {check.status === "checking" ? "Checking…" : "I've installed it"}
              </Button>
            </div>
            {check.status === "not-found" && (
              <div className="space-y-2">
                {githubLinked ? (
                  <p className="text-muted-foreground text-xs">
                    Your GitHub account is connected, but it isn&apos;t a member of an
                    org with the app installed. Make sure the app is installed on your
                    organization (not your personal account), then check again.
                  </p>
                ) : (
                  <>
                    <p className="text-muted-foreground text-xs">
                      We couldn&apos;t match you to an org member by email — your GitHub
                      email may be private or different from the one you signed up with.
                      Connect your GitHub account and we&apos;ll link you to your
                      workspace with the right role.
                    </p>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={connectGithubAccount}
                    >
                      Connect GitHub account
                    </Button>
                  </>
                )}
              </div>
            )}
            {check.status === "error" && (
              <p className="text-destructive text-xs">{check.message}</p>
            )}
          </CardContent>
        </Card>

        {COMING_SOON_TOOLS.map((tool) => (
          <Card key={tool.name} className="opacity-60">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{tool.name}</CardTitle>
                <Badge variant="outline">Coming soon</Badge>
              </div>
              <CardDescription>{tool.description}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
    </section>
  );
}
