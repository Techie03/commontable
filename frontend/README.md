# CommonTable frontend (Next.js / React)

Placeholder for the three web surfaces (spec section 8.1):

- **Customer ordering** — responsive web ordering (fast pilot option), mobile-first.
- **Restaurant dashboard** — desktop-first: order queue, menu, reports.
- **Admin console** — desktop-first: users, zones, pricing, refunds, metrics.

The driver app is React Native (separate app; see spec section 8.2) and is
not part of this package.

Design direction (spec section 1.8): deep forest green, teal, warm white,
neutral charcoal. Prices and fees easy to understand; avoid clutter.

## Develop

```bash
npm install
npm run dev   # http://localhost:3000
```

The API base URL is `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
