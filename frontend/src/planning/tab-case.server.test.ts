// @vitest-environment node
import { expect, it, vi } from "vitest";
import { attachTabCase, createTabCaseOwner } from "./tab-case";

it("cannot allocate or access a module-global case outside the browser", () => {
  expect(typeof window).toBe("undefined");
  expect(() => createTabCaseOwner()).toThrow("The questionnaire case is browser-only.");
  expect(() => attachTabCase("test.service", vi.fn())).toThrow("The questionnaire case is browser-only.");
});
