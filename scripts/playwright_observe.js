async page => {
  await page.addInitScript(() => {
    window.__webPerfAudit = {
      lcp: null,
      cls: 0,
      shiftCount: 0,
      clsWindowStart: null,
      clsWindowLast: null,
      clsWindowValue: 0,
      longTasks: [],
      unsupported: [],
    };

    const state = window.__webPerfAudit;
    const observe = (type, callback) => {
      try {
        new PerformanceObserver(callback).observe({ type, buffered: true });
      } catch (error) {
        state.unsupported.push({ type, error: String(error) });
      }
    };

    observe("largest-contentful-paint", list => {
      const entries = list.getEntries();
      const entry = entries[entries.length - 1];
      if (!entry) return;
      state.lcp = {
        startTime: entry.startTime,
        size: entry.size,
        url: entry.url || null,
        element: entry.element ? entry.element.tagName : null,
      };
    });

    observe("layout-shift", list => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput) {
          state.shiftCount += 1;
          const startsNewWindow = state.clsWindowStart === null
            || entry.startTime - state.clsWindowLast >= 1000
            || entry.startTime - state.clsWindowStart > 5000;
          if (startsNewWindow) {
            state.clsWindowStart = entry.startTime;
            state.clsWindowValue = entry.value;
          } else {
            state.clsWindowValue += entry.value;
          }
          state.clsWindowLast = entry.startTime;
          state.cls = Math.max(state.cls, state.clsWindowValue);
        }
      }
    });

    observe("longtask", list => {
      for (const entry of list.getEntries()) {
        state.longTasks.push({ startTime: entry.startTime, duration: entry.duration });
      }
    });
  });
  return "performance observers will initialize on the next navigation";
}
