// "Portals" dropdown for the landing page topbar and the app header.
// Lists every role portal in one place, next to the sign in control.

"use client";

import HeaderDropdown from "./HeaderDropdown";

const PORTALS = [
  { href: "/order", title: "Customer", desc: "Browse menus, order, track delivery" },
  { href: "/restaurant", title: "Restaurant", desc: "Menus, orders, Direct2Door" },
  { href: "/driver", title: "Driver", desc: "Assigned deliveries and drop offs" },
  { href: "/dispatch", title: "Dispatcher", desc: "Live orders and driver assignment" },
  { href: "/admin", title: "Admin", desc: "Users, roles, zones, pricing, ledger" },
];

export default function PortalsDropdown() {
  return <HeaderDropdown label="Portals" items={PORTALS} />;
}
