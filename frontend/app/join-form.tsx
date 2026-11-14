// Restaurant signup form on the landing page, in the style of the
// reference merchant site. No invented claims: no earnings estimate and
// no commission offer, because neither has been decided. On submit the
// details are saved as a lead and the visitor continues to account
// creation with the restaurant role preselected; the restaurant setup
// form prefills from the lead.

"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { saveRestaurantLead } from "@/lib/restaurant-lead";

const BUSINESS_TYPES = [
  "Restaurant",
  "Food Truck",
  "Bakery",
  "Cafe",
  "Grocery",
  "Other",
];

export default function JoinForm() {
  const { user } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [businessType, setBusinessType] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    saveRestaurantLead({
      name: name.trim(),
      address: address.trim(),
      email: email.trim(),
      phone: phone.trim(),
      businessType,
    });
    if (user) {
      router.push("/restaurant");
    } else {
      router.push("/register?role=restaurant_owner");
    }
  }

  return (
    <div className="lp-join" id="join">
      <h2>Join the Denton pilot</h2>
      <p className="lp-join-lede">
        Your restaurant, your menu prices, one clear delivery fee. We verify
        every restaurant before it can take orders.
      </p>
      <form onSubmit={handleSubmit}>
        <label className="lp-field">
          <span className="app-visually-hidden">Store name</span>
          <input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Store name"
          />
        </label>
        <label className="lp-field lp-address-field">
          <span className="app-visually-hidden">Store address</span>
          <span className="lp-pin" aria-hidden="true">
            📍
          </span>
          <input
            type="text"
            required
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="Store address"
          />
        </label>
        <div className="lp-join-row">
          <label className="lp-field">
            <span className="app-visually-hidden">Email Address</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email Address"
            />
          </label>
          <label className="lp-field">
            <span className="app-visually-hidden">Store phone</span>
            <input
              type="tel"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="Store phone"
            />
          </label>
        </div>
        <label className="lp-field lp-select-field">
          <span className="app-visually-hidden">Business type</span>
          <select
            required
            value={businessType}
            onChange={(e) => setBusinessType(e.target.value)}
          >
            <option value="" disabled>
              Select your business type
            </option>
            {BUSINESS_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <span className="lp-chevron" aria-hidden="true">
            ▾
          </span>
        </label>
        <p className="lp-consent">
          By clicking &ldquo;Get started,&rdquo; I agree to be contacted by
          CommonTable about joining the pilot.
        </p>
        <button type="submit" className="lp-submit">
          Get started
        </button>
      </form>
    </div>
  );
}
