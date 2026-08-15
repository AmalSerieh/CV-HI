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
  // Console log resume analysis calculations for user debugging
  try {
    const reportScript = document.getElementById("analysis-report-json");
    if (reportScript && reportScript.textContent) {
      const reportData = JSON.parse(reportScript.textContent);
      console.group("%c📊 Resume Intelligence Scoring Engine - Calculation Debugger", "color: #0d6efd; font-size: 14px; font-weight: bold;");
      console.log("%c🎯 Overall Score:", "font-weight: bold; font-size: 13px; color: #198754;", (reportData.overall_score !== undefined ? reportData.overall_score : reportData.scoring_engine?.overall_score || 0), "/ 100");
      console.log("📑 Full Analysis Report Object:", reportData);
      console.log("⚠️ Applied Penalties:", reportData.all_penalties || reportData.scoring_engine?.all_penalties || []);
      console.log("❗ Missing Elements:", reportData.all_missing_elements || reportData.scoring_engine?.all_missing_elements || []);

      const scoreBd = reportData.score_breakdown || reportData.scoring_engine?.score_breakdown || {};
      if (Object.keys(scoreBd).length > 0) {
        console.group("🔢 Section Breakdown (7 Evaluation Modules):");
        const tableData = {};
        for (const [secKey, secVal] of Object.entries(scoreBd)) {
          tableData[secKey] = {
            "Module Name (EN)": secVal.section_name || secKey,
            "Module Name (AR)": secVal.section_name_ar || secKey,
            "Weight": secVal.weight_percentage || "N/A",
            "Score": `${secVal.score !== undefined ? secVal.score : 0} / ${secVal.max_score || 100}`,
            "Percentage": `${secVal.percentage !== undefined ? secVal.percentage : (secVal.normalized_100 || 0)}%`,
            "Status": secVal.status_ar || secVal.status || "N/A"
          };
        }
        console.table(tableData);
        console.groupEnd();
      }
      console.groupEnd();
    }
  } catch (err) {
    console.warn("Could not parse analysis report for console logging:", err);
  }

  // Initialize Bootstrap Popovers for Academic References and Citations
  if (typeof bootstrap !== 'undefined' && bootstrap.Popover) {
    const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
    [...popoverTriggerList].forEach(popoverTriggerEl => {
      new bootstrap.Popover(popoverTriggerEl, {
        html: true,
        trigger: 'hover focus click',
        sanitize: false
      });
    });
  }

  // Initialize Bootstrap Tooltips
  if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].forEach(tooltipTriggerEl => {
      new bootstrap.Tooltip(tooltipTriggerEl);
    });
  }

  document.getElementById("print-result")?.addEventListener("click", () => window.print());
  const jsonSection = document.getElementById("json");
  const loadJson = document.getElementById("load-json");
  const copyJson = document.getElementById("copy-json");
  const rawJson = document.getElementById("raw-json");
  const jsonStatus = document.getElementById("json-status");
  loadJson?.addEventListener("click", async () => {
    if (loadJson) {
      loadJson.disabled = true;
      loadJson.textContent = "Loading…";
    }
    try {
      if (!jsonSection?.dataset?.resultUrl) throw new Error("no_result_url");
      const response = await fetch(jsonSection.dataset.resultUrl, {
        headers: { "Accept": "application/json" }
      });
      if (!response.ok) throw new Error("json_request_failed");
      const payload = await response.json();
      if (rawJson) {
        rawJson.textContent = JSON.stringify(payload, null, 2);
        rawJson.classList.remove("d-none");
      }
      if (jsonStatus) {
        jsonStatus.classList.add("d-none");
      }
      if (copyJson) {
        copyJson.disabled = false;
      }
      if (loadJson) {
        loadJson.textContent = "JSON loaded";
      }
    } catch (_error) {
      if (jsonStatus) {
        jsonStatus.textContent = "The technical JSON could not be loaded. Use Download JSON instead.";
        jsonStatus.classList.remove("alert-secondary");
        jsonStatus.classList.add("alert-warning");
      }
      if (loadJson) {
        loadJson.disabled = false;
        loadJson.textContent = "Try again";
      }
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
