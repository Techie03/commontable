"use client";

// Interactive "How it works" demo for the CommonTable landing page.
// Demo/showcase only: no ordering, account, or payment functionality.
// All copy and figures come from the startup blueprint; every price is
// labeled a hypothesis and every figure is labeled a demo illustration.

import { useEffect, useRef, useState } from "react";

const STAGE_LABELS = [
  "Customer orders",
  "Restaurant accepts",
  "Driver delivers",
  "Delivered",
] as const;

const STAGE_DESCRIPTIONS = [
  "A customer browses a demo menu, adds items, and checks out with every fee disclosed before paying.",
  "The demo restaurant accepts the order, confirms a prep estimate, and starts preparing.",
  "Dispatch sends a clear offer first. The driver sees the route and the pay before accepting, then picks up and delivers.",
  "The order is delivered with proof of delivery, and the demo ledger records the contribution.",
] as const;

type RoleState = "idle" | "active" | "done";

const ROLE_PANELS: {
  role: string;
  status: string;
  state: RoleState;
}[][] = [
  [
    { role: "Customer", status: "Browsing the menu", state: "active" },
    { role: "Restaurant", status: "Waiting for orders", state: "idle" },
    { role: "Driver", status: "Available, no offers yet", state: "idle" },
    { role: "Admin", status: "No active orders", state: "idle" },
  ],
  [
    {
      role: "Customer",
      status: "Order placed, waiting for confirmation",
      state: "active",
    },
    {
      role: "Restaurant",
      status: "Order #DEMO-101, accepted, preparing",
      state: "active",
    },
    {
      role: "Driver",
      status: "Offer incoming, route and pay shown first",
      state: "idle",
    },
    { role: "Admin", status: "Order received, dispatch pending", state: "active" },
  ],
  [
    { role: "Customer", status: "On the way, live tracking", state: "active" },
    { role: "Restaurant", status: "Order ready, handed to driver", state: "done" },
    { role: "Driver", status: "Picked up, en route to customer", state: "active" },
    { role: "Admin", status: "Route active, driver en route", state: "active" },
  ],
  [
    { role: "Customer", status: "Delivered, rate your order", state: "done" },
    { role: "Restaurant", status: "Order completed", state: "done" },
    { role: "Driver", status: "Delivered, trip complete", state: "done" },
    {
      role: "Admin",
      status: "Ledger updated, contribution +$1.52 (demo)",
      state: "done",
    },
  ],
];

const TIMELINE_STEPS = [
  "Order placed",
  "Accepted by restaurant",
  "Preparing",
  "Picked up",
  "Delivered",
] as const;

const ROUTE_PATH =
  "M 44 176 C 100 170, 120 120, 180 116 S 280 84, 312 48";

function formatClock(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function StageZero({ onPlaceOrder }: { onPlaceOrder: () => void }) {
  return (
    <div className="demo-phone" aria-label="Demo phone showing a customer order">
      <div className="demo-phone-notch" />
      <p className="demo-phone-brand">CommonTable · Demo</p>
      <p className="demo-phone-restaurant">
        Demo Restaurant · Denton, TX <span className="demo-tag">Demo</span>
      </p>
      <ul className="demo-menu">
        <li>
          <span>Margherita Pizza</span>
          <span className="demo-menu-price">$14.00</span>
          <span className="demo-added">Added ✓</span>
        </li>
        <li>
          <span>Pasta Alfredo</span>
          <span className="demo-menu-price">$12.00</span>
          <span className="demo-added">Added ✓</span>
        </li>
        <li>
          <span>Lemonade</span>
          <span className="demo-menu-price">$4.00</span>
          <span className="demo-added">Added ✓</span>
        </li>
      </ul>
      <p className="demo-delivery-choice">
        Delivery: <strong>Standard</strong> · Normal delivery ETA
      </p>
      <dl className="demo-breakdown">
        <div>
          <dt>Food subtotal</dt>
          <dd>$30.00</dd>
        </div>
        <div>
          <dt>Delivery fee (Standard)</dt>
          <dd>$3.99</dd>
        </div>
        <div>
          <dt>Tax (demo)</dt>
          <dd>$2.48</dd>
        </div>
        <div>
          <dt>Tip (optional, demo)</dt>
          <dd>$3.00</dd>
        </div>
        <div className="demo-total">
          <dt>Total</dt>
          <dd>$39.47</dd>
        </div>
      </dl>
      <button
        type="button"
        className="demo-order-button"
        onClick={onPlaceOrder}
      >
        Place demo order
      </button>
      <p className="demo-mockup-note">
        Demo figures for illustration. No real order is placed.
      </p>
    </div>
  );
}

function StageOne({
  accepted,
  prepSeconds,
}: {
  accepted: boolean;
  prepSeconds: number;
}) {
  return (
    <div
      className="demo-console"
      aria-label="Demo restaurant console showing order acceptance"
    >
      <div className="demo-console-header">
        <p>Restaurant console · Demo</p>
        <span className="demo-tag">Demo</span>
      </div>
      <div className="demo-columns">
        <div className="demo-column">
          <h4>New</h4>
          {!accepted ? (
            <article className="demo-order-card demo-order-card-new">
              <p className="demo-order-id">#DEMO-101</p>
              <p>3 items · $30.00 food</p>
              <p>Standard delivery</p>
              <p className="demo-order-cta">Reviewing order…</p>
            </article>
          ) : (
            <p className="demo-empty">No new orders</p>
          )}
        </div>
        <div className="demo-column">
          <h4>Preparing</h4>
          {accepted ? (
            <article className="demo-order-card demo-order-card-preparing">
              <p className="demo-order-id">#DEMO-101</p>
              <p>Accepted ✓ · Prep started</p>
              <p className="demo-prep-timer">
                Prep time <strong>{formatClock(prepSeconds)}</strong>
              </p>
              <div
                className="demo-prep-bar"
                role="progressbar"
                aria-valuenow={Math.round(
                  ((900 - prepSeconds) / 900) * 100,
                )}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Preparation progress"
              >
                <span
                  style={{
                    width: `${((900 - prepSeconds) / 900) * 100}%`,
                  }}
                />
              </div>
            </article>
          ) : (
            <p className="demo-empty">Waiting for acceptance</p>
          )}
        </div>
        <div className="demo-column">
          <h4>Ready</h4>
          <p className="demo-empty">Nothing ready yet</p>
        </div>
      </div>
      <p className="demo-mockup-note">
        Demo: the restaurant accepts and confirms a prep estimate of 15
        minutes.
      </p>
    </div>
  );
}

function StageTwo({ offerAccepted }: { offerAccepted: boolean }) {
  return (
    <div className="demo-delivery" aria-label="Demo driver map and offer">
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
          className={offerAccepted ? "demo-route-drawn" : "demo-route-idle"}
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
        {offerAccepted ? (
          <g>
            <circle r="10" fill="#0f766e" stroke="#fdfbf7" strokeWidth="2">
              <animateMotion
                dur="5s"
                fill="freeze"
                path={ROUTE_PATH}
              />
            </circle>
            <circle r="4" fill="#fdfbf7">
              <animateMotion
                dur="5s"
                fill="freeze"
                path={ROUTE_PATH}
              />
            </circle>
          </g>
        ) : (
          <g>
            <circle cx="44" cy="176" r="10" fill="#0f766e" stroke="#fdfbf7" strokeWidth="2" />
            <circle cx="44" cy="176" r="4" fill="#fdfbf7" />
          </g>
        )}
      </svg>
      <article className="demo-offer">
        <p className="demo-offer-title">
          Demo delivery offer <span className="demo-tag">Demo</span>
        </p>
        <dl className="demo-offer-details">
          <div>
            <dt>Stops</dt>
            <dd>1</dd>
          </div>
          <div>
            <dt>Distance (demo)</dt>
            <dd>2.1 mi</dd>
          </div>
          <div>
            <dt>Time (demo)</dt>
            <dd>About 12 min</dd>
          </div>
          <div>
            <dt>Pay (demo illustration)</dt>
            <dd>$2.50</dd>
          </div>
        </dl>
        <p className="demo-offer-rule">
          Route and pay shown before accepting.
        </p>
        <p className={offerAccepted ? "demo-offer-state accepted" : "demo-offer-state"}>
          {offerAccepted
            ? "Offer accepted ✓ · Picked up, en route to customer"
            : "Reviewing offer…"}
        </p>
      </article>
      <p className="demo-mockup-note">
        Demo figures for illustration. The $2.50 pay figure comes from the
        blueprint planning example and is not a real payout.
      </p>
    </div>
  );
}

function StageThree() {
  return (
    <div
      className="demo-delivered"
      aria-label="Demo delivery confirmation and ledger"
    >
      <ol className="demo-timeline">
        {TIMELINE_STEPS.map((step, index) => (
          <li
            key={step}
            className="demo-timeline-step"
            style={{ animationDelay: `${index * 0.35}s` }}
          >
            <span className="demo-timeline-check" aria-hidden="true">
              ✓
            </span>
            <span>{step}</span>
          </li>
        ))}
      </ol>
      <article className="demo-proof">
        <p className="demo-proof-title">Delivered ✓</p>
        <p>Photo confirmation on file (demo).</p>
        <p>The customer can rate the experience and contact support.</p>
      </article>
      <article className="demo-ledger">
        <p className="demo-ledger-title">Demo ledger</p>
        <p>
          +$3.99 delivery revenue + $0.75 fulfillment fee, less $2.50 driver
          allocation, $0.42 processing, $0.30 support ={" "}
          <strong>+$1.52 contribution</strong>.
        </p>
        <p className="demo-ledger-note">
          Demo illustration from the blueprint, not a forecast.
        </p>
      </article>
    </div>
  );
}

function JourneyVideo() {
  const [videoReady, setVideoReady] = useState(false);
  return (
    <figure className="demo-video-block">
      <figcaption>
        <strong>Watch the journey at a glance.</strong> A courier follows the
        route from a neighborhood restaurant to a customer home. Demo
        animation: no real orders, restaurants, or drivers.
      </figcaption>
      <div className="demo-video-frame">
        <div className="demo-video-fallback" aria-hidden="true">
          <svg viewBox="0 0 360 120" role="img">
            <rect x="0" y="0" width="360" height="120" rx="10" fill="#0b2b1f" />
            <path
              d="M 30 90 C 110 90, 130 40, 200 40 S 300 60, 330 30"
              fill="none"
              stroke="#14b8a6"
              strokeWidth="3"
              strokeDasharray="7 6"
              strokeLinecap="round"
            />
            <circle cx="30" cy="90" r="8" fill="#fdfbf7" />
            <circle cx="330" cy="30" r="8" fill="#14b8a6" />
            <circle r="7" fill="#fdfbf7">
              <animateMotion
                dur="4s"
                repeatCount="indefinite"
                path="M 30 90 C 110 90, 130 40, 200 40 S 300 60, 330 30"
              />
            </circle>
          </svg>
          <p>Restaurant → Home · Demo route animation</p>
        </div>
        <video
          className={videoReady ? "demo-video ready" : "demo-video"}
          src="/demo-journey.mp4"
          controls
          muted
          loop
          playsInline
          preload="metadata"
          aria-label="Demo animation of a courier delivering an order"
          onCanPlay={() => setVideoReady(true)}
          onError={() => setVideoReady(false)}
        />
      </div>
    </figure>
  );
}

export default function DemoWalkthrough() {
  const [stage, setStage] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [offerAccepted, setOfferAccepted] = useState(false);
  const [prepSeconds, setPrepSeconds] = useState(900);
  const stageRef = useRef(0);
  stageRef.current = stage;

  useEffect(() => {
    if (!playing) return;
    const timer = setTimeout(() => {
      if (stageRef.current < STAGE_LABELS.length - 1) {
        setStage(stageRef.current + 1);
      } else {
        setPlaying(false);
      }
    }, 6000);
    return () => clearTimeout(timer);
  }, [playing, stage]);

  useEffect(() => {
    setAccepted(false);
    setOfferAccepted(false);
    setPrepSeconds(900);
    if (stage === 1) {
      const timer = setTimeout(() => setAccepted(true), 1200);
      return () => clearTimeout(timer);
    }
    if (stage === 2) {
      const timer = setTimeout(() => setOfferAccepted(true), 1500);
      return () => clearTimeout(timer);
    }
  }, [stage]);

  useEffect(() => {
    if (stage !== 1 || !accepted) return;
    const timer = setInterval(() => {
      setPrepSeconds((value) => (value > 0 ? value - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [stage, accepted]);

  const goToStage = (index: number) => {
    setPlaying(false);
    setStage(index);
  };

  const togglePlay = () => {
    if (!playing && stage === STAGE_LABELS.length - 1) {
      setStage(0);
      setPlaying(true);
      return;
    }
    setPlaying((value) => !value);
  };

  return (
    <div className="demo-walkthrough">
      <div className="demo-intro">
        <h3>Try the demo: one order, four views</h3>
        <p>
          Follow a single demo order from checkout to delivery. Press play and
          the walkthrough advances on its own, or tap any stage to jump to it.
        </p>
        <p className="demo-disclaimer">
          Interactive demo: no real orders are placed. All prices are planning
          hypotheses and all figures are demo illustrations.
        </p>
      </div>

      <div className="demo-tabs" role="tablist" aria-label="Demo stages">
        {STAGE_LABELS.map((label, index) => (
          <button
            key={label}
            type="button"
            role="tab"
            aria-selected={stage === index}
            className={stage === index ? "demo-tab active" : "demo-tab"}
            onClick={() => goToStage(index)}
          >
            <span className="demo-tab-number">{index + 1}</span>
            <span className="demo-tab-label">{label}</span>
          </button>
        ))}
      </div>

      <div className="demo-controls">
        <button
          type="button"
          className="demo-play-button"
          onClick={togglePlay}
          aria-label={
            playing
              ? "Pause the demo walkthrough"
              : stage === STAGE_LABELS.length - 1
                ? "Replay the demo walkthrough"
                : "Play the demo walkthrough"
          }
        >
          {playing
            ? "❚❚ Pause"
            : stage === STAGE_LABELS.length - 1
              ? "↻ Replay"
              : "▶ Play"}
        </button>
        <div
          className="demo-progress"
          role="progressbar"
          aria-valuenow={stage + 1}
          aria-valuemin={1}
          aria-valuemax={STAGE_LABELS.length}
          aria-label={`Demo stage ${stage + 1} of ${STAGE_LABELS.length}`}
        >
          <span
            style={{
              width: `${((stage + 1) / STAGE_LABELS.length) * 100}%`,
            }}
          />
        </div>
        <p className="demo-stage-counter">
          Stage {stage + 1} of {STAGE_LABELS.length}
        </p>
      </div>

      <p className="demo-stage-description">{STAGE_DESCRIPTIONS[stage]}</p>

      <div className="demo-stage-layout">
        <div
          className="demo-stage-panel"
          key={stage}
          role="tabpanel"
          aria-label={STAGE_LABELS[stage]}
        >
          {stage === 0 && (
            <StageZero onPlaceOrder={() => goToStage(1)} />
          )}
          {stage === 1 && (
            <StageOne accepted={accepted} prepSeconds={prepSeconds} />
          )}
          {stage === 2 && <StageTwo offerAccepted={offerAccepted} />}
          {stage === 3 && <StageThree />}
        </div>

        <aside
          className="demo-roles"
          aria-label="Live status for each role in the demo"
        >
          <h4>Live status</h4>
          <ul>
            {ROLE_PANELS[stage].map((panel) => (
              <li key={panel.role} className={`demo-role demo-role-${panel.state}`}>
                <span
                  className="demo-role-dot"
                  aria-hidden="true"
                />
                <span className="demo-role-name">{panel.role}</span>
                <span className="demo-role-status">{panel.status}</span>
              </li>
            ))}
          </ul>
        </aside>
      </div>

      <JourneyVideo />
    </div>
  );
}
