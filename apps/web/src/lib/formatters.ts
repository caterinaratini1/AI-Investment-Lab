const numberFormatters = new Map<string, Intl.NumberFormat>();

function numberFormatter(currency: string): Intl.NumberFormat {
  const existing = numberFormatters.get(currency);
  if (existing) return existing;
  const formatter = new Intl.NumberFormat("en-IE", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  numberFormatters.set(currency, formatter);
  return formatter;
}

export function formatMoney(value: number | null, currency = "EUR"): string {
  return value === null ? "—" : numberFormatter(currency).format(value);
}

export function formatPercent(value: number | null, digits = 2, signed = true): string {
  if (value === null) return "—";
  return new Intl.NumberFormat("en-IE", {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    signDisplay: signed ? "exceptZero" : "auto",
  }).format(value);
}

export function formatPoints(value: number | null): string {
  if (value === null) return "—";
  const points = value * 100;
  return `${points > 0 ? "+" : ""}${points.toFixed(2)} pp`;
}

export function formatQuantity(value: number): string {
  return new Intl.NumberFormat("en-IE", { maximumFractionDigits: 4 }).format(value);
}

export function formatDate(value: string | null, long = true): string {
  if (!value) return "Awaiting first snapshot";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: long ? "long" : "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}
