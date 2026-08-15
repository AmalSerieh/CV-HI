"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const directionToggle = document.getElementById("direction-toggle");
  if (directionToggle) {
    directionToggle.addEventListener("click", () => {
      const root = document.documentElement;
      const next = root.getAttribute("dir") === "rtl" ? "ltr" : "rtl";
      root.setAttribute("dir", next);
    });
  }

  // Initialize Bootstrap Popovers (for Academic References) & Tooltips
  if (typeof bootstrap !== "undefined") {
    const popoverTriggerList = Array.from(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.forEach((popoverTriggerEl) => {
      new bootstrap.Popover(popoverTriggerEl, {
        html: true,
        trigger: "hover focus click",
        sanitize: false
      });
    });

    const tooltipTriggerList = Array.from(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach((tooltipTriggerEl) => {
      new bootstrap.Tooltip(tooltipTriggerEl);
    });
  }
});
