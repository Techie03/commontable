// Restaurant lead captured by the landing-page signup form. Kept in
// localStorage so it survives the account-creation step: the restaurant
// setup form prefills from it, and it is cleared once the restaurant is
// created.

export const RESTAURANT_LEAD_KEY = "commontable-restaurant-lead";

export interface RestaurantLead {
  name: string;
  address: string;
  email: string;
  phone: string;
  businessType: string;
}

export function saveRestaurantLead(lead: RestaurantLead): void {
  try {
    window.localStorage.setItem(RESTAURANT_LEAD_KEY, JSON.stringify(lead));
  } catch {
    // ignore
  }
}

export function readRestaurantLead(): RestaurantLead | null {
  try {
    const raw = window.localStorage.getItem(RESTAURANT_LEAD_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<RestaurantLead>;
    if (typeof parsed.name !== "string") return null;
    return {
      name: parsed.name ?? "",
      address: typeof parsed.address === "string" ? parsed.address : "",
      email: typeof parsed.email === "string" ? parsed.email : "",
      phone: typeof parsed.phone === "string" ? parsed.phone : "",
      businessType:
        typeof parsed.businessType === "string" ? parsed.businessType : "",
    };
  } catch {
    return null;
  }
}

export function clearRestaurantLead(): void {
  try {
    window.localStorage.removeItem(RESTAURANT_LEAD_KEY);
  } catch {
    // ignore
  }
}
