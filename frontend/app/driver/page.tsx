// Driver workspace: availability toggle, delivery offers with the full
// route and pay shown before accept, active delivery (pickup and delivery
// confirmation), issue reporting, and earnings.

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import ApiOffline from "@/components/ApiOffline";
import {
  acceptOffer,
  ApiError,
  confirmDeliver,
  confirmPickup,
  declineOffer,
  getAccessToken,
  getDriverEarnings,
  getDriverMe,
  getDriverOffers,
  getDriverTasks,
  reportDeliveryIssue,
  setDriverAvailability,
  wsUrl,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatCents } from "@/lib/money";
import {
  asList,
  shortId,
  taskId,
  type DeliveryTask,
  type DriverProfile,
  type Earnings,
} from "@/lib/types";

const ACTIVE_TASK_KEY = "commontable.driver_active_task";

export default function DriverPage() {
  return (
    <AppShell>
      <DriverWorkspace />
    </AppShell>
  );
}

function DriverWorkspace() {
  const { user, ready } = useAuth();
  const [profile, setProfile] = useState<DriverProfile | null>(null);
  const [offers, setOffers] = useState<DeliveryTask[]>([]);
  const [earnings, setEarnings] = useState<Earnings | null>(null);
  const [activeTask, setActiveTask] = useState<DeliveryTask | null>(null);
  const [pickedUp, setPickedUp] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [live, setLive] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [proofNote, setProofNote] = useState("");
  const [issueText, setIssueText] = useState("");
  const [issueSent, setIssueSent] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const handleError = useCallback((err: unknown) => {
    if (err instanceof ApiError && err.unreachable) setOffline(true);
    else if (err instanceof ApiError) setError(err.message);
    else setError("Something went wrong. Please try again.");
  }, []);

  const loadOffers = useCallback(async () => {
    try {
      setOffers(await getDriverOffers());
    } catch (err) {
      handleError(err);
    }
  }, [handleError]);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [p, e] = await Promise.all([
        getDriverMe(),
        getDriverEarnings().catch(() => null as Earnings | null),
      ]);
      setProfile(p);
      setEarnings(e);
      await loadOffers();
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }, [handleError, loadOffers]);

  useEffect(() => {
    if (!ready) return;
    if (!user) {
      setLoading(false);
      return;
    }
    // Restore the active delivery from the server first, so it survives a
    // refresh on any device; fall back to the browser-saved copy if the
    // server has no active task (or cannot be reached).
    let cancelled = false;
    (async () => {
      try {
        const tasks = await getDriverTasks();
        if (!cancelled && tasks.length > 0) {
          const task = tasks[0];
          setActiveTask(task);
          setPickedUp(task.status === "picked_up");
          return;
        }
      } catch {
        // fall through to the browser-saved copy
      }
      if (cancelled) return;
      try {
        const raw = window.localStorage.getItem(ACTIVE_TASK_KEY);
        if (raw) {
          const saved = JSON.parse(raw) as {
            task: DeliveryTask;
            pickedUp: boolean;
          };
          setActiveTask(saved.task);
          setPickedUp(saved.pickedUp);
        }
      } catch {
        // ignore
      }
    })();
    load();
    return () => {
      cancelled = true;
    };
  }, [ready, user, load]);

  // Live offers over the driver channel.
  useEffect(() => {
    const token = getAccessToken();
    const driverId = profile?.id ?? user?.id;
    if (!token || !driverId || offline) return;
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(
        `${wsUrl(`/api/v1/ws/driver/${driverId}`)}?token=${encodeURIComponent(token)}`
      );
    } catch {
      return;
    }
    wsRef.current = ws;
    ws.onopen = () => setLive(true);
    ws.onclose = () => setLive(false);
    ws.onerror = () => setLive(false);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string) as { type?: string };
        if (msg.type === "offer.created" || msg.type === "offer.withdrawn") {
          loadOffers();
        }
      } catch {
        // Ignore malformed frames.
      }
    };
    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [profile?.id, user?.id, offline, loadOffers]);

  const saveActiveTask = (task: DeliveryTask | null, isPickedUp: boolean) => {
    setActiveTask(task);
    setPickedUp(isPickedUp);
    try {
      if (task) {
        window.localStorage.setItem(
          ACTIVE_TASK_KEY,
          JSON.stringify({ task, pickedUp: isPickedUp })
        );
      } else {
        window.localStorage.removeItem(ACTIVE_TASK_KEY);
      }
    } catch {
      // ignore
    }
  };

  const toggleOnline = async () => {
    if (!profile) return;
    const next = !profile.online;
    setBusy("availability");
    setError(null);
    try {
      const updated = await setDriverAvailability(next);
      setProfile(updated);
    } catch (err) {
      handleError(err);
    } finally {
      setBusy(null);
    }
  };

  const handleAccept = async (task: DeliveryTask) => {
    setBusy(taskId(task));
    setError(null);
    try {
      await acceptOffer(taskId(task));
      saveActiveTask(task, false);
      setIssueSent(false);
      await loadOffers();
    } catch (err) {
      handleError(err);
    } finally {
      setBusy(null);
    }
  };

  const handleDecline = async (task: DeliveryTask) => {
    setBusy(taskId(task));
    setError(null);
    try {
      await declineOffer(taskId(task));
      await loadOffers();
    } catch (err) {
      handleError(err);
    } finally {
      setBusy(null);
    }
  };

  const handlePickup = async () => {
    if (!activeTask) return;
    setBusy("pickup");
    setError(null);
    try {
      await confirmPickup(taskId(activeTask));
      saveActiveTask(activeTask, true);
    } catch (err) {
      handleError(err);
    } finally {
      setBusy(null);
    }
  };

  const handleDeliver = async () => {
    if (!activeTask) return;
    setBusy("deliver");
    setError(null);
    try {
      await confirmDeliver(taskId(activeTask), proofNote || undefined);
      saveActiveTask(null, false);
      setProofNote("");
      const e = await getDriverEarnings().catch(() => null);
      setEarnings(e);
    } catch (err) {
      handleError(err);
    } finally {
      setBusy(null);
    }
  };

  const handleIssue = async () => {
    if (!activeTask || !issueText.trim()) return;
    setBusy("issue");
    setError(null);
    try {
      await reportDeliveryIssue(taskId(activeTask), issueText.trim());
      setIssueSent(true);
      setIssueText("");
    } catch (err) {
      handleError(err);
    } finally {
      setBusy(null);
    }
  };

  if (offline) {
    return <ApiOffline onRetry={() => { setOffline(false); setLoading(true); load(); }} />;
  }

  if (!ready || loading) {
    return <p>Loading the driver workspace…</p>;
  }

  if (!user) {
    return (
      <div>
        <h1>Driver</h1>
        <p>
          <Link href="/login">Sign in</Link> with a driver account to see
          offers and deliveries.
        </p>
      </div>
    );
  }

  const earningsEntries = asList(earnings?.entries ?? earnings?.items);
  const totalPay =
    earnings?.total_cents ?? earnings?.total_pay_cents ?? null;

  return (
    <div>
      <h1>Driver</h1>
      <p className="app-live-indicator" role="status">
        {live
          ? "Live offers connected. New offers appear here as they arrive."
          : "Live offers are not connected right now. Refresh to check for new offers."}
      </p>
      {error && (
        <p className="app-error" role="alert">
          {error}
        </p>
      )}

      <section className="app-card" aria-label="Availability">
        <h2>Availability</h2>
        <p>
          Onboarding status:{" "}
          <strong>
            {profile?.onboarding_status ??
              (profile?.approved ? "approved" : "unknown")}
          </strong>
        </p>
        {profile?.vehicle && (
          <p>
            Vehicle:{" "}
            {[profile.vehicle.make, profile.vehicle.model, profile.vehicle.plate]
              .filter(Boolean)
              .join(" ")}
          </p>
        )}
        <button
          type="button"
          className={`app-btn${profile?.online ? " app-btn-danger" : ""}`}
          onClick={toggleOnline}
          disabled={busy === "availability"}
        >
          {busy === "availability"
            ? "Updating…"
            : profile?.online
              ? "Go offline"
              : "Go online"}
        </button>
        <p className="app-muted">
          {profile?.online
            ? "You are online and can receive offers."
            : "You are offline and will not receive offers."}
        </p>
      </section>

      {activeTask && (
        <section className="app-card" aria-label="Active delivery">
          <h2>Active delivery</h2>
          <p>
            <strong>Order {shortId(activeTask.order_id)}</strong>
            {activeTask.restaurant_name
              ? ` · ${activeTask.restaurant_name}`
              : ""}
          </p>
          <p>Pick up: {activeTask.pickup_address ?? "See the order for the address."}</p>
          <p>Drop off: {activeTask.dropoff_address ?? "See the order for the address."}</p>
          <p>
            Pay: <strong>{formatCents(activeTask.pay_cents)}</strong>
          </p>
          <p className="app-muted">
            {pickedUp
              ? "Picked up. Head to the drop off address."
              : "Head to the restaurant to pick up the order."}
          </p>
          {!pickedUp ? (
            <button
              type="button"
              className="app-btn"
              onClick={handlePickup}
              disabled={busy === "pickup"}
            >
              {busy === "pickup" ? "Confirming…" : "Confirm pickup"}
            </button>
          ) : (
            <>
              <label className="app-field">
                <span>Delivery note (optional)</span>
                <input
                  className="app-input"
                  value={proofNote}
                  onChange={(e) => setProofNote(e.target.value)}
                  placeholder="Left at the front door"
                />
              </label>
              <button
                type="button"
                className="app-btn"
                onClick={handleDeliver}
                disabled={busy === "deliver"}
              >
                {busy === "deliver" ? "Confirming…" : "Confirm delivery"}
              </button>
            </>
          )}
          <div className="app-issue">
            <h3>Report a problem</h3>
            {issueSent ? (
              <p>Thanks. Your report was sent to support.</p>
            ) : (
              <>
                <label className="app-field">
                  <span>What happened?</span>
                  <textarea
                    className="app-input"
                    value={issueText}
                    onChange={(e) => setIssueText(e.target.value)}
                    rows={3}
                    placeholder="Describe the issue"
                  />
                </label>
                <button
                  type="button"
                  className="app-btn app-btn-ghost"
                  onClick={handleIssue}
                  disabled={busy === "issue" || !issueText.trim()}
                >
                  {busy === "issue" ? "Sending…" : "Report issue"}
                </button>
              </>
            )}
          </div>
        </section>
      )}

      <section aria-label="Delivery offers">
        <h2>Delivery offers</h2>
        {offers.length === 0 ? (
          <p>No offers right now. Stay online and new offers will appear here.</p>
        ) : (
          <ul className="app-list">
            {offers.map((task) => (
              <li key={taskId(task)} className="app-list-row app-offer-row">
                <div>
                  <span className="app-list-title">
                    Order {shortId(task.order_id)}
                    {task.restaurant_name ? ` · ${task.restaurant_name}` : ""}
                  </span>
                  <span className="app-list-sub">
                    Pick up: {task.pickup_address ?? "Address on the order"}
                  </span>
                  <span className="app-list-sub">
                    Drop off: {task.dropoff_address ?? "Address on the order"}
                  </span>
                  <span className="app-list-sub">
                    {task.distance_miles != null
                      ? `${task.distance_miles} miles`
                      : "Distance estimate unavailable"}
                    {task.eta_minutes != null
                      ? ` · about ${task.eta_minutes} min`
                      : ""}
                  </span>
                  <span className="app-offer-pay">
                    Pay {formatCents(task.pay_cents)}
                  </span>
                </div>
                <div className="app-actions">
                  <button
                    type="button"
                    className="app-btn app-btn-small"
                    disabled={busy === taskId(task) || activeTask != null}
                    onClick={() => handleAccept(task)}
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    className="app-btn app-btn-small app-btn-ghost"
                    disabled={busy === taskId(task)}
                    onClick={() => handleDecline(task)}
                  >
                    Decline
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
        {activeTask && (
          <p className="app-muted">
            Finish the active delivery before accepting another offer.
          </p>
        )}
      </section>

      <section aria-label="Earnings">
        <h2>Earnings</h2>
        {earnings == null ? (
          <p>No earnings data yet.</p>
        ) : (
          <>
            <div className="app-stat-strip">
              <div className="app-stat">
                <span className="app-stat-number">{formatCents(totalPay)}</span>
                <span className="app-stat-label">Total pay</span>
              </div>
              <div className="app-stat">
                <span className="app-stat-number">
                  {earnings.deliveries ?? earningsEntries.length}
                </span>
                <span className="app-stat-label">Deliveries</span>
              </div>
              <div className="app-stat">
                <span className="app-stat-number">
                  {formatCents(earnings.total_tip_cents)}
                </span>
                <span className="app-stat-label">Total tips</span>
              </div>
            </div>
            {earningsEntries.length > 0 && (
              <ul className="app-list">
                {earningsEntries.map((entry, idx) => (
                  <li
                    key={`${entry.order_id}-${idx}`}
                    className="app-list-row"
                  >
                    <span>
                      <strong>Order {shortId(entry.order_id)}</strong>
                      <span className="app-list-sub">
                        {(entry.delivered_at ?? entry.created_at)
                          ? new Date(
                              (entry.delivered_at ?? entry.created_at) as string
                            ).toLocaleString()
                          : ""}
                      </span>
                    </span>
                    <span className="app-list-right">
                      <span>Pay {formatCents(entry.pay_cents)}</span>
                      {entry.tip_cents != null && entry.tip_cents > 0 && (
                        <span>Tip {formatCents(entry.tip_cents)}</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>
    </div>
  );
}
