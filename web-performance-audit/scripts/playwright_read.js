async page => page.evaluate(() => {
  const state = window.__webPerfAudit || {};
  const paints = performance.getEntriesByType("paint");
  const fcpEntry = paints.find(entry => entry.name === "first-contentful-paint");
  const fcp = fcpEntry ? fcpEntry.startTime : null;
  const navigation = performance.getEntriesByType("navigation")[0];
  const longTasks = Array.isArray(state.longTasks) ? state.longTasks : [];
  const afterFcp = fcp === null
    ? []
    : longTasks.filter(task => task.startTime + task.duration > fcp);
  const observedBlocking = afterFcp.reduce((total, task) => {
    const blockingStart = task.startTime + 50;
    const observedStart = Math.max(blockingStart, fcp);
    return total + Math.max(0, task.startTime + task.duration - observedStart);
  }, 0);

  return JSON.stringify({
    sampled_at_ms_since_navigation: Math.round(performance.now()),
    fcp_ms: fcp === null ? null : Math.round(fcp),
    lcp_ms: state.lcp ? Math.round(state.lcp.startTime) : null,
    lcp_element: state.lcp ? state.lcp.element : null,
    lcp_url: state.lcp ? state.lcp.url : null,
    cls: Math.round((state.cls || 0) * 1000) / 1000,
    shift_events: state.shiftCount || 0,
    observed_long_tasks: longTasks.length,
    observed_long_task_blocking_after_fcp_ms: Math.round(observedBlocking),
    navigation: navigation ? {
      ttfb_ms: Math.round(navigation.responseStart),
      dom_content_loaded_ms: Math.round(navigation.domContentLoadedEventEnd),
      load_event_ms: Math.round(navigation.loadEventEnd),
    } : null,
    unsupported_observers: state.unsupported || [],
    caveat: "Observed long-task blocking is not Lighthouse TBT; the sample ends when this script runs.",
  }, null, 2);
})
