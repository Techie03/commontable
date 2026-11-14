// Merged header menu for the landing page topbar and the app header:
// every role portal plus, for visitors, account creation by role.
// One dropdown instead of two. The landing page has no auth context,
// so the caller decides whether the signup section shows.

"use client";

import HeaderDropdown from "./HeaderDropdown";

const PORTALS = [
  { href: "/order", title: "Customer", desc: "Browse menus, order, track delivery" },
  { href: "/restaurant", title: "Restaurant", desc: "Menus, orders, Direct2Door" },
  { href: "/driver", title: "Driver", desc: "Assigned deliveries and drop offs" },
  { href: "/dispatch", title: "Dispatcher", desc: "Live orders and driver assignment" },
  { href: "/admin", title: "Admin", desc: "Users, roles, zones, pricing, ledger" },
];

const CREATE_ACCOUNT_ROLES = [
  {
    href: "/register?role=customer",
    title: "Customer",
    desc: "Order food and track delivery",
  },
  {
    href: "/register?role=restaurant_owner",
    title: "Restaurant",
    desc: "Menus, orders, Direct2Door",
  },
  {
    href: "/register?role=driver",
    title: "Driver",
    desc: "Deliver orders and earn per trip",
  },
];

export default function PortalsDropdown({
  showSignup = true,
}: {
  showSignup?: boolean;
}) {
  const sections = [
    { heading: "Portals", items: PORTALS },
    ...(showSignup
      ? [{ heading: "Create an account", items: CREATE_ACCOUNT_ROLES }]
      : []),
  ];
  return <HeaderDropdown label="Portals" sections={sections} />;
}
