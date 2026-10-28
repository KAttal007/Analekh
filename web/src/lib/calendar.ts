export const iso = (d: Date): string => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export const parseIso = (s: string): Date => {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
};

export const addDays = (s: string, n: number): string => {
  const d = parseIso(s);
  d.setDate(d.getDate() + n);
  return iso(d);
};

export const addMonths = (s: string, n: number): string => {
  const d = parseIso(s);
  d.setDate(1); // no 31 Jan + 1 month = 3 Mar
  d.setMonth(d.getMonth() + n);
  return iso(d);
};

export const startOfWeek = (s: string): string => {
  const day = (parseIso(s).getDay() + 6) % 7; // Monday = 0
  return addDays(s, -day);
};

export const daysFrom = (start: string, count: number): string[] => Array.from({ length: count }, (_, i) => addDays(start, i));

export const isWeekend = (s: string): boolean => [0, 6].includes(parseIso(s).getDay());

export function monthGrid(anchor: string): { start: string; end: string; days: string[] } {
  const first = parseIso(anchor);
  first.setDate(1);
  const start = startOfWeek(iso(first));
  const last = new Date(first.getFullYear(), first.getMonth() + 1, 0);
  const end = addDays(startOfWeek(iso(last)), 6);
  const count = Math.round((parseIso(end).getTime() - parseIso(start).getTime()) / 864e5) + 1;
  return { start, end, days: daysFrom(start, count) };
}

const fmt = (opts: Intl.DateTimeFormatOptions) => (s: string) => new Intl.DateTimeFormat("en-IN", opts).format(parseIso(s));
export const weekdayShort = fmt({ weekday: "short" });
export const dayNumber = fmt({ day: "numeric" });
export const monthShort = fmt({ month: "short" });
export const monthLong = fmt({ month: "long", year: "numeric" });
export const dayLong = fmt({ weekday: "long", day: "numeric", month: "long" });
export const rangeLabel = (a: string, b: string): string => `${dayNumber(a)} ${monthShort(a)} – ${dayNumber(b)} ${monthShort(b)}`;
