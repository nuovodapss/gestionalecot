const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.js',
  timeout: 45_000,
  use: {
    baseURL: 'http://127.0.0.1:8510',
    browserName: 'chromium',
    headless: true,
    launchOptions: {
      executablePath: process.env.COT_CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    },
  },
  webServer: {
    command: '.venv/bin/python -m streamlit run app.py --server.headless true --server.port 8510',
    url: 'http://127.0.0.1:8510/_stcore/health',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
