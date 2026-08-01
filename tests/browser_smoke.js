const fs = require("fs");
const path = require("path");

const playwrightPackage = process.env.PLAYWRIGHT_CORE || "playwright";
const { chromium } = require(playwrightPackage);

async function main() {
  const url = process.argv[2] || "http://127.0.0.1:8788/";
  const root = path.resolve(__dirname, "..");
  const errors = [];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  page.on("console", message => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  page.on("pageerror", error => errors.push(`pageerror: ${error.message}`));

  await page.goto(url, { waitUntil: "networkidle" });
  const title = await page.title();
  const heading = await page.locator(".brand strong").innerText();
  const health = await page.locator("#health").innerText();
  await page.screenshot({ path: path.join(root, "docs", "workbench-desktop.png"), fullPage: true });

  await page.locator("#knowledgeBtn").click();
  await page.waitForFunction(() => /找到 \d+ 条依据|检索失败/.test(document.querySelector("#knowledgeState")?.textContent || ""), null, { timeout: 60000 });
  const knowledgeState = await page.locator("#knowledgeState").innerText();
  const knowledgeText = await page.locator("#knowledgeResults").innerText();
  await page.screenshot({ path: path.join(root, "qa", "knowledge-search.png"), fullPage: true });

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  const mobilePage = await mobile.newPage();
  mobilePage.on("console", message => {
    if (message.type() === "error") errors.push(`mobile console: ${message.text()}`);
  });
  mobilePage.on("pageerror", error => errors.push(`mobile pageerror: ${error.message}`));
  await mobilePage.goto(url, { waitUntil: "networkidle" });
  const overflow = await mobilePage.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  await mobilePage.screenshot({ path: path.join(root, "docs", "workbench-mobile.png"), fullPage: true });

  const report = { url, title, heading, health, knowledgeState, knowledgeTextLength: knowledgeText.length, overflow, errors };
  fs.writeFileSync(path.join(root, "qa", "browser-smoke.json"), JSON.stringify(report, null, 2) + "\n");
  await mobile.close();
  await context.close();
  await browser.close();

  if (!title.includes("AI 视频智能体")) throw new Error(`unexpected title: ${title}`);
  if (!health.includes("引擎") || !knowledgeState.includes("找到")) throw new Error(JSON.stringify(report));
  if (overflow > 1 || errors.length) throw new Error(JSON.stringify(report));
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
