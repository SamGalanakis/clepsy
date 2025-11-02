/* ---------- Insights: Time Spent per Tag (refactored to use createClepsyChart) ---------- */

/* ---------- Insights: Time Spent per Tag (window-aware, createClepsyChart-enabled) ---------- */

(function () {
  const TITLE = 'Time Spent per Tag';
  const TITLE_FONT = 14;
  const SUBTITLE_FONT = 11;
  const SUMMARY_FONT = 10;
  const HEADER_LINE_GAP = 4;
  const TITLE_GAP = 6;

  const DEFAULT_THEME = {
    chartBackground: 'transparent',
    grid: '#555',
    muted: '#999',
    text: '#ddd',
    productivity: {
      very_productive: '#4ade80',
      productive: '#22c55e',
      neutral: '#a3a3a3',
      distracting: '#f59e0b',
      very_distracting: '#ef4444',
    },
  };

  function normalizeTheme(theme) {
    const merged = Object.assign({}, DEFAULT_THEME, theme || {});
    merged.productivity = Object.assign(
      {},
      DEFAULT_THEME.productivity,
      (theme && theme.productivity) || {}
    );
    return merged;
  }

  function safeDate(value) {
    if (!value) return null;
    const d = new Date(value);
    return Number.isFinite(d.getTime()) ? d : null;
  }

  function formatWindowLabel(startIso, endIso) {
    const start = safeDate(startIso);
    const end = safeDate(endIso);
    if (!start || !end) return null;
    try {
      const fmt = new Intl.DateTimeFormat(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
      return `${fmt.format(start)} – ${fmt.format(end)}`;
    } catch (_) {
      return `${start.toISOString()} – ${end.toISOString()}`;
    }
  }

  function formatSummaryTimestamp(isoValue) {
    const dt = safeDate(isoValue);
    if (!dt) return null;
    try {
      const fmt = new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      });
      return fmt.format(dt);
    } catch (_) {
      return dt.toISOString();
    }
  }

  function buildHeaderLines(theme, { windowLabel, summary }) {
    const lines = [
      {
        text: TITLE,
        fontSize: TITLE_FONT,
        fontWeight: 600,
        fill: theme.text || '#ddd',
      },
    ];
    if (windowLabel) {
      lines.push({
        text: windowLabel,
        fontSize: SUBTITLE_FONT,
        fontWeight: 500,
        fill: theme.muted || '#999',
      });
    }
    if (summary) {
      lines.push({
        text: summary,
        fontSize: SUMMARY_FONT,
        fontWeight: 400,
        fill: theme.muted || '#999',
      });
    }
    return lines;
  }

  function attachLineOffsets(lines) {
    let cursor = 0;
    return lines.map((line, idx) => {
      const increment = line.fontSize + (idx === 0 ? 2 : HEADER_LINE_GAP);
      cursor += increment;
      return Object.assign({}, line, { y: cursor });
    });
  }

  function renderHeader(svg, width, linesWithOffsets) {
    linesWithOffsets.forEach((line) => {
      svg
        .append('text')
        .attr('x', width / 2)
        .attr('y', line.y)
        .attr('text-anchor', 'middle')
        .attr('fill', line.fill)
        .style('font-size', `${line.fontSize}px`)
        .style('font-weight', line.fontWeight)
        .text(line.text);
    });
  }

  function buildIntervals(spec, windowStart, windowEnd) {
    const events = (spec && spec.events) ? spec.events.slice() : [];
    if (!events.length) return [];
    events.sort((a, b) => new Date(a.event_time) - new Date(b.event_time));
    const intervals = [];
    let openTime = null;
    const startBound = windowStart.getTime();
    const endBound = windowEnd.getTime();

    for (const ev of events) {
      if (ev.event_type === 'open') {
        openTime = safeDate(ev.event_time) || openTime;
      } else if (ev.event_type === 'close' && openTime) {
        const closeTime = safeDate(ev.event_time);
        if (!closeTime) {
          openTime = null;
          continue;
        }
        const startMs = Math.max(openTime.getTime(), startBound);
        const endMs = Math.min(closeTime.getTime(), endBound);
        if (endMs > startMs) {
          intervals.push({
            start: new Date(startMs),
            end: new Date(endMs),
          });
        }
        openTime = null;
      }
    }

    if (openTime) {
      const startMs = Math.max(openTime.getTime(), startBound);
      if (endBound > startMs) {
        intervals.push({
          start: new Date(startMs),
          end: new Date(endBound),
        });
      }
    }

    return intervals;
  }

  function collectTagDurations(specs, windowStart, windowEnd) {
    const durations = new Map();
    const uniqueTagIds = new Set();
    let activeActivityCount = 0;

    for (const spec of specs) {
      const tags = (spec && spec.activity && Array.isArray(spec.activity.tags))
        ? spec.activity.tags
        : [];
      if (!tags.length) continue;
      const intervals = buildIntervals(spec, windowStart, windowEnd);
      if (!intervals.length) continue;
      activeActivityCount += 1;
      for (const tag of tags) {
        uniqueTagIds.add(tag.id ?? tag.name);
      }
      for (const interval of intervals) {
        const seconds = Math.max(0, (interval.end - interval.start) / 1000);
        if (!seconds) continue;
        for (const tag of tags) {
          const key = tag.id ?? tag.name ?? `tag-${durations.size}`;
          if (!durations.has(key)) {
            durations.set(key, {
              id: key,
              name: tag.name || `Tag ${key}`,
              seconds: 0,
            });
          }
          const entry = durations.get(key);
          entry.seconds += seconds;
        }
      }
    }

    const rows = Array.from(durations.values())
      .filter((d) => d.seconds > 0)
      .sort((a, b) => b.seconds - a.seconds || a.name.localeCompare(b.name));

    return { rows, uniqueTagIds, activeActivityCount };
  }

  function buildSummaryLabel(data, rows, uniqueTagCount, activeActivityCount) {
    const meta = (data && data.metadata) || {};
    const totalTagCount = Number.isFinite(meta.tag_count)
      ? meta.tag_count
      : uniqueTagCount;
    const totalActivityCount = Number.isFinite(meta.activity_count)
      ? meta.activity_count
      : (Array.isArray(data?.activity_specs) ? data.activity_specs.length : null);

    const parts = [];
    const visibleTags = rows.length;
    if (visibleTags) {
      let tagText = `Tags: ${visibleTags}`;
      if (totalTagCount && totalTagCount > visibleTags) {
        tagText += ` of ${totalTagCount}`;
      }
      parts.push(tagText);
    }

    if (activeActivityCount) {
      let actText = `Active activities: ${activeActivityCount}`;
      if (totalActivityCount && totalActivityCount > activeActivityCount) {
        actText += ` of ${totalActivityCount}`;
      }
      parts.push(actText);
    } else if (totalActivityCount) {
      parts.push(`Activities: ${totalActivityCount}`);
    }

    const agg = formatSummaryTimestamp(data && data.last_aggregation_end_time);
    if (agg) parts.push(`Data through ${agg}`);
    return parts.join(' · ');
  }

  function renderEmptyState(ctx, linesWithOffsets, message) {
    const { container, width: W, height: H, theme } = ctx;
    const svg = d3
      .select(container)
      .append('svg')
      .attr('width', '100%')
      .attr('height', H)
      .attr('viewBox', `0 0 ${W} ${H}`)
      .attr('preserveAspectRatio', 'xMidYMid meet')
      .style('background-color', theme.chartBackground);

    renderHeader(svg, W, linesWithOffsets);
    const headerBottom = linesWithOffsets.length
      ? linesWithOffsets[linesWithOffsets.length - 1].y
      : 0;
    svg
      .append('text')
      .attr('x', W / 2)
      .attr('y', Math.max(headerBottom + 32, H / 2))
      .attr('text-anchor', 'middle')
      .attr('fill', theme.muted || '#888')
      .style('font-size', '12px')
      .text(message);
    return { state: { lastRender: Date.now(), visibleTags: 0 } };
  }

  function formatSeconds(total) {
    const sec = Math.max(0, Math.round(total || 0));
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (h > 0) {
      return s ? `${h}h ${m}m` : `${h}h ${m}m`;
    }
    if (m > 0) {
      return s ? `${m}m ${s}s` : `${m}m`;
    }
    return `${s}s`;
  }

  function renderTimeSpentPerTag(ctx) {
    const theme = normalizeTheme(ctx.theme);
    const { container, width: W, height: H, data } = ctx;

    const windowLabel = formatWindowLabel(data && data.start_date, data && data.end_date);
    const headerLines = attachLineOffsets(
      buildHeaderLines(theme, {
        windowLabel,
        summary: data
          ? buildSummaryLabel(data, [], 0, 0)
          : null,
      })
    );

    if (!data) {
      return renderEmptyState(
        { container, width: W, height: H, theme },
        headerLines,
        'No data'
      );
    }

    const windowStart = safeDate(data.start_date);
    const windowEnd = safeDate(data.end_date);
    if (!windowStart || !windowEnd || windowEnd <= windowStart) {
      return renderEmptyState(
        { container, width: W, height: H, theme },
        headerLines,
        'Invalid time window'
      );
    }

    const specs = Array.isArray(data.activity_specs) ? data.activity_specs : [];
    const { rows, uniqueTagIds, activeActivityCount } = collectTagDurations(
      specs,
      windowStart,
      windowEnd
    );

    if (!rows.length) {
      const summaryLines = attachLineOffsets(
        buildHeaderLines(theme, {
          windowLabel,
          summary: buildSummaryLabel(data, rows, uniqueTagIds.size, activeActivityCount),
        })
      );
      return renderEmptyState(
        { container, width: W, height: H, theme },
        summaryLines,
        'No tagged activity within the selected window.'
      );
    }

    const linesWithOffsets = attachLineOffsets(
      buildHeaderLines(theme, {
        windowLabel,
        summary: buildSummaryLabel(
          data,
          rows,
          uniqueTagIds.size,
          activeActivityCount
        ),
      })
    );
    const headerBottom = linesWithOffsets.length
      ? linesWithOffsets[linesWithOffsets.length - 1].y
      : 0;
    const marginTop = headerBottom + TITLE_GAP;

    const margin0 = { top: marginTop, right: 24, bottom: 56, left: 56 };
    const innerW0 = Math.max(0, W - margin0.left - margin0.right);
    const x0 = d3
      .scaleBand()
      .domain(rows.map((r) => r.name))
      .range([0, innerW0])
      .padding(0.25);
    const tickHeight =
      window.chartUtils && typeof window.chartUtils.measureBottomAxisTickHeight === 'function'
        ? window.chartUtils.measureBottomAxisTickHeight(container, W, H, x0, {
            rotateDeg: -35,
            textClass: 'text-xs',
            textFill: theme.muted,
            pad: 10,
            marginLeft: margin0.left,
            marginTop: margin0.top,
          })
        : 56;

    const margin = { top: marginTop, right: 24, bottom: tickHeight, left: 56 };
    const innerW = Math.max(0, W - margin.left - margin.right);
    const innerH = Math.max(140, H - margin.top - margin.bottom);

    const svg = d3
      .select(container)
      .append('svg')
      .attr('width', '100%')
      .attr('height', H)
      .attr('viewBox', `0 0 ${W} ${H}`)
      .attr('preserveAspectRatio', 'xMidYMid meet')
      .style('overflow', 'hidden')
      .style('background-color', theme.chartBackground);

    renderHeader(svg, W, linesWithOffsets);

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);
    const x = d3
      .scaleBand()
      .domain(rows.map((r) => r.name))
      .range([0, innerW])
      .padding(0.25);
    const maxSeconds = d3.max(rows, (r) => r.seconds) || 0;
    const y = d3
      .scaleLinear()
      .domain([0, maxSeconds])
      .nice()
      .range([innerH, 0]);

    const palette = [
      theme.productivity.very_productive,
      theme.productivity.productive,
      theme.productivity.neutral,
      theme.productivity.distracting,
      theme.productivity.very_distracting,
    ];
    const colorForIndex = (i) => palette[i % palette.length];

    const plot = g.append('g');
    plot
      .selectAll('rect')
      .data(rows)
      .enter()
      .append('rect')
      .attr('class', 'bar')
      .attr('x', (d) => x(d.name))
      .attr('y', (d) => y(d.seconds))
      .attr('width', x.bandwidth())
      .attr('height', (d) => Math.max(1, innerH - y(d.seconds)))
      .attr('fill', (d, i) => colorForIndex(i))
      .attr('stroke', (d, i) => {
        const base = colorForIndex(i);
        const darker = d3.color(base)?.darker(0.6);
        return darker ? darker.toString() : base;
      })
      .attr('stroke-width', 0.5)
      .append('title')
      .text((d) => `${d.name}: ${formatSeconds(d.seconds)}`);

    const xAxisGen = d3.axisBottom(x).tickSizeOuter(0);
    const xAxis = g
      .append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(xAxisGen);
    xAxis
      .selectAll('text')
      .attr('class', 'text-xs')
      .attr('transform', 'rotate(-35)')
      .style('text-anchor', 'end')
      .attr('dx', '-0.6em')
      .attr('dy', '0.25em')
      .style('fill', theme.muted);
    xAxis.selectAll('path, line').style('stroke', theme.grid);

    const yAxis = g
      .append('g')
      .call(d3.axisLeft(y).ticks(5).tickFormat((d) => formatSeconds(d)));
    yAxis.selectAll('text').attr('class', 'text-xs').style('fill', theme.muted);
    yAxis.selectAll('path, line').style('stroke', theme.grid);

    const maxZoom = Math.max(3, Math.min(10, Math.ceil(rows.length / 5)));
    return {
      state: {
        lastRender: Date.now(),
        visibleTags: rows.length,
        uniqueTagCount: uniqueTagIds.size,
      },
      bandZoom: {
        g,
        x,
        innerW,
        innerH,
        maxZoom,
        bars: () => plot.selectAll('rect.bar'),
        xAxisSel: xAxis,
        xAxisGen,
        valueAccessor: (d) => d.name,
      },
    };
  }

  window.initInsightsTimeSpentPerTagFromJson = function (jsonData) {
    let parsed = null;
    try {
      parsed = typeof jsonData === 'string' ? JSON.parse(jsonData) : jsonData;
    } catch (_) {
      parsed = null;
    }
    const el = document.getElementById('time-spent-per-tag');
    if (!el) return;
    if (parsed) {
      try {
        el.dataset.insights = JSON.stringify(parsed);
      } catch (_) {
        /* no-op */
      }
    }
    if (!el.__clepsyChart) {
      el.__clepsyChart = createClepsyChart({
        containerId: 'time-spent-per-tag',
        wrapperId: 'time-spent-per-tag-wrapper',
        render: renderTimeSpentPerTag,
      });
    } else {
      el.__clepsyChart();
    }
  };
})();
