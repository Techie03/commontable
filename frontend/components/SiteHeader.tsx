// Role aware header for the MVP slice pages. Links shown depend on the
// signed in user's roles. This is navigation only, never a security check:
// the API enforces roles on every endpoint.

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function SiteHeader() {
  const { user, ready, logout, hasRole } = useAuth();
  const router = useRouter();

  const isCustomer = hasRole("customer");
  const isRestaurant = hasRole(
    "restaurant_owner",
    "restaurant_manager",
    "restaurant_staff"
  );
  const isDriver = hasRole("driver");
  const isDispatcher = hasRole("dispatcher");
  const isAdmin = hasRole("admin");

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <header className="app-header">
      <div className="container app-header-inner">
        <Link href="/" className="wordmark">
          CommonTable
        </Link>
        <nav className="app-nav" aria-label="Main">
          <Link href="/order">Order</Link>
          {isCustomer && <Link href="/orders">My orders</Link>}
          {isRestaurant && (
            <>
              <Link href="/restaurant">Restaurant</Link>
              <Link href="/restaurant/menu">Menu</Link>
              <Link href="/restaurant/direct2door">Direct2Door</Link>
            </>
          )}
          {isDriver && <Link href="/driver">Driver</Link>}
          {isDispatcher && <Link href="/dispatch">Dispatch</Link>}
          {isAdmin && <Link href="/admin">Admin</Link>}
        </nav>
        <div className="app-header-user">
          {ready && user ? (
            <>
              <span className="app-header-email" title={user.email}>
                {user.full_name || user.email}
              </span>
              <button type="button" className="app-btn app-btn-small" onClick={handleLogout}>
                Sign out
              </button>
            </>
          ) : ready ? (
            <>
              <Link href="/login" className="app-btn app-btn-small app-btn-ghost">
                Sign in
              </Link>
              <Link href="/register" className="app-btn app-btn-small">
                Create account
              </Link>
            </>
          ) : null}
        </div>
      </div>
    </header>
  );
}
