"use strict";

window.selectTemplate = function(templateType) {
  const singleRadio = document.getElementById("radio-single");
  const twoRadio = document.getElementById("radio-two");
  const cardSingle = document.getElementById("card-template-single");
  const cardTwo = document.getElementById("card-template-two");
  const confirmBtn = document.getElementById("confirmDocxDownloadBtn");

  if (templateType === 'single_column') {
    if (singleRadio) singleRadio.checked = true;
    cardSingle?.classList.add("active-template");
    cardTwo?.classList.remove("active-template");
  } else {
    if (twoRadio) twoRadio.checked = true;
    cardTwo?.classList.add("active-template");
    cardSingle?.classList.remove("active-template");
  }

  if (confirmBtn) {
    const baseUrl = confirmBtn.getAttribute("href").split("?")[0];
    confirmBtn.setAttribute("href", `${baseUrl}?template=${templateType}`);
  }
};

document.addEventListener("DOMContentLoaded", () => {
  const page = document.querySelector("[data-results-page]");
  if (!page) return;

  document.getElementById("print-result")?.addEventListener("click", () => window.print());

  if (window.location.hash === "#rewrites") {
    const rewriteTab = document.getElementById("rewrites-tab");
    const tabApi = window.bootstrap?.Tab;
    if (rewriteTab && tabApi?.getOrCreateInstance) {
      try {
        tabApi.getOrCreateInstance(rewriteTab).show();
      } catch (_error) {
        // Review controls remain usable even if optional tab activation fails.
      }
    }
  }

  const reviewSection = page.querySelector("[data-review-url]");
  const reviewSaveStatus = document.getElementById("review-save-status");

  const showReviewMessage = (message, isError = false) => {
    if (!reviewSaveStatus) return;
    reviewSaveStatus.classList.remove("d-none", "alert-secondary", "alert-warning");
    reviewSaveStatus.classList.add(isError ? "alert-warning" : "alert-secondary");
    reviewSaveStatus.textContent = message;
  };

  const setReviewStatus = (item, decision) => {
    const badge = item.querySelector("[data-review-status]");
    if (badge) {
      badge.textContent = decision.charAt(0).toUpperCase() + decision.slice(1);
      badge.classList.remove("status-pending", "status-accepted", "status-rejected");
      badge.classList.add(`status-${decision}`);
    }

    item.querySelectorAll(".review-decision").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.decision === decision));
    });
    item.querySelectorAll("[data-review-content]").forEach((choice) => {
      const selected = decision === "accepted"
        ? choice.dataset.reviewContent === "proposed"
        : choice.dataset.reviewContent === "original";
      choice.classList.toggle("is-final-choice", selected);
      choice.querySelector("[data-review-final-marker]")?.classList.toggle("d-none", !selected);
    });
  };

  const fetchJson = async (url, options) => {
    const response = await fetch(url, options);
    const contentType = response.headers.get("Content-Type") || "";
    let payload = null;
    if (response.status !== 204 && contentType.includes("application/json")) {
      payload = await response.json();
    }
    if (!response.ok) {
      const detail = payload && typeof payload.detail === "string" ? payload.detail : "Request failed.";
      throw new Error(detail);
    }
    return payload;
  };

  const saveReviewDecision = async (button) => {
    const item = button.closest("[data-review-item]");
    const itemId = button.dataset.reviewId;
    const decision = button.dataset.decision;
    const kind = button.dataset.reviewKind;
    if (
      !reviewSection ||
      !item ||
      item.dataset.reviewItem !== itemId ||
      !["accepted", "rejected"].includes(decision) ||
      !["summary", "bullet", "skills"].includes(kind)
    ) {
      showReviewMessage("This review action is unavailable. Reload the page and try again.", true);
      return;
    }

    const body = kind === "bullet"
      ? { experience_bullets: { [itemId]: decision } }
      : { [kind]: decision };
    const itemButtons = item.querySelectorAll(".review-decision");
    const originalLabel = button.textContent;
    itemButtons.forEach((itemButton) => { itemButton.disabled = true; });
    button.textContent = "Saving…";
    showReviewMessage("Saving decision…");

    try {
      const payload = await fetchJson(reviewSection.dataset.reviewUrl, {
        method: "PATCH",
        headers: { "Accept": "application/json", "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const saved = kind === "bullet"
        ? payload?.experience_bullets?.find((entry) => entry.id === itemId)
        : payload?.[kind];
      if (!saved || saved.decision !== decision) throw new Error("Decision was not persisted.");
      setReviewStatus(item, decision);
      showReviewMessage("Decision saved. The final resume preview will use this choice.");
    } catch (_error) {
      showReviewMessage("The decision could not be saved. Please try again.", true);
    } finally {
      button.textContent = originalLabel;
      itemButtons.forEach((itemButton) => { itemButton.disabled = false; });
    }
  };

  reviewSection?.addEventListener("click", (event) => {
    const button = event.target.closest?.(".review-decision");
    if (!button || !reviewSection.contains(button) || button.disabled) return;
    void saveReviewDecision(button);
  });

  const jsonSection = document.getElementById("json");
  const loadJson = document.getElementById("load-json");
  const copyJson = document.getElementById("copy-json");
  const rawJson = document.getElementById("raw-json");
  const jsonStatus = document.getElementById("json-status");
  if (jsonSection && loadJson && copyJson && rawJson && jsonStatus) {
    loadJson.addEventListener("click", async () => {
      loadJson.disabled = true;
      loadJson.textContent = "Loading…";
      try {
        const payload = await fetchJson(jsonSection.dataset.resultUrl, {
          headers: { "Accept": "application/json" }
        });
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
  }

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
