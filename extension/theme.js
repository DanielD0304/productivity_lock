// Runs before the page paints, so a chosen theme never flashes the other one first.
(function () {
  let choice = null;
  try {
    choice = localStorage.getItem("plock-theme");
  } catch {
    // Storage blocked: follow the system.
  }
  if (choice === "light" || choice === "dark") document.documentElement.dataset.theme = choice;
})();
