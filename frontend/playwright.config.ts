import { defineConfig, devices } from "@playwright/test";

// In Codex/restricted terminal runs, prefer PW_CHROME_EXECUTABLE_PATH pointing
// to the local Chrome binary and execute smoke outside the sandbox.
const chromeExecutablePath = process.env.PW_CHROME_EXECUTABLE_PATH || "";

export default defineConfig({
  testDir: "./tests/smoke",
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  use: {
    baseURL: "http://127.0.0.1:3010",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run dev:smoke",
    url: "http://127.0.0.1:3010",
    reuseExistingServer: false,
    timeout: 30_000,
  },
  projects: [
    {
      name: "chrome",
      use: {
        ...devices["Desktop Chrome"],
        ...(chromeExecutablePath
          ? { launchOptions: { executablePath: chromeExecutablePath } }
          : { channel: "chrome" }),
      },
    },
  ],
});
