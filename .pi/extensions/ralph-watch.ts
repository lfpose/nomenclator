/**
 * Ralph Watch Extension
 *
 * Integrates Ralph loop monitoring into Pi's TUI.
 * Monitors .ralph-obs/ directory for loop state, health events, and iteration stats.
 *
 * Features:
 * - /ralph-watch command to toggle monitoring on/off
 * - Status indicator in footer showing loop health
 * - Widget showing detailed stats (current task, stuck count, success rate, etc.)
 * - Real-time updates from .ralph-obs/state.json, health.log, and iterations.jsonl
 */

import type { ExtensionAPI, ExtensionContext } from "@mariozechner/pi-coding-agent";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { watch } from "node:fs/promises";

// Types for Ralph data
interface RalphState {
	current_task: string;
	stuck_count: number;
	last_successful: string;
	total_failed: number;
	updated_at: string;
}

interface IterationStats {
	total: number;
	success: number;
	failed: number;
	errors: number;
	successRate: number;
}

interface HealthEvent {
	timestamp: string;
	level: "INFO" | "WARN" | "ERROR";
	message: string;
}

// Extension state
let watchEnabled = false;
let updateInterval: NodeJS.Timeout | null = null;
let currentRalphState: RalphState | null = null;
let currentIterationStats: IterationStats | null = null;
let currentHealthEvents: HealthEvent[] = [];

// Parse state.json
async function parseRalphState(obsDir: string): Promise<RalphState | null> {
	try {
		const content = await readFile(join(obsDir, "state.json"), "utf-8");
		return JSON.parse(content);
	} catch {
		return null;
	}
}

// Parse iterations.jsonl
async function parseIterationStats(obsDir: string): Promise<IterationStats> {
	try {
		const content = await readFile(join(obsDir, "iterations.jsonl"), "utf-8");
		const lines = content.trim().split("\n").filter(Boolean);

		let success = 0;
		let failed = 0;
		let errors = 0;

		for (const line of lines) {
			try {
				const entry = JSON.parse(line);
				if (entry.status === "success") success++;
				else if (entry.status === "test_failed") failed++;
				else if (entry.status === "agent_error") errors++;
			} catch {
				// Skip malformed lines
			}
		}

		const total = lines.length;
		const successRate = total > 0 ? Math.round((success / total) * 100) : 0;

		return { total, success, failed, errors, successRate };
	} catch {
		return { total: 0, success: 0, failed: 0, errors: 0, successRate: 0 };
	}
}

// Parse health.log
async function parseHealthEvents(obsDir: string): Promise<HealthEvent[]> {
	try {
		const content = await readFile(join(obsDir, "health.log"), "utf-8");
		const lines = content.trim().split("\n").filter(Boolean);

		// Get last 5 events
		const recentLines = lines.slice(-5);

		return recentLines.map((line) => {
			// Parse format: [timestamp] [LEVEL] message
			const timestampMatch = line.match(/\[([^\]]+)\]/);
			const levelMatch = line.match(/\[(INFO|WARN|ERROR)\]/);

			const timestamp = timestampMatch?.[1] || "";
			const level = (levelMatch?.[1] as "INFO" | "WARN" | "ERROR") || "INFO";
			const message = line.replace(/\[.*?\]\s*\[.*?\]\s*/, "");

			return { timestamp, level, message };
		});
	} catch {
		return [];
	}
}

// Update function - reads all data and updates UI
async function updateRalphData(ctx: ExtensionContext): Promise<void> {
	if (!ctx.cwd || !watchEnabled) return;

	const obsDir = join(ctx.cwd, ".ralph-obs");

	// Read all data
	currentRalphState = await parseRalphState(obsDir);
	currentIterationStats = await parseIterationStats(obsDir);
	currentHealthEvents = await parseHealthEvents(obsDir);

	updateStatus(ctx);
	updateWidget(ctx);
}

// Update footer status
function updateStatus(ctx: ExtensionContext): void {
	if (!watchEnabled || !currentRalphState) {
		ctx.ui.setStatus("ralph-watch", undefined);
		return;
	}

	const theme = ctx.ui.theme;
	const { stuck_count, total_failed } = currentRalphState;

	let status: string;
	let color: (s: string) => string;

	if (stuck_count >= 5) {
		status = "🚫 STOPPED";
		color = theme.fg.bind(theme, "error");
	} else if (stuck_count >= 3) {
		status = "⚠️ WARNING";
		color = theme.fg.bind(theme, "warning");
	} else if (stuck_count >= 1) {
		status = "⚠️ FAILURES";
		color = theme.fg.bind(theme, "warning");
	} else if (total_failed > 0) {
		status = "✓ RUNNING";
		color = theme.fg.bind(theme, "accent");
	} else {
		status = "✓ HEALTHY";
		color = theme.fg.bind(theme, "success");
	}

	ctx.ui.setStatus("ralph-watch", color(status));
}

// Update widget with detailed stats
function updateWidget(ctx: ExtensionContext): void {
	if (!watchEnabled) {
		ctx.ui.setWidget("ralph-watch", undefined);
		return;
	}

	const theme = ctx.ui.theme;
	const lines: string[] = [];

	// Header
	lines.push("");
	lines.push(theme.bold(theme.fg("accent", " Ralph Loop Status ")));
	lines.push("");

	if (currentRalphState) {
		// Current state
		lines.push(`${theme.fg("dim", "Task:")}    ${currentRalphState.current_task || "none"}`);
		lines.push(
			`${theme.fg("dim", "Stuck:")}   ${currentRalphState.stuck_count}${theme.fg("dim", "/5")}`
		);

		const failedColor =
			currentRalphState.total_failed > 0 ? "error" : "success";
		lines.push(
			`${theme.fg("dim", "Failed:")}  ${theme.fg(failedColor, String(currentRalphState.total_failed))}`
		);

		// Last success
		const lastSuccess = currentRalphState.last_successful;
		if (lastSuccess && lastSuccess !== "never") {
			const date = new Date(lastSuccess);
			const timeAgo = getTimeAgo(date);
			lines.push(`${theme.fg("dim", "Last:")}    ${theme.fg("muted", timeAgo)}`);
		}

		lines.push("");
	}

	if (currentIterationStats && currentIterationStats.total > 0) {
		// Iteration stats
		lines.push(`${theme.fg("dim", "Total:")}   ${currentIterationStats.total}`);
		lines.push(
			`${theme.fg("dim", "Success:")} ${theme.fg("success", String(currentIterationStats.success))} (${currentIterationStats.successRate}%)`
		);

		if (currentIterationStats.failed > 0) {
			lines.push(
				`${theme.fg("dim", "Failed:")}  ${theme.fg("error", String(currentIterationStats.failed))}`
			);
		}

		if (currentIterationStats.errors > 0) {
			lines.push(
				`${theme.fg("dim", "Errors:")}  ${theme.fg("warning", String(currentIterationStats.errors))}`
			);
		}

		lines.push("");
	}

	if (currentHealthEvents.length > 0) {
		// Recent health events
		lines.push(`${theme.fg("dim", "Recent:")}`);
		for (const event of currentHealthEvents.slice(0, 3)) {
			const icon =
				event.level === "INFO"
					? theme.fg("success", "✓")
					: event.level === "WARN"
						? theme.fg("warning", "⚠")
						: theme.fg("error", "✗");
			lines.push(`  ${icon} ${theme.fg("muted", event.message.substring(0, 40))}`);
		}
	}

	ctx.ui.setWidget("ralph-watch", lines, { placement: "aboveEditor" });
}

// Get human-readable time ago
function getTimeAgo(date: Date): string {
	const now = new Date();
	const diffMs = now.getTime() - date.getTime();
	const diffSec = Math.floor(diffMs / 1000);
	const diffMin = Math.floor(diffSec / 60);
	const diffHour = Math.floor(diffMin / 60);
	const diffDay = Math.floor(diffHour / 24);

	if (diffSec < 60) return `${diffSec}s ago`;
	if (diffMin < 60) return `${diffMin}m ago`;
	if (diffHour < 24) return `${diffHour}h ago`;
	return `${diffDay}d ago`;
}

// Toggle watch mode
function toggleWatch(ctx: ExtensionContext): void {
	watchEnabled = !watchEnabled;

	if (watchEnabled) {
		// Enable
		updateRalphData(ctx);
		updateInterval = setInterval(() => updateRalphData(ctx), 2000);
		ctx.ui.notify("Ralph watch enabled", "info");
	} else {
		// Disable
		if (updateInterval) {
			clearInterval(updateInterval);
			updateInterval = null;
		}
		currentRalphState = null;
		currentIterationStats = null;
		currentHealthEvents = [];
		ctx.ui.setStatus("ralph-watch", undefined);
		ctx.ui.setWidget("ralph-watch", undefined);
		ctx.ui.notify("Ralph watch disabled", "info");
	}

	persistState(ctx);
}

// Persist state to session
function persistState(ctx: ExtensionContext): void {
	ctx.pi.appendEntry("ralph-watch", {
		enabled: watchEnabled,
	});
}

// Restore state from session
async function restoreState(ctx: ExtensionContext): Promise<void> {
	for (const entry of ctx.sessionManager.getEntries()) {
		if (entry.type === "custom" && entry.customType === "ralph-watch") {
			const state = entry.data as { enabled?: boolean };
			if (state.enabled) {
				watchEnabled = true;
				updateRalphData(ctx);
				updateInterval = setInterval(() => updateRalphData(ctx), 2000);
				ctx.ui.notify("Ralph watch restored", "info");
			}
			break;
		}
	}
}

export default function ralphWatchExtension(pi: ExtensionAPI): void {
	// Session start - restore previous state
	pi.on("session_start", async (_event, ctx) => {
		if (!ctx.hasUI) return;
		await restoreState(ctx);
	});

	// Register command
	pi.registerCommand("ralph-watch", {
		description: "Toggle Ralph loop monitoring (shows .ralph-obs data in TUI)",
		handler: async (_args, ctx) => {
			toggleWatch(ctx);
		},
	});

	// Register keyboard shortcut
	pi.registerShortcut("ctrl+alt+r", {
		description: "Toggle Ralph watch",
		handler: async (ctx) => {
			toggleWatch(ctx);
		},
	});

	// Register flag
	pi.registerFlag("ralph-watch", {
		description: "Start with Ralph watch enabled",
		type: "boolean",
		default: false,
	});

	// Cleanup on session shutdown
	pi.on("session_shutdown", async () => {
		if (updateInterval) {
			clearInterval(updateInterval);
			updateInterval = null;
		}
	});

	// Handle flag on startup
	pi.on("session_start", async (_event, ctx) => {
		if (!ctx.hasUI) return;
		if (pi.getFlag("--ralph-watch") && !watchEnabled) {
			toggleWatch(ctx);
		}
	});
}
