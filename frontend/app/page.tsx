// CommonTable landing page. Content is grounded in the startup blueprint
// (workspace/user/files/CommonTable_Direct2Door_Startup_Blueprint.docx).
// Live sections (demo menu, restaurants coming soon) fetch from the API
// client-side in ./home-live and link to /order; no checkout happens here.
// Prices are labeled as planning hypotheses, per the blueprint.

import DemoWalkthrough from "./demo";
import HomeLiveSections from "./home-live";

export default function Home() {
  return (
    <main>
      <header className="topbar">
        <div className="container topbar-inner">
          <a className="wordmark" href="#top">
            CommonTable
          </a>
          <nav aria-label="Page sections">
            <a href="#menu">Menu</a>
            <a href="#restaurants">Restaurants</a>
            <a href="#portals">Portals</a>
            <a href="#problem">Problem</a>
            <a href="#concepts">Concepts</a>
            <a href="#delivery">Delivery options</a>
            <a href="#how-it-works">How it works</a>
            <a href="#roadmap">Roadmap</a>
          </nav>
          <span className="status-pill">In development</span>
        </div>
      </header>

      <section className="hero" id="top">
        <div className="container">
          <h1>CommonTable</h1>
          <p className="tagline">
            Restaurant prices. Affordable delivery. One smarter local network.
          </p>
          <p className="intro">
            CommonTable is a local food delivery network in development. It
            brings together customers, independent restaurants, and a shared
            driver network, so delivery costs less and stays fair to everyone
            at the table.
          </p>
          <span className="pilot-badge">
            Now building. Piloting in Denton, TX.
          </span>
          <div className="hero-cta-row">
            <a className="hero-cta" href="/order">
              Order food
            </a>
            <a className="hero-cta hero-cta-secondary" href="/prototype">
              Try the live prototype
            </a>
          </div>
        </div>
      </section>

      <HomeLiveSections />

      <section className="section" id="portals">
        <div className="container">
          <h2>Portals for every role</h2>
          <p className="lede">
            CommonTable is one network with a portal for each side of the
            table. Sign in to open your portal. One account can hold several
            roles.
          </p>
          <div className="card-grid">
            <article className="card">
              <h3>Customer</h3>
              <p>
                Browse menus, place orders, and track delivery live.
              </p>
              <p>
                <a className="section-cta-btn" href="/order">
                  Open the customer portal
                </a>
              </p>
            </article>
            <article className="card">
              <h3>Restaurant</h3>
              <p>
                Manage your menu, receive orders, and run Direct2Door
                delivery from your own site.
              </p>
              <p>
                <a className="section-cta-btn" href="/restaurant">
                  Open the restaurant portal
                </a>
              </p>
            </article>
            <article className="card">
              <h3>Driver</h3>
              <p>
                See assigned deliveries and confirm pickup and delivery.
              </p>
              <p>
                <a className="section-cta-btn" href="/driver">
                  Open the driver portal
                </a>
              </p>
            </article>
            <article className="card">
              <h3>Dispatcher</h3>
              <p>
                Watch live orders, assign drivers, and keep deliveries on
                track.
              </p>
              <p>
                <a className="section-cta-btn" href="/dispatch">
                  Open the dispatch portal
                </a>
              </p>
            </article>
            <article className="card">
              <h3>Admin</h3>
              <p>
                Manage users, roles, restaurants, zones, pricing, and the
                ledger.
              </p>
              <p>
                <a className="section-cta-btn" href="/admin">
                  Open the admin console
                </a>
              </p>
            </article>
          </div>
        </div>
      </section>

      <section className="section" id="problem">
        <div className="container">
          <h2>The problem with delivery today</h2>
          <p className="lede">
            Delivery should be simple: the restaurant&apos;s own price, plus a
            fair and clearly disclosed delivery fee. Today, that is rarely how
            it works.
          </p>
          <div className="card-grid">
            <article className="card">
              <h3>Different prices for the same food</h3>
              <p>
                Third party marketplaces can show different menu prices or
                fees than a restaurant&apos;s direct channel, so the same meal
                can cost more depending on where you order it.
              </p>
            </article>
            <article className="card">
              <h3>Delivery is often missing</h3>
              <p>
                Customers who prefer ordering direct often find pickup is the
                only option, even when they would gladly pay a fair delivery
                fee.
              </p>
            </article>
            <article className="card">
              <h3>Too small to run a fleet</h3>
              <p>
                Independent restaurants may not have enough order volume to
                justify their own drivers, vehicles, and delivery operations.
              </p>
            </article>
            <article className="card">
              <h3>One driver per order is expensive</h3>
              <p>
                Sending one driver for one order is expensive when orders are
                close together and demand is predictable. Pooling compatible
                deliveries can bring the cost down.
              </p>
            </article>
          </div>
        </div>
      </section>

      <section className="section tint" id="concepts">
        <div className="container">
          <h2>One network, two ways to order</h2>
          <p className="lede">
            CommonTable and Direct2Door are not two separate services. They
            are two ways to order from the same shared local driver network.
            The only difference is where you order.
          </p>
          <div className="concept-grid">
            <article className="concept platform">
              <h3>CommonTable</h3>
              <p className="role">The platform</p>
              <p>
                The customer app and the operating network behind it,
                connecting restaurants, drivers, and customers in one local
                system.
              </p>
              <ul>
                <li>Customer app</li>
                <li>Restaurant network</li>
                <li>Shared driver network</li>
                <li>Dispatch engine</li>
                <li>Payments and tracking</li>
                <li>Reporting and local delivery programs</li>
              </ul>
            </article>
            <article className="concept service">
              <h3>Direct2Door</h3>
              <p className="role">The service</p>
              <p>
                Delivery embedded in a participating restaurant&apos;s own
                website or direct ordering channel, at the restaurant&apos;s
                direct menu prices.
              </p>
              <ul>
                <li>Orders placed on the restaurant&apos;s own site</li>
                <li>Restaurant keeps its menu pricing and brand</li>
                <li>Restaurant keeps the direct customer relationship</li>
                <li>Delivery fulfilled by the CommonTable driver network</li>
              </ul>
            </article>
          </div>
          <table className="concept-compare">
            <thead>
              <tr>
                <th></th>
                <th>CommonTable</th>
                <th>Direct2Door</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th>Where you order</th>
                <td>In the CommonTable app</td>
                <td>On the restaurant&apos;s own website</td>
              </tr>
              <tr>
                <th>What you see</th>
                <td>Many local restaurants in one place</td>
                <td>One restaurant, its own channel</td>
              </tr>
              <tr>
                <th>Whose brand you see</th>
                <td>CommonTable</td>
                <td>The restaurant&apos;s</td>
              </tr>
              <tr>
                <th>Who delivers</th>
                <td>The shared CommonTable driver network</td>
                <td>The same shared driver network</td>
              </tr>
              <tr>
                <th>What the restaurant keeps</th>
                <td>Its menu pricing and brand</td>
                <td>
                  Its menu pricing, brand, and direct customer relationship
                </td>
              </tr>
            </tbody>
          </table>
          <p className="concept-summary">
            Short version: CommonTable is the app for ordering from many
            local restaurants. Direct2Door is delivery from one
            restaurant&apos;s own website. Same drivers either way.
          </p>
        </div>
      </section>

      <section className="section" id="delivery">
        <div className="container">
          <h2>Delivery options</h2>
          <p className="lede">
            Customers choose the speed and price that fit the moment. Saver
            keeps costs low by pooling compatible orders. Express never waits
            for a batch.
          </p>
          <div className="price-grid">
            <article className="price-card">
              <h3>Saver</h3>
              <p className="price">$1.99 to $2.49</p>
              <p>
                Flexible delivery window. Compatible orders are pooled, and
                orders are held only within the disclosed window.
              </p>
            </article>
            <article className="price-card">
              <h3>Standard</h3>
              <p className="price">$3.49 to $4.99</p>
              <p>
                Normal delivery ETA. Pooling is used only when it does not
                break the promised delivery time.
              </p>
            </article>
            <article className="price-card">
              <h3>Express</h3>
              <p className="price">$5.99 to $8.99</p>
              <p>
                Priority delivery, usually a single order or a priority route.
                No forced batching, and an Express order is never delayed to
                create a batch.
              </p>
            </article>
            <article className="price-card">
              <h3>Group / office</h3>
              <p className="price">$1 to $2 per order</p>
              <p>
                Shared destination. Orders are consolidated to a designated
                drop off point, for apartments, offices, and campuses.
              </p>
            </article>
          </div>
          <p className="hypothesis-note">
            <strong>Planning hypotheses, not final prices.</strong> The prices
            above are hypotheses for customer research. Actual pricing will
            reflect local driver pay, distance, time, insurance, payment
            costs, refunds, and demand.
          </p>
        </div>
      </section>

      <section className="section tint" id="how-it-works">
        <div className="container">
          <h2>How it works</h2>
          <p className="lede">
            Transparent pricing from the start: the restaurant&apos;s agreed
            direct menu price, with the delivery fee, tax, and optional tip
            disclosed before checkout.
          </p>
          <DemoWalkthrough />
          <p className="prototype-cta-wrap">
            <a className="prototype-cta" href="/prototype">
              Try the live prototype
            </a>
            <span>
              Place a demo order and follow it through every role: customer,
              restaurant, driver, and admin.
            </span>
          </p>
          <div className="how-grid">
            <div className="how-block">
              <h3>For customers</h3>
              <ol className="steps">
                <li>
                  Enter your address and see eligible restaurants near you.
                </li>
                <li>Pick a restaurant and choose your items and modifiers.</li>
                <li>
                  Choose a delivery option: Saver, Standard, Express, or
                  pickup where offered.
                </li>
                <li>
                  Check out with a transparent total: food subtotal, delivery
                  fee, tax, optional tip, and total.
                </li>
                <li>
                  Track your order with status updates from acceptance to
                  delivery.
                </li>
              </ol>
            </div>
            <div className="how-block">
              <h3>For restaurants</h3>
              <ol className="steps">
                <li>
                  Offer delivery without building an in house driver fleet.
                </li>
                <li>
                  Keep control of menu pricing, brand, and the direct customer
                  relationship.
                </li>
                <li>
                  Receive orders through a website integration, a POS
                  connection, or a simple dashboard.
                </li>
                <li>
                  Confirm prep time, mark orders ready, and see order volume
                  and delivery quality reports.
                </li>
              </ol>
            </div>
          </div>
        </div>
      </section>

      <section className="pilot" id="pilot">
        <div className="container">
          <h2>Now building. Piloting in Denton, TX.</h2>
          <p>
            Denton is the confirmed pilot zone. The first release focuses on
            one compact zone and a limited number of restaurants, so the team
            can prove reliable fulfillment and fair route economics before
            expanding.
          </p>
        </div>
      </section>

      <section className="section" id="roadmap">
        <div className="container">
          <h2>Roadmap</h2>
          <p className="lede">
            The plan moves in five phases, from discovery to a controlled
            pilot, expanding only when service quality and unit economics
            hold.
          </p>
          <ol className="roadmap">
            <li>
              <span className="phase">1. Discovery</span>
              <span className="timing">Weeks 1 to 2</span>
              <p className="work">
                Interview restaurants, customers, drivers, and property
                managers, and map direct order workflows.
              </p>
            </li>
            <li>
              <span className="phase">2. Partner commitments</span>
              <span className="timing">Weeks 3 to 4</span>
              <p className="work">
                Sign pilot restaurants and define menu parity, fulfillment
                fees, prep signals, and support rules.
              </p>
            </li>
            <li>
              <span className="phase">3. MVP build</span>
              <span className="timing">Weeks 5 to 10</span>
              <p className="work">
                Build ordering, the restaurant dashboard, the driver workflow,
                the admin console, and basic dispatch.
              </p>
            </li>
            <li>
              <span className="phase">4. Controlled pilot</span>
              <span className="timing">Weeks 11 to 12</span>
              <p className="work">
                Run limited hours in a small zone and measure actual route
                costs and the customer experience.
              </p>
            </li>
            <li>
              <span className="phase">5. Improve and expand</span>
              <span className="timing">Months 4 to 6</span>
              <p className="work">
                Tune pricing, batching, staffing, integrations, and partner
                channels, and expand only when service quality and unit
                economics hold.
              </p>
            </li>
          </ol>
        </div>
      </section>

      <footer className="footer">
        <div className="container">
          <p className="footer-brand">CommonTable</p>
          <p>
            CommonTable and Direct2Door are working names. They have not been
            cleared for trademark or domain use.
          </p>
          <p>
            CommonTable is in development. Prices on this page are planning
            hypotheses, not final prices.
          </p>
        </div>
      </footer>
    </main>
  );
}
