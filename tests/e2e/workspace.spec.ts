import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
const headers = { Authorization: "Bearer local-rescueloop-demo" };
const api = "http://127.0.0.1:8002/api";
test.describe.configure({ mode: "serial" });
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Enter seller dashboard" }).click();
  await expect(
    page.getByRole("heading", { name: "A little care goes a long way." }),
  ).toBeVisible();
});
test("five seller sections, saved metrics, and mobile navigation", async ({
  page,
}) => {
  await expect(
    page.getByRole("region", { name: "Case statistics" }),
  ).toContainText("12");
  for (const [link, heading] of [
    ["Inbox", "Conversations"],
    ["Requests", "Requests"],
    ["Policies", "Automation rules"],
    ["Insights", "Small signals. Useful next steps."],
  ]) {
    await page
      .getByRole("navigation")
      .getByRole("link", { name: new RegExp("^" + link) })
      .click();
    await expect(
      page.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Inbox", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Conversations", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
test("seller approval waits for independent customer consent", async ({
  page,
  request,
}) => {
  await page.getByRole("button", { name: /ORD1043 — Customization/ }).click();
  await page
    .getByRole("button", { name: "Approve proposal", exact: true })
    .click();
  await expect(
    page.getByText("Pending Customer", { exact: true }),
  ).toBeVisible();
  let state = await (await request.get(api + "/workspace", { headers })).json();
  const proposal = state.cases.find((c: { id: string }) => c.id === "CASE1043");
  expect(
    state.orders.find((o: { id: string }) => o.id === "ORD1043").total_paise,
  ).toBe(79900);
  // Fixture input is deliberately outside the seller website.
  const accepted = await request.post(
    api + "/demo/conversations/CONV002/messages",
    {
      headers,
      data: {
        text: "CONFIRM " + proposal.proposal_ref,
        message_id: randomUUID(),
      },
    },
  );
  expect(accepted.ok()).toBeTruthy();
  await page.getByRole("button", { name: "Close case", exact: true }).click();
  await page
    .getByRole("button", { name: "Refresh workspace", exact: true })
    .click();
  state = await (await request.get(api + "/workspace", { headers })).json();
  expect(
    state.orders.find((o: { id: string }) => o.id === "ORD1043").total_paise,
  ).toBe(114700);
  expect(
    state.orders.find((o: { id: string }) => o.id === "ORD1043").paid_paise,
  ).toBe(0);
  expect(
    state.cases.find((c: { id: string }) => c.id === "CASE1043").primary_status,
  ).toBe("resolved");
});
test("policy draft does not change the active published rule", async ({
  page,
  request,
}) => {
  await page.getByRole("link", { name: "Policies", exact: true }).click();
  await page
    .getByLabel("Policy instruction", { exact: true })
    .fill("Change return window to 10 days");
  await page.getByRole("button", { name: "Create draft", exact: true }).click();
  await page.getByRole("button", { name: "Review", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Review policy version 2" }),
  ).toBeVisible();
  const state = await (
    await request.get(api + "/workspace", { headers })
  ).json();
  expect(
    state.policies.find((p: { published: boolean }) => p.published).rules
      .return_window_days,
  ).toBe(7);
});
