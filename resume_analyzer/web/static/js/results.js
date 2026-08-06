"use strict";

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("print-result")?.addEventListener("click", () => window.print());
  const jsonSection = document.getElementById("json");
  const loadJson = document.getElementById("load-json");
  const copyJson = document.getElementById("copy-json");
  const rawJson = document.getElementById("raw-json");
  const jsonStatus = document.getElementById("json-status");
  loadJson?.addEventListener("click", async () => {
    loadJson.disabled = true;
    loadJson.textContent = "Loading…";
    try {
      const response = await fetch(jsonSection.dataset.resultUrl, {
        headers: { "Accept": "application/json" }
      });
      if (!response.ok) throw new Error("json_request_failed");
      const payload = await response.json();
      rawJson.textContent = JSON.stringify(payload, null, 2);
      rawJson.classList.remove("d-none");
      jsonStatus.classList.add("d-none");
      copyJson.disabled = false;
      loadJson.textContent = "JSON loaded";
    } catch (_error) {
      jsonStatus.textContent = "The technical JSON could not be loaded. Use Download JSON instead.";
      jsonStatus.classList.remove("alert-secondary");
      jsonStatus.classList.add("alert-warning");
      loadJson.disabled = false;
      loadJson.textContent = "Try again";
    }
  });
  document.querySelectorAll(".copy-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const target = document.getElementById(button.dataset.copyTarget);
      if (!target) return;
      const original = button.textContent;
      try {
        await navigator.clipboard.writeText(target.textContent || "");
        button.textContent = "Copied";
      } catch (_error) {
        button.textContent = "Copy unavailable";
      }
      window.setTimeout(() => { button.textContent = original; }, 1600);
    });
  });
});
