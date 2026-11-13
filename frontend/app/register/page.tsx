// Registration with role selection. The visitor picks a role and the
// account is created with it: customer, restaurant owner, or driver.
// Dispatcher and admin accounts are created by the CommonTable team, never
// self-assigned. A ?role= query param preselects the role (used by the
// Create account menu in the header).

"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import ApiOffline from "@/components/ApiOffline";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const ROLES = [
  {
    value: "customer",
    title: "Customer",
    desc: "Order from local restaurants and track delivery live.",
    landing: "/order",
  },
  {
    value: "restaurant_owner",
    title: "Restaurant",
    desc: "Manage your menu, receive orders, and run Direct2Door delivery.",
    landing: "/restaurant",
  },
  {
    value: "driver",
    title: "Driver",
    desc: "Deliver orders and earn per trip. Our team approves your account before you can go online.",
    landing: "/driver",
  },
] as const;

type RoleValue = (typeof ROLES)[number]["value"];

function isRoleValue(value: string | null): value is RoleValue {
  return ROLES.some((r) => r.value === value);
}

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
  const [role, setRole] = useState<RoleValue>("customer");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);

  // Preselect the role from ?role= when the header menu deep-links here.
  useEffect(() => {
    const param = new URLSearchParams(window.location.search).get("role");
    if (isRoleValue(param)) setRole(param);
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setOffline(false);
    try {
      await register(email.trim(), password, fullName.trim(), role);
      const landing = ROLES.find((r) => r.value === role)?.landing ?? "/order";
      router.push(landing);
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
      <h1>Create your account</h1>
      <p className="app-lede">
        Choose your role first. Your account is created for that role, and
        you land in its portal right after signing up.
      </p>
      <form className="app-form" onSubmit={handleSubmit}>
        <fieldset className="role-picker">
          <legend>I am joining as</legend>
          {ROLES.map((r) => (
            <label key={r.value} className="role-option">
              <input
                type="radio"
                name="role"
                value={r.value}
                checked={role === r.value}
                onChange={() => setRole(r.value)}
              />
              <span>
                <span className="role-option-title">{r.title}</span>
                <span className="role-option-desc">{r.desc}</span>
              </span>
            </label>
          ))}
        </fieldset>
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
        Dispatcher and admin accounts are created by the CommonTable team.
      </p>
      <p className="app-form-foot">
        Already have an account? <Link href="/login">Sign in</Link>
      </p>
    </div>
  );
}
