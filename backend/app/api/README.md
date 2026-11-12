# API routers (one per service module, per spec section 10)

Planned routers — none implemented yet; they land with the approved MVP slice:

- `auth.py` — register, login, refresh, logout, /users/me
- `restaurants.py` — restaurant + menu CRUD, reports
- `orders.py` — order lifecycle, accept/reject/ready/cancel, events, ratings
- `dispatch.py` — serviceability, dispatch board, manual assign/override
- `drivers.py` — availability, offers, earnings
- `deliveries.py` — pickup/delivery confirmation, issue reporting
- `direct2door.py` — quote, order intake, webhooks
- `payments.py` — payment intents, provider webhook, ledger, refunds
- `admin.py` — zones, pricing rules, metrics, support, approvals
- `ws.py` — WebSocket channels (orders, driver, dispatch, restaurant)
