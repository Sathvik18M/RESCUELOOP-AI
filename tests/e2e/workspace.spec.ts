import { test, expect } from "@playwright/test";
import path from "node:path";

test.describe.configure({ mode: "serial" });
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Enter demo workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Your store, in the loop." }),
  ).toBeVisible();
  await expect(page.getByText("Everyday Leather Wallet").first()).toBeVisible();
});

test("overview renders, navigation works, and mobile stays within viewport", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.screenshot({
    path: ".local/screenshots/overview-desktop.png",
    fullPage: true,
  });
  for (const [route, heading] of [
    ["orders", "Your orders"],
    ["products", "Everyday Leather Wallet"],
    ["policies", "Store rules"],
    ["pickup", "Pickup reservations"],
    ["returns", "Returns & refunds"],
    ["evidence", "A clearer picture starts here"],
    ["feedback", "Customer feedback"],
    ["insights", "Small signals. Useful next steps."],
    ["activity", "Action log"],
    ["settings", "Store profile"],
  ]) {
    await page.goto(`/${route}`);
    await expect(
      page.getByRole("heading", { name: heading, exact: true }).first(),
    ).toBeVisible();
  }
  await page.goto("/insights");
  await page
    .getByRole("button", { name: "Analyze feedback", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Demo analysis", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Your store, in the loop." }),
  ).toBeVisible();
  await page.screenshot({
    path: ".local/screenshots/overview-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  await page.getByRole("link", { name: "WhatsApp inbox" }).click();
  await expect(
    page.getByRole("heading", { name: "Conversations", exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("seller quotation waits for customer acceptance and updates the order", async ({
  page,
  request,
}) => {
  await page.goto("/approvals");
  await page.getByRole("button", { name: "Review request" }).first().click();
  await page.getByLabel("Engraving / additional quote (₹)").fill("199");
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const headers = { Authorization: "Bearer local-rescueloop-demo" };
  const before = await request.get("http://127.0.0.1:8001/api/orders/ORD1043", {
    headers,
  });
  expect((await before.json()).total_paise).toBe(79900);
  await page.goto("/inbox");
  await page.getByRole("button", { name: /Ananya Rao/ }).click();
  await page
    .getByRole("textbox", { name: "Message", exact: true })
    .fill("CONFIRM CASE1043");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page.locator(".messages").getByText(/Customization added. Order subtotal/),
  ).toBeVisible();
  await page.screenshot({
    path: ".local/screenshots/inbox-desktop.png",
    fullPage: true,
  });
  const after = await request.get("http://127.0.0.1:8001/api/orders/ORD1043", {
    headers,
  });
  expect((await after.json()).total_paise).toBe(114700);
});

test("pickup request reaches seller, reserves a slot, and verifies handover", async ({
  page,
  request,
}) => {
  await page.goto("/inbox");
  await page.getByRole("button", { name: /Ananya Rao/ }).click();
  await page
    .getByRole("textbox", { name: "Message", exact: true })
    .fill("Can I collect the wallet tomorrow afternoon?");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page.locator(".messages").getByText(/Your pickup request has been sent/),
  ).toBeVisible();
  await page.goto("/approvals");
  await page.getByRole("button", { name: "Review request" }).click();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const headers = { Authorization: "Bearer local-rescueloop-demo" };
  let data = await (
    await request.get("http://127.0.0.1:8001/api/workspace", { headers })
  ).json();
  const pickup = data.cases.find((c: { kind: string }) => c.kind === "pickup");
  await page.goto("/inbox");
  await page.getByRole("button", { name: /Ananya Rao/ }).click();
  await page
    .getByRole("textbox", { name: "Message", exact: true })
    .fill(`CONFIRM ${pickup.id}`);
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page.locator(".messages").getByText(/Pickup reserved:/),
  ).toBeVisible();
  const text = await page
    .locator(".message p")
    .filter({ hasText: "Collection code:" })
    .innerText();
  const code = text.match(/Collection code: (\d{6})/)![1];
  await page.goto("/pickup");
  await page.getByRole("button", { name: "Mark ready" }).click();
  await page.getByRole("button", { name: "Verify collection" }).click();
  await page.getByLabel("Customer's six-digit code").fill(code);
  await page.getByRole("button", { name: "Confirm handover" }).click();
  await expect(page.getByText("Collected", { exact: true })).toBeVisible();
  data = await (
    await request.get("http://127.0.0.1:8001/api/workspace", { headers })
  ).json();
  expect(
    data.orders.find((o: { id: string }) => o.id === "ORD1043").status,
  ).toBe("delivered");
});

test("failed delivery and photo refund enforce confirmation and approval", async ({
  page,
  request,
}) => {
  await page.goto("/inbox");
  await page
    .getByRole("textbox", { name: "Message", exact: true })
    .fill("Address: 12 Demo Road, Bengaluru");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page.locator(".messages").getByText(/Your redelivery request for/),
  ).toBeVisible();
  const headers = { Authorization: "Bearer local-rescueloop-demo" };
  let data = await (
    await request.get("http://127.0.0.1:8001/api/workspace", { headers })
  ).json();
  const redelivery = data.cases.find(
    (c: { kind: string }) => c.kind === "redelivery",
  );
  await page
    .getByRole("textbox", { name: "Message", exact: true })
    .fill(`CONFIRM ${redelivery.id}`);
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page
      .locator(".messages")
      .getByText(/Redelivery scheduled with DemoCourier/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Demo studio" }).click();
  await page.getByRole("button", { name: /Photo complaint & refund/ }).click();
  // A generated test photograph exercises the upload path without external media.
  await page
    .locator('input[type="file"]')
    .setInputFiles(path.resolve("data/demo/assets/test-evidence.png"));
  await expect(
    page.locator(".messages").getByText(/Your photo has been saved for review/),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "Message", exact: true })
    .fill("I want a refund");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page.locator(".messages").getByText(/Your refund request has been sent/),
  ).toBeVisible();
  await page.goto("/returns");
  await page.getByRole("button", { name: "Review request" }).click();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  data = await (
    await request.get("http://127.0.0.1:8001/api/workspace", { headers })
  ).json();
  const refund = data.cases.find((c: { kind: string }) => c.kind === "refund");
  expect(data.refunds.length).toBe(0);
  await page.goto("/inbox");
  await page
    .getByRole("textbox", { name: "Message", exact: true })
    .fill(`CONFIRM ${refund.id}`);
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page.locator(".messages").getByText(/Simulated refund completed:/),
  ).toBeVisible();
  await page.goto("/evidence");
  await expect(
    page.getByRole("img", { name: "Customer-provided product evidence" }),
  ).toBeVisible();
});
