// Menu management: item create, edit, delete, and availability toggles.
// Staff accounts can only change availability (the API enforces this;
// the form reflects it by disabling the other fields for staff).

"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import ApiOffline from "@/components/ApiOffline";
import {
  ApiError,
  createMenuItem,
  deleteMenuItem,
  getMenu,
  getRestaurant,
  updateMenuItem,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { centsToDollarsInput, dollarsToCents, formatCents } from "@/lib/money";
import type { MenuItem, Restaurant } from "@/lib/types";

const MANUAL_ID_KEY = "commontable.restaurant_manual_id";

export default function MenuPage() {
  return (
    <AppShell>
      <MenuManager />
    </AppShell>
  );
}

function MenuManager() {
  const { user, ready, restaurantId, hasRole } = useAuth();
  const [manualId, setManualId] = useState("");
  const [restaurant, setRestaurant] = useState<Restaurant | null>(null);
  const [items, setItems] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newPrice, setNewPrice] = useState("");
  const [newCategory, setNewCategory] = useState("");
  const [editing, setEditing] = useState<MenuItem | null>(null);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editPrice, setEditPrice] = useState("");
  const [editCategory, setEditCategory] = useState("");

  const activeId = restaurantId ?? manualId;
  // Staff may only toggle availability; owner/manager/admin get full edit.
  const staffOnly =
    hasRole("restaurant_staff") &&
    !hasRole("restaurant_owner", "restaurant_manager", "admin");

  useEffect(() => {
    try {
      const saved = window.sessionStorage.getItem(MANUAL_ID_KEY);
      if (saved) setManualId(saved);
    } catch {
      // ignore
    }
  }, []);

  const load = useCallback(async () => {
    if (!activeId) {
      setLoading(false);
      return;
    }
    setError(null);
    try {
      const [r, list] = await Promise.all([
        getRestaurant(activeId),
        getMenu(activeId),
      ]);
      setRestaurant(r);
      setItems(list);
    } catch (err) {
      if (err instanceof ApiError && err.unreachable) setOffline(true);
      else if (err instanceof ApiError) setError(err.message);
      else setError("Could not load the menu.");
    } finally {
      setLoading(false);
    }
  }, [activeId]);

  useEffect(() => {
    if (!ready) return;
    load();
  }, [ready, load]);

  const handleError = (err: unknown) => {
    if (err instanceof ApiError && err.unreachable) setOffline(true);
    else if (err instanceof ApiError) setError(err.message);
    else setError("That change did not go through. Please try again.");
  };

  const handleCreate = async () => {
    const priceCents = dollarsToCents(newPrice);
    if (!newName.trim()) {
      setError("Give the item a name.");
      return;
    }
    if (priceCents == null) {
      setError("Enter a valid price in dollars.");
      return;
    }
    setBusyId("new");
    setError(null);
    try {
      await createMenuItem(activeId, {
        name: newName.trim(),
        description: newDesc.trim() || undefined,
        price_cents: priceCents,
        category: newCategory.trim() || undefined,
        available: true,
      });
      setNewName("");
      setNewDesc("");
      setNewPrice("");
      setNewCategory("");
      await load();
    } catch (err) {
      handleError(err);
    } finally {
      setBusyId(null);
    }
  };

  const startEdit = (item: MenuItem) => {
    setEditing(item);
    setEditName(item.name);
    setEditDesc(item.description ?? "");
    setEditPrice(centsToDollarsInput(item.price_cents));
    setEditCategory(item.category ?? "");
  };

  const handleSaveEdit = async () => {
    if (!editing) return;
    const priceCents = dollarsToCents(editPrice);
    if (!editName.trim()) {
      setError("Give the item a name.");
      return;
    }
    if (priceCents == null) {
      setError("Enter a valid price in dollars.");
      return;
    }
    setBusyId(editing.id);
    setError(null);
    try {
      await updateMenuItem(activeId, editing.id, {
        name: editName.trim(),
        description: editDesc.trim(),
        price_cents: priceCents,
        category: editCategory.trim(),
      });
      setEditing(null);
      await load();
    } catch (err) {
      handleError(err);
    } finally {
      setBusyId(null);
    }
  };

  const handleToggle = async (item: MenuItem) => {
    setBusyId(item.id);
    setError(null);
    try {
      await updateMenuItem(activeId, item.id, { available: !item.available });
      await load();
    } catch (err) {
      handleError(err);
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (item: MenuItem) => {
    if (!window.confirm(`Remove "${item.name}" from the menu?`)) return;
    setBusyId(item.id);
    setError(null);
    try {
      await deleteMenuItem(activeId, item.id);
      await load();
    } catch (err) {
      handleError(err);
    } finally {
      setBusyId(null);
    }
  };

  if (offline) {
    return <ApiOffline onRetry={() => { setOffline(false); setLoading(true); load(); }} />;
  }

  if (!ready || loading) {
    return <p>Loading the menu…</p>;
  }

  if (!user) {
    return (
      <div>
        <h1>Menu</h1>
        <p>
          <Link href="/login">Sign in</Link> with a restaurant account to
          manage the menu.
        </p>
      </div>
    );
  }

  if (!activeId) {
    return (
      <div>
        <h1>Menu</h1>
        <p>
          No restaurant is linked to your account yet. Open the{" "}
          <Link href="/restaurant">restaurant dashboard</Link> first.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1>Menu for {restaurant?.name ?? "your restaurant"}</h1>
      <p className="app-lede">
        Items at the restaurant's own menu prices. Turn an item off when it
        runs out; customers see it as unavailable.
      </p>
      {staffOnly && (
        <p className="app-notice">
          Your staff role can change item availability only. Owners and
          managers can add, edit, and remove items.
        </p>
      )}
      {error && (
        <p className="app-error" role="alert">
          {error}
        </p>
      )}

      {!staffOnly && (
        <section className="app-card" aria-label="Add a menu item">
          <h2>Add a menu item</h2>
          <div className="app-form-grid">
            <label className="app-field">
              <span>Name</span>
              <input
                className="app-input"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Margherita Pizza"
              />
            </label>
            <label className="app-field">
              <span>Price ($)</span>
              <input
                className="app-input"
                inputMode="decimal"
                value={newPrice}
                onChange={(e) => setNewPrice(e.target.value)}
                placeholder="10.80"
              />
            </label>
            <label className="app-field">
              <span>Category (optional)</span>
              <input
                className="app-input"
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                placeholder="Mains"
              />
            </label>
            <label className="app-field app-field-wide">
              <span>Description (optional)</span>
              <input
                className="app-input"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="Tomato, mozzarella, basil"
              />
            </label>
          </div>
          <button
            type="button"
            className="app-btn"
            onClick={handleCreate}
            disabled={busyId === "new"}
          >
            {busyId === "new" ? "Adding…" : "Add item"}
          </button>
        </section>
      )}

      <section aria-label="Menu items">
        <h2>Menu items</h2>
        {items.length === 0 ? (
          <p>No menu items yet.</p>
        ) : (
          <ul className="app-list">
            {items.map((item) => (
              <li key={item.id} className="app-list-row app-menu-row">
                {editing?.id === item.id ? (
                  <div className="app-edit-form">
                    <div className="app-form-grid">
                      <label className="app-field">
                        <span>Name</span>
                        <input
                          className="app-input"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                        />
                      </label>
                      <label className="app-field">
                        <span>Price ($)</span>
                        <input
                          className="app-input"
                          inputMode="decimal"
                          value={editPrice}
                          onChange={(e) => setEditPrice(e.target.value)}
                        />
                      </label>
                      <label className="app-field">
                        <span>Category</span>
                        <input
                          className="app-input"
                          value={editCategory}
                          onChange={(e) => setEditCategory(e.target.value)}
                        />
                      </label>
                      <label className="app-field app-field-wide">
                        <span>Description</span>
                        <input
                          className="app-input"
                          value={editDesc}
                          onChange={(e) => setEditDesc(e.target.value)}
                        />
                      </label>
                    </div>
                    <div className="app-actions">
                      <button
                        type="button"
                        className="app-btn app-btn-small"
                        onClick={handleSaveEdit}
                        disabled={busyId === item.id}
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        className="app-btn app-btn-small app-btn-ghost"
                        onClick={() => setEditing(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="app-menu-info">
                      <span className="app-list-title">{item.name}</span>
                      {item.description && (
                        <span className="app-list-sub">{item.description}</span>
                      )}
                      <span className="app-menu-price">
                        {formatCents(item.price_cents)}
                        {item.category ? ` · ${item.category}` : ""}
                      </span>
                      {!item.available && (
                        <span className="app-tag app-tag-muted">Unavailable</span>
                      )}
                    </div>
                    <div className="app-actions">
                      <button
                        type="button"
                        className="app-btn app-btn-small app-btn-ghost"
                        disabled={busyId === item.id}
                        onClick={() => handleToggle(item)}
                      >
                        {item.available ? "Mark unavailable" : "Mark available"}
                      </button>
                      {!staffOnly && (
                        <>
                          <button
                            type="button"
                            className="app-btn app-btn-small"
                            onClick={() => startEdit(item)}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="app-btn app-btn-small app-btn-danger"
                            disabled={busyId === item.id}
                            onClick={() => handleDelete(item)}
                          >
                            Remove
                          </button>
                        </>
                      )}
                    </div>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
