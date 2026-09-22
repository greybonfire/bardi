import type { FullResult, Reporter, Suite, TestCase, TestResult } from "@playwright/test/reporter";

export const titles = ["ar: real National ID renewal", "en: real National ID renewal", "en: possession correction and recovery"];

// Never forward Playwright errors, stdout, stderr, attachments or request data.
export default class PrivateReporter implements Reporter {
  private valid = false;
  private passed = 0;
  private failed = 0;
  private errors = 0;
  private failingIds: number[] = [];
  onBegin(_config: unknown, suite: Suite) {
    const tests = suite.allTests();
    this.valid = tests.length === 3 && titles.every((title) => tests.filter((test) => test.title === title).length === 1);
  }
  onTestEnd(test: TestCase, result: TestResult) {
    if (result.status === "passed" && test.expectedStatus === "passed" && result.retry === 0) this.passed++;
    else { this.failed++; this.failingIds.push(titles.indexOf(test.title) + 1); }
  }
  onError() { this.errors++; }
  async onEnd(result: FullResult): Promise<{ status: "passed" | "failed" }> {
    const ok = this.valid && this.passed === 3 && this.failed === 0 && this.errors === 0 && result.status === "passed";
    console.log(JSON.stringify({ suite: "real-national-id", passed: this.passed, failed: this.failed, errors: this.errors, failingIds: this.failingIds, status: ok ? "passed" : "failed" }));
    return { status: ok ? "passed" : "failed" };
  }
  printsToStdio() { return true; }
}
