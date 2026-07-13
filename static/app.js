(() => {
  "use strict";

  // The only career path currently defined in skills/*.md frontmatter.
  // A path picker would be over-engineering for a single-path personal demo;
  // add one if/when a second path exists.
  const LEARNING_PATH = "product-manager";

  const statGrid = document.getElementById("stat-grid");
  const periodButtons = document.querySelectorAll(".period-toggle button");
  const pathContainer = document.getElementById("path-container");
  const projectsContainer = document.getElementById("projects-container");
  const decisionsContainer = document.getElementById("decisions-container");
  const tokenSavingsContainer = document.getElementById("token-savings-container");

  const style = getComputedStyle(document.documentElement);
  const cssVar = (name) => style.getPropertyValue(name).trim();

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

  function renderTokenSavingsHeadline(period, tokenSaving) {
    if (!tokenSaving || tokenSaving.baseline_tokens_est == null) {
      tokenSavingsContainer.innerHTML =
        '<div class="empty-state">No library snapshot yet -- run the MCP server once to initialize it.</div>';
      return;
    }
    const pct = tokenSaving.saving_pct != null ? `${tokenSaving.saving_pct}%` : "–";
    const periodLabel = period === "monthly" ? "this month" : "this week";
    tokenSavingsContainer.innerHTML = `
      <div class="token-card">
        <div class="token-headline">
          <span class="token-pct num">${pct}</span>
          <span class="token-sublabel">fewer context tokens served ${periodLabel}</span>
        </div>
        <div class="token-detail">${tokenSaving.actual_tokens_est.toLocaleString()} tokens served vs. ${tokenSaving.baseline_tokens_est.toLocaleString()} if the whole library had been loaded up front (~${tokenSaving.saving_tokens_est.toLocaleString()} avoided)</div>
        <div class="token-chart-wrap"><canvas id="chart-token-comparison" role="img" aria-label="Bar chart comparing actual vs baseline tokens across weekly, monthly, and all-time windows"></canvas></div>
        <div class="token-caveat">${tokenSaving.label}.</div>
      </div>`;
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
      renderTokenSavingsHeadline(period, recap.token_saving);
      loadTokenComparisonChart();
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

  async function fetchJson(url) {
    const response = await fetch(url);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${response.status})`);
    }
    return response.json();
  }

  // Shared bar-chart styling: single accent hue per chart (each chart is one
  // series, so no categorical palette or legend is needed -- the card title
  // already names the series), recessive gridlines, muted axis text, the
  // library's default hover tooltip.
  function barChartOptions() {
    const gridColor = cssVar("--border");
    const tickColor = cssVar("--ink-muted");
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: tickColor } },
        y: {
          beginAtZero: true,
          grid: { color: gridColor },
          ticks: { color: tickColor, precision: 0 },
        },
      },
    };
  }

  function renderBarChart(canvasId, labels, data, valueLabel) {
    const canvas = document.getElementById(canvasId);
    new Chart(canvas, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: valueLabel,
            data,
            backgroundColor: cssVar("--accent"),
            borderRadius: 4,
            maxBarThickness: 48,
          },
        ],
      },
      options: barChartOptions(),
    });
  }

  let tokenComparisonChart = null;

  async function loadTokenComparisonChart() {
    let weekly, monthly, cumulative;
    try {
      [weekly, monthly, cumulative] = await Promise.all([
        fetchJson("/api/token-report?period=weekly"),
        fetchJson("/api/token-report?period=monthly"),
        fetchJson("/api/token-report"),
      ]);
    } catch (err) {
      return; // headline card above already surfaces the error state
    }
    if (weekly.baseline_tokens_est == null) return; // no snapshot yet

    const windows = [weekly, monthly, cumulative];
    const canvas = document.getElementById("chart-token-comparison");
    if (!canvas) return;

    if (tokenComparisonChart) {
      tokenComparisonChart.destroy();
    }
    const gridColor = cssVar("--border");
    const tickColor = cssVar("--ink-muted");
    tokenComparisonChart = new Chart(canvas, {
      type: "bar",
      data: {
        labels: ["This week", "This month", "All time"],
        datasets: [
          {
            label: "Baseline (whole library)",
            data: windows.map((w) => w.baseline_tokens_est),
            backgroundColor: tickColor,
            borderRadius: 4,
            maxBarThickness: 40,
          },
          {
            label: "Actual (served)",
            data: windows.map((w) => w.actual_tokens_est),
            backgroundColor: cssVar("--accent"),
            borderRadius: 4,
            maxBarThickness: 40,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: "bottom",
            labels: { color: cssVar("--ink"), boxWidth: 12, font: { size: 11 } },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: tickColor } },
          y: {
            beginAtZero: true,
            grid: { color: gridColor },
            ticks: { color: tickColor, precision: 0 },
          },
        },
      },
    });
  }

  async function loadCharts() {
    try {
      const projects = await fetchJson("/api/projects");
      const withTime = projects.filter((p) => p.total_duration_seconds > 0);
      if (withTime.length === 0) {
        document.getElementById("chart-time-per-project").closest(".chart-card").innerHTML =
          '<h3>Time per project</h3><div class="empty-state">No completed sessions yet.</div>';
      } else {
        renderBarChart(
          "chart-time-per-project",
          withTime.map((p) => p.name),
          withTime.map((p) => Math.round((p.total_duration_seconds / 3600) * 10) / 10),
          "Hours logged"
        );
      }
    } catch (err) {
      renderError(document.getElementById("chart-grid"), err.message);
    }

    try {
      const skills = await fetchJson("/api/skills");
      const used = skills.filter((s) => s.fetch_count > 0);
      if (used.length === 0) {
        document.getElementById("chart-skill-usage").closest(".chart-card").innerHTML =
          '<h3>Skill fetch counts</h3><div class="empty-state">No skills fetched yet.</div>';
      } else {
        renderBarChart(
          "chart-skill-usage",
          used.map((s) => s.title),
          used.map((s) => s.fetch_count),
          "Times fetched"
        );
      }
    } catch (err) {
      renderError(document.getElementById("chart-grid"), err.message);
    }
  }

  async function loadLearningPath() {
    try {
      const stats = await fetchJson(`/api/learning-stats?path=${encodeURIComponent(LEARNING_PATH)}`);
      if (!stats.path_skill_total) {
        pathContainer.innerHTML = `<div class="empty-state">No skills tagged for the "${LEARNING_PATH}" path yet.</div>`;
        return;
      }
      const pct = Math.round((stats.path_skill_engaged_count / stats.path_skill_total) * 100);
      const chips = [
        ...stats.path_skills_fetched.map((name) => `<span class="skill-chip is-fetched" title="Fetched via get_skill">${name}</span>`),
        ...stats.path_skills_referenced_only.map((name) => `<span class="skill-chip is-referenced" title="Detected in worklog text, not explicitly fetched">${name}</span>`),
        ...stats.path_skills_remaining.map((name) => `<span class="skill-chip">${name}</span>`),
      ].join("");
      pathContainer.innerHTML = `
        <div class="path-card">
          <div class="path-summary">
            <span class="fraction">${stats.path_skill_engaged_count} of ${stats.path_skill_total}</span>
            <span class="path-name">${LEARNING_PATH} track skills engaged with</span>
          </div>
          <div class="path-bar"><div class="path-bar-fill" style="width: ${pct}%"></div></div>
          <div class="skill-chip-list">${chips}</div>
        </div>`;
    } catch (err) {
      renderError(pathContainer, err.message);
    }
  }

  async function loadProjects() {
    try {
      const projects = await fetchJson("/api/projects");
      if (projects.length === 0) {
        projectsContainer.innerHTML = '<div class="empty-state">No projects logged yet.</div>';
        return;
      }
      const rows = projects
        .map(
          (p) => `
          <tr>
            <td>${p.name}</td>
            <td>${p.status}</td>
            <td class="num">${p.session_count}</td>
            <td class="num">${formatDuration(p.total_duration_seconds)}</td>
            <td class="num">${p.last_activity ?? "&ndash;"}</td>
          </tr>`
        )
        .join("");
      projectsContainer.innerHTML = `
        <div class="table-wrap">
          <table class="projects">
            <thead>
              <tr>
                <th>Project</th><th>Status</th>
                <th class="num">Sessions</th><th class="num">Time logged</th><th class="num">Last activity</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`;
    } catch (err) {
      renderError(projectsContainer, err.message);
    }
  }

  async function loadDecisions() {
    try {
      const decisions = await fetchJson("/api/decisions?limit=10");
      if (decisions.length === 0) {
        decisionsContainer.innerHTML = '<div class="empty-state">No decisions logged yet.</div>';
        return;
      }
      const items = decisions
        .map(
          (d) => `
          <div class="decision-item">
            <div class="decision-header">
              <span class="decision-title">${d.decision}</span>
              <span class="decision-meta">${d.created_at} &middot; ${d.project}</span>
            </div>
            <div class="decision-reasoning">${d.reasoning}</div>
            ${d.rejected_alternative ? `<div class="decision-rejected"><strong>Rejected:</strong> ${d.rejected_alternative}</div>` : ""}
          </div>`
        )
        .join("");
      decisionsContainer.innerHTML = `<div class="decision-list">${items}</div>`;
    } catch (err) {
      renderError(decisionsContainer, err.message);
    }
  }

  loadRecap("weekly");
  loadCharts();
  loadLearningPath();
  loadProjects();
  loadDecisions();
})();
