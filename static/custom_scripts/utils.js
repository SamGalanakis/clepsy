// Utility functions for timeline and productivity diagrams

// Helper function to add opacity to a color
function addOpacityToColor(color, opacity) {
    try {
        // Handle oklch colors by converting them to rgba
        if (color.startsWith('oklch(')) {
            // For oklch colors, we'll use CSS to handle the conversion
            // Create a temporary element to compute the color
            const tempEl = document.createElement('div');
            tempEl.style.color = color;
            document.body.appendChild(tempEl);
            const computedColor = getComputedStyle(tempEl).color;
            document.body.removeChild(tempEl);

            // Convert rgb/rgba to rgba with opacity
            if (computedColor.startsWith('rgb(')) {
                return computedColor.replace('rgb(', 'rgba(').replace(')', `, ${opacity})`);
            } else if (computedColor.startsWith('rgba(')) {
                // Replace existing alpha with new opacity
                return computedColor.replace(/,\s*[\d.]+\)$/, `, ${opacity})`);
            }
            return computedColor;
        }

        // Handle hex colors
        if (color.startsWith('#')) {
            const hex = color.slice(1);
            const r = parseInt(hex.substr(0, 2), 16);
            const g = parseInt(hex.substr(2, 2), 16);
            const b = parseInt(hex.substr(4, 2), 16);
            return `rgba(${r}, ${g}, ${b}, ${opacity})`;
        }

        // Handle rgb colors
        if (color.startsWith('rgb(')) {
            return color.replace('rgb(', 'rgba(').replace(')', `, ${opacity})`);
        }

        // Handle rgba colors
        if (color.startsWith('rgba(')) {
            return color.replace(/,\s*[\d.]+\)$/, `, ${opacity})`);
        }

        // Fallback: return the original color
        return color;
    } catch (e) {
        console.warn('Failed to add opacity to color:', color, e);
        return color;
    }
}

// Helper function to get CSS custom property value with fallbacks
function getCSSVariable(varName, fallback = '#666666') {
    try {
        const value = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
        // Return fallback if empty or invalid
        return value || fallback;
    } catch (e) {
        console.warn(`Failed to get CSS variable ${varName}, using fallback:`, fallback);
        return fallback;
    }
}

// Get theme-aware colors with fallbacks for timeline
function getTimelineColors() {
    // Check if we're in dark mode
    const isDarkMode = document.documentElement.classList.contains('dark') ||
                      document.documentElement.classList.contains('theme-dark') ||
                      window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (isDarkMode) {
        return {
            background: getCSSVariable('--background', '#1a1a1a'),
            chartBackground: getCSSVariable('--card', '#262626'),
            border: getCSSVariable('--border', '#404040'),
            text: getCSSVariable('--foreground', '#ffffff'),
            muted: getCSSVariable('--muted-foreground', '#a0a0a0'),
            grid: getCSSVariable('--border', '#404040'),
            currentTime: '#ef4444', // Red for current time
            aggregationBoundary: '#3b82f6', // Blue for aggregation boundary
            productivity: {
                very_productive: '#22c55e',    // Green - good
                productive: '#84cc16',         // Light green - good
                neutral: '#71717a',            // Gray - neutral
                distracting: '#f59e0b',        // Orange - warning
                very_distracting: '#ef4444'    // Red - bad
            }
        };
    } else {
        return {
            background: getCSSVariable('--background', '#ffffff'),
            chartBackground: getCSSVariable('--card', '#f9fafb'),
            border: getCSSVariable('--border', '#e5e5e5'),
            text: getCSSVariable('--foreground', '#000000'),
            muted: getCSSVariable('--muted-foreground', '#6c757d'),
            grid: getCSSVariable('--border', '#e5e5e5'),
            currentTime: '#dc2626', // Red for current time
            aggregationBoundary: '#2563eb', // Blue for aggregation boundary
            productivity: {
                very_productive: '#16a34a',    // Green - good
                productive: '#65a30d',         // Light green - good
                neutral: '#6b7280',            // Gray - neutral
                distracting: '#d97706',        // Orange - warning
                very_distracting: '#dc2626'    // Red - bad
            }
        };
    }
}

// Get theme-aware colors with fallbacks for productivity diagram
function getProductivityColors() {
    // Check if we're in dark mode
    const isDarkMode = document.documentElement.classList.contains('dark') ||
                      document.documentElement.classList.contains('theme-dark') ||
                      window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (isDarkMode) {
        return {
            background: getCSSVariable('--background', '#1a1a1a'),
            chartBackground: getCSSVariable('--card', '#262626'),
            border: getCSSVariable('--border', '#404040'),
            text: getCSSVariable('--foreground', '#ffffff'),
            muted: getCSSVariable('--muted-foreground', '#a0a0a0'),
            grid: getCSSVariable('--border', '#404040'),
            // Semantic productivity colors (green = good, red = bad)
            productivity: {
                very_productive: '#22c55e',   // Green - very good
                productive: '#84cc16',        // Light green - good
                neutral: '#eab308',          // Yellow - neutral/okay
                distracting: '#f97316',      // Orange - concerning
                very_distracting: '#ef4444', // Red - bad
                unknown: '#71717a'           // Gray - unknown
            }
        };
    } else {
        return {
            background: getCSSVariable('--background', '#ffffff'),
            chartBackground: getCSSVariable('--card', '#f9fafb'),
            border: getCSSVariable('--border', '#e5e5e5'),
            text: getCSSVariable('--foreground', '#000000'),
            muted: getCSSVariable('--muted-foreground', '#6c757d'),
            grid: getCSSVariable('--border', '#e5e5e5'),
            // Semantic productivity colors (green = good, red = bad)
            productivity: {
                very_productive: '#16a34a',   // Green - very good
                productive: '#65a30d',        // Light green - good
                neutral: '#ca8a04',          // Yellow - neutral/okay
                distracting: '#ea580c',      // Orange - concerning
                very_distracting: '#dc2626', // Red - bad
                unknown: '#6b7280'           // Gray - unknown
            }
        };
    }
}
