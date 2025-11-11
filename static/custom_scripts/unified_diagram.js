




function convertProductivityToNumber(productivity) {
        const productivityMap = {
            'very_productive': 1.0,
            'productive': 0.8,
            'neutral': 0.6,
            'distracting': 0.4,
            'very_distracting': 0.2,
        };
        return productivityMap[productivity] || 0.0;
    }

// Make ongoing-activity end-time calculation available globally so all helpers can use it
function calculateOngoingActivityEndTime(startTime, lastAggregationEnd, currentTime, timelineViewEndTime) {
    const validStartTime = (startTime instanceof Date && !isNaN(startTime)) ? startTime : new Date();
    const validCurrentTime = (currentTime instanceof Date && !isNaN(currentTime)) ? currentTime : new Date();
    const validLastAggregationEnd = (lastAggregationEnd instanceof Date && !isNaN(lastAggregationEnd)) ? lastAggregationEnd : null;

    let potentialEndTimes = [];
    potentialEndTimes.push(validCurrentTime.getTime());

    if (validLastAggregationEnd) {
        potentialEndTimes.push(validLastAggregationEnd.getTime());
    }

    let calculatedEndTimeMs = Math.min(...potentialEndTimes);
    let finalEndTime = new Date(Math.max(validStartTime.getTime(), calculatedEndTimeMs));

    if (!(finalEndTime instanceof Date && !isNaN(finalEndTime)) || finalEndTime < validStartTime) {
        finalEndTime = new Date(validStartTime.getTime());
    }

    return finalEndTime;
}

function isOpenEvent(type) {
    const normalized = (type || "").toString().toLowerCase();
    return normalized === "open" || normalized === "start";
}

function isCloseEvent(type) {
    const normalized = (type || "").toString().toLowerCase();
    return normalized === "close" || normalized === "end";
}

function clampIntervalToWindow(startDate, endDate, windowStart, windowEnd) {
    if (!(startDate instanceof Date) || isNaN(startDate) || !(endDate instanceof Date) || isNaN(endDate)) {
        return null;
    }
    const windowStartMs = windowStart.getTime();
    const windowEndMs = windowEnd.getTime();
    const startMs = startDate.getTime();
    const endMs = endDate.getTime();

    if (!Number.isFinite(windowStartMs) || !Number.isFinite(windowEndMs) || windowEndMs <= windowStartMs) {
        return null;
    }

    if (endMs <= windowStartMs || startMs >= windowEndMs) {
        return null;
    }

    const clampedStartMs = Math.max(startMs, windowStartMs);
    const clampedEndMs = Math.min(endMs, windowEndMs);

    if (clampedEndMs <= clampedStartMs) {
        return null;
    }

    return {
        start: new Date(clampedStartMs),
        end: new Date(clampedEndMs),
        truncatedStart: startMs < windowStartMs,
        truncatedEnd: endMs > windowEndMs,
    };
}

function buildWindowedIntervalsForSpec(spec, windowStart, windowEnd, lastAggregationEnd, currentTime) {
    const intervals = [];
    if (!spec || !spec.activity) {
        return intervals;
    }

    const rawEvents = Array.isArray(spec.events) ? spec.events.slice() : [];
    if (!rawEvents.length) {
        return intervals;
    }

    const parsedEvents = rawEvents
        .map((event) => {
            const time = new Date(event.event_time);
            if (!(time instanceof Date) || isNaN(time)) {
                return null;
            }
            return {
                time,
                type: event.event_type,
            };
        })
        .filter(Boolean)
        .sort((a, b) => {
            const diff = a.time - b.time;
            if (diff !== 0) return diff;
            if (isCloseEvent(a.type) && isOpenEvent(b.type)) return -1;
            if (isOpenEvent(a.type) && isCloseEvent(b.type)) return 1;
            return 0;
        });

    if (!parsedEvents.length) {
        return intervals;
    }

    const activity = spec.activity;
    const prodLevel = activity.productivity_level || activity.app_productivity || "neutral";
    const tags = Array.isArray(activity.tags) ? activity.tags : [];
    const displayName = activity.name || "Untitled Activity";
    const description = activity.description || "";
    const activityId = activity.id;

    let currentStart = null;

    parsedEvents.forEach((event) => {
        if (isOpenEvent(event.type)) {
            currentStart = event.time;
        } else if (isCloseEvent(event.type) && currentStart) {
            const clamped = clampIntervalToWindow(currentStart, event.time, windowStart, windowEnd);
            if (clamped) {
                intervals.push({
                    start: clamped.start,
                    end: clamped.end,
                    prod: prodLevel,
                    name: displayName,
                    description,
                    tags,
                    activityId,
                    isOngoing: false,
                    originalStart: currentStart,
                    originalEnd: event.time,
                    truncatedStart: clamped.truncatedStart,
                    truncatedEnd: clamped.truncatedEnd,
                });
            }
            currentStart = null;
        }
    });

    if (currentStart) {
        const ongoingEnd = calculateOngoingActivityEndTime(currentStart, lastAggregationEnd, currentTime, windowEnd);
        const clamped = clampIntervalToWindow(currentStart, ongoingEnd, windowStart, windowEnd);
        if (clamped) {
            intervals.push({
                start: clamped.start,
                end: clamped.end,
                prod: prodLevel,
                name: displayName,
                description,
                tags,
                activityId,
                isOngoing: true,
                originalStart: currentStart,
                originalEnd: ongoingEnd,
                truncatedStart: clamped.truncatedStart,
                truncatedEnd: clamped.truncatedEnd,
            });
        }
    }

    return intervals.sort((a, b) => a.start - b.start);
}


function createProductivityTimeSeriesData(activitySpecs, startTime, endTime, lastAggregationEnd, currentTime) {
    console.log("Creating time series data for productivity with", activitySpecs.length ?? 0, "activity specs");

    if (!(startTime instanceof Date) || isNaN(startTime)) startTime = new Date(startTime);
    if (!(endTime instanceof Date) || isNaN(endTime)) endTime = new Date(endTime);

    if (!activitySpecs || !Array.isArray(activitySpecs)) {
        console.warn("activitySpecs is not an array:", activitySpecs);
        return [];
    }

    const windowStart = startTime;
    const windowEnd = endTime;
    const windowedIntervals = [];

    activitySpecs.forEach((spec, specIndex) => {
        const intervals = buildWindowedIntervalsForSpec(spec, windowStart, windowEnd, lastAggregationEnd, currentTime);
        intervals.forEach((interval, intervalIndex) => {
            const originalStartMs = interval.originalStart instanceof Date ? interval.originalStart.getTime() : interval.start.getTime();
            const originalEndMs = interval.originalEnd instanceof Date ? interval.originalEnd.getTime() : interval.end.getTime();
            windowedIntervals.push({
                start: interval.start,
                end: interval.end,
                productivityLevel: interval.prod,
                key: `${interval.activityId ?? specIndex}-${originalStartMs}-${originalEndMs}-${intervalIndex}`,
            });
        });
    });

    if (!windowedIntervals.length) {
        console.log("No windowed intervals found for productivity diagram");
        return [];
    }

    const events = [];
    windowedIntervals.forEach((interval) => {
        const numericValue = convertProductivityToNumber(interval.productivityLevel);
        events.push({ time: interval.start, type: 'open', key: interval.key, value: numericValue });
        events.push({ time: interval.end, type: 'close', key: interval.key, value: numericValue });
    });

    events.sort((a, b) => {
        const diff = a.time - b.time;
        if (diff !== 0) return diff;
        if (a.type === 'close' && b.type === 'open') return -1;
        if (a.type === 'open' && b.type === 'close') return 1;
        return 0;
    });

    const activeIntervals = new Map();
    const intervals = [];
    let previousTime = windowStart;
    let previousProductivity = 0;

    events.forEach((event, index) => {
        let eventTime = event.time;
        if (eventTime < windowStart) eventTime = windowStart;
        if (eventTime > windowEnd) eventTime = windowEnd;

        if (eventTime > previousTime) {
            intervals.push({
                startTime: new Date(previousTime),
                endTime: new Date(eventTime),
                productivity: previousProductivity,
                hasActivity: previousProductivity > 0,
            });
        }

        if (event.type === 'open') {
            activeIntervals.set(event.key, event.value);
        } else {
            activeIntervals.delete(event.key);
        }

        let maxProductivity = 0;
        activeIntervals.forEach((value) => {
            maxProductivity = Math.max(maxProductivity, value);
        });

        previousTime = eventTime;
        previousProductivity = maxProductivity;

        if (event.time instanceof Date && !isNaN(event.time)) {
            console.log(`Event ${index}: ${event.type} at ${event.time.toTimeString()}, open intervals: ${activeIntervals.size}, productivity value: ${maxProductivity}`);
        }
    });

    if (previousTime < windowEnd) {
        intervals.push({
            startTime: new Date(previousTime),
            endTime: new Date(windowEnd),
            productivity: previousProductivity,
            hasActivity: previousProductivity > 0,
        });
    }

    const filteredIntervals = intervals.filter(interval => interval.endTime > interval.startTime);

    console.log(`Created ${filteredIntervals.length} productivity intervals (window-clamped)`);
    console.log("Sample intervals:", filteredIntervals.slice(0, 3).map(i => ({
        start: i.startTime.toTimeString(),
        end: i.endTime.toTimeString(),
        productivity: i.productivity,
        hasActivity: i.hasActivity,
    })));

    return filteredIntervals;
}











window.initUnifiedDiagramFromJson = function(jsonData) {
    console.log("Initializing unified diagram from JSON data");
    try {
        const data = JSON.parse(jsonData);
        console.log(`Initializing unified diagram with ${data.activity_specs?.length ?? 'n/a'} activities`);
        console.log('Init payload dates:', data.start_date, '→', data.end_date);

        const lastAggregationEndTime = data.last_aggregation_end_time
            ? new Date(data.last_aggregation_end_time)
            : null;
        const currentTime = data.current_time ? new Date(data.current_time) : new Date();

        console.log("Unified diagram last_aggregation_end_time raw:", data.last_aggregation_end_time);
        console.log("Unified diagram lastAggregationEndTime Date:", lastAggregationEndTime);
        console.log("Unified diagram current_time raw:", data.current_time);
        console.log("Unified diagram currentTime Date:", currentTime);

        // Call the unified setup function
    console.log('Calling setupUnifiedDiagram with specs length:', data.activity_specs?.length ?? 0);
    setupUnifiedDiagram(
            data.activity_specs,
            new Date(data.start_date),
            new Date(data.end_date),
            lastAggregationEndTime,
            currentTime
        );
    } catch (e) {
        console.error("Error initializing unified diagram from JSON:", e);
    }
}

/**
 * Main function to setup both timeline and productivity diagrams in a unified D3.js context
 */
function setupUnifiedDiagram(
    initialActivitySpecsData,
    originalStartTime,
    originalEndTime,
    initialLastAggregationEnd,
    initialCurrentTime
) {
    // Store original times in closure scope
    const originalStart = new Date(originalStartTime);
    const originalEnd = new Date(originalEndTime);

    // Define the unified render function
    function renderUnifiedDiagrams(
        activitySpecsData,
        userStartTime,
        userEndTime,
        lastAggregationEnd,
        currentTime
    ) {
        console.log("Rendering unified diagrams...");
        console.log("Unified lastAggregationEnd received:", lastAggregationEnd);
        console.log("Unified currentTime received:", currentTime);

        // Get the single unified container
        const unifiedContainer = document.getElementById("unified-diagrams-container");

        if (!unifiedContainer) {
            console.error("Unified diagrams container not found");
            return;
        }

        // Save current zoom transform before clearing (if it exists)
        let savedZoomTransform = null;
        if (window._unifiedTimelineZoomTransform) {
            savedZoomTransform = window._unifiedTimelineZoomTransform;
        }

        // Clear existing content
        d3.select(unifiedContainer).selectAll("*").remove();

        // Get theme-aware colors for both diagrams
        const timelineColors = getTimelineColors();


        // Add CSS styles
        addTimelineCSS();

        // Render Timeline with saved zoom transform
        renderTimelinePortion(
            unifiedContainer,
            activitySpecsData,
            userStartTime,
            userEndTime,
            lastAggregationEnd,
            currentTime,
            timelineColors,
            savedZoomTransform
        );


    }

    // Helper functions from original timeline.js
    function intervalsOverlap(intervalA, intervalB) {
        const a_starts_before_b_ends = intervalA.start < intervalB.end;
        const b_starts_before_a_ends = intervalB.start < intervalA.end;
        return a_starts_before_b_ends && b_starts_before_a_ends;
    }

    function calculateBarWidth(interval, xScale) {
        const startX = xScale(interval.start);
        const endX = xScale(interval.end);
        return Math.max(3, endX - startX);
    }

    function calculateTextDisplay(barWidthPx, text, fontSizePx = 11, fontWeight = 'bold', paddingPx = 10) {
        // Handle undefined or null text
        if (!text || typeof text !== 'string') {
            return { show: false, displayText: '' };
        }

        let avgCharWidth;
        if (fontSizePx <= 10) {
            avgCharWidth = fontSizePx * 0.65;
        } else {
            avgCharWidth = fontSizePx * 0.6;
        }
        if (fontWeight === 'bold') {
            avgCharWidth *= 1.15;
        }

        const estimatedTextWidth = (text.length * avgCharWidth) + paddingPx;

        // If text fits completely, show it
        if (barWidthPx > estimatedTextWidth) {
            return { show: true, displayText: text };
        }

        // Calculate how many characters can fit with "..." ellipsis
        const ellipsisWidth = 3 * avgCharWidth;
        const availableWidth = barWidthPx - paddingPx - ellipsisWidth;

        if (availableWidth > avgCharWidth * 3) { // Need at least 3 chars + ellipsis
            const maxChars = Math.floor(availableWidth / avgCharWidth);
            const truncated = text.substring(0, maxChars) + '...';
            return { show: true, displayText: truncated };
        }

        // Bar too narrow even for truncated text
        return { show: false, displayText: '' };
    }

    // Legacy function for backwards compatibility
    function doesTextFit(barWidthPx, text, fontSizePx = 11, fontWeight = 'bold', paddingPx = 10) {
        const result = calculateTextDisplay(barWidthPx, text, fontSizePx, fontWeight, paddingPx);
        return result.show && result.displayText === text; // Only true if full text fits
    }

    // Note: calculateOngoingActivityEndTime is defined at top-level for shared use

    // Create tooltip content function styled with Tailwind utility classes
    function createTimelineTooltipContent(d, color) {
        const startTime = d3.timeFormat("%H:%M:%S")(d.start);
        const endTime = d.isOngoing ? "ongoing" : d3.timeFormat("%H:%M:%S")(d.end);
        const date = d3.timeFormat("%Y-%m-%d")(d.start);

        const duration = (d.end - d.start) / 1000; // in seconds
        let durationText = d.isOngoing ? "ongoing" : "";

        if (!d.isOngoing) {
            if (duration >= 3600) {
                const hours = Math.floor(duration / 3600);
                const minutes = Math.floor((duration % 3600) / 60);
                durationText = `${hours}h ${minutes}m`;
            } else {
                const minutes = Math.floor(duration / 60);
                const seconds = Math.floor(duration % 60);
                durationText = `${minutes}m ${seconds}s`;
            }
        }

        // Outer wrapper to match app surfaces
        let content = `
            <div class="rounded-md border border-border bg-popover text-popover-foreground shadow-md p-3">
                <div class="flex items-start justify-between border-b border-border pb-1.5 mb-2">
                    <span class="text-sm font-semibold">${d.name}</span>
                    <span class="ml-3 text-[10px] text-muted-foreground">ID: ${d.activityId}</span>
                </div>
                <div class="text-xs space-y-2">
        `;

        // Show productivity level with colored indicator
        const productivityLevel = d.prod || 'neutral';
        const displayProductivity = productivityLevel.replace(/_/g, ' ');
        content += `
                    <div class="flex items-center gap-2">
                        <span class="inline-block w-2.5 h-2.5 rounded-full" style="background-color: ${color(productivityLevel)};"></span>
                        <span class="text-muted-foreground">Productivity:</span>
                        <strong class="capitalize">${displayProductivity}</strong>
                    </div>
        `;

        // Description if available
        if (d.description && d.description.trim() !== '') {
            content += `
                    <div class="text-foreground/80">${d.description}</div>
            `;
        }

        // Tags with app-like pill styling
        if (d.tags && d.tags.length > 0) {
            content += `
                    <div>
                        <span class="text-muted-foreground">Tags:</span>
                        <div class="mt-1.5 flex flex-wrap gap-1">
            `;

            content += d.tags.map(tag =>
                `<span class="inline-block rounded border border-border bg-secondary text-secondary-foreground px-1.5 py-0.5 text-[11px]">${tag.name}</span>`
            ).join("");

            content += `
                        </div>
                    </div>
            `;
        }

        // Time information
        content += `
                    <div class="mt-2 text-[11px] text-muted-foreground space-y-0.5">
                        <div>Date: ${date}</div>
                        <div>Time: ${startTime} to ${endTime}</div>
                        <div>Duration: ${durationText}</div>
                    </div>
                </div>
            </div>
        `;

        return content;
    }

    function renderTimelinePortion(container, activitySpecsData, userStartTime, userEndTime, lastAggregationEnd, currentTime, colors, savedZoomTransform = null) {
        console.log("Rendering timeline portion...");

        // Validate input
        if (!activitySpecsData || !Array.isArray(activitySpecsData)) {
            console.warn("activitySpecsData is not an array:", activitySpecsData);
            return;
        }

        // Track session expand/collapse state (persisted across renders)
        if (!window._sessionExpandedState) {
            window._sessionExpandedState = new Set();
        }

        // Group activities by ID and build intervals
        const activitiesById = new Map();
        const sessionsBySessionId = new Map();

        activitySpecsData.forEach(spec => {
            const activityId = spec?.activity?.id;
            if (activityId == null) {
                return;
            }

            const intervals = buildWindowedIntervalsForSpec(
                spec,
                userStartTime,
                userEndTime,
                lastAggregationEnd,
                currentTime
            );

            if (!intervals.length) {
                return;
            }

            if (!activitiesById.has(activityId)) {
                activitiesById.set(activityId, {
                    activity_id: activityId,
                    activity_name: spec.activity?.name || "Untitled Activity",
                    specs: [],
                    intervals: [],
                    earliestStart: null,
                    tags: Array.isArray(spec.activity?.tags) ? spec.activity.tags : [],
                    session: spec.session || null,  // Finalized session
                    candidate_sessions: spec.candidate_sessions || [],
                });
            }

            const activityGroup = activitiesById.get(activityId);
            activityGroup.specs.push(spec);
            activityGroup.intervals.push(...intervals);

            intervals.forEach(interval => {
                if (!activityGroup.earliestStart || interval.start < activityGroup.earliestStart) {
                    activityGroup.earliestStart = interval.start;
                }
            });

            // Group by finalized session (only finalized sessions get visual grouping)
            if (spec.session && spec.session.id) {
                const sessionId = spec.session.id;
                if (!sessionsBySessionId.has(sessionId)) {
                    sessionsBySessionId.set(sessionId, {
                        session_id: sessionId,
                        session_name: spec.session.name,
                        activities: [],
                        intervals: [],
                        earliestStart: null,
                        latestEnd: null,
                        isExpanded: window._sessionExpandedState.has(sessionId),
                    });
                }
                const sessionGroup = sessionsBySessionId.get(sessionId);
                sessionGroup.activities.push(activityGroup);
                sessionGroup.intervals.push(...intervals);

                intervals.forEach(interval => {
                    if (!sessionGroup.earliestStart || interval.start < sessionGroup.earliestStart) {
                        sessionGroup.earliestStart = interval.start;
                    }
                    if (!sessionGroup.latestEnd || interval.end > sessionGroup.latestEnd) {
                        sessionGroup.latestEnd = interval.end;
                    }
                });
            }
        });

        const processed = Array.from(activitiesById.values())
            .filter(group => group.intervals.length > 0);
        processed.sort((a, b) => {
            const aTime = (a.earliestStart || userStartTime).getTime();
            const bTime = (b.earliestStart || userStartTime).getTime();
            return aTime - bTime;
        });

        console.log("Timeline intervals created:", processed.reduce((sum, act) => sum + act.intervals.length, 0));
        console.log("Sessions found:", sessionsBySessionId.size);

        // Helper function: calculate weighted average productivity for a session
        function calculateSessionProductivity(activities) {
            let totalWeightedProd = 0;
            let totalDuration = 0;

            activities.forEach(activity => {
                activity.intervals.forEach(interval => {
                    const duration = (interval.end - interval.start) / 1000; // seconds
                    const prodValue = convertProductivityToNumber(interval.prod);
                    totalWeightedProd += prodValue * duration;
                    totalDuration += duration;
                });
            });

            if (totalDuration === 0) return 'neutral';

            const avgProdValue = totalWeightedProd / totalDuration;

            // Map back to productivity level (closest match)
            if (avgProdValue >= 0.9) return 'very_productive';
            if (avgProdValue >= 0.7) return 'productive';
            if (avgProdValue >= 0.5) return 'neutral';
            if (avgProdValue >= 0.3) return 'distracting';
            return 'very_distracting';
        }

        // Create renderable items (mix of session blocks and individual activities)
        const renderableItems = [];
        const activitiesBySessionId = new Map();

        // Group activities by session
        processed.forEach(activity => {
            if (activity.session && activity.session.id) {
                const sessionId = activity.session.id;
                if (!activitiesBySessionId.has(sessionId)) {
                    activitiesBySessionId.set(sessionId, []);
                }
                activitiesBySessionId.get(sessionId).push(activity);
            } else {
                // Activities without sessions render normally (will be assigned to rows starting from row 1)
                renderableItems.push({
                    type: 'activity',
                    activity: activity,
                    intervals: activity.intervals,
                });
            }
        });

        // Add session blocks (collapsed or expanded)
        sessionsBySessionId.forEach((sessionGroup, sessionId) => {
            const sessionActivities = activitiesBySessionId.get(sessionId) || [];
            const sessionProd = calculateSessionProductivity(sessionActivities);

            if (sessionGroup.isExpanded) {
                // Expanded: render session block in row 0, then individual activities inline
                renderableItems.push({
                    type: 'session-expanded',
                    sessionId: sessionId,
                    sessionName: sessionGroup.session_name,
                    sessionProd: sessionProd,
                    intervals: [{
                        start: sessionGroup.earliestStart,
                        end: sessionGroup.latestEnd,
                        isSession: true,
                        prod: sessionProd,
                    }],
                    forceRow: 0, // Always render expanded sessions in row 0
                });

                // Add individual activities to render inline (they'll get assigned rows naturally)
                sessionActivities.forEach(activity => {
                    renderableItems.push({
                        type: 'activity-in-expanded-session',
                        activity: activity,
                        sessionId: sessionId,
                        intervals: activity.intervals,
                    });
                });
            } else {
                // Collapsed: render single session block with weighted average color
                renderableItems.push({
                    type: 'session-collapsed',
                    sessionId: sessionId,
                    sessionName: sessionGroup.session_name,
                    sessionProd: sessionProd,
                    intervals: [{
                        start: sessionGroup.earliestStart,
                        end: sessionGroup.latestEnd,
                        isSession: true,
                        sessionId: sessionId,
                        name: sessionGroup.session_name,
                        prod: sessionProd,
                    }],
                });
            }
        });

        // Sort renderable items by earliest start time
        renderableItems.sort((a, b) => {
            const aStart = a.intervals[0]?.start || userStartTime;
            const bStart = b.intervals[0]?.start || userStartTime;
            return aStart.getTime() - bStart.getTime();
        });

        // Row assignment logic - reserve row 0 for expanded sessions
        // Initialize with row 0 empty (for expanded sessions)
        const rowsData = [[]]; // Row 0 is reserved

        renderableItems.forEach(item => {
            // If item has forceRow (expanded sessions), assign to row 0
            if (item.forceRow === 0) {
                item.row = 0;
                rowsData[0].push(...item.intervals);
                return;
            }

            let assignedRow = -1;

            // Start checking from row 1 (skip row 0 which is reserved)
            for (let row = 1; row < rowsData.length; row++) {
                let canFitInRow = true;

                for (const interval of item.intervals) {
                    for (const existingInterval of rowsData[row]) {
                        if (intervalsOverlap(interval, existingInterval)) {
                            canFitInRow = false;
                            break;
                        }
                    }
                    if (!canFitInRow) break;
                }

                if (canFitInRow) {
                    assignedRow = row;
                    break;
                }
            }

            if (assignedRow === -1) {
                assignedRow = rowsData.length;
                rowsData.push([]);
            }

            item.row = assignedRow;
            rowsData[assignedRow].push(...item.intervals);
        });

        const totalRows = rowsData.length;

    // Chart dimensions (height depends on number of rows, with a minimum)
    // Fullscreen logic removed; rely on natural container sizing.
        const rect = container.getBoundingClientRect();
        const chartWidth = rect.width;
        const margin = { top: 8, right: 16, bottom: 32, left: 16 };
        const rowsCount = Math.max(totalRows, 1);

    const baseRowHeight = 50; // px per row
    const desiredRowHeight = baseRowHeight;
    const minChartHeight = 400; // px including margins (static minimum)

    // Decide if heatmap will be shown (reserve space accordingly)
    const totalRangeMs = userEndTime.getTime() - userStartTime.getTime();
    const minRangeForHeatmapMs = 30 * 60 * 1000; // 30 minutes
    const willShowHeatmap = totalRangeMs >= minRangeForHeatmapMs;
    // Make heatmap a bit taller than activity bars (bars are ~0.5x row height)
    const heatmapHeight = willShowHeatmap ? Math.floor(desiredRowHeight * 0.95) : 0;
    const heatmapSpacing = willShowHeatmap ? 4 : 0; // small gap above axis

        const innerRowsHeight = Math.max(
            rowsCount * desiredRowHeight,
            Math.max(0, minChartHeight - margin.top - margin.bottom)
        );
        const innerHeight = innerRowsHeight + heatmapHeight + heatmapSpacing;
        const chartHeight = innerHeight + margin.top + margin.bottom;
    const innerWidth = Math.max(0, chartWidth - margin.left - margin.right);

    const svg = d3.select(container)
        .append("svg")
        .attr("width", "100%")
        .attr("height", chartHeight)
        .attr("viewBox", [0, 0, chartWidth, chartHeight])
        .attr("preserveAspectRatio", "xMidYMid meet")
        .style("background-color", colors.background);

        const g = svg.append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`);

    // Fullscreen hover button removed.



        // Create x scale for this specific timeline
        const timelineXScale = d3.scaleTime()
            .domain([userStartTime, userEndTime])
            .range([0, innerWidth]);

        // Add a transparent background to capture interactions in empty areas
        // This ensures zoom/pan works even when not hovering over bars or heatmap.
        g.append("rect")
            .attr("class", "zoom-background")
            .attr("x", 0)
            .attr("y", 0)
            .attr("width", innerWidth)
            .attr("height", innerHeight)
            .attr("fill", "transparent")
            .style("pointer-events", "all");

        // Y position function
        function yPosition(rowIndex) {
            return rowIndex * desiredRowHeight;
        }

        // Color scale for productivity
        const color = d3.scaleOrdinal()
            .domain([
                "very_productive",
                "productive",
                "neutral",
                "distracting",
                "very_distracting"
            ])
            .range([
                colors.productivity.very_productive,
                colors.productivity.productive,
                colors.productivity.neutral,
                colors.productivity.distracting,
                colors.productivity.very_distracting
            ]);

    // Keep references for heatmap segment updates
    let heatSegG = null;
    let updateHeatSegments = null;

    // ----- Productivity heatmap strip (between lowest row and x-axis) -----
        if (willShowHeatmap) {
            // Decide bin size based on total range (daily/weekly/monthly heuristics)
            let binMs;
            if (totalRangeMs <= 36 * 60 * 60 * 1000) {
                // Daily
                binMs = 0.5 * 60 * 1000; // 5 min
            } else if (totalRangeMs <= 10 * 24 * 60 * 60 * 1000) {
                // Weekly-ish
                binMs = 15 * 60 * 1000; // 15 min
            } else {
                // Monthly-ish
                binMs = totalRangeMs <= 40 * 24 * 60 * 60 * 1000
                    ? 60 * 60 * 1000   // 1 hour
                    : 2 * 60 * 60 * 1000; // 2 hours
            }

            const minCoverage = 0.3;
            // Gaussian Weighted Moving Average parameters
            // Choose radius based on bin size so smoothing spans a sensible time window
            let windowRadius;
            if (binMs <= 5 * 60 * 1000) {
                windowRadius = 4; // ~45 min span
            } else if (binMs <= 15 * 60 * 1000) {
                windowRadius = 4; // ~2 hours span
            } else if (binMs <= 60 * 60 * 1000) {
                windowRadius = 3; // ~7 hours span
            } else {
                windowRadius = 2; // coarse bins → smaller radius
            }
            const sigma = Math.max(0.8, windowRadius / 2); // gaussian width (in bins)
            const gaussKernel = [];
            for (let k = -windowRadius; k <= windowRadius; k++) {
                gaussKernel.push({ k, w: Math.exp(-0.5 * Math.pow(k / sigma, 2)) });
            }

            // Use existing function to get productivity time series intervals
            const tsIntervals = createProductivityTimeSeriesData(
                activitySpecsData,
                userStartTime,
                userEndTime,
                lastAggregationEnd,
                currentTime
            );

        // Build binned series
            const bins = [];
            const domainStart = new Date(Math.floor(userStartTime.getTime() / binMs) * binMs);
            for (let t = domainStart.getTime(); t < userEndTime.getTime(); t += binMs) {
                const bStart = new Date(Math.max(t, userStartTime.getTime()));
                const bEnd = new Date(Math.min(t + binMs, userEndTime.getTime()));
                const duration = bEnd.getTime() - bStart.getTime();
                if (duration <= 0) continue;

                let coveredMs = 0;
                let weighted = 0;
        let firstOvStartMs = Number.POSITIVE_INFINITY;
        let lastOvEndMs = Number.NEGATIVE_INFINITY;
                for (const iv of tsIntervals) {
                    if (!iv.hasActivity) continue;
                    const ovStart = Math.max(new Date(iv.startTime).getTime(), bStart.getTime());
                    const ovEnd = Math.min(new Date(iv.endTime).getTime(), bEnd.getTime());
                    const ov = ovEnd - ovStart;
                    if (ov > 0) {
                        coveredMs += ov;
                        weighted += ov * iv.productivity;
            if (ovStart < firstOvStartMs) firstOvStartMs = ovStart;
            if (ovEnd > lastOvEndMs) lastOvEndMs = ovEnd;
                    }
                }

                const coverage = coveredMs / duration;
                const value = coveredMs > 0 ? (weighted / coveredMs) : null;
        const startFill = coveredMs > 0 ? new Date(firstOvStartMs) : null;
        const endFill = coveredMs > 0 ? new Date(lastOvEndMs) : null;
        bins.push({ start: bStart, end: bEnd, coverage, value, startFill, endFill });
            }

            // Gaussian weighted moving average (respect minCoverage)
            const smoothed = bins.map((_, i) => {
                let num = 0, den = 0;
                for (let idx = 0; idx < gaussKernel.length; idx++) {
                    const { k, w } = gaussKernel[idx];
                    const j = i + k;
                    const b = bins[j];
                    if (!b) continue;
                    if (b.value != null && b.coverage >= minCoverage) {
                        num += w * b.value;
                        den += w;
                    }
                }
                return den > 0 ? num / den : null;
            });

            // Color scale for heatmap (diverging)
            const heatColor = d3.scaleLinear()
                .domain([0.2, 0.6, 1.0])
                .range([
                    colors.productivity.very_distracting,
                    colors.productivity.neutral,
                    colors.productivity.very_productive,
                ])
                .interpolate(d3.interpolateRgb);

            // Pin the productivity strip just above the x-axis
            const heatmapY = innerHeight - heatmapSpacing - heatmapHeight;

            const heatG = g.append("g").attr("class", "productivity-heatmap");

            // Subtle background band to distinguish from activity rows
            heatG.append("rect")
                .attr("class", "heatmap-bg")
                .attr("x", 0)
                .attr("y", heatmapY)
                .attr("width", innerWidth)
                .attr("height", heatmapHeight)
                .attr("fill", colors.productivity.neutral)
                .attr("opacity", 0.06)
                .attr("shape-rendering", "crispEdges");

            // Thin separator line above the heatmap strip
            heatG.append("line")
                .attr("x1", 0)
                .attr("x2", innerWidth)
                .attr("y1", heatmapY - 1)
                .attr("y2", heatmapY - 1)
                .attr("stroke", colors.productivity.neutral)
                .attr("stroke-opacity", 0.35)
                .attr("shape-rendering", "crispEdges");

            // Label above the strip, centered, to avoid overlapping the color area
            heatG.append("text")
                .attr("x", innerWidth / 2)
                .attr("y", Math.max(0, heatmapY - 6))
                .attr("text-anchor", "middle")
                .attr("dominant-baseline", "baseline")
                .attr("font-size", 11)
                .attr("fill", colors.productivity.neutral)
                .style("opacity", 0.7)
                .style("pointer-events", "none")
                .text("Productivity");

            function binColorOpacity(b, i) {
                const val = smoothed[i];
                if (val == null || !b || b.coverage <= 0) {
                    return { color: colors.productivity.neutral, opacity: 0.0 };
                }
                // Quantize value to reduce rapid flicker/fuzz when zoomed out
                const vClamped = Math.max(0.2, Math.min(1.0, val));
                const steps = 9; // increase/decrease for more/less variation
                const stepSize = (1.0 - 0.2) / steps;
                const idx = Math.max(0, Math.min(steps - 1, Math.floor((vClamped - 0.2) / stepSize)));
                const vQ = 0.2 + (idx + 0.5) * stepSize;
                const color = heatColor(vQ);
                // Softer opacity to avoid overpowering activity bars; quantize for stability
                const rawAlpha = 0.2 + 0.5 * b.coverage; // 0.2..0.7
                const alpha = Math.max(0.2, Math.min(0.7, Math.round(rawAlpha * 20) / 20)); // 0.05 increments
                return { color, opacity: alpha };
            }
            // Segment group
            heatSegG = heatG.append("g").attr("class", "heatmap-segments");

            function computeSegments(scale) {
                const totalW = innerWidth;
                const ext = bins.map((b, i) => ({
                    b,
                    i,
                    t0: b.startFill ? Math.max(0, Math.min(totalW, scale(b.startFill))) : null,
                    t1: b.endFill ? Math.max(0, Math.min(totalW, scale(b.endFill))) : null
                })).filter(x => x.t0 != null && x.t1 != null && x.t1 > x.t0);
                if (!ext.length) return [];

                // Coalesce into larger segments when productivity (color) stays the same.
                // For opacity, compute a width-weighted mean coverage across the segment
                const segments = [];
                for (const item of ext) {
                    const co = binColorOpacity(item.b, item.i);
                    const t0 = Math.round(item.t0);
                    const t1 = Math.round(item.t1);
                    if (t1 <= t0) continue;
                    const last = segments[segments.length - 1];
                    const width = t1 - t0;
                    if (last && last.color === co.color && Math.abs(last.end - t0) <= 1) {
                        // Extend existing run; accumulate coverage for opacity later
                        last.end = t1;
                        last.coverageWeighted += (item.b.coverage ?? 0) * width;
                        last.widthAccum += width;
                    } else {
                        segments.push({
                            start: t0,
                            end: t1,
                            color: co.color,
                            // temp accumulators for opacity
                            coverageWeighted: (item.b.coverage ?? 0) * width,
                            widthAccum: width
                        });
                    }
                }

                // Finalize opacity per segment based on aggregated coverage
                for (const seg of segments) {
                    const avgCoverage = seg.widthAccum > 0 ? seg.coverageWeighted / seg.widthAccum : 0;
                    const rawAlpha = 0.2 + 0.5 * avgCoverage;
                    const alpha = Math.max(0.2, Math.min(0.7, Math.round(rawAlpha * 20) / 20));
                    seg.opacity = alpha;
                    delete seg.coverageWeighted;
                    delete seg.widthAccum;
                }

                // Ensure pixel continuity to avoid 1px gaps from rounding
                for (let i = 1; i < segments.length; i++) {
                    segments[i].start = Math.max(segments[i].start, segments[i-1].end);
                }

                return segments;
            }

            updateHeatSegments = (zx) => {
                try {
                    const scale = zx || timelineXScale;
                    const segments = computeSegments(scale);
                    const sel = heatSegG.selectAll("rect.heat-seg").data(segments);
                    sel.join(
                        enter => enter.append("rect")
                            .attr("class", "heat-seg")
                            .attr("x", d => d.start)
                            .attr("y", heatmapY)
                            .attr("width", d => Math.max(1, d.end - d.start))
                            .attr("height", heatmapHeight)
                            .attr("fill", d => d.color)
                            .attr("opacity", d => d.opacity)
                            .attr("shape-rendering", "crispEdges")
                            .attr("stroke", "none"),
                        update => update
                            .attr("x", d => d.start)
                            .attr("width", d => Math.max(1, d.end - d.start))
                            .attr("opacity", d => d.opacity)
                            .attr("fill", d => d.color),
                        exit => exit.remove()
                    );
                } catch (_) { /* no-op */ }
            };

            // Initial segments render
            updateHeatSegments();
        }

        // Add pattern definitions for session bars
        const defs = svg.append("defs");

        // Create patterns for each session
        const sessionIds = new Set();
        renderableItems.forEach(item => {
            if ((item.type === 'session-collapsed' || item.type === 'session-expanded') && item.sessionId) {
                sessionIds.add(item.sessionId);
            }
        });

        sessionIds.forEach(sessionId => {
            // Get session data to determine color
            const sessionItem = renderableItems.find(item => item.sessionId === sessionId);
            const sessionProd = sessionItem?.intervals?.[0]?.prod || 'neutral';
            const baseColor = color(sessionProd);
            const d3Color = d3.color(baseColor);

            // Pattern for collapsed sessions (normal contrast)
            const lightColor = d3Color ? d3Color.brighter(0.4) : baseColor;
            const medColor = d3Color ? d3Color.brighter(0.2) : baseColor;

            const pattern = defs.append("pattern")
                .attr("id", `session-pattern-${sessionId}`)
                .attr("width", 8)
                .attr("height", 8)
                .attr("patternUnits", "userSpaceOnUse")
                .attr("patternTransform", "rotate(45)");

            pattern.append("rect")
                .attr("width", 8)
                .attr("height", 8)
                .attr("fill", lightColor);

            pattern.append("line")
                .attr("x1", 0)
                .attr("y1", 0)
                .attr("x2", 0)
                .attr("y2", 8)
                .attr("stroke", medColor)
                .attr("stroke-width", 3);

            // Pattern for expanded sessions (lower contrast)
            const lightColorExpanded = d3Color ? d3Color.brighter(0.6) : baseColor;
            const medColorExpanded = d3Color ? d3Color.brighter(0.45) : baseColor;

            const patternExpanded = defs.append("pattern")
                .attr("id", `session-pattern-expanded-${sessionId}`)
                .attr("width", 8)
                .attr("height", 8)
                .attr("patternUnits", "userSpaceOnUse")
                .attr("patternTransform", "rotate(45)");

            patternExpanded.append("rect")
                .attr("width", 8)
                .attr("height", 8)
                .attr("fill", lightColorExpanded);

            patternExpanded.append("line")
                .attr("x1", 0)
                .attr("y1", 0)
                .attr("x2", 0)
                .attr("y2", 8)
                .attr("stroke", medColorExpanded)
                .attr("stroke-width", 2);
        });

        // Draw intervals - no brush needed anymore with scroll zoom
        const rows = g.selectAll(".timeline-row")
            .data(renderableItems)
            .enter().append("g")
            .attr("class", d => {
                if (d.type === 'session-collapsed' || d.type === 'session-expanded') {
                    return "timeline-row session-row";
                }
                return "timeline-row";
            })
            .attr("transform", d => `translate(0, ${yPosition(d.row)})`);

    // Define bar vertical layout: nearly full row height with small padding for visual separation
    const barPaddingY = 3; // pixels top & bottom
    const barY = barPaddingY;
    const barHeightFull = desiredRowHeight - barPaddingY * 2;

    const activityBars = rows.selectAll(".active-bar, .session-bar")
            .data(d => {
                if (d.type === 'session-collapsed' || d.type === 'session-expanded') {
                    // Session blocks
                    return d.intervals.map(interval => ({
                        ...interval,
                        type: d.type,
                        sessionId: d.sessionId,
                        sessionName: d.sessionName,
                    }));
                } else if (d.type === 'activity' || d.type === 'activity-in-expanded-session') {
                    // Regular activities
                    console.log(`Processing activity: ${d.activity.activity_name || d.activity.activity_id}`);
                    return d.activity.intervals.map(interval => ({
                        ...interval,
                        type: d.type,
                        sessionId: d.sessionId || null,
                    }));
                }
                return [];
            })
            .enter().append("rect")
            .attr("class", d => {
                if (d.isSession) {
                    return `session-bar session-${d.sessionId} clickable`;
                }
                return `active-bar activity-${d.activityId} clickable`;
            })
            .attr("x", d => timelineXScale(d.start))
            .attr("y", d => {
                if (d.isSession && d.type === 'session-expanded') {
                    // Expanded session: center vertically with 65% height
                    const expandedHeight = barHeightFull * 0.65;
                    return barY + (barHeightFull - expandedHeight) / 2;
                }
                return barY;
            })
            .attr("width", d => calculateBarWidth(d, timelineXScale))
            .attr("height", d => {
                if (d.isSession && d.type === 'session-expanded') {
                    // Expanded session: 65% height
                    return barHeightFull * 0.65;
                }
                return barHeightFull;
            })
            .attr("rx", d => d.isSession ? 6 : 3)
            .attr("ry", d => d.isSession ? 6 : 3)
            .attr("fill", d => {
                if (d.isSession) {
                    // Use different pattern for expanded vs collapsed sessions
                    if (d.type === 'session-expanded') {
                        return `url(#session-pattern-expanded-${d.sessionId})`;
                    }
                    return `url(#session-pattern-${d.sessionId})`;
                }
                return color(d.prod);
            })
            .attr("stroke", d => {
                const fillColor = d.isSession ? color(d.prod) : color(d.prod);
                const d3Color = d3.color(fillColor);
                return d3Color ? d3Color.darker(0.5) : fillColor;
            })
            .attr("stroke-width", 1)
            .attr("opacity", 1)
            .style("cursor", "pointer")
            .style("pointer-events", "all") // Ensure mouse events work
            .on("click", function(event, d) {
                if (d.isSession) {
                    // Toggle session expand/collapse
                    event.stopPropagation();
                    const sessionId = d.sessionId;
                    if (window._sessionExpandedState.has(sessionId)) {
                        window._sessionExpandedState.delete(sessionId);
                    } else {
                        window._sessionExpandedState.add(sessionId);
                    }
                    // Re-render with updated state
                    renderUnifiedDiagrams(
                        activitySpecsData,
                        userStartTime,
                        userEndTime,
                        lastAggregationEnd,
                        currentTime
                    );
                    return;
                }
                // Use HTMX to open activity edit modal (same as original timeline.js)
                const url = `/s/activities/edit-activity-modal?activity_id=${encodeURIComponent(d.activityId)}`;
                console.log('Direct HTMX GET for activity edit:', url);
                if (window.htmx) {
                    htmx.ajax('GET', url, {target: '#edit-activity-modal-content', swap: 'innerHTML'}).then(() => {
                        const dialog = document.getElementById('edit-activity-modal');
                        if (dialog) dialog.showModal();
                    });
                } else {
                    fetch(url).then(r => r.text()).then(html => {
                        const target = document.querySelector('#edit-activity-modal-content');
                        if (target) target.innerHTML = html;
                        const dialog = document.getElementById('edit-activity-modal');
                        if (dialog) dialog.showModal();
                    });
                }
            })
            .on("mouseover", function(event, d) {
                if (d.isSession) {
                    // Highlight session block
                    g.selectAll(`.session-${d.sessionId}`)
                        .attr("stroke-width", 3)
                        .attr("opacity", 0.9);

                    // Remove any existing tooltips
                    d3.select("body").selectAll(".tooltip").remove();

                    // Create session tooltip
                    const startTime = d3.timeFormat("%H:%M:%S")(d.start);
                    const endTime = d3.timeFormat("%H:%M:%S")(d.end);
                    const duration = (d.end - d.start) / 1000;
                    const hours = Math.floor(duration / 3600);
                    const minutes = Math.floor((duration % 3600) / 60);
                    const durationText = hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;

                    const productivityLevel = d.prod || 'neutral';
                    const displayProductivity = productivityLevel.replace(/_/g, ' ');

                    const tooltipContent = `
                        <div class="rounded-md border border-border bg-popover text-popover-foreground shadow-md p-3">
                            <div class="flex items-start justify-between border-b border-border pb-1.5 mb-2">
                                <span class="text-sm font-semibold">📋 ${d.name || 'Session'}</span>
                                <span class="ml-3 text-[10px] text-muted-foreground">ID: ${d.sessionId}</span>
                            </div>
                            <div class="text-xs space-y-2">
                                <div class="flex items-center gap-2">
                                    <span class="inline-block w-2.5 h-2.5 rounded-full" style="background-color: ${color(productivityLevel)};"></span>
                                    <span class="text-muted-foreground">Avg Productivity:</span>
                                    <strong class="capitalize">${displayProductivity}</strong>
                                </div>
                                <div class="flex items-center gap-2">
                                    <span class="text-muted-foreground">Type:</span>
                                    <strong>Session (Click to expand/collapse)</strong>
                                </div>
                                <div class="mt-2 text-[11px] text-muted-foreground space-y-0.5">
                                    <div>Time: ${startTime} to ${endTime}</div>
                                    <div>Duration: ${durationText}</div>
                                </div>
                            </div>
                        </div>
                    `;

                    d3.select("body").append("div")
                        .attr("class", "tooltip")
                        .html(tooltipContent)
                        .style("left", (event.pageX + 15) + "px")
                        .style("top", (event.pageY - 50) + "px")
                        .style("visibility", "visible")
                        .style("opacity", 0)
                        .transition()
                        .duration(200)
                        .style("opacity", 1);
                } else {
                    // Highlight all bars belonging to the same activity
                    g.selectAll(`.activity-${d.activityId}`)
                        .attr("stroke-width", 2)
                        .attr("stroke", "#2c3e50");

                    // Remove any existing tooltips
                    d3.select("body").selectAll(".tooltip").remove();

                    // Create new tooltip with enhanced styling (same as original timeline.js)
                    d3.select("body").append("div")
                        .attr("class", "tooltip")
                        .html(createTimelineTooltipContent(d, color))
                        .style("left", (event.pageX + 15) + "px")
                        .style("top", (event.pageY - 50) + "px")
                        .style("visibility", "visible")
                        .style("opacity", 0)
                        .transition()
                        .duration(200)
                        .style("opacity", 1);
                }
            })
            .on("mouseout", function(event, d) {
                if (d.isSession) {
                    // Restore session styling
                    g.selectAll(`.session-${d.sessionId}`)
                        .attr("stroke-width", 2)
                        .attr("opacity", 0.75);
                } else {
                    // Restore original styling
                    g.selectAll(`.activity-${d.activityId}`)
                        .attr("stroke-width", 1)
                        .attr("stroke", d => {
                            const fillColor = color(d.prod);
                            const d3Color = d3.color(fillColor);
                            return d3Color ? d3Color.darker(0.5) : fillColor;
                        });
                }

                // Fade out tooltip
                d3.select("body").select(".tooltip")
                    .transition()
                    .duration(200)
                    .style("opacity", 0)
                    .remove();
            })
            .on("mousemove", function(event) {
                // Position tooltip to follow cursor (same as original timeline.js)
                const tooltip = d3.select("body").select(".tooltip");
                const tooltipNode = tooltip.node();
                if (tooltipNode) {
                    const tooltipWidth = tooltipNode.offsetWidth;
                    const tooltipHeight = tooltipNode.offsetHeight;

                    let xPos = event.pageX + 15;
                    if (xPos + tooltipWidth > window.innerWidth) {
                        xPos = event.pageX - tooltipWidth - 10;
                    }

                    let yPos = event.pageY - 50;
                    if (yPos + tooltipHeight > window.innerHeight) {
                        yPos = event.pageY - tooltipHeight - 10;
                    }

                    tooltip
                        .style("left", xPos + "px")
                        .style("top", yPos + "px");
                }
            });

        // Add text labels if bars are wide enough (centered vertically in new bar layout)
    activityBars.each(function(d) {
            const barElement = d3.select(this);
            const barWidth = parseFloat(barElement.attr("width"));
            const barX = parseFloat(barElement.attr("x"));
            const barY = parseFloat(barElement.attr("y"));
            const barHeight = parseFloat(barElement.attr("height"));

            const labelText = d.isSession ? (d.sessionName || d.name) : d.name;
            const fontSize = d.isSession ? 11 : 10;

            const textResult = calculateTextDisplay(barWidth, labelText, fontSize, 'bold', 10);

            // Always create the label group (even if initially hidden) so zoom can show it later
            const parentRow = d3.select(this.parentNode);

            const textElement = parentRow.append("g")
                .attr("class", d.isSession ? "session-bar-label" : "activity-bar-label")
                .attr("transform", `translate(${barX + barWidth / 2}, ${barY + barHeight / 2})`)
                .datum(d)
                .style("pointer-events", "none")
                .style("display", textResult.show ? null : "none"); // Hide if doesn't fit initially

            // Unified text styling for both sessions and activities
            const textFontSize = d.isSession ? "11px" : "10px";

            // Add bold text with dark color for contrast
            textElement.append("text")
                .attr("text-anchor", "middle")
                .attr("dominant-baseline", "middle")
                .attr("font-size", textFontSize)
                .attr("font-weight", "bold")
                .attr("fill", "#1a1a1a")
                .text(textResult.displayText);
        });

        // Add axes
        const timeAxisGen = d3.axisBottom(timelineXScale)
            .tickFormat(d3.timeFormat("%H:%M"));

        const timeAxisSel = g.append("g")
            .attr("transform", `translate(0, ${innerHeight})`)
            .call(timeAxisGen);

        // ----- Install time-based zoom/pan and wire updates -----

            const TEN_MINUTES_MS = 10 * 60 * 1000;
            const computedMaxZoom = Number.isFinite(totalRangeMs) && totalRangeMs > 0
                ? Math.max(1, totalRangeMs / TEN_MINUTES_MS)
                : 1;

            const zoomController = window.chartUtils.installTimeZoom({
        g,
                x: timelineXScale,
                innerW: innerWidth,
                innerH: innerHeight,
                maxZoom: computedMaxZoom,
        attachTo: 'g',
                onZoom: (zx, event) => {
                    try {
                        // Save zoom transform for preservation across re-renders
                        if (event && event.transform) {
                            window._unifiedTimelineZoomTransform = event.transform;
                        }

                        // Update activity bars
                        activityBars
                            .attr("x", d => zx(d.start))
                            .attr("width", d => Math.max(1, zx(d.end) - zx(d.start)));

                        // Update labels (centered on bar, hide if too narrow, truncate if needed)
                        const labelSelector = ".timeline-row .activity-bar-label, .timeline-row .session-bar-label";

                        g.selectAll(labelSelector)
                            .each(function(d) {
                                if (!d) return;

                                const w = Math.max(0, zx(d.end) - zx(d.start));
                                const cx = zx(d.start) + w / 2;

                                // Calculate vertical center based on bar type
                                let cy;
                                if (d.isSession && d.type === 'session-expanded') {
                                    // Expanded session: 65% height, centered
                                    const expandedHeight = barHeightFull * 0.65;
                                    const expandedY = barY + (barHeightFull - expandedHeight) / 2;
                                    cy = expandedY + expandedHeight / 2;
                                } else {
                                    cy = barY + barHeightFull / 2;
                                }

                                const labelText = d.isSession ? (d.sessionName || d.name) : d.name;
                                const fontSize = d.isSession ? 11 : 10;
                                const textResult = calculateTextDisplay(w, labelText, fontSize, 'bold', 10);

                                const labelGroup = d3.select(this);
                                labelGroup.attr("transform", `translate(${cx}, ${cy})`);

                                if (textResult.show) {
                                    // Update text content
                                    labelGroup.selectAll("text").text(textResult.displayText);
                                    labelGroup.style("display", null);
                                } else {
                                    labelGroup.style("display", "none");
                                }
                            });

                        // Update heatmap segments if present
                        if (updateHeatSegments) updateHeatSegments(zx);

                        // Update axis
                        timeAxisSel.call(timeAxisGen.scale(zx));
                    } catch (_) {}
                }
            });

        // Restore saved zoom transform if available
        if (savedZoomTransform && zoomController && zoomController.zoom) {
            try {
                // Apply the saved transform immediately using the zoom behavior
                g.call(zoomController.zoom.transform, savedZoomTransform);
            } catch (err) {
                console.warn("Failed to restore zoom transform:", err);
            }
        }



        }



    // Add CSS for the timeline tooltip and styling (same as original timeline.js)
    function addTimelineCSS() {
        if (!document.getElementById('timeline-styles')) {
            document.head.insertAdjacentHTML('beforeend', `
                <style id="timeline-styles">
                    .tag {
                        display: inline-block;
                        background-color: #e0f0ff;
                        border: 1px solid #a0d0ff;
                        border-radius: 3px;
                        padding: 1px 4px;
                        margin: 1px 2px;
                        font-size: 12px;
                    }

                    .tooltip {
                        background-color: transparent !important;
                        border: none !important;
                        border-radius: 0 !important;
                        padding: 0 !important;
                        box-shadow: none !important;
                        position: absolute;
                        z-index: 100;
                        max-width: 320px;
                        pointer-events: none;
                        transition: opacity 0.2s;
                    }

                    .active-bar {
                        transition: stroke 0.2s, stroke-width 0.2s;
                        cursor: pointer;
                    }

                    .activity-bar-label {
                        pointer-events: none;
                        user-select: none;
                    }

                    .grid text {
                        fill: #555;
                        font-weight: 500;
                    }

                    .grid path {
                        stroke: #ccc;
                    }

                    .grid line {
                        stroke: #e5e5e5;
                    }

                    .timeline-brush .selection,

                    .timeline-brush .overlay,
                    .productivity-brush .overlay {
                        pointer-events: all;
                        cursor: crosshair;
                    }
                </style>
            `);
        }
    }



    // Initial render
    renderUnifiedDiagrams(
        initialActivitySpecsData,
        originalStart,
        originalEnd,
        initialLastAggregationEnd,
        initialCurrentTime
    );

    // Helper: re-render from the latest dataset on the container (reflects current view mode & range)
    function rerenderFromDataset() {
        try {
            const container = document.getElementById('unified-diagrams-container');
            if (!container) return;
            const raw = container.dataset.unified;
            if (!raw) return;
            const data = JSON.parse(raw);
            const lastAggregationEndTime = data.last_aggregation_end_time ? new Date(data.last_aggregation_end_time) : null;
            const currentTime = data.current_time ? new Date(data.current_time) : new Date();
            renderUnifiedDiagrams(
                data.activity_specs,
                new Date(data.start_date),
                new Date(data.end_date),
                lastAggregationEndTime,
                currentTime
            );
        } catch (e) {
            console.warn('Falling back to initial unified diagram render (parse failed):', e);
            renderUnifiedDiagrams(
                initialActivitySpecsData,
                originalStart,
                originalEnd,
                initialLastAggregationEnd,
                initialCurrentTime
            );
        }
    }

    // Add resize handler
    const resizeHandler = () => { rerenderFromDataset(); };

    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(resizeHandler, 250);
    });

    // Re-render when the container itself resizes
    const unifiedContainer = document.getElementById("unified-diagrams-container");
    if (unifiedContainer && 'ResizeObserver' in window) {
        const ro = new ResizeObserver(() => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(resizeHandler, 100);
        });
        ro.observe(unifiedContainer);
    }

    // Listen for unified theme change event and re-render
    document.addEventListener('theme_changed', (e) => {
        try {
            console.log('theme_changed event received:', e?.detail);
        } catch (_) {}
    rerenderFromDataset();
    });

}

console.log("Unified diagram script loaded");
