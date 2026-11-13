// Sign in. On success the user goes to the page that matches their roles.

"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import ApiOffline from "@/components/ApiOffline";
import { ApiError } from "@/lib/api";
import { homeForUser, useAuth } from "@/lib/auth";

export default function LoginPage() {
  return (
    <AppShell>
      <LoginForm />
    </AppShell>
  );
}

function LoginForm() {
  const { login, busy, user } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setOffline(false);
    try {
      await login(email.trim(), password);
      // homeForUser needs the fresh user; login() already stored it, so
      // read the stored copy rather than the (stale) render state.
      const stored = (() => {
        try {
          const raw = window.localStorage.getItem("commontable.user");
          return raw ? JSON.parse(raw) : null;
        } catch {
          return null;
        }
      })();
      router.push(homeForUser(stored ?? user));
    } catch (err) {
      if (err instanceof ApiError && err.unreachable) {
        setOffline(true);
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Sign in failed. Please try again.");
      }
    }
  }

  if (offline) {
    return <ApiOffline onRetry={() => setOffline(false)} />;
  }

  return (
    <div className="app-narrow">
      <h1>Sign in</h1>
      <p className="app-lede">
        Sign in to order, track deliveries, or open your restaurant, driver,
        or dispatch workspace.
      </p>
      <form className="app-form" onSubmit={handleSubmit}>
        <label className="app-field">
          <span>Email</span>
          <input
            className="app-input"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />
        </label>
        <label className="app-field">
          <span>Password</span>
          <input
            className="app-input"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && (
          <p className="app-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="app-btn app-btn-wide" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p className="app-form-foot">
        New to CommonTable?{" "}
        <Link href="/register">Create a customer account</Link>
      </p>
    </div>
  );
}
