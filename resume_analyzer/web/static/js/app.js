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
});
