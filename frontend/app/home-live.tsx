// Live sections for the landing page: the Demo Diner menu with photos and
// the Denton restaurants coming soon. Client-side fetch so the static page
// never waits on the API (the free backend sleeps when idle). If the API is
// unreachable, the sections stay hidden and the page still works.

"use client";

import { useEffect, useState } from "react";
import { getMenu, listComingSoonRestaurants } from "@/lib/api";
import { formatCents } from "@/lib/money";
import {
  restaurantAddress,
  type MenuItem,
  type Restaurant,
} from "@/lib/types";

const DEMO_RESTAURANT_ID = "1";
const PREVIEW_COUNT = 12;

export default function HomeLiveSections() {
  const [comingSoon, setComingSoon] = useState<Restaurant[]>([]);
  const [comingSoonTotal, setComingSoonTotal] = useState(0);
  const [menu, setMenu] = useState<MenuItem[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([
      listComingSoonRestaurants(undefined, 1, PREVIEW_COUNT),
      getMenu(DEMO_RESTAURANT_ID),
    ]).then(([soon, menuRes]) => {
      if (cancelled) return;
      if (soon.status === "fulfilled") {
        setComingSoon(soon.value.items);
        setComingSoonTotal(soon.value.total);
      }
      if (menuRes.status === "fulfilled") setMenu(menuRes.value);
      setLoaded(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!loaded) return null;
  if (comingSoon.length === 0 && menu.length === 0) return null;

  return (
    <>
      {menu.length > 0 && (
        <section className="section" id="menu">
          <div className="container">
            <h2>Order from Demo Diner</h2>
            <p className="lede">
              The demo restaurant, serving the Denton pilot zone now. Real
              ordering end to end, with a demo checkout: no card is charged
              and no real money moves.
            </p>
            <div className="food-grid">
              {menu.map((item) => (
                <article key={item.id} className="food-card">
                  {item.image_url && (
                    <img src={item.image_url} alt="" loading="lazy" />
                  )}
                  <div className="food-body">
                    <h3>{item.name}</h3>
                    <p className="food-price">
                      {formatCents(item.price_cents)}
                    </p>
                    {!item.available && (
                      <span className="food-tag">Unavailable</span>
                    )}
                  </div>
                </article>
              ))}
            </div>
            <p className="section-cta">
              <a className="section-cta-btn" href="/order">
                Order food
              </a>
            </p>
          </div>
        </section>
      )}

      {comingSoon.length > 0 && (
        <section className="section tint" id="restaurants">
          <div className="container">
            <h2>
              {comingSoonTotal} restaurants coming soon in Denton
            </h2>
            <p className="lede">
              These local restaurants have not joined CommonTable yet.
              Ordering opens as each one comes on board.
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
      )}
    </>
  );
}
