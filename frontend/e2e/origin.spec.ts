import { test, expect, type APIResponse, type Response } from "@playwright/test";
import type { PlanningRequest } from "../src/api/contract";
import { nextQuestion, passportId, services } from "./fixtures.mjs";

// The existing Playwright config supplies BARDI_SITE_ORIGIN=publicOrigin while
// Next listens on 127.0.0.1. These exercise the real server, not route mocks.
// Only fixed synthetic input is used; never attach bodies, logs or traces.
const publicOrigin = "http://localhost:3010";
const listenerOrigin = "http://127.0.0.1:3010";
const input: PlanningRequest = {
  service_id: passportId, facts: {}, locale: "en",
  evaluation_context: { evaluation_date: "2026-09-12" },
};
const credentials = {
  Cookie: "origin_test=TEST-ONLY-CREDENTIAL", Authorization: "Bearer TEST-ONLY-CREDENTIAL",
};

function expectPublicHeaders(response: APIResponse | Response) {
  const headers = response.headers();
  expect(headers["cache-control"]).toBe("no-store");
  expect(headers).not.toHaveProperty("set-cookie");
  expect(headers).not.toHaveProperty("access-control-allow-origin");
}

async function expectPlanningResponse(response: APIResponse | Response, status: 200 | 403) {
  expect(response.status()).toBe(status);
  expect(await response.json()).toEqual(status === 200 ? nextQuestion(passportId, "en", 0) : {
    type: "invalid", diagnostics: [{ code: "forbidden_origin", path: [] }],
  });
  expectPublicHeaders(response);
}

for (const [origin, status] of [[publicOrigin, 200], [listenerOrigin, 403]] as const) {
  test(`browser Origin ${origin} gets ${status} regardless of same-origin listener transport`, async ({ page, context }) => {
    await context.addCookies([{ name: "origin_test", value: "TEST-ONLY-CREDENTIAL", url: origin }]);
    // A public JSON document gives the browser a genuine server origin without
    // coupling this boundary regression to SSR pages or questionnaire lifecycle.
    const navigation = await page.goto(`${origin}/v1/services`);
    expect(navigation?.status()).toBe(200);
    expect(await navigation?.json()).toEqual({ services });
    const pending = page.waitForResponse((response) =>
      response.url() === `${origin}/v1/planning` && response.request().method() === "POST");
    await page.evaluate(async (data) => {
      const response = await fetch("/v1/planning", {
        method: "POST", body: JSON.stringify(data), headers: { "Content-Type": "application/json" },
        credentials: "omit", cache: "no-store", referrerPolicy: "no-referrer", redirect: "error",
      });
      await response.arrayBuffer();
    }, input);
    const response = await pending;
    const headers = await response.request().allHeaders();
    expect(headers.origin).toBe(origin);
    expect(headers["sec-fetch-site"]).toBe("same-origin");
    for (const name of ["cookie", "authorization", "referer"]) expect(headers).not.toHaveProperty(name);
    await expectPlanningResponse(response, status);
    expect(await context.cookies()).toHaveLength(1); // Only the deliberately seeded credential.
  });
}

for (const target of [publicOrigin, listenerOrigin]) {
  test(`API accepts configured public Origin via ${target}, not forwarded host identity`, async ({ request }) => {
    const response = await request.post(`${target}/v1/planning`, {
      data: input, headers: {
        ...credentials, Origin: publicOrigin, "Sec-Fetch-Site": "same-origin",
        "X-Forwarded-Host": "attacker.example", "X-Forwarded-Proto": "https",
        Forwarded: "host=attacker.example;proto=https",
      },
    });
    // The upstream stand-in also rejects any forwarded identity/credential header.
    await expectPlanningResponse(response, 200);
  });

  test(`API denies foreign, opaque and non-literal Origin via ${target}`, async ({ request }) => {
    for (const origin of [
      listenerOrigin, "https://attacker.example", "null", "", "http://localhost:3011",
      "http://localhost:03010", "HTTP://localhost:3010", "http://LOCALHOST:3010",
      "http://user:password@localhost:3010", "http://@localhost:3010", `${publicOrigin}/`,
      `${publicOrigin}/path/..`, `${publicOrigin}?`, `${publicOrigin}#`, `blob:${publicOrigin}/opaque`,
      `${publicOrigin}, https://attacker.example`, `${publicOrigin} ${publicOrigin}`,
    ]) {
      await expectPlanningResponse(await request.post(`${target}/v1/planning`, {
        data: input, headers: { Origin: origin, "Sec-Fetch-Site": "same-origin" },
      }), 403);
    }
  });
}

test("API ignores spoofed Host and forwarded headers rather than trusting a foreign Origin", async ({ request }) => {
  await expectPlanningResponse(await request.post(`${listenerOrigin}/v1/planning`, {
    data: input, headers: {
      Origin: "https://attacker.example", Host: "attacker.example", "X-Forwarded-Host": "attacker.example",
      "X-Forwarded-Proto": "https", Forwarded: "host=attacker.example;proto=https", "Sec-Fetch-Site": "same-origin",
    },
  }), 403);
});

test("API cannot authorize an unconfigured Origin using a spoofed forwarded scheme", async ({ request }) => {
  await expectPlanningResponse(await request.post(`${listenerOrigin}/v1/planning`, {
    data: input, headers: {
      Origin: "https://localhost:3010", Host: "localhost:3010", "X-Forwarded-Host": "localhost:3010",
      "X-Forwarded-Proto": "https", "Sec-Fetch-Site": "same-origin",
    },
  }), 403);
});

test("API allows origin-less stateless callers but rejects explicit cross-site browser metadata", async ({ request }) => {
  await expectPlanningResponse(await request.post("/v1/planning", { data: input, headers: credentials }), 200);
  const crossSiteHeaders: Record<string, string>[] = [
    { "Sec-Fetch-Site": "cross-site" },
    { "Sec-Fetch-Site": "cross-site", Origin: publicOrigin },
  ];
  for (const headers of crossSiteHeaders) {
    await expectPlanningResponse(await request.post("/v1/planning", { data: input, headers }), 403);
  }
});

test("public Service GET is unaffected by foreign or opaque Origin", async ({ request }) => {
  for (const origin of ["https://attacker.example", "null"]) {
    const response = await request.get("/v1/services", {
      headers: { ...credentials, Origin: origin, "Sec-Fetch-Site": "cross-site" },
    });
    expect(response.status()).toBe(200);
    expect(await response.json()).toEqual({ services });
    expectPublicHeaders(response);
  }
});
