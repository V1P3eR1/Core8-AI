'use strict';
/*
 * Proposed meeting slots. These are suggestions built from fixed working hours
 * only: the tool has no calendar access, so a human must check availability
 * before offering any of them. Dates are local to the machine running the tool.
 */
const pad = (n) => (n < 10 ? '0' : '') + n;

function proposeSlots(now, opts) {
  const o = Object.assign({ days: [0, 1, 2, 3, 4], times: ['10:00', '14:00', '16:30'], count: 3 }, opts || {});
  const out = [];
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12, 0, 0);
  let guard = 0;
  while (out.length < o.count && guard++ < 30) {
    d.setDate(d.getDate() + 1);
    if (!o.days.includes(d.getDay())) continue;
    out.push({
      date: d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()),
      time: o.times[out.length % o.times.length],
      calendarChecked: false
    });
  }
  return out;
}

module.exports = { proposeSlots };
