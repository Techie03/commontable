// Shown whenever the API is unreachable or not configured. Every slice
// page renders this instead of crashing, going blank, or showing fake data.

"use client";

import { OFFLINE_MESSAGE } from "@/lib/api";

export default function ApiOffline({
  message = OFFLINE_MESSAGE,
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="app-offline" role="alert">
      <h2>Service not connected yet</h2>
      <p>{message}</p>
      <p>
        Nothing here is live data. Once the ordering service is connected,
        this page will load real restaurants, menus, and orders.
      </p>
      {onRetry && (
        <button type="button" className="app-btn" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
