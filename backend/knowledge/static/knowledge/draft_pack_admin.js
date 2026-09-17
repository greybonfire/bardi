/* Retain only the user's File input. Never stage research in browser storage. */
(() => {
  const form = document.getElementById("draft-pack-form");
  if (!form || !window.fetch || !window.FormData) return;
  const file = document.getElementById("id_pack");
  const result = document.getElementById("pack-result");
  const progress = document.getElementById("pack-progress");
  let generation = 0;
  let controller;
  file.addEventListener("change", () => {
    generation += 1;
    controller?.abort();
    form.removeAttribute("aria-busy");
    result.replaceChildren();
    progress.textContent = "File changed. Inspect before confirming.";
  });
  form.addEventListener("submit", async (event) => {
    if (event.submitter?.value !== "inspect") return;
    event.preventDefault();
    controller?.abort();
    controller = new AbortController();
    const current = ++generation;
    const data = new FormData(form);
    data.set("action", "inspect");
    data.delete("token");
    data.delete("allow_deletions");
    result.replaceChildren();
    progress.textContent = "Inspecting proposed changes… Nothing saved.";
    form.setAttribute("aria-busy", "true");
    try {
      // The submit button named "action" shadows the native form.action property.
      const response = await fetch(form.getAttribute("action") || window.location.href, {
        method: "POST", body: data, credentials: "same-origin",
        headers: {"X-Draft-Pack-Fragment": "1"}, signal: controller.signal,
      });
      const html = await response.text();
      if (current !== generation) return;
      if (response.redirected || ![200, 400].includes(response.status)) {
        throw new Error("Request unavailable");
      }
      // Only same-origin server-rendered, autoescaped templates enter this fragment.
      result.innerHTML = html;
      progress.textContent = response.ok ? "Inspection complete. Review before confirming." : "Inspection failed. Resolve the issues below.";
    } catch (error) {
      if (current === generation && error.name !== "AbortError") {
        progress.textContent = "Inspection unavailable. Retry, or reload to use the standard upload form.";
      }
    } finally {
      if (current === generation) form.removeAttribute("aria-busy");
    }
  });
})();
