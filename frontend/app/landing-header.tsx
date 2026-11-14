// Landing-page header, in the style of the reference merchant site:
// wordmark, Login, a Get Started pill, and a hamburger menu that opens a
// full-width link panel. Links only go to pages and sections that exist.

"use client";

import { useState } from "react";
import Link from "next/link";

const MENU_LINKS = [
  { href: "/order", label: "Order food" },
  { href: "/restaurant", label: "For restaurants" },
  { href: "/driver", label: "For drivers" },
  { href: "#how-it-works", label: "How it works" },
  { href: "#delivery", label: "Pricing" },
  { href: "#portals", label: "Portals" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
];

export default function LandingHeader() {
  const [open, setOpen] = useState(false);

  return (
    <header className="lp-header">
      <div className="container lp-header-inner">
        <a className="lp-wordmark" href="#top">
          CommonTable
        </a>
        <div className="lp-header-actions">
          <Link href="/login" className="lp-login">
            Login
          </Link>
          <a href="#join" className="lp-get-started">
            Get Started
          </a>
          <button
            type="button"
            className="lp-menu-btn"
            aria-expanded={open}
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen(!open)}
          >
            {open ? "✕" : "☰"}
          </button>
        </div>
      </div>
      {open && (
        <nav className="lp-menu" aria-label="Site menu">
          <div className="container">
            {MENU_LINKS.map((link) => (
              <a
                key={link.href + link.label}
                href={link.href}
                className="lp-menu-link"
                onClick={() => setOpen(false)}
              >
                <span>{link.label}</span>
                <span aria-hidden="true">›</span>
              </a>
            ))}
          </div>
        </nav>
      )}
    </header>
  );
}
