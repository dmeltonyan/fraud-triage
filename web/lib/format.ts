// Formatting shared by every page.

const CATEGORY_NAMES: Record<string, string> = {
  entertainment: "Entertainment",
  food_dining: "Food and dining",
  gas_transport: "Gas and transport",
  grocery_net: "Online grocery",
  grocery_pos: "In-store grocery",
  health_fitness: "Health and fitness",
  home: "Home",
  kids_pets: "Kids and pets",
  misc_net: "Online miscellaneous",
  misc_pos: "In-store miscellaneous",
  personal_care: "Personal care",
  shopping_net: "Online shopping",
  shopping_pos: "In-store shopping",
  travel: "Travel",
};

export function categoryName(category: string): string {
  return CATEGORY_NAMES[category] ?? category;
}

const dollars = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export function money(value: number): string {
  return dollars.format(value);
}

const wholeDollars = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

/** Rounded to the dollar, for headline figures. */
export function wholeMoney(value: number): string {
  return wholeDollars.format(value);
}

export function percent(probability: number): string {
  return `${(probability * 100).toFixed(probability < 0.1 ? 1 : 0)}%`;
}

// Timestamps from the API have no time zone: show them exactly as recorded.
export function timeOfDay(timestamp: string): string {
  return timestamp.slice(11, 16); // "2020-12-24T21:56:57" -> "21:56"
}

export function dateTime(timestamp: string): string {
  return `${timestamp.slice(0, 10)} ${timestamp.slice(11, 16)}`;
}
