(function () {
  "use strict";

  const statusByComparison = {
    past: ["🟢 Completed", "status-completed"],
    today: ["🟡 Today", "status-today"],
    future: ["⚪ Upcoming", "status-upcoming"],
  };
  const statusClasses = Object.values(statusByComparison).map((status) => status[1]);

  function berlinDate() {
    const parts = new Intl.DateTimeFormat("en", {
      timeZone: "Europe/Berlin",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(new Date());
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${values.year}-${values.month}-${values.day}`;
  }

  function isIsoDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;

    const [year, month, day] = value.split("-").map(Number);
    const parsed = new Date(Date.UTC(year, month - 1, day));
    return parsed.getUTCFullYear() === year
      && parsed.getUTCMonth() === month - 1
      && parsed.getUTCDate() === day;
  }

  function updateSessionStatuses() {
    const today = berlinDate();

    document.querySelectorAll(".session-status").forEach((element) => {
      const eventDate = element.dataset.date || "";
      if (!isIsoDate(eventDate)) return;

      const comparison = eventDate < today
        ? "past"
        : eventDate === today ? "today" : "future";
      const [label, statusClass] = statusByComparison[comparison];

      element.textContent = label;
      element.classList.remove(...statusClasses);
      element.classList.add(statusClass);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", updateSessionStatuses);
  } else {
    updateSessionStatuses();
  }
  window.addEventListener("pageshow", updateSessionStatuses);
  window.setInterval(updateSessionStatuses, 60 * 1000);
}());
