// Browse-only menu for a restaurant that has not joined CommonTable
// yet. Read-only by design: no cart, no checkout, no ordering of any
// kind. The menu was collected from the restaurant's own published
// menu; prices may have changed since. Items with no published price
// show "Price not listed".

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import ApiOffline from "@/components/ApiOffline";
import { ApiError, getBrowseMenu } from "@/lib/api";
import { formatCents } from "@/lib/money";
import {
  restaurantAddress,
  type BrowseMenu,
  type MenuItem,
  type Restaurant,
} from "@/lib/types";

function groupByCategory(items: MenuItem[]): [string, MenuItem[]][] {
  const groups: [string, MenuItem[]][] = [];
  for (const item of items) {
    const name = item.category || "Menu";
    const group = groups.find(([n]) => n === name);
    if (group) group[1].push(item);
    else groups.push([name, [item]]);
  }
  return groups;
}

export default function BrowseMenuPage() {
  return (
    <AppShell>
      <BrowseMenuBody />
    </AppShell>
  );
}

function BrowseMenuBody() {
  const params = useParams();
  const id = String(params.id);
  const [menu, setMenu] = useState<BrowseMenu | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getBrowseMenu(id)
      .then((m) => {
        if (!cancelled) setMenu(m);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.unreachable) setOffline(true);
        else setNotFound(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (offline) {
    return <ApiOffline onRetry={() => setOffline(false)} />;
  }

  if (loading) {
    return (
      <div className="app-narrow">
        <p>Loading the menu…</p>
      </div>
    );
  }

  if (notFound || !menu) {
    return (
      <div className="app-narrow">
        <h1>Menu not available</h1>
        <p className="app-lede">
          This restaurant has no menu to browse here. It may have joined
          CommonTable since, in which case you can order from it on the
          order page.
        </p>
        <p>
          <Link href="/order" className="app-btn">
            Go to the order page
          </Link>
        </p>
      </div>
    );
  }

  const asRestaurant = {
    locations: menu.locations,
  } as unknown as Restaurant;
  const address = restaurantAddress(asRestaurant);
  const groups = groupByCategory(menu.items);

  return (
    <div className="app-narrow">
      <p>
        <Link href="/order">← Back to restaurants</Link>
      </p>
      <h1>{menu.name}</h1>
      <p className="app-lede">
        {[menu.primary_category, address, menu.phone]
          .filter(Boolean)
          .join(" · ")}
      </p>
      <div className="browse-banner" role="note">
        <strong>Browse only.</strong> {menu.name} hasn&apos;t joined
        CommonTable yet, so this menu is for browsing, not ordering. It
        was collected from the restaurant&apos;s own published menu, and
        prices may have changed since. Food photos are representative
        images of each dish. Ordering opens when they join.
        {menu.website && (
          <>
            {" "}
            <a href={menu.website} target="_blank" rel="noreferrer">
              See the current menu on their site
            </a>
            .
          </>
        )}
      </div>
      {menu.items.length === 0 ? (
        <p>This restaurant has no menu items listed yet.</p>
      ) : (
        groups.map(([category, items]) => (
          <section key={category} aria-label={category}>
            <h2>{category}</h2>
            <ul className="app-list">
              {items.map((item) => (
                <li key={item.id} className="app-list-row app-menu-row">
                  {item.image_url && (
                    <img
                      src={item.image_url}
                      alt=""
                      className="app-menu-thumb"
                      loading="lazy"
                    />
                  )}
                  <span>
                    <span className="app-list-title">{item.name}</span>
                    {item.description && (
                      <span className="app-list-sub">{item.description}</span>
                    )}
                  </span>
                  <span className="app-list-price">
                    {item.price_cents > 0
                      ? formatCents(item.price_cents)
                      : "Price not listed"}
                  </span>
                  {!item.available && (
                    <span className="app-tag">Unavailable</span>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}
