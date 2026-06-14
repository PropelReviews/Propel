import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  ApiError,
  getMe,
  redirectToLogin,
  redirectToLogout,
  type AuthUser,
} from "@/lib/api";
import {
  clearCachedDistinctId,
  writeCachedDistinctId,
} from "@/lib/posthog-persistence";
import { posthog } from "@/providers/posthog-provider";

const USER_STORAGE_KEY = "propel_user";

type AuthStatus = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  user: AuthUser | null;
  /** @deprecated Session is cookie-based; kept for call-site compatibility. */
  token: string | null;
  status: AuthStatus;
  signIn: () => void;
  signUp: () => void;
  signOut: () => void;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function readCachedUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed === "object" &&
      "id" in parsed &&
      "email" in parsed &&
      typeof (parsed as AuthUser).id === "string" &&
      typeof (parsed as AuthUser).email === "string"
    ) {
      return parsed as AuthUser;
    }
  } catch {
    // Ignore corrupt cache.
  }
  return null;
}

function writeCachedUser(user: AuthUser | null) {
  try {
    if (user) localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
    else localStorage.removeItem(USER_STORAGE_KEY);
  } catch {
    // Ignore storage failures.
  }
}

function identify(user: AuthUser) {
  posthog?.identify(user.id, { email: user.email, name: user.name });
  writeCachedDistinctId(user.id);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    const cachedUser = readCachedUser();
    if (cachedUser) {
      posthog?.identify(cachedUser.id, {
        email: cachedUser.email,
        name: cachedUser.name,
      });
    }

    let cancelled = false;
    (async () => {
      try {
        const me = await getMe();
        if (cancelled) return;
        setUser(me);
        setStatus("authenticated");
        writeCachedUser(me);
        identify(me);
      } catch (error) {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401) {
          writeCachedUser(null);
          clearCachedDistinctId();
        } else {
          posthog?.captureException(error, { context: "auth_bootstrap" });
        }
        setUser(null);
        setStatus("anonymous");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(() => {
    posthog?.capture("sign_in_submitted");
    redirectToLogin();
  }, []);

  const signUp = useCallback(() => {
    posthog?.capture("sign_up_submitted");
    redirectToLogin();
  }, []);

  const refreshUser = useCallback(async () => {
    const me = await getMe();
    setUser(me);
    writeCachedUser(me);
  }, []);

  const signOut = useCallback(() => {
    writeCachedUser(null);
    clearCachedDistinctId();
    setUser(null);
    setStatus("anonymous");
    posthog?.reset();
    redirectToLogout();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token: user ? "session" : null,
      status,
      signIn,
      signUp,
      signOut,
      refreshUser,
    }),
    [user, status, signIn, signUp, signOut, refreshUser],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
