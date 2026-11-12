"use client";

// Interactive CommonTable prototype: four role views on one shared live
// order state, client side only. Demo only: no real orders, restaurants,
// drivers, or payments. All prices are planning hypotheses and all figures
// are demo illustrations.

import { useEffect, useState } from "react";

type Role = "customer" | "restaurant" | "driver" | "admin";
type Channel = "CommonTable" | "Direct2Door";
type OrderStatus = "placed" | "preparing" | "ready" | "picked_up" | "delivered";

interface MenuItem {
  id: string;
  name: string;
  note: string;
  price: number;
}

interface OrderItem {
  id: string;
  name: string;
  price: number;
  qty: number;
}

interface Order {
  id: string;
  items: OrderItem[];
  channel: Channel;
  status: OrderStatus;
  foodSubtotal: number;
  deliveryFee: number;
  tax: number;
  tip: number;
  total: number;
  driverPay: number;
  distanceMi: number;
  etaMin: number;
  prepSecondsLeft: number;
  offerAccepted: boolean;
  proofNote: string | null;
}

const MENU: MenuItem[] = [
  { id: "margherita", name: "Margherita Pizza", note: "Tomato, mozzarella, basil", price: 10.8 },
  { id: "alfredo", name: "Pasta Alfredo", note: "Cream sauce, parmesan", price: 12.0 },
  { id: "salad", name: "Garden Salad", note: "Greens, tomato, cucumber", price: 8.25 },
  { id: "garlic-bread", name: "Garlic Bread", note: "Toasted, garlic butter", price: 5.5 },
  { id: "lemonade", name: "Lemonade", note: "Fresh squeezed, served cold", price: 4.0 },
  { id: "tiramisu", name: "Tiramisu", note: "Coffee, mascarpone, cocoa", price: 6.5 },
];

const DELIVERY_FEE = 3.99;
const TAX_RATE = 0.0825;
const DRIVER_PAY = 2.5;
const FULFILLMENT_FEE = 0.75;
const PROCESSING_COST = 0.42;
const SUPPORT_COST = 0.3;
const PREP_SECONDS = 900;
const ROUTE_PATH = "M 44 176 C 100 170, 120 120, 180 116 S 280 84, 312 48";

const TIMELINE_STEPS = [
  "Order placed",
  "Accepted by restaurant",
  "Preparing",
  "Ready for pickup",
  "Picked up",
  "Delivered",
] as const;

const STATUS_LABELS: Record<OrderStatus, string> = {
  placed: "New",
  preparing: "Preparing",
  ready: "Ready",
  picked_up: "Out for delivery",
  delivered: "Delivered",
};

function money(value: number): string {
  return `$${value.toFixed(2)}`;
}

function roundCents(value: number): number {
  return Math.round(value * 100) / 100;
}

function formatClock(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function completedSteps(status: OrderStatus): number {
  switch (status) {
    case "placed":
      return 1;
    case "preparing":
      return 3;
    case "ready":
      return 4;
    case "picked_up":
      return 5;
    case "delivered":
      return 6;
  }
}

function seedOrders(): Order[] {
  return [
    {
      id: "DEMO-101",
      items: [{ id: "margherita", name: "Margherita Pizza", price: 10.8, qty: 1 }],
      channel: "CommonTable",
      status: "placed",
      foodSubtotal: 10.8,
      deliveryFee: DELIVERY_FEE,
      tax: 0.89,
      tip: 3.0,
      total: 18.68,
      driverPay: DRIVER_PAY,
      distanceMi: 2.1,
      etaMin: 12,
      prepSecondsLeft: PREP_SECONDS,
      offerAccepted: false,
      proofNote: null,
    },
  ];
}

function DemoMap({ courierMoving }: { courierMoving: boolean }) {
  return (
    <svg
      className="demo-map"
      viewBox="0 0 360 220"
      role="img"
      aria-label="Demo map showing the driver route from the restaurant to the customer home"
    >
      <rect x="0" y="0" width="360" height="220" rx="12" fill="#eaf5f2" />
      <rect x="20" y="24" width="70" height="48" rx="6" fill="#d8e9e2" />
      <rect x="110" y="20" width="60" height="40" rx="6" fill="#d8e9e2" />
      <rect x="200" y="28" width="80" height="44" rx="6" fill="#d8e9e2" />
      <rect x="24" y="110" width="56" height="40" rx="6" fill="#d8e9e2" />
      <rect x="200" y="140" width="70" height="48" rx="6" fill="#d8e9e2" />
      <rect x="110" y="160" width="60" height="36" rx="6" fill="#d8e9e2" />
      <path
        d="M 0 100 H 360 M 100 0 V 220 M 250 0 V 220 M 0 190 H 360"
        stroke="#ffffff"
        strokeWidth="10"
      />
      <path
        d={ROUTE_PATH}
        fill="none"
        stroke="#14b8a6"
        strokeWidth="4"
        strokeDasharray="8 6"
        strokeLinecap="round"
        className={courierMoving ? "demo-route-drawn" : "demo-route-idle"}
      />
      <g>
        <circle cx="44" cy="176" r="12" fill="#123f2e" />
        <text x="44" y="181" textAnchor="middle" fill="#fdfbf7" fontSize="13">
          R
        </text>
        <text x="44" y="200" textAnchor="middle" fontSize="11" fill="#123f2e">
          Demo restaurant
        </text>
      </g>
      <g>
        <circle cx="312" cy="48" r="12" fill="#0f766e" />
        <text x="312" y="53" textAnchor="middle" fill="#fdfbf7" fontSize="13">
          H
        </text>
        <text x="312" y="28" textAnchor="middle" fontSize="11" fill="#123f2e">
          Customer home
        </text>
      </g>
      {courierMoving ? (
        <g>
          <circle r="10" fill="#0f766e" stroke="#fdfbf7" strokeWidth="2">
            <animateMotion dur="5s" fill="freeze" path={ROUTE_PATH} />
          </circle>
          <circle r="4" fill="#fdfbf7">
            <animateMotion dur="5s" fill="freeze" path={ROUTE_PATH} />
          </circle>
        </g>
      ) : (
        <g>
          <circle cx="44" cy="176" r="10" fill="#0f766e" stroke="#fdfbf7" strokeWidth="2" />
          <circle cx="44" cy="176" r="4" fill="#fdfbf7" />
        </g>
      )}
    </svg>
  );
}

function TrackingTimeline({ order }: { order: Order }) {
  const done = completedSteps(order.status);
  return (
    <ol className="demo-timeline proto-timeline">
      {TIMELINE_STEPS.map((step, index) => (
        <li
          key={step}
          className={
            index < done
              ? "demo-timeline-step proto-timeline-done"
              : "demo-timeline-step proto-timeline-todo"
          }
        >
          <span className="demo-timeline-check" aria-hidden="true">
            {index < done ? "✓" : index + 1}
          </span>
          <span>{step}</span>
        </li>
      ))}
    </ol>
  );
}

function CustomerView({
  orders,
  cart,
  channel,
  tip,
  onAdd,
  onRemove,
  onChannel,
  onTip,
  onPlaceOrder,
}: {
  orders: Order[];
  cart: Record<string, number>;
  channel: Channel;
  tip: number;
  onAdd: (id: string) => void;
  onRemove: (id: string) => void;
  onChannel: (channel: Channel) => void;
  onTip: (tip: number) => void;
  onPlaceOrder: () => void;
}) {
  const cartItems = MENU.filter((item) => (cart[item.id] ?? 0) > 0).map(
    (item) => ({ ...item, qty: cart[item.id] ?? 0 }),
  );
  const foodSubtotal = roundCents(
    cartItems.reduce((sum, item) => sum + item.price * item.qty, 0),
  );
  const tax = roundCents(foodSubtotal * TAX_RATE);
  const total = roundCents(foodSubtotal + DELIVERY_FEE + tax + tip);
  const latestOrder = orders[orders.length - 1] ?? null;

  return (
    <div className="proto-customer">
      <div className="proto-channel-switch" role="group" aria-label="Ordering channel">
        <button
          type="button"
          className={channel === "CommonTable" ? "proto-channel active" : "proto-channel"}
          onClick={() => onChannel("CommonTable")}
        >
          CommonTable app
        </button>
        <button
          type="button"
          className={channel === "Direct2Door" ? "proto-channel active" : "proto-channel"}
          onClick={() => onChannel("Direct2Door")}
        >
          Direct2Door own site
        </button>
      </div>
      <p className="proto-channel-note">
        {channel === "CommonTable"
          ? "You are ordering in the CommonTable app, where many local restaurants are listed in one place."
          : "You are ordering from the restaurant\u2019s own website. Same menu, same drivers, no CommonTable app needed."}
      </p>
      <p className="proto-channel-note">
        The difference is where you order. CommonTable is the app.
        Direct2Door is the restaurant&apos;s own website. Both use the same
        driver network.
      </p>

      <div className="proto-customer-grid">
        <div className="demo-phone proto-phone" aria-label="Demo customer app">
          <div className="demo-phone-notch" />
          <p className="demo-phone-brand">
            {channel === "CommonTable" ? "CommonTable · Demo" : "Direct2Door · Demo"}
          </p>
          <p className="demo-phone-restaurant">
            Demo Restaurant · Denton, TX <span className="demo-tag">Demo</span>
          </p>
          <p className="demo-delivery-choice">
            Delivery: <strong>Standard</strong> · Normal delivery ETA
          </p>
          <ul className="proto-menu">
            {MENU.map((item) => {
              const qty = cart[item.id] ?? 0;
              return (
                <li key={item.id}>
                  <div className="proto-menu-info">
                    <span className="proto-menu-name">{item.name}</span>
                    <span className="proto-menu-note">{item.note}</span>
                  </div>
                  <span className="demo-menu-price">{money(item.price)}</span>
                  <span className="proto-stepper">
                    <button
                      type="button"
                      className="proto-stepper-btn"
                      onClick={() => onRemove(item.id)}
                      disabled={qty === 0}
                      aria-label={`Remove one ${item.name} from the cart`}
                    >
                      −
                    </button>
                    <span className="proto-stepper-qty" aria-label={`${item.name} quantity`}>
                      {qty}
                    </span>
                    <button
                      type="button"
                      className="proto-stepper-btn"
                      onClick={() => onAdd(item.id)}
                      aria-label={`Add one ${item.name} to the cart`}
                    >
                      +
                    </button>
                  </span>
                </li>
              );
            })}
          </ul>

          <h4 className="proto-cart-title">Your cart</h4>
          {cartItems.length === 0 ? (
            <p className="demo-empty">Your cart is empty. Add a dish to start a demo order.</p>
          ) : (
            <ul className="proto-cart-list">
              {cartItems.map((item) => (
                <li key={item.id}>
                  <span>
                    {item.qty} × {item.name}
                  </span>
                  <span>{money(roundCents(item.price * item.qty))}</span>
                </li>
              ))}
            </ul>
          )}

          <dl className="demo-breakdown">
            <div>
              <dt>Food subtotal</dt>
              <dd>{money(foodSubtotal)}</dd>
            </div>
            <div>
              <dt>Delivery fee (Standard)</dt>
              <dd>{money(DELIVERY_FEE)}</dd>
            </div>
            <div>
              <dt>Tax (demo)</dt>
              <dd>{money(tax)}</dd>
            </div>
            <div>
              <dt>Tip (optional, demo)</dt>
              <dd>{money(tip)}</dd>
            </div>
            <div className="demo-total">
              <dt>Total</dt>
              <dd>{money(total)}</dd>
            </div>
          </dl>

          <div className="proto-tip-row" role="group" aria-label="Tip amount">
            {[0, 2, 3, 5].map((value) => (
              <button
                key={value}
                type="button"
                className={tip === value ? "proto-tip active" : "proto-tip"}
                onClick={() => onTip(value)}
              >
                {value === 0 ? "No tip" : money(value)}
              </button>
            ))}
          </div>

          <button
            type="button"
            className="demo-order-button"
            onClick={onPlaceOrder}
            disabled={cartItems.length === 0}
          >
            Place demo order
          </button>
          <p className="demo-mockup-note">
            Demo figures for illustration. No real order is placed and no payment is taken.
          </p>
        </div>

        <div className="proto-tracking">
          <h3>Track your order</h3>
          {latestOrder ? (
            <>
              <p className="proto-tracking-order">
                Order <strong>#{latestOrder.id}</strong> · {STATUS_LABELS[latestOrder.status]}
                {latestOrder.channel === "Direct2Door" ? " · Ordered on the restaurant\u2019s own website" : ""}
              </p>
              <TrackingTimeline order={latestOrder} />
              {latestOrder.status === "delivered" && latestOrder.proofNote ? (
                <p className="proto-proof">{latestOrder.proofNote}</p>
              ) : null}
            </>
          ) : (
            <p className="demo-empty">
              No orders yet. Add items and place a demo order to see tracking here.
            </p>
          )}
          <h4 className="proto-orders-title">Your demo orders</h4>
          {orders.length === 0 ? (
            <p className="demo-empty">No demo orders yet.</p>
          ) : (
            <ul className="proto-order-list">
              {[...orders].reverse().map((order) => (
                <li key={order.id}>
                  <span>
                    <strong>#{order.id}</strong> · {order.items.reduce((n, item) => n + item.qty, 0)} items ·{" "}
                    {order.channel}
                  </span>
                  <span className="proto-order-status">{STATUS_LABELS[order.status]}</span>
                  <span>{money(order.total)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function RestaurantView({
  orders,
  onAccept,
  onReady,
}: {
  orders: Order[];
  onAccept: (id: string) => void;
  onReady: (id: string) => void;
}) {
  const incoming = orders.filter((order) => order.status === "placed");
  const preparing = orders.filter((order) => order.status === "preparing");
  const ready = orders.filter((order) => order.status === "ready");

  return (
    <div className="demo-console proto-console" aria-label="Demo restaurant console">
      <div className="demo-console-header">
        <p>Restaurant console · Demo</p>
        <span className="demo-tag">Demo</span>
      </div>
      <p className="proto-view-note">
        New demo orders land here. Accept an order to start the 15 minute prep timer, then mark it
        ready for driver pickup.
      </p>
      <div className="demo-columns">
        <div className="demo-column">
          <h4>New</h4>
          {incoming.length === 0 ? (
            <p className="demo-empty">No new orders</p>
          ) : (
            incoming.map((order) => (
              <article key={order.id} className="demo-order-card demo-order-card-new">
                <p className="demo-order-id">#{order.id}</p>
                <p>
                  {order.items.reduce((n, item) => n + item.qty, 0)} items · {money(order.foodSubtotal)}{" "}
                  food
                </p>
                <p>
                  {order.items.map((item) => `${item.qty} × ${item.name}`).join(", ")}
                </p>
                <p>Channel: {order.channel}</p>
                <p>Standard delivery</p>
                <button
                  type="button"
                  className="proto-action"
                  onClick={() => onAccept(order.id)}
                >
                  Accept order
                </button>
              </article>
            ))
          )}
        </div>
        <div className="demo-column">
          <h4>Preparing</h4>
          {preparing.length === 0 ? (
            <p className="demo-empty">Nothing preparing</p>
          ) : (
            preparing.map((order) => (
              <article key={order.id} className="demo-order-card demo-order-card-preparing">
                <p className="demo-order-id">#{order.id}</p>
                <p>Accepted ✓ · Prep started</p>
                <p className="demo-prep-timer">
                  Prep time <strong>{formatClock(order.prepSecondsLeft)}</strong>
                </p>
                <div
                  className="demo-prep-bar"
                  role="progressbar"
                  aria-valuenow={Math.round(((PREP_SECONDS - order.prepSecondsLeft) / PREP_SECONDS) * 100)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="Preparation progress"
                >
                  <span
                    style={{
                      width: `${((PREP_SECONDS - order.prepSecondsLeft) / PREP_SECONDS) * 100}%`,
                    }}
                  />
                </div>
                <button
                  type="button"
                  className="proto-action"
                  onClick={() => onReady(order.id)}
                >
                  Mark ready
                </button>
              </article>
            ))
          )}
        </div>
        <div className="demo-column">
          <h4>Ready</h4>
          {ready.length === 0 ? (
            <p className="demo-empty">Nothing ready yet</p>
          ) : (
            ready.map((order) => (
              <article key={order.id} className="demo-order-card">
                <p className="demo-order-id">#{order.id}</p>
                <p>Ready for pickup ✓</p>
                <p>
                  {order.offerAccepted
                    ? "Driver accepted the offer and is on the way."
                    : "Waiting for a driver to accept the offer."}
                </p>
              </article>
            ))
          )}
        </div>
      </div>
      <p className="demo-mockup-note">
        Demo: the restaurant accepts and confirms a prep estimate of 15 minutes.
      </p>
    </div>
  );
}

function DriverView({
  orders,
  onAcceptOffer,
  onPickedUp,
  onDelivered,
}: {
  orders: Order[];
  onAcceptOffer: (id: string) => void;
  onPickedUp: (id: string) => void;
  onDelivered: (id: string) => void;
}) {
  const offers = orders.filter((order) => order.status === "ready" && !order.offerAccepted);
  const accepted = orders.filter((order) => order.status === "ready" && order.offerAccepted);
  const enRoute = orders.filter((order) => order.status === "picked_up");
  const delivered = orders.filter((order) => order.status === "delivered");

  return (
    <div className="proto-driver">
      <div className="demo-console-header">
        <p>Driver app · Demo</p>
        <span className="demo-tag">Demo</span>
      </div>
      <p className="proto-view-note">
        Offers show the route, the distance, the time, and the pay before you accept. Nothing here
        is a real trip or a real payout.
      </p>

      {offers.length === 0 && accepted.length === 0 && enRoute.length === 0 ? (
        <p className="demo-empty">
          No delivery offers right now. Offers appear here when the restaurant marks an order ready.
        </p>
      ) : null}

      {offers.map((order) => (
        <div key={order.id} className="demo-delivery proto-offer-row">
          <DemoMap courierMoving={false} />
          <article className="demo-offer">
            <p className="demo-offer-title">
              Demo delivery offer · #{order.id} <span className="demo-tag">Demo</span>
            </p>
            <dl className="demo-offer-details">
              <div>
                <dt>Stops</dt>
                <dd>1</dd>
              </div>
              <div>
                <dt>Distance (demo)</dt>
                <dd>{order.distanceMi} mi</dd>
              </div>
              <div>
                <dt>Time (demo)</dt>
                <dd>About {order.etaMin} min</dd>
              </div>
              <div>
                <dt>Pay (demo illustration)</dt>
                <dd>{money(order.driverPay)}</dd>
              </div>
            </dl>
            <p className="demo-offer-rule">Route and pay shown before accepting.</p>
            <button
              type="button"
              className="proto-offer-accept"
              onClick={() => onAcceptOffer(order.id)}
            >
              Accept offer
            </button>
          </article>
          <p className="demo-mockup-note">
            Demo figures for illustration. The {money(order.driverPay)} pay figure comes from the
            blueprint planning example and is not a real payout.
          </p>
        </div>
      ))}

      {accepted.map((order) => (
        <div key={order.id} className="demo-delivery proto-offer-row">
          <DemoMap courierMoving={false} />
          <article className="demo-offer">
            <p className="demo-offer-title">
              Offer accepted · #{order.id} <span className="demo-tag">Demo</span>
            </p>
            <p className="demo-offer-state accepted">
              Offer accepted ✓ · Head to the restaurant to pick up.
            </p>
            <button
              type="button"
              className="proto-offer-accept"
              onClick={() => onPickedUp(order.id)}
            >
              Mark picked up
            </button>
          </article>
        </div>
      ))}

      {enRoute.map((order) => (
        <div key={order.id} className="demo-delivery proto-offer-row">
          <DemoMap courierMoving={true} />
          <article className="demo-offer">
            <p className="demo-offer-title">
              En route · #{order.id} <span className="demo-tag">Demo</span>
            </p>
            <p className="demo-offer-state accepted">
              Picked up ✓ · En route to the customer, about {order.etaMin} min.
            </p>
            <button
              type="button"
              className="proto-offer-accept"
              onClick={() => onDelivered(order.id)}
            >
              Mark delivered
            </button>
          </article>
        </div>
      ))}

      {delivered.length > 0 ? (
        <div className="proto-delivered-list">
          <h4>Delivered trips</h4>
          {delivered.map((order) => (
            <article key={order.id} className="demo-proof">
              <p className="demo-proof-title">Delivered ✓ · #{order.id}</p>
              <p>{order.proofNote}</p>
              <p>
                Trip complete. Pay shown for this demo trip: {money(order.driverPay)} (demo
                illustration).
              </p>
            </article>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function AdminView({ orders }: { orders: Order[] }) {
  const delivered = orders.filter((order) => order.status === "delivered");
  const active = orders.filter((order) => order.status !== "delivered");
  const deliveredCount = delivered.length;
  const deliveryRevenue = roundCents(deliveredCount * DELIVERY_FEE);
  const fulfillmentRevenue = roundCents(deliveredCount * FULFILLMENT_FEE);
  const driverCost = roundCents(deliveredCount * DRIVER_PAY);
  const processingCost = roundCents(deliveredCount * PROCESSING_COST);
  const supportCost = roundCents(deliveredCount * SUPPORT_COST);
  const contribution = roundCents(
    deliveryRevenue + fulfillmentRevenue - driverCost - processingCost - supportCost,
  );

  return (
    <div className="proto-admin">
      <div className="demo-console-header">
        <p>Admin control tower · Demo</p>
        <span className="demo-tag">Demo</span>
      </div>

      <div className="proto-stat-strip">
        <div className="proto-stat">
          <span className="proto-stat-number">{orders.length}</span>
          <span className="proto-stat-label">Demo orders</span>
        </div>
        <div className="proto-stat">
          <span className="proto-stat-number">{active.length}</span>
          <span className="proto-stat-label">Active now</span>
        </div>
        <div className="proto-stat">
          <span className="proto-stat-number">{deliveredCount}</span>
          <span className="proto-stat-label">Delivered</span>
        </div>
        <div className="proto-stat">
          <span className="proto-stat-number">{money(contribution)}</span>
          <span className="proto-stat-label">Contribution (demo)</span>
        </div>
      </div>

      <h3 className="proto-section-title">Live orders</h3>
      {orders.length === 0 ? (
        <p className="demo-empty">No demo orders yet.</p>
      ) : (
        <div className="proto-table-wrap">
          <table className="proto-table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Channel</th>
                <th>Items</th>
                <th>Food</th>
                <th>Delivery fee</th>
                <th>Tip</th>
                <th>Total</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id}>
                  <td>#{order.id}</td>
                  <td>{order.channel}</td>
                  <td>{order.items.reduce((n, item) => n + item.qty, 0)}</td>
                  <td>{money(order.foodSubtotal)}</td>
                  <td>{money(order.deliveryFee)}</td>
                  <td>{money(order.tip)}</td>
                  <td>{money(order.total)}</td>
                  <td>{STATUS_LABELS[order.status]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3 className="proto-section-title">Demo ledger</h3>
      {deliveredCount === 0 ? (
        <p className="demo-empty">
          No delivered orders yet. The ledger fills in when a demo order is delivered.
        </p>
      ) : (
        <article className="demo-ledger proto-ledger">
          <p className="demo-ledger-title">
            Delivered orders: {deliveredCount} · Demo economics
          </p>
          <dl className="proto-ledger-lines">
            <div>
              <dt>Delivery revenue ({deliveredCount} × {money(DELIVERY_FEE)})</dt>
              <dd>+{money(deliveryRevenue)}</dd>
            </div>
            <div>
              <dt>Fulfillment fee ({deliveredCount} × {money(FULFILLMENT_FEE)})</dt>
              <dd>+{money(fulfillmentRevenue)}</dd>
            </div>
            <div>
              <dt>Driver allocation ({deliveredCount} × {money(DRIVER_PAY)})</dt>
              <dd>−{money(driverCost)}</dd>
            </div>
            <div>
              <dt>Processing ({deliveredCount} × {money(PROCESSING_COST)})</dt>
              <dd>−{money(processingCost)}</dd>
            </div>
            <div>
              <dt>Support and insurance ({deliveredCount} × {money(SUPPORT_COST)})</dt>
              <dd>−{money(supportCost)}</dd>
            </div>
            <div className="proto-ledger-total">
              <dt>Contribution</dt>
              <dd>
                {contribution >= 0 ? "+" : "−"}
                {money(Math.abs(contribution))}
              </dd>
            </div>
          </dl>
          <p className="demo-ledger-note">
            Demo illustration from the blueprint, not a forecast. Per order, the example is +$3.99
            delivery revenue + $0.75 fulfillment fee, less $2.50 driver allocation, $0.42
            processing, $0.30 support = +$1.52 contribution.
          </p>
        </article>
      )}
    </div>
  );
}

export default function PrototypePage() {
  const [role, setRole] = useState<Role>("customer");
  const [orders, setOrders] = useState<Order[]>(seedOrders);
  const [nextNumber, setNextNumber] = useState(102);
  const [cart, setCart] = useState<Record<string, number>>({});
  const [channel, setChannel] = useState<Channel>("CommonTable");
  const [tip, setTip] = useState(3);

  useEffect(() => {
    const timer = setInterval(() => {
      setOrders((current) =>
        current.map((order) =>
          order.status === "preparing" && order.prepSecondsLeft > 0
            ? { ...order, prepSecondsLeft: order.prepSecondsLeft - 1 }
            : order,
        ),
      );
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const addToCart = (id: string) =>
    setCart((current) => ({ ...current, [id]: (current[id] ?? 0) + 1 }));

  const removeFromCart = (id: string) =>
    setCart((current) => {
      const qty = current[id] ?? 0;
      if (qty <= 1) {
        const next = { ...current };
        delete next[id];
        return next;
      }
      return { ...current, [id]: qty - 1 };
    });

  const placeOrder = () => {
    const items: OrderItem[] = MENU.filter((item) => (cart[item.id] ?? 0) > 0).map((item) => ({
      id: item.id,
      name: item.name,
      price: item.price,
      qty: cart[item.id] ?? 0,
    }));
    if (items.length === 0) return;
    const foodSubtotal = roundCents(
      items.reduce((sum, item) => sum + item.price * item.qty, 0),
    );
    const tax = roundCents(foodSubtotal * TAX_RATE);
    const total = roundCents(foodSubtotal + DELIVERY_FEE + tax + tip);
    const order: Order = {
      id: `DEMO-${nextNumber}`,
      items,
      channel,
      status: "placed",
      foodSubtotal,
      deliveryFee: DELIVERY_FEE,
      tax,
      tip,
      total,
      driverPay: DRIVER_PAY,
      distanceMi: 2.1,
      etaMin: 12,
      prepSecondsLeft: PREP_SECONDS,
      offerAccepted: false,
      proofNote: null,
    };
    setOrders((current) => [...current, order]);
    setNextNumber((n) => n + 1);
    setCart({});
  };

  const updateOrder = (id: string, patch: Partial<Order>) =>
    setOrders((current) =>
      current.map((order) => (order.id === id ? { ...order, ...patch } : order)),
    );

  const resetDemo = () => {
    setOrders(seedOrders());
    setNextNumber(102);
    setCart({});
    setChannel("CommonTable");
    setTip(3);
    setRole("customer");
  };

  const roleTabs: { key: Role; label: string; hint: string }[] = [
    { key: "customer", label: "Customer", hint: "Order and track" },
    { key: "restaurant", label: "Restaurant", hint: "Accept and prepare" },
    { key: "driver", label: "Driver", hint: "Offers and delivery" },
    { key: "admin", label: "Admin", hint: "Orders and ledger" },
  ];

  return (
    <main>
      <header className="topbar">
        <div className="container topbar-inner">
          <a className="wordmark" href="/">
            CommonTable
          </a>
          <nav aria-label="Page sections">
            <a href="/">Home</a>
            <a href="/#how-it-works">How it works</a>
          </nav>
          <span className="status-pill">Prototype · Demo</span>
        </div>
      </header>

      <div className="proto-banner">
        <div className="container">
          <p>
            <strong>Interactive prototype. Demo only.</strong> No real orders, restaurants,
            drivers, or payments.
          </p>
        </div>
      </div>

      <section className="proto-hero">
        <div className="container">
          <h1>Interactive prototype</h1>
          <p className="proto-intro">
            Try the full CommonTable order flow. Place a demo order as a customer, accept it as
            the restaurant, deliver it as the driver, and watch the admin ledger update. Every
            view shares one live order state, and nothing here is real.
          </p>
          <p className="proto-loop-hint">
            One order, four views: Customer places it, Restaurant accepts it, Driver delivers it,
            Admin sees it. A demo order is already waiting for the restaurant.
          </p>
          <button type="button" className="proto-reset" onClick={resetDemo}>
            Reset demo
          </button>
        </div>
      </section>

      <section className="proto-body">
        <div className="container">
          <div className="demo-tabs proto-tabs" role="tablist" aria-label="Prototype roles">
            {roleTabs.map((tab, index) => (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={role === tab.key}
                className={role === tab.key ? "demo-tab active" : "demo-tab"}
                onClick={() => setRole(tab.key)}
              >
                <span className="demo-tab-number">{index + 1}</span>
                <span>
                  <span className="demo-tab-label">{tab.label}</span>
                  <span className="proto-tab-hint">{tab.hint}</span>
                </span>
              </button>
            ))}
          </div>

          <div className="proto-panel" role="tabpanel" aria-label={`${roleTabs.find((t) => t.key === role)?.label} view`}>
            {role === "customer" && (
              <CustomerView
                orders={orders}
                cart={cart}
                channel={channel}
                tip={tip}
                onAdd={addToCart}
                onRemove={removeFromCart}
                onChannel={setChannel}
                onTip={setTip}
                onPlaceOrder={placeOrder}
              />
            )}
            {role === "restaurant" && (
              <RestaurantView
                orders={orders}
                onAccept={(id) => updateOrder(id, { status: "preparing", prepSecondsLeft: PREP_SECONDS })}
                onReady={(id) => updateOrder(id, { status: "ready" })}
              />
            )}
            {role === "driver" && (
              <DriverView
                orders={orders}
                onAcceptOffer={(id) => updateOrder(id, { offerAccepted: true })}
                onPickedUp={(id) => updateOrder(id, { status: "picked_up" })}
                onDelivered={(id) =>
                  updateOrder(id, {
                    status: "delivered",
                    proofNote: "Photo confirmation on file (demo). Order handed to the customer.",
                  })
                }
              />
            )}
            {role === "admin" && <AdminView orders={orders} />}
          </div>

          <p className="proto-footer-note">
            All prices are planning hypotheses and all figures are demo illustrations. This
            prototype runs entirely in your browser: orders exist only in this session, and
            refreshing the page starts the demo over.
          </p>
        </div>
      </section>

      <footer className="footer">
        <div className="container">
          <p className="footer-brand">CommonTable</p>
          <p>
            CommonTable and Direct2Door are working names. They have not been cleared for
            trademark or domain use.
          </p>
          <p>
            This prototype is a demo. No real orders, restaurants, drivers, or payments are
            involved.
          </p>
        </div>
      </footer>
    </main>
  );
}
