(function () {
  "use strict";

  const timeZone = "Europe/Berlin";
  let calendarElement;
  let statusElement;
  let dialog;

  function words(value) {
    return String(value || "event").trim().replace(/[-_]+/g, " ");
  }

  function sentenceCase(value) {
    const text = words(value);
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function eventTitle(event) {
    const match = String(event.session_id || "").match(/(?:^|-)session-(\d+)/i);
    const type = sentenceCase(event.type);
    return match ? `Session ${match[1].padStart(2, "0")} — ${type}` : type;
  }

  function categoryClass(type) {
    return words(type).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  function calendarEvent(event, index) {
    const date = String(event.date || "");
    return {
      id: event.event_id || `course-event-${index + 1}`,
      title: eventTitle(event),
      start: `${date}T${event.start}:00`,
      end: `${date}T${event.end}:00`,
      classNames: [categoryClass(event.type)],
      extendedProps: {
        source: event,
        location: event.location || ""
      }
    };
  }

  function addDetail(list, term, value) {
    if (!value) return;
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = term;
    dd.textContent = value;
    list.append(dt, dd);
  }

  function materialLabel(material) {
    return sentenceCase(material.type || "material");
  }

  function showDetails(info) {
    const source = info.event.extendedProps.source || {};
    dialog.querySelector("#event-details-title").textContent = info.event.title;
    const body = dialog.querySelector("#event-details-body");
    body.replaceChildren();

    const list = document.createElement("dl");
    list.className = "calendar-detail-list";
    addDetail(list, "Session", source.session_id ? eventTitle(source) : sentenceCase(source.type));
    addDetail(list, "Date", source.date);
    addDetail(list, "Time", source.start && source.end ? `${source.start}–${source.end}` : source.start || source.end);
    addDetail(list, "Location", source.location);

    if (Array.isArray(source.materials) && source.materials.length) {
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      const links = document.createElement("ul");
      dt.textContent = "Materials";
      links.className = "calendar-materials";
      source.materials.forEach((material) => {
        if (!material || !material.path) return;
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.href = material.path;
        link.textContent = materialLabel(material);
        item.append(link);
        links.append(item);
      });
      if (links.childElementCount) {
        dd.append(links);
        list.append(dt, dd);
      }
    }

    body.append(list);
    dialog.showModal();
  }

  function typingTarget(target) {
    return target instanceof HTMLElement &&
      (target.matches("input, textarea, select") || target.isContentEditable);
  }

  async function initialize() {
    try {
      const response = await fetch(new URL("course.yml", document.baseURI));
      if (!response.ok) throw new Error(`course.yml returned ${response.status}`);
      const course = jsyaml.load(await response.text(), {schema: jsyaml.JSON_SCHEMA});
      const sourceEvents = Array.isArray(course.events) ? course.events : [];
      const events = sourceEvents
        .filter((event) => event && event.date && event.start && event.end)
        .map(calendarEvent);

      if (typeof EventCalendar !== "function") {
        throw new Error("The EventCalendar library did not load.");
      }

      const calendar = new EventCalendar(calendarElement, {
        view: "dayGridMonth",
        date: events.length ? events[0].start.slice(0, 10) : undefined,
        timeZone,
        firstDay: 1,
        weekends: false,
        nowIndicator: true,
        height: "auto",
        headerToolbar: {
          start: "prev,next today",
          center: "title",
          end: "dayGridMonth,timeGridWeek,listWeek"
        },
        buttonText: {
          today: "Today",
          dayGridMonth: "Month",
          timeGridWeek: "Week",
          listWeek: "Schedule"
        },
        events,
        eventClick: showDetails
      });

      statusElement.textContent = events.length === sourceEvents.length
        ? ""
        : `${sourceEvents.length - events.length} incomplete schedule item(s) could not be displayed.`;

      document.addEventListener("keydown", (keyboardEvent) => {
        if (typingTarget(keyboardEvent.target)) return;
        if (keyboardEvent.key === "ArrowLeft") calendar.prev();
        else if (keyboardEvent.key === "ArrowRight") calendar.next();
        else if (keyboardEvent.key.toLowerCase() === "t") calendar.today();
        else return;
        keyboardEvent.preventDefault();
      });
    } catch (error) {
      statusElement.textContent = "The course schedule could not be loaded. Please reload the page.";
      statusElement.classList.add("text-danger");
      console.error("Calendar initialization failed:", error);
    }
  }

  function start() {
    calendarElement = document.getElementById("ec");
    statusElement = document.getElementById("calendar-status");
    dialog = document.getElementById("event-details");

    if (!calendarElement || !statusElement || !dialog) {
      console.error("Calendar initialization failed: required page elements are missing.");
      return;
    }

    const closeButton = dialog.querySelector(".calendar-dialog-close");
    if (closeButton) {
      closeButton.addEventListener("click", () => dialog.close());
    }
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    initialize();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, {once: true});
  } else {
    start();
  }
}());
