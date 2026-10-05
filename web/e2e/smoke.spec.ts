import { expect, test } from "@playwright/test";

// A day with review cases in the demo data, and the overview's example case.
const DAY = "2020-12-24";
const EXAMPLE_CASE = "808d112f86a9385ce6243430dbb22dff";

test("overview explains the project and leads into the demo", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("decides what to do about it");
  await expect(page.getByText(/% less/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "How it works" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Built with" })).toBeVisible();
  await expect(page.getByText("LightGBM", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Start with an example case" }).click();
  await expect(page).toHaveURL(new RegExp(`/case/${EXAMPLE_CASE}$`));
  await expect(page.getByText("$745.88", { exact: true })).toBeVisible(); // the amount, not the reason
});

test("every page has the banner, navigation and footer", async ({ page }) => {
  for (const path of ["/", "/queue", "/results"]) {
    await page.goto(path);
    await expect(page.getByText("Simulated data. Decisions here are for demonstration only.")).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
    await expect(page.getByText("Built by David Meltonyan")).toBeVisible();
  }
  // Wait for the page's own content, as a person would, so the click isn't lost
  // while the page's JavaScript is still starting up.
  await expect(page.getByRole("heading", { name: "Results", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Try it" }).click();
  await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible();
  await page.getByRole("link", { name: "Overview" }).click();
  await expect(page.getByRole("heading", { name: "How it works" })).toBeVisible();
});

test("queue lists a day's cases, as a table on desktop and cards on a phone", async ({ page, isMobile }) => {
  await page.goto(`/queue?date=${DAY}`);
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
  await page.goto(`/queue?date=${DAY}`);
  await expect(page.getByText(/\d+ cases? \(daily budget 30\)/)).toBeVisible(); // first day loaded
  await page.getByLabel("Day").fill("2020-11-15");
  await expect(page).toHaveURL(/date=2020-11-15/);
  await expect(page.getByText(/\d+ cases? \(daily budget 30\)|No review cases on 2020-11-15/)).toBeVisible();
});

test("review one case end to end", async ({ page }) => {
  await page.goto(`/queue?date=${DAY}`);
  await page.locator("a[href^='/case/']:visible").first().click();

  await expect(page.getByRole("heading", { name: "Why the model flagged it" })).toBeVisible();
  await expect(page.locator("ol li")).toHaveCount(3);
  await expect(page.getByRole("heading", { name: "What the policy decided" })).toBeVisible();
  await expect(page.getByText("(chosen)")).toBeVisible();

  await page.getByLabel("Note (optional)").fill("Playwright smoke test");
  await page.getByRole("button", { name: "Confirm fraud" }).click();
  await expect(page.getByText(/This transaction was actually (fraud|legitimate)\./)).toBeVisible();
  await expect(page.getByText("You marked it fraud. Your decision has been saved.")).toBeVisible();

  await page.getByRole("link", { name: /Back to the queue for/ }).click();
  await expect(page).toHaveURL(new RegExp(`/queue\\?date=${DAY}`));
});

test("decision buttons work from the keyboard", async ({ page, isMobile }) => {
  test.skip(isMobile, "keyboard check runs on desktop only");
  await page.goto(`/queue?date=${DAY}`);
  await page.locator("a[href^='/case/']:visible").nth(1).click();
  const legit = page.getByRole("button", { name: "Mark legitimate" });
  await legit.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText("You marked it legitimate. Your decision has been saved.")).toBeVisible();
});

test("results page shows the headline, table and charts", async ({ page }) => {
  await page.goto("/results");
  await expect(page.getByText(/the cost-based policy cost \$[\d,.]+ in total/)).toBeVisible();
  // A table cell on desktop, a card on a phone: check whichever is showing.
  await expect(page.getByText("Cost-based (this project)").filter({ visible: true })).toBeVisible();
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
  for (const path of ["/", `/queue?date=${DAY}`, `/case/${EXAMPLE_CASE}`, "/results"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `${path} is wider than the screen`).toBeLessThanOrEqual(0);
  }
});
