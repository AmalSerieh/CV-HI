"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const view = document.getElementById("progress-view");
  if (!view) return;
  const analysisId = view.dataset.analysisId;
  const alertBox = document.getElementById("progress-alert");
  const items = Array.from(document.querySelectorAll(".stage-item"));
  const pipelineStages = ["extracting_text", "detecting_sections", "extracting_entities", "suggesting_target_role", "generating_recommendations", "calculating_ats", "matching_job", "generating_rewrites"];
  const mark = (payload) => {
    items.forEach((item) => item.classList.remove("is-active", "is-complete"));
    items.filter((item) => ["uploading", "validating_document"].includes(item.dataset.stage)).forEach((item) => item.classList.add("is-complete"));
    if (payload.stage === "running_pipeline") {
      pipelineStages.forEach((key) => document.querySelector(`[data-stage="${key}"]`)?.classList.add("is-active"));
    } else if (payload.stage === "validating_final_report") {
      pipelineStages.forEach((key) => document.querySelector(`[data-stage="${key}"]`)?.classList.add("is-complete"));
      document.querySelector('[data-stage="validating_final_report"]')?.classList.add("is-active");
    }
  };
  const poll = async () => {
    try {
      const response = await fetch(`/api/analyses/${analysisId}`, { headers: { "Accept": "application/json" } });
      const payload = await response.json();
      if (!response.ok) throw new Error("status unavailable");
      if (payload.status === "completed") { window.location.reload(); return; }
      if (payload.status === "failed") {
        alertBox.textContent = payload.error?.message || "Analysis failed."; alertBox.classList.remove("d-none"); return;
      }
      mark(payload); window.setTimeout(poll, 900);
    } catch (_error) {
      alertBox.textContent = "Status is temporarily unavailable. Retrying…"; alertBox.classList.remove("d-none"); window.setTimeout(poll, 2500);
    }
  };
  poll();
});
