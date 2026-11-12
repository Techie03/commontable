# CommonTable frontend (Next.js / React)

Placeholder for the three web surfaces (spec section 8.1):

- **Customer ordering** — responsive web ordering (fast pilot option), mobile-first.
- **Restaurant dashboard** — desktop-first: order queue, menu, reports.
- **Admin console** — desktop-first: users, zones, pricing, refunds, metrics.

The driver app is React Native (separate app; see spec section 8.2) and is
not part of this package.

Design direction (spec section 1.8): deep forest green, teal, warm white,
neutral charcoal. Prices and fees easy to understand; avoid clutter.

## Landing page interactive demo

`app/page.tsx` renders the marketing landing page. The "How it works"
section embeds `app/demo.tsx`, an interactive walkthrough of one demo
order in four stages (customer orders, restaurant accepts, driver
delivers, delivered), with live role panels and a journey video.

Demo/showcase only: no ordering, account, or payment functionality. All
copy and figures come from the startup blueprint; every price is labeled
a hypothesis and every figure is labeled a demo illustration.

The journey video (`public/demo-journey.mp4`, 10-second generated clip)
is a **local-only asset**: the GitHub snapshot push can only carry UTF-8
text files, so the clip is gitignored and never pushed. The page shows a
CSS route animation in its place whenever the video file is absent, so
deploys built from GitHub still show the full animated demo.

## Develop

```bash
npm install
npm run dev   # http://localhost:3000
```

The API base URL is `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
