import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { acceptInvite } from "@/lib/invites";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";

type AcceptState =
  | { status: "accepting" }
  | { status: "accepted" }
  | { status: "error"; message: string };

/**
 * Landing page for invite links (`/invites/:token/accept`). The route is
 * wrapped in `RequireAuth`, so anonymous visitors sign in first and return
 * here to join the workspace.
 */
export function InviteAcceptPage() {
  const { token: inviteToken } = useParams<{ token: string }>();
  const { token } = useAuth();
  const { setTenant, refresh } = useTenant();
  const [state, setState] = useState<AcceptState>({ status: "accepting" });
  const attempted = useRef(false);

  useEffect(() => {
    if (!token || !inviteToken || attempted.current) return;
    attempted.current = true;
    (async () => {
      try {
        const accepted = await acceptInvite(token, inviteToken);
        await refresh();
        setTenant(accepted.tenant_id);
        setState({ status: "accepted" });
      } catch (error) {
        setState({
          status: "error",
          message:
            error instanceof ApiError
              ? error.message
              : "This invite link is invalid or has expired.",
        });
      }
    })();
  }, [token, inviteToken, refresh, setTenant]);

  return (
    <main className="flex min-h-svh items-center justify-center p-8">
      <Card className="w-full max-w-md">
        {state.status === "accepting" ? (
          <CardHeader>
            <CardTitle>Joining workspace…</CardTitle>
            <CardDescription>Accepting your invitation.</CardDescription>
          </CardHeader>
        ) : state.status === "accepted" ? (
          <>
            <CardHeader>
              <CardTitle>You&apos;re in</CardTitle>
              <CardDescription>
                Your invitation was accepted and you now have access to the workspace.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild analyticsName="invite_accepted_view_dashboard">
                <Link to="/home">Go to your dashboard</Link>
              </Button>
            </CardContent>
          </>
        ) : (
          <>
            <CardHeader>
              <CardTitle>Couldn&apos;t accept invite</CardTitle>
              <CardDescription>{state.message}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild variant="outline" analyticsName="invite_error_home">
                <Link to="/">Back home</Link>
              </Button>
            </CardContent>
          </>
        )}
      </Card>
    </main>
  );
}
