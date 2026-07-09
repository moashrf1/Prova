(() => {
  "use strict";

  const statGrid = document.getElementById("stat-grid");
  const periodButtons = document.querySelectorAll(".period-toggle button");

  function formatDuration(totalSeconds) {
    const totalMinutes = Math.round(totalSeconds / 60);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    if (hours === 0) return `${minutes}m`;
    return `${hours}h ${minutes}m`;
  }

  function renderStatCards(recap) {
    const cards = [
      { value: recap.session_count, label: "Sessions" },
      { value: formatDuration(recap.total_duration_seconds), label: "Time logged" },
      { value: recap.decision_count, label: "Decisions" },
      { value: recap.skills_fetched_count, label: "Skills fetched" },
    ];
    statGrid.innerHTML = cards
      .map(
        (card) => `
        <div class="stat-card">
          <div class="value num">${card.value}</div>
          <div class="label">${card.label}</div>
        </div>`
      )
      .join("");
  }

  function renderError(container, message) {
    container.innerHTML = `<div class="error-state">${message}</div>`;
  }

  async function loadRecap(period) {
    statGrid.querySelectorAll(".stat-card").forEach((card) => card.classList.add("is-loading"));
    try {
      const response = await fetch(`/api/recap?period=${encodeURIComponent(period)}`);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed (${response.status})`);
      }
      const recap = await response.json();
      renderStatCards(recap);
      return recap;
    } catch (err) {
      renderError(statGrid, err.message || "Could not load the recap.");
    }
  }

  periodButtons.forEach((button) => {
    button.addEventListener("click", () => {
      periodButtons.forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
      loadRecap(button.dataset.period);
    });
  });

  loadRecap("weekly");
})();
