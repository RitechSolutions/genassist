import { test, expect } from "./fixtures";

test("AI Agents › Functionality", async ({ page }) => {
  const agentName = `ai_agent_${Date.now()}`;
  const updatedAgentName = `updated_${agentName}`;

  await page.getByRole("button", { name: "Agent Studio" }).click();
  await page.getByRole("link", { name: "Workflows" }).click();
  await page.waitForURL("**/ai-agents");

  await page.getByText("New Workflow").click();
  await page.getByRole("textbox", { name: "Enter agent name" }).fill(agentName);
  await page.getByRole("textbox", { name: "Enter agent name" }).press("Tab");
  await page.getByRole("textbox", { name: "Enter agent description" }).click();
  await page
    .getByRole("textbox", { name: "Enter agent description" })
    .fill("This is a test agent description");

  await page.getByRole("textbox", { name: "Enter welcome message" }).click();
  await page
    .getByRole("textbox", { name: "Enter welcome message" })
    .fill("welcome message");

  await page.getByRole("button", { name: "Add FAQ" }).click();
  await page
    .getByRole("textbox", { name: "Enter a sample query" })
    .fill("frequently asked questions");
  await page.getByRole("button", { name: "Add FAQ" }).click();
  await page.waitForTimeout(2000);
  await page.getByRole("button").filter({ hasText: /^$/ }).nth(1).click();

  await page.waitForTimeout(500);
  await page.getByRole("button", { name: "Create Agent" }).click();

  await page.waitForTimeout(1000);

  const agentRow = page.locator("div").filter({ hasText: agentName }).first();
  await expect(agentRow).toBeVisible();
  await page.goto("/ai-agents");

  const dropdownButton = agentRow.locator("button").last();
  await dropdownButton.click();

  await page.waitForTimeout(1000);
  await page.getByRole("menuitem", { name: "Edit" }).click();

  await page.getByRole("button", { name: "Edit" }).click();

  await page.getByRole("textbox", { name: "Enter agent name" }).click();
  await page
    .getByRole("textbox", { name: "Enter agent name" })
    .fill(updatedAgentName);
  await page.getByRole("textbox", { name: "Enter agent description" }).click();
  await page
    .getByRole("textbox", { name: "Enter agent description" })
    .fill("This is a test agent description updated");
  await page.getByRole("textbox", { name: "Enter welcome message" }).click();
  await page
    .getByRole("textbox", { name: "Enter welcome message" })
    .fill("welcome message updated");
  await page.getByRole("button", { name: "Add FAQ" }).click();
  await page.waitForTimeout(1000);
  await page.getByRole("button", { name: "Update Agent" }).click();

  await page.waitForTimeout(2000);

  await page.goto("/ai-agents");

  await page.getByRole("switch").first().click();

  await page.waitForTimeout(2000);

  const updatedDropdownButton = agentRow.locator("button").last();

  await page.locator("div").filter({ hasText: updatedAgentName }).first();

  agentRow.locator("button").last();
  await updatedDropdownButton.click();

  await page.getByText("Get integration code").click();
  await page.waitForTimeout(500);
  await page.goto("/ai-agents");

  agentRow.locator("button").last();
  await updatedDropdownButton.click();
  await page.getByText("Manage Keys").click();
  await page.waitForTimeout(500);
  await page.goto("/ai-agents");

  agentRow.locator("button").last();
  await updatedDropdownButton.click();
  await page.getByRole("menuitem", { name: "Chat as Customer" }).click();
  await page.waitForTimeout(500);
  await page.goto("/ai-agents");

  await updatedDropdownButton.click();

  await page.getByRole("menuitem", { name: "Delete" }).click();

  await page.waitForTimeout(2000);
});
