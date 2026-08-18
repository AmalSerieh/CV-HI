"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const page = document.querySelector("[data-final-resume-page]");
  if (!page) return;

  const modal = document.getElementById("template-modal");
  const generate = document.getElementById("generate-resume");
  const status = document.getElementById("download-status");
  if (!modal || !generate || !status) return;

  let templateId = null;
  document.querySelectorAll(".template-choice").forEach((choice) => {
    choice.addEventListener("change", () => {
      templateId = choice.value;
      generate.disabled = false;
      document.querySelectorAll(".template-option").forEach((option) => {
        option.classList.toggle("is-selected", option.contains(choice));
      });
    });
  });

  generate.addEventListener("click", async () => {
    if (!templateId) return;
    generate.disabled = true;
    status.classList.remove("d-none", "alert-warning");
    status.classList.add("alert-secondary");
    status.textContent = "Generating your Word resume…";
    try {
      const response = await fetch(modal.dataset.downloadUrl, {
        method: "POST",
        headers: {
          "Accept": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ template_id: templateId })
      });
      if (!response.ok) throw new Error("resume_download_failed");
      const disposition = response.headers.get("Content-Disposition") || "";
      const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      const plainName = disposition.match(/filename="([^"]+)"/i);
      const filename = encodedName
        ? decodeURIComponent(encodedName[1])
        : (plainName ? plainName[1] : "Optimized-Resume.docx");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      status.textContent = "Your Word resume is ready.";
    } catch (_error) {
      status.classList.remove("alert-secondary");
      status.classList.add("alert-warning");
      status.textContent = "The Word resume could not be generated. Please try again.";
    } finally {
      generate.disabled = false;
    }
  });
});
