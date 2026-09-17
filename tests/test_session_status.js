const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync("assets/session-status.js", "utf8");

function loadStatusScript(now, dates) {
  let currentTime = now;
  const elements = dates.map((date) => ({
    dataset: { date },
    textContent: "fallback",
    classes: new Set(["session-status", "status-upcoming"]),
    classList: {
      add(...names) { names.forEach((name) => this.owner.classes.add(name)); },
      remove(...names) { names.forEach((name) => this.owner.classes.delete(name)); },
    },
  }));
  elements.forEach((element) => { element.classList.owner = element; });

  const listeners = {};
  let interval;
  const RealDate = Date;
  class FakeDate extends RealDate {
    constructor(...args) { super(...(args.length ? args : [currentTime])); }
  }
  FakeDate.UTC = RealDate.UTC;

  const context = {
    Date: FakeDate,
    Intl,
    document: {
      readyState: "complete",
      querySelectorAll: () => elements,
    },
    window: {
      addEventListener: (name, callback) => { listeners[name] = callback; },
      setInterval: (callback, delay) => { interval = { callback, delay }; },
    },
  };
  vm.runInNewContext(source, context);
  return {
    elements,
    listeners,
    interval,
    setNow(value) { currentTime = value; },
  };
}

test("sets past, current, and future statuses using the Berlin date", () => {
  const result = loadStatusScript("2027-01-02T12:00:00Z", [
    "2027-01-01", "2027-01-02", "2027-01-03",
  ]);

  assert.deepEqual(result.elements.map((element) => element.textContent), [
    "🟢 Completed", "🟡 Today", "⚪ Upcoming",
  ]);
  assert.ok(result.elements[0].classes.has("status-completed"));
  assert.ok(result.elements[1].classes.has("status-today"));
  assert.ok(result.elements[2].classes.has("status-upcoming"));
});

test("refreshes every minute and after back-forward cache restoration", () => {
  const result = loadStatusScript("2027-01-01T22:59:30Z", ["2027-01-02"]);
  assert.equal(result.elements[0].textContent, "⚪ Upcoming");
  assert.equal(result.interval.delay, 60000);

  result.setNow("2027-01-01T23:00:30Z");
  result.interval.callback();
  assert.equal(result.elements[0].textContent, "🟡 Today");
  result.elements[0].textContent = "stale";
  result.listeners.pageshow();
  assert.equal(result.elements[0].textContent, "🟡 Today");
});

test("leaves missing and invalid dates at their server-rendered fallback", () => {
  const result = loadStatusScript("2027-01-02T12:00:00Z", ["", "2027-02-30"]);
  assert.deepEqual(result.elements.map((element) => element.textContent), [
    "fallback", "fallback",
  ]);
});
