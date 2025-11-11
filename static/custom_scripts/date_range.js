

const Temporal = temporal.Temporal;
if (!Temporal) {
  throw new Error('Temporal API is not available. Please include the Temporal polyfill before date_range.js.');
}

console.log('Temporal API is available.');

function parseToPlainDate(referenceDateStr) {
  try {
    if (referenceDateStr.includes('T') || referenceDateStr.includes(' ')) {
      return Temporal.PlainDateTime.from(referenceDateStr).toPlainDate();
    }
    return Temporal.PlainDate.from(referenceDateStr);
  } catch (e) {
    const dateOnly = referenceDateStr.split('T')[0].split(' ')[0];
    return Temporal.PlainDate.from(dateOnly);
  }
}

// Compute [start, endExclusive] for given reference, viewMode, offset.
// referenceDateStr is timezone-less local string (e.g., '2025-09-03T14:30:00').
// timeZone is currently unused for civil math but kept for future adjustments.
function computeDateRange(referenceDateStr, viewMode, offset = 0, timeZone) {
  const vm = String(viewMode).toLowerCase();
  const ref = parseToPlainDate(referenceDateStr);

  if (vm === 'daily') {
    const start = ref.add({ days: offset });
    const endExclusive = start.add({ days: 1 });
    return { start, endExclusive };
  }

  if (vm === 'weekly') {
    const shifted = ref.add({ days: offset * 7 });
    const subtractDays = shifted.dayOfWeek - 1; // Monday=1..Sunday=7
    const start = shifted.subtract({ days: subtractDays });
    const endExclusive = start.add({ days: 7 });
    return { start, endExclusive };
  }

  if (vm === 'monthly') {
    const start = ref.with({ day: 1 }).add({ months: offset });
    const endExclusive = start.add({ months: 1 });
    return { start, endExclusive };
  }

  throw new Error('Unsupported view mode: ' + viewMode);
}

// Ordinal suffix (1st, 2nd, 3rd, 4th, ...)
function ordinal(day) {
  if (day % 100 >= 11 && day % 100 <= 13) return day + 'th';
  const suf = { 1: 'st', 2: 'nd', 3: 'rd' }[day % 10] || 'th';
  return day + suf;
}

const MONTH_NAMES = [
  'January','February','March','April','May','June','July','August','September','October','November','December'
];
const MONTH_ABBR = [
  'Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'
];

function formatDateWithOrdinalCivil(y, m, d) {
  return `${ordinal(d)} ${MONTH_NAMES[m - 1]} ${y}`;
}

// Format the current range label (Daily/Weekly/Monthly)
function formatDateRangeLabelInternal(viewMode, start, endExclusive) {
  const vm = String(viewMode).toLowerCase();
  if (vm === 'daily') {
    return formatDateWithOrdinalCivil(start.year, start.month, start.day);
  }
  if (vm === 'weekly') {
    const endInc = endExclusive.subtract({ days: 1 });
    const sameYear = start.year === endInc.year;
    const sameMonth = sameYear && (start.month === endInc.month);
    if (!sameYear) {
      return `${start.day} ${MONTH_ABBR[start.month - 1]} ${start.year} – ${endInc.day} ${MONTH_ABBR[endInc.month - 1]} ${endInc.year}`;
    }
    if (!sameMonth) {
      return `${start.day} ${MONTH_ABBR[start.month - 1]} – ${endInc.day} ${MONTH_ABBR[endInc.month - 1]}`;
    }
    return `${start.day}–${endInc.day} ${MONTH_ABBR[start.month - 1]}`;
  }
  if (vm === 'monthly') {
    return `${MONTH_NAMES[start.month - 1]} ${start.year}`;
  }
  throw new Error('Unsupported view mode: ' + viewMode);
}

// Convenience: return ISO YYYY-MM-DD strings for start and endExclusive
// No padding helpers needed; Temporal.PlainDate.toString() returns YYYY-MM-DD

// Expose globals
window.computeDateRange = computeDateRange;
window.formatDateRangeLabel = (referenceDateStr, viewMode, offset = 0, timeZone) => {
  const { start, endExclusive } = computeDateRange(referenceDateStr, viewMode, offset, timeZone);
  return formatDateRangeLabelInternal(viewMode, start, endExclusive);
};
window.computeDateRangeISO = (referenceDateStr, viewMode, offset = 0, timeZone) => {
  const { start, endExclusive } = computeDateRange(referenceDateStr, viewMode, offset, timeZone);
  return { start: start.toString(), endExclusive: endExclusive.toString() };
};
