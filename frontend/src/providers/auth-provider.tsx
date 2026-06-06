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
  login as apiLogin,
  register as apiRegister,
  type AuthUser,
} from "@/lib/api";
import { posthog } from "@/providers/posthog-provider";

const TOKEN_STORAGE_KEY = "propel_token";

type AuthStatus = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  user: AuthUser | null;
  token: string | null;
  status: AuthStatus;
  signIn: (input: { email: string; password: string }) => Promise<void>;
  signUp: (input: {
    email: string;
    password: string;
    name?: string;
  }) => Promise<void>;
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token);
    else localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // Ignore storage failures (private mode, disabled storage).
  }
}

function identify(user: AuthUser) {
  posthog?.identify(user.id, { email: user.email, name: user.name });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(() => readToken());
  const [status, setStatus] = useState<AuthStatus>(() =>
    readToken() ? "loading" : "anonymous",
  );

  // Bootstrap the session from a persisted token on mount.
  useEffect(() => {
    const existing = readToken();
    if (!existing) {
      setStatus("anonymous");
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const me = await getMe(existing);
        if (cancelled) return;
        setUser(me);
        setToken(existing);
        setStatus("authenticated");
        identify(me);
      } catch (error) {
        if (cancelled) return;
        // Invalid/expired token: clear it and fall back to anonymous.
        if (error instanceof ApiError && error.status === 401) {
          writeToken(null);
        }
        setUser(null);
        setToken(null);
        setStatus("anonymous");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const establishSession = useCallback(async (accessToken: string) => {
    writeToken(accessToken);
    const me = await getMe(accessToken);
    setUser(me);
    setToken(accessToken);
    setStatus("authenticated");
    identify(me);
  }, []);

  const signIn = useCallback(
    async (input: { email: string; password: string }) => {
      posthog?.capture("sign_in_submitted");
      try {
        const { access_token } = await apiLogin(input);
        await establishSession(access_token);
        posthog?.capture("sign_in_succeeded");
      } catch (error) {
        posthog?.capture("sign_in_failed", {
          reason: error instanceof ApiError ? error.code : "unknown",
        });
        throw error;
      }
    },
    [establishSession],
  );

  const signUp = useCallback(
    async (input: { email: string; password: string; name?: string }) => {
      posthog?.capture("sign_up_submitted");
      try {
        await apiRegister(input);
        const { access_token } = await apiLogin({
          email: input.email,
          password: input.password,
        });
        await establishSession(access_token);
        posthog?.capture("sign_up_succeeded");
      } catch (error) {
        posthog?.capture("sign_up_failed", {
          reason: error instanceof ApiError ? error.code : "unknown",
        });
        throw error;
      }
    },
    [establishSession],
  );

  const signOut = useCallback(() => {
    writeToken(null);
    setUser(null);
    setToken(null);
    setStatus("anonymous");
    posthog?.reset();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, token, status, signIn, signUp, signOut }),
    [user, token, status, signIn, signUp, signOut],
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
