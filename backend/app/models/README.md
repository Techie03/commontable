# SQLAlchemy models (per spec section 9 ERD)

Planned model modules — none implemented yet:

- `identity.py` — users, roles, user_roles, customers
- `restaurants.py` — restaurants, restaurant_locations, menus, menu_items, modifiers
- `geo.py` — service_zones, addresses (PostGIS geometry)
- `orders.py` — orders, order_items, status_events
- `payments.py` — payments, ledger_entries, refunds
- `delivery.py` — drivers, driver_vehicles, driver_shifts, delivery_tasks, route_batches, route_stops
- `integrations.py` — integrations, pricing_rules
- `support.py` — support_tickets, ratings

Rules (spec section 9.3): money as integer cents; timestamps UTC;
checkout_snapshot, status_events, and ledger_entries are append-only.
