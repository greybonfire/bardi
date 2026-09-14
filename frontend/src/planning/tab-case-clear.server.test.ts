// @vitest-environment node
import { expect, it } from "vitest";
import { clearTabCase } from "./tab-case";

it("cannot allocate case-clearing state outside the browser", () => {
  expect(() => clearTabCase()).toThrow("The questionnaire case is browser-only.");
});
