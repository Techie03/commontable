// Notifications bell for signed-in users: an icon button with an unread
// badge that opens a panel of the user's notifications (newest first).
// The bell rings when the unread count grows. Refreshes on mount, when
// opened, every 60 seconds, and when the window regains focus. Clicking
// a notification marks it read and opens its order when it has one.

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  listNotificationsPage,
  markAllNotificationsRead,
  markNotificationRead,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { NotificationItem } from "@/lib/types";

function timeAgo(iso?: string): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function NotificationBell() {
  const { user, ready } = useAuth();
  const router = useRouter();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [ringing, setRinging] = useState(false);
  const prevUnread = useRef(0);
  const ringTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const page = await listNotificationsPage();
      setItems(page.items ?? []);
      const count = page.unread_count ?? 0;
      if (count > prevUnread.current) {
        setRinging(true);
        if (ringTimer.current) clearTimeout(ringTimer.current);
        ringTimer.current = setTimeout(() => setRinging(false), 1200);
      }
      prevUnread.current = count;
      setUnread(count);
    } catch {
      // Notifications are a nicety, not the page: a failed fetch leaves
      // the bell showing what it already has instead of breaking the page.
    }
  }, []);

  useEffect(() => {
    if (!ready || !user) return;
    setLoading(true);
    load().finally(() => setLoading(false));
    const timer = setInterval(load, 60_000);
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", onFocus);
      if (ringTimer.current) clearTimeout(ringTimer.current);
    };
  }, [ready, user, load]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open ]);

  if (!ready || !user) return null;

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) load();
  };

  const openItem = async (item: NotificationItem) => {
    if (!item.read) {
      setItems((prev) =>
        prev.map((n) => (n.id === item.id ? { ...n, read: true } : n))
      );
      setUnread((c) => Math.max(0, c - 1));
      prevUnread.current = Math.max(0, prevUnread.current - 1);
      try {
        await markNotificationRead(String(item.id));
      } catch {
        // The row already shows as read; the next refresh reconciles.
      }
    }
    setOpen(false);
    if (item.order_id != null) router.push(`/order/${item.order_id}`);
  };

  const markAllRead = async () => {
    setItems((prev) => prev.map((n) => ({ ...n, read: true })));
    setUnread(0);
    prevUnread.current = 0;
    try {
      await markAllNotificationsRead();
    } catch {
      // Same as above: the next refresh reconciles.
    }
  };

  return (
    <div className="app-bell" ref={ref}>
      <button
        type="button"
        className={`app-icon-button app-bell-btn${ringing ? " ringing" : ""}`}
        aria-label={
          unread > 0
            ? `Notifications, ${unread} unread`
            : "Notifications"
        }
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={toggle}
      >
        <span aria-hidden="true">🔔</span>
        {unread > 0 && (
          <span key={unread} className="app-cart-badge app-bell-badge">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="app-bell-panel" role="menu" aria-label="Notifications">
          <div className="app-bell-panel-head">
            <strong>Notifications</strong>
            {unread > 0 && (
              <button
                type="button"
                className="app-bell-mark-all"
                onClick={markAllRead}
              >
                Mark all read
              </button>
            )}
          </div>
          {loading && items.length === 0 ? (
            <p className="app-bell-empty">Loading…</p>
          ) : items.length === 0 ? (
            <p className="app-bell-empty">No notifications yet.</p>
          ) : (
            <ul className="app-bell-list">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    role="menuitem"
                    className={`app-bell-item${item.read ? "" : " unread"}`}
                    onClick={() => openItem(item)}
                  >
                    <span className="app-bell-item-title">
                      {!item.read && (
                        <span
                          className="app-bell-dot"
                          aria-label="Unread"
                        />
                      )}
                      {item.title ?? "Notification"}
                    </span>
                    {(item.body ?? item.message) && (
                      <span className="app-bell-item-body">
                        {item.body ?? item.message}
                      </span>
                    )}
                    <span className="app-bell-item-time">
                      {timeAgo(item.created_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
