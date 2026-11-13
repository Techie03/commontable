// Live section for the landing page: the Denton restaurants coming
// soon. Client-side fetch so the static page never waits on the API
// (the free backend sleeps when idle). If the API is unreachable, the
// section stays hidden and the page still works. Pilot restaurants with
// a collected menu get a "View menu" link to the browse-only menu page.

"use client";

import { useEffect, useState } from "react";
import { listComingSoonRestaurants } from "@/lib/api";
import {
  restaurantAddress,
  type Restaurant,
} from "@/lib/types";

const PREVIEW_COUNT = 12;

export default function HomeLiveSections() {
  const [comingSoon, setComingSoon] = useState<Restaurant[]>([]);
  const [comingSoonTotal, setComingSoonTotal] = useState(0);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listComingSoonRestaurants(undefined, 1, PREVIEW_COUNT)
      .then((res) => {
        if (cancelled) return;
        setComingSoon(res.items);
        setComingSoonTotal(res.total);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!loaded) return null;
  if (comingSoon.length === 0) return null;

  return (
    <section className="section tint" id="restaurants">
      <div className="container">
        <h2>{comingSoonTotal} restaurants coming soon in Denton</h2>
        <p className="lede">
          These local restaurants have not joined CommonTable yet.
          Ordering opens as each one comes on board. Pilot restaurants
          with a collected menu can be browsed now.
        </p>
        <div className="spot-grid">
          {comingSoon.map((r) => (
            <article key={r.id} className="spot-card">
              <h3>{r.name}</h3>
              <p>
                {[r.primary_category, restaurantAddress(r)]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              <span className="spot-tag">Coming soon</span>
              {r.has_menu && (
                <a className="spot-menu-link" href={`/menu/${r.id}`}>
                  View menu →
                </a>
              )}
            </article>
          ))}
        </div>
        <p className="section-cta">
          <a className="section-cta-btn" href="/order">
            Browse all {comingSoonTotal} on the order page
          </a>
        </p>
      </div>
    </section>
  );
}
