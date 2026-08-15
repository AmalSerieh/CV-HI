"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("analysis-form");
  if (!form) return;
  const input = document.getElementById("resume-file");
  const dropZone = document.getElementById("drop-zone");
  const selected = document.getElementById("selected-file");
  const errorBox = document.getElementById("form-error");
  const submit = document.getElementById("submit-analysis");
  const provider = document.getElementById("ai-provider");
  const model = document.getElementById("ai-model");
  const outputLanguage = document.getElementById("output-language");
  const rewriteToggle = document.getElementById("enable_rewrites");
  const rewriteOptions = document.getElementById("rewrite-options");
  const rewriteExperience = document.getElementById("rewrite_experience");
  const bulletRewriteOptions = document.getElementById("bullet-rewrite-options");
  const providerHelp = document.querySelectorAll(".provider-help");
  const bulletModes = document.querySelectorAll(".bullet-mode");
  const bulletCount = document.getElementById("bullet-count-field");
  const bulletSelection = document.getElementById("bullet-selection-field");
  const bulletAllWarning = document.getElementById("bullet-all-warning");

  const showError = (message) => {
    errorBox.textContent = message;
    errorBox.classList.remove("d-none");
    errorBox.focus();
  };
  const clearError = () => { errorBox.textContent = ""; errorBox.classList.add("d-none"); };
  const describeFile = () => {
    const file = input.files[0];
    selected.textContent = file ? `${file.name} · ${(file.size / 1048576).toFixed(2)} MB` : "No file selected";
  };
  ["dragenter", "dragover"].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
    event.preventDefault(); dropZone.classList.add("is-dragging");
  }));
  ["dragleave", "drop"].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
    event.preventDefault(); dropZone.classList.remove("is-dragging");
  }));
  dropZone.addEventListener("drop", (event) => {
    if (event.dataTransfer.files.length) { input.files = event.dataTransfer.files; describeFile(); }
  });
  input.addEventListener("change", describeFile);
  const updateRewriteVisibility = () => {
    const enabled = Boolean(rewriteToggle?.checked && !rewriteToggle.disabled);
    rewriteOptions?.classList.toggle("d-none", !enabled);
    bulletRewriteOptions?.classList.toggle(
      "d-none",
      !enabled || !rewriteExperience?.checked
    );
  };
  const updateProvider = () => {
    if (!provider) return;
    const selectedProvider = provider.value;
    const usesModel = selectedProvider !== "none";
    if (model) {
      model.disabled = !usesModel;
      model.required = usesModel;
    }
    if (outputLanguage) {
      outputLanguage.disabled = !usesModel;
    }
    if (rewriteToggle) {
      rewriteToggle.disabled = !usesModel;
      if (!usesModel) rewriteToggle.checked = false;
    }
    if (selectedProvider === "ollama" && model && !model.value.trim()) {
      model.value = model.dataset?.defaultModel || "gemma3:4b";
    }
    if (
      selectedProvider === "transformers"
      && model
      && model.dataset?.configuredProvider === "ollama"
      && model.value === model.dataset?.defaultModel
    ) {
      model.value = "";
    }
    providerHelp.forEach((element) => {
      element.classList.toggle("d-none", element.id !== `provider-help-${selectedProvider}`);
    });
    updateRewriteVisibility();
  };
  provider.addEventListener("change", updateProvider);
  rewriteToggle?.addEventListener("change", updateRewriteVisibility);
  rewriteExperience?.addEventListener("change", updateRewriteVisibility);
  const updateBulletMode = () => {
    const mode = document.querySelector(".bullet-mode:checked")?.value || "first";
    bulletCount.classList.toggle("d-none", mode !== "first");
    bulletSelection.classList.toggle("d-none", mode !== "specific");
    bulletAllWarning.classList.toggle("d-none", mode !== "all");
  };
  bulletModes.forEach((radio) => radio.addEventListener("change", updateBulletMode));
  updateProvider();
  updateRewriteVisibility();
  updateBulletMode();
  form.addEventListener("submit", async (event) => {
    event.preventDefault(); clearError();
    const file = input.files[0];
    if (!file) { showError("Select a PDF or DOCX resume."); return; }
    const extension = file.name.toLowerCase().split(".").pop();
    if (!["pdf", "docx"].includes(extension)) { showError("Only PDF and DOCX resumes are supported."); return; }
    const data = new FormData(form);
    document.querySelectorAll(".feature-toggle").forEach((toggle) => data.set(toggle.name, toggle.checked ? "true" : "false"));
    if (submit) { submit.disabled = true; submit.textContent = "Uploading…"; }
    try {
      const response = await fetch("/api/analyses", { method: "POST", body: data, headers: { "Accept": "application/json" } });
      const payload = await response.json();
      if (!response.ok) {
        const message = payload.error?.message || payload.detail || "The analysis could not be started.";
        showError(typeof message === "string" ? message : "Check the submitted fields.");
        return;
      }
      window.location.assign(payload.page_url);
    } catch (_error) {
      showError("The local application could not be reached. Try again.");
    } finally {
      if (submit) { submit.disabled = false; submit.textContent = "Start analysis"; }
    }
  });
});
const form = document.getElementById('analysis-form');
const progressContainer = document.getElementById('analysis-progress-container');
const submitBtn = document.getElementById('submit-analysis');

form.addEventListener('submit', function(e) {
    // إظهار شريط التقدم
    if (progressContainer) {
        progressContainer.classList.remove('d-none');
    }

    // إيقاف الزر مؤقتاً لمنع التكرار
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.style.opacity = '0.7';
    }
});