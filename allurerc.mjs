import { defineConfig } from "allure";

export default defineConfig({
  name: "Web 自动化测试",
  output: "allure-report",
  historyPath: "allure-history.jsonl",
  plugins: {
    awesome: {
      options: {
        reportLanguage: "zh",
      },
    },
  },
});
