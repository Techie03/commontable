// Money helpers. The API contract uses integer cents everywhere
// (field names ending in _cents). No floats for money.

export function formatCents(
  cents: number | null | undefined,
  currency = "USD"
): string {
  if (cents == null || Number.isNaN(cents)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(cents / 100);
}

/** Parse a dollar amount typed into a form field into integer cents. */
export function dollarsToCents(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const n = Number.parseFloat(trimmed);
  if (Number.isNaN(n) || n < 0) return null;
  return Math.round(n * 100);
}

/** Format integer cents as a plain dollar amount for an input field. */
export function centsToDollarsInput(cents: number | null | undefined): string {
  if (cents == null || Number.isNaN(cents)) return "";
  return (cents / 100).toFixed(2);
}
