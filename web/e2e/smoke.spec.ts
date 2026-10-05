import { expect, test } from "@playwright/test";

// A day with review cases in the demo data.
const DAY = "2020-12-24";

test("every page loads with the banner and navigation", async ({ page }) => {
  for (const path of ["/", "/results"]) {
    await page.goto(path);
    await expect(page.getByText("Simulated data. Decisions here are for demonstration only.")).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
  }
  // Wait for the page's own content, as a person would, so the click isn't lost
  // while the page's JavaScript is still starting up.
  await expect(page.getByRole("heading", { name: "Results", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Review queue" }).click();
  await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible();
  await page.getByRole("link", { name: "Results" }).click();
  await expect(page.getByRole("heading", { name: "Results", exact: true })).toBeVisible();
});

test("queue lists a day's cases, as a table on desktop and cards on a phone", async ({ page, isMobile }) => {
  await page.goto(`/?date=${DAY}`);
  await expect(page.getByText(/\d+ cases? \(daily budget 30\)/)).toBeVisible();
  if (isMobile) {
    await expect(page.locator("table")).toBeHidden();
    await expect(page.locator("ul li a[href^='/case/']").first()).toBeVisible();
  } else {
    await expect(page.locator("table")).toBeVisible();
    await expect(page.locator("tbody tr").first()).toBeVisible();
  }
});

test("changing the date loads that day", async ({ page }) => {
  await page.goto(`/?date=${DAY}`);
  await expect(page.getByText(/\d+ cases? \(daily budget 30\)/)).toBeVisible(); // first day loaded
  await page.getByLabel("Day").fill("2020-11-15");
  await expect(page).toHaveURL(/date=2020-11-15/);
  await expect(page.getByText(/\d+ cases? \(daily budget 30\)|No review cases on 2020-11-15/)).toBeVisible();
});

test("review one case end to end", async ({ page }) => {
  await page.goto(`/?date=${DAY}`);
  await page.locator("a[href^='/case/']:visible").first().click();

  await expect(page.getByRole("heading", { name: "Why the model scored it this way" })).toBeVisible();
  await expect(page.locator("ol li")).toHaveCount(3);
  await expect(page.getByText("Expected cost of each action")).toBeVisible();
  await expect(page.getByText("(chosen)")).toBeVisible();

  await page.getByLabel("Note (optional)").fill("Playwright smoke test");
  await page.getByRole("button", { name: "Confirm fraud" }).click();
  await expect(page.getByText(/This transaction was actually (fraud|legitimate)\./)).toBeVisible();
  await expect(page.getByText("You marked it fraud. Your decision has been saved.")).toBeVisible();

  await page.getByText(/Back to the queue|Review queue/).first().click();
  await expect(page).toHaveURL(/\/(\?date=.*)?$/);
});

test("decision buttons work from the keyboard", async ({ page, isMobile }) => {
  test.skip(isMobile, "keyboard check runs on desktop only");
  await page.goto(`/?date=${DAY}`);
  await page.locator("a[href^='/case/']:visible").nth(1).click();
  const legit = page.getByRole("button", { name: "Mark legitimate" });
  await legit.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText("You marked it legitimate. Your decision has been saved.")).toBeVisible();
});

test("results page shows the headline, table and charts", async ({ page }) => {
  await page.goto("/results");
  await expect(page.getByText(/the cost-based policy cost \$[\d,.]+ in total/)).toBeVisible();
  await expect(page.getByRole("cell", { name: /Cost-based \(this project\)/ })).toBeVisible();
  for (const alt of [/Line chart of fraud dollars lost/, /Reliability chart/]) {
    const image = page.getByRole("img", { name: alt });
    await expect(image).toBeVisible();
    expect(await image.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
  }
  await expect(page.getByRole("heading", { name: "Assumptions" })).toBeVisible();
});

test("an unknown case says so", async ({ page }) => {
  await page.goto("/case/ffffffffffffffffffffffffffffffff");
  await expect(page.getByRole("heading", { name: "Case not found" })).toBeVisible();
  await page.goto("/case/not-a-real-id");
  await expect(page.getByRole("heading", { name: "Case not found" })).toBeVisible();
});

test("no page has horizontal scrolling", async ({ page }) => {
  for (const path of [`/?date=${DAY}`, "/results"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `${path} is wider than the screen`).toBeLessThanOrEqual(0);
  }
});
