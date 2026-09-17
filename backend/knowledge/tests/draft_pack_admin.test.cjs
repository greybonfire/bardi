const assert = require("node:assert/strict");
const { File } = require("node:buffer");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = readFileSync(path.join(__dirname, "../static/knowledge/draft_pack_admin.js"), "utf8");
const uploadURL = "https://admin.example.test/admin/knowledge/procedureversion/draft-pack/import/";

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

// Deliberately small DOM adapter, not a browser emulator. Model named-property
// shadowing and successful form controls; execute the real shipped script.
function harness(action = null) {
  function element() {
    const listeners = new Map();
    const attributes = new Map();
    return {
      textContent: "", innerHTML: "",
      addEventListener(name, handler) { listeners.set(name, handler); },
      dispatch(name, event) { return listeners.get(name)(event); },
      getAttribute(name) { return attributes.get(name) ?? null; },
      setAttribute(name, value) { attributes.set(name, value); },
      removeAttribute(name) { attributes.delete(name); },
      replaceChildren() { this.innerHTML = ""; },
    };
  }
  const form = element();
  const file = element();
  file.files = [new File(['{"format_version":1}'], "pack.json", { type: "application/json" })];
  const button = { name: "action", value: "inspect", toString: () => "[object HTMLButtonElement]" };
  form.action = button; // Native form named control shadows the action property.
  if (action !== null) form.setAttribute("action", action);
  const result = element();
  const progress = element();
  const elements = { "draft-pack-form": form, id_pack: file, "pack-result": result, "pack-progress": progress };
  class FormDataAdapter extends FormData {
    constructor(source) {
      super();
      assert.equal(source, form);
      this.set("pack", file.files[0]);
      this.set("csrfmiddlewaretoken", "csrf-value");
      this.set("token", "old-confirmation-token");
      this.set("allow_deletions", "on");
      // A submit button is omitted by FormData(form) without a submitter.
    }
  }
  const requests = [];
  const fetch = (url, options) => {
    const pending = deferred();
    requests.push({ url, options, ...pending });
    // Do not auto-reject on abort: test generation checks even if cancellation
    // is too late or the transport/body reader still completes.
    return pending.promise;
  };
  vm.runInNewContext(script, {
    document: { getElementById: (id) => elements[id] },
    window: { fetch, FormData: FormDataAdapter, location: { href: uploadURL } },
    fetch, FormData: FormDataAdapter, AbortController,
  }, { filename: "draft_pack_admin.js" });
  return {
    form, file, result, progress, requests,
    inspect() {
      let prevented = false;
      const done = form.dispatch("submit", { submitter: button, preventDefault() { prevented = true; } });
      assert.equal(prevented, true);
      return done;
    },
    change() { file.dispatch("change"); },
  };
}

const response = (html) => ({ status: 200, ok: true, redirected: false, text: async () => html });

for (const action of [null, "", uploadURL, "/admin/knowledge/procedureversion/42/draft-pack/update/"]) {
  test(`inspection uses upload URL, not named button (action=${JSON.stringify(action)})`, async () => {
    const h = harness(action);
    const originalFile = h.file.files[0];
    const done = h.inspect();
    const request = h.requests[0];
    assert.equal(request.url, action || uploadURL);
    assert.equal(request.options.method, "POST");
    assert.equal(request.options.credentials, "same-origin");
    assert.equal(request.options.headers["X-Draft-Pack-Fragment"], "1");
    assert.equal(request.options.body.get("pack"), originalFile);
    assert.equal(request.options.body.get("action"), "inspect");
    assert.equal(request.options.body.get("csrfmiddlewaretoken"), "csrf-value");
    assert.equal(request.options.body.has("token"), false);
    assert.equal(request.options.body.has("allow_deletions"), false);
    request.resolve(response("inspection"));
    await done;
    assert.equal(h.file.files[0], originalFile);
    assert.equal(h.result.innerHTML, "inspection");
    assert.equal(h.form.getAttribute("aria-busy"), null);
  });
}

for (const reject of [false, true]) {
  test(`file change invalidates inspection and ignores obsolete ${reject ? "rejection" : "response"}`, async () => {
    const h = harness();
    const done = h.inspect();
    h.result.innerHTML = "old confirmation";
    h.file.files = [new File(["{}"], "replacement.json")];
    h.change();
    assert.equal(h.requests[0].options.signal.aborted, true);
    assert.equal(h.result.innerHTML, "");
    assert.equal(h.form.getAttribute("aria-busy"), null);
    const message = h.progress.textContent;
    assert.equal(message, "File changed. Inspect before confirming.");
    if (reject) h.requests[0].reject(new Error("late failure"));
    else h.requests[0].resolve(response("obsolete confirmation"));
    await done;
    assert.equal(h.result.innerHTML, "");
    assert.equal(h.progress.textContent, message);
  });

  test(`new inspection suppresses obsolete ${reject ? "rejection" : "body completion"}`, async () => {
    const h = harness();
    const first = h.inspect();
    const body = deferred();
    if (!reject) {
      h.requests[0].resolve({ ...response(""), text: () => body.promise });
      await Promise.resolve();
    }
    const second = h.inspect();
    assert.equal(h.requests[0].options.signal.aborted, true);
    if (reject) h.requests[0].reject(new Error("late failure"));
    else body.resolve("obsolete confirmation");
    await first;
    assert.equal(h.result.innerHTML, "");
    assert.equal(h.form.getAttribute("aria-busy"), "true");
    assert.equal(h.progress.textContent, "Inspecting proposed changes… Nothing saved.");
    h.requests[1].resolve(response("current confirmation"));
    await second;
    assert.equal(h.result.innerHTML, "current confirmation");
    assert.equal(h.progress.textContent, "Inspection complete. Review before confirming.");
    assert.equal(h.form.getAttribute("aria-busy"), null);
  });
}

test("confirmation stays on the native submission path", async () => {
  const h = harness();
  await h.form.dispatch("submit", {
    submitter: { name: "action", value: "confirm" },
    preventDefault() { assert.fail("confirmation must not be intercepted"); },
  });
  assert.equal(h.requests.length, 0);
});
