// Privacy Policy — what CommonTable collects, why, and what it does
// with it. Working draft pending legal review; see the Terms for the
// matching service rules.

import AppShell from "@/components/AppShell";

export default function PrivacyPage() {
  return (
    <AppShell>
      <h1>Privacy Policy</h1>
      <p className="app-lede">Effective November 14, 2026.</p>
      <p className="app-notice">
        This is a working draft. It will be reviewed by a lawyer before
        CommonTable takes its first real payment.
      </p>

      <h2>What we collect</h2>
      <p>
        <strong>Account information.</strong> When you create an account we
        collect your name, email address, and phone number, and the role you
        sign up for (customer, restaurant, driver).
      </p>
      <p>
        <strong>Order information.</strong> When you order, we collect the
        items you order, the delivery address you give us, any delivery
        instructions, and the order total.
      </p>
      <p>
        <strong>Location.</strong> If you use “Use my current location,” your
        browser shares your approximate location with us once, so we can tell
        whether you are inside the delivery zone. We do not track your
        location in the background.
      </p>
      <p>
        <strong>Restaurant information.</strong> Restaurants that join
        CommonTable give us the owner’s name, business phone, business
        address, and a website or public listing. We use this to verify the
        restaurant is a real operating business before it can take orders.
      </p>
      <p>
        <strong>Driver information.</strong> Drivers give us the details
        needed to assign and track deliveries.
      </p>
      <p>
        <strong>Payment information.</strong> None today. Payments are not
        live yet: no real money moves through CommonTable during the pilot,
        and we do not collect or store card numbers. When payments launch,
        this policy will be updated to describe exactly what is collected
        and who processes it.
      </p>

      <h2>How we use it</h2>
      <p>
        We use your information to run the service: to create and secure your
        account, to place and fulfill orders, to show restaurants and drivers
        the details they need for your order, to verify restaurants, and to
        answer support questions. We do not sell your personal information.
      </p>

      <h2>What we share</h2>
      <p>
        A restaurant sees the orders placed with it, including the customer’s
        name and delivery address. A driver assigned to your delivery sees
        the delivery address and order details. We do not share your
        information with advertisers or data brokers. We may disclose
        information when the law requires it.
      </p>

      <h2>Security</h2>
      <p>
        Passwords are stored hashed, never in plain text. Access to accounts
        is protected by sign-in. No system is perfectly secure, and we cannot
        promise that unauthorized access will never happen, but we take
        reasonable steps to protect your information.
      </p>

      <h2>How long we keep it</h2>
      <p>
        We keep account and order records for as long as your account is
        active and as long as the law requires for business records. You can
        ask us to delete your account and its personal data; order records
        needed for tax or legal reasons may be kept in anonymized form.
      </p>

      <h2>Your choices</h2>
      <p>
        You can update your account details at any time. You can ask us to
        delete your account. You can turn off location sharing in your
        browser; the “Use my current location” feature simply will not work
        without it.
      </p>

      <h2>Children</h2>
      <p>
        CommonTable is for people 18 and older. We do not knowingly collect
        information from children.
      </p>

      <h2>Changes to this policy</h2>
      <p>
        If we change this policy, we will update the effective date above and
        post the new version here. Material changes will be announced in the
        app.
      </p>

      <h2>Contact</h2>
      <p>
        Questions about this policy? A dedicated privacy contact email will
        be published here before public launch. Until then, reach us through
        the support channel in your CommonTable account.
      </p>
    </AppShell>
  );
}
