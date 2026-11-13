// Generic header dropdown: a button that opens a small menu of links.
// Used for the Portals menu and the Create account role menu. Closes on
// outside click, Escape, or selection. Navigation only, never a security
// check: the API enforces roles on every endpoint.

"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

export type HeaderDropdownItem = {
  href: string;
  title: string;
  desc: string;
};

export default function HeaderDropdown({
  label,
  items,
}: {
  label: string;
  items: HeaderDropdownItem[];
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

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
  }, [open]);

  return (
    <div className="header-dropdown" ref={ref}>
      <button
        type="button"
        className="header-dropdown-btn"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {label} <span aria-hidden="true">{open ? "▴" : "▾"}</span>
      </button>
      {open && (
        <div className="header-dropdown-menu" role="menu">
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              role="menuitem"
              onClick={() => setOpen(false)}
            >
              <span className="header-dropdown-item-title">{item.title}</span>
              <span className="header-dropdown-item-desc">{item.desc}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
