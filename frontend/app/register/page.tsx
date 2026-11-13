// Customer registration. The API creates customer accounts only;
// restaurant, driver, dispatcher, and admin accounts are created by an
// admin.

"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import ApiOffline from "@/components/ApiOffline";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  return (
    <AppShell>
      <RegisterForm />
    </AppShell>
  );
}

function RegisterForm() {
  const { register, busy } = useAuth();
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setOffline(false);
    try {
      await register(email.trim(), password, fullName.trim());
      router.push("/order");
    } catch (err) {
      if (err instanceof ApiError && err.unreachable) {
        setOffline(true);
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Could not create the account. Please try again.");
      }
    }
  }

  if (offline) {
    return <ApiOffline onRetry={() => setOffline(false)} />;
  }

  return (
    <div className="app-narrow">
      <h1>Create a customer account</h1>
      <p className="app-lede">
        Order from local restaurants at their own menu prices, with clear
        delivery fees and no hidden markups.
      </p>
      <form className="app-form" onSubmit={handleSubmit}>
        <label className="app-field">
          <span>Full name</span>
          <input
            className="app-input"
            type="text"
            autoComplete="name"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Your name"
          />
        </label>
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
            autoComplete="new-password"
            required
            minLength={8}
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
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p className="app-form-foot">
        Already have an account? <Link href="/login">Sign in</Link>
      </p>
    </div>
  );
}
