/**
 * Ralph Watch Extension
 *
 * Integrates Ralph loop monitoring into Pi's TUI as a sidebar panel.
 * Monitors .ralph-obs/ directory for loop state, health events, and iteration stats.
 *
 * Features:
 * - /ralph-watch command to toggle monitoring on/off
 * - Sidebar panel on the right showing real-time stats
 * - Status indicator in footer showing loop health
 * - Real-time updates from .ralph-obs/state.json, health.log, and iterations.jsonl
 */

import type { ExtensionAPI, ExtensionContext } from "@mariozechner/pi-coding-agent";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { Container, Text, Box } from "@mariozechner/pi-tui";

// Types for Ralph data
interface RalphState {
	current_task: string;
	stuck_count: number;
	last_successful: string;
	total_failed: number;
	pid?: number;
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
let overlayHandle: { close: () => void; setHidden: (hidden: boolean) => void } | null = null;
let sidebarUpdateFn: ((state: RalphState | null, stats: IterationStats | null, events: HealthEvent[], isRunning: boolean) => void) | null = null;
let isRalphRunning = false;

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

// Check if process is running
async function isProcessRunning(pid: number): Promise<boolean> {
	try {
		const { exec } = await import("node:child_process");
		return new Promise((resolve) => {
			exec(`kill -0 ${pid} 2>/dev/null`, (error) => {
				resolve(!error);
			});
		});
	} catch {
		return false;
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

	// Check if Ralph process is running
	// Default to false when there's no PID, otherwise we'd show RUNNING forever
	isRalphRunning = false;
	if (currentRalphState?.pid) {
		isRalphRunning = await isProcessRunning(currentRalphState.pid);
	} else if (currentRalphState?.updated_at) {
		// If no PID but we have state, check if it's stale (> 5 minutes old)
		const stateAge = Date.now() - new Date(currentRalphState.updated_at).getTime();
		if (stateAge < 5 * 60 * 1000) {
			// State is recent, assume running (old state format without PID)
			isRalphRunning = true;
		}
	}

	// Update sidebar if it's visible
	if (sidebarUpdateFn) {
		sidebarUpdateFn(currentRalphState, currentIterationStats, currentHealthEvents, isRalphRunning);
	}

	updateStatus(ctx);
}

// Update footer status
async function updateStatus(ctx: ExtensionContext): Promise<void> {
	if (!watchEnabled || !currentRalphState) {
		ctx.ui.setStatus("ralph-watch", undefined);
		return;
	}

	const theme = ctx.ui.theme;
	const { stuck_count, total_failed, pid } = currentRalphState;

	// Check if Ralph process is actually running
	let isRunning = false;
	if (pid) {
		isRunning = await isProcessRunning(pid);
	} else if (currentRalphState?.updated_at) {
		// If no PID but we have state, check if it's stale (> 5 minutes old)
		const stateAge = Date.now() - new Date(currentRalphState.updated_at).getTime();
		isRunning = stateAge < 5 * 60 * 1000;
	}

	let status: string;
	let color: (s: string) => string;

	if (!isRunning) {
		status = "⭕ STOPPED";
		color = theme.fg.bind(theme, "dim");
	} else if (stuck_count >= 5) {
		status = "🚫 STUCK";
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

// Sidebar component class
class RalphSidebarComponent extends Container {
	private theme: any;
	private invalidateFn: () => void;
	private ralphState: RalphState | null = null;
	private iterationStats: IterationStats | null = null;
	private healthEvents: HealthEvent[] = [];
	private isRunning: boolean = true;

	constructor(theme: any, invalidateFn: () => void) {
		super();
		this.theme = theme;
		this.invalidateFn = invalidateFn;
	}

	updateData(state: RalphState | null, stats: IterationStats | null, events: HealthEvent[], running: boolean): void {
		this.ralphState = state;
		this.iterationStats = stats;
		this.healthEvents = events;
		this.isRunning = running;
		this.invalidate();
	}

	override invalidate(): void {
		super.invalidate();
		this.rebuild();
	}

	private rebuild(): void {
		this.clear();
		const theme = this.theme;
		const th = theme;

		// Create content lines
		const lines: string[] = [];

		// Header
		lines.push("");
		lines.push(th.bold(th.fg("accent", " Ralph Status ")));
		lines.push("");

		if (this.ralphState) {
			// Current state
			lines.push(`${th.fg("dim", "Task:")}    ${this.ralphState.current_task || "none"}`);
			const runningStatus = this.isRunning ? th.fg("success", "●") : th.fg("dim", "○");
			lines.push(`${th.fg("dim", "Stuck:")}   ${this.ralphState.stuck_count}${th.fg("dim", "/5")} ${runningStatus}`);

			const failedColor = this.ralphState.total_failed > 0 ? "error" : "success";
			lines.push(`${th.fg("dim", "Failed:")}  ${th.fg(failedColor, String(this.ralphState.total_failed))}`);

			// Last success
			const lastSuccess = this.ralphState.last_successful;
			if (lastSuccess && lastSuccess !== "never") {
				const date = new Date(lastSuccess);
				const timeAgo = this.getTimeAgo(date);
				lines.push(`${th.fg("dim", "Last:")}    ${th.fg("muted", timeAgo)}`);
			}

			lines.push("");
		}

		if (this.iterationStats && this.iterationStats.total > 0) {
			// Iteration stats
			lines.push(`${th.fg("dim", "Total:")}   ${this.iterationStats.total}`);
			lines.push(
				`${th.fg("dim", "Success:")} ${th.fg("success", String(this.iterationStats.success))} (${this.iterationStats.successRate}%)`
			);

			if (this.iterationStats.failed > 0) {
				lines.push(`${th.fg("dim", "Failed:")}  ${th.fg("error", String(this.iterationStats.failed))}`);
			}

			if (this.iterationStats.errors > 0) {
				lines.push(`${th.fg("dim", "Errors:")}  ${th.fg("warning", String(this.iterationStats.errors))}`);
			}

			lines.push("");
		}

		if (this.healthEvents.length > 0) {
			// Recent health events
			lines.push(`${th.fg("dim", "Recent:")}`);
			for (const event of this.healthEvents.slice(0, 5)) {
				const icon =
					event.level === "INFO"
						? th.fg("success", "✓")
						: event.level === "WARN"
							? th.fg("warning", "⚠")
							: th.fg("error", "✗");
				// Truncate message to fit
				const msg = event.message.length > 25 ? event.message.substring(0, 25) + "..." : event.message;
				lines.push(`  ${icon} ${th.fg("muted", msg)}`);
			}
		}

		// Add lines as Text components
		for (const line of lines) {
			this.addChild(new Text(line, 0, 0));
		}
	}

	private getTimeAgo(date: Date): string {
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
}

// Show sidebar overlay
function showSidebar(ctx: ExtensionContext): void {
	if (overlayHandle) {
		// Already showing, just update data
		return;
	}

	overlayHandle = ctx.ui.custom<boolean>(
		(tui, theme, _kb, done) => {
			const component = new Box(1, 1, (s) => theme.bg("selectedBg", s));
			const sidebar = new RalphSidebarComponent(theme, () => tui.requestRender());
			component.addChild(sidebar);

			// Initial data
			sidebar.updateData(currentRalphState, currentIterationStats, currentHealthEvents, isRalphRunning);

			// Store reference to update later
			sidebarUpdateFn = (state: RalphState | null, stats: IterationStats | null, events: HealthEvent[], running: boolean) => {
				sidebar.updateData(state, stats, events, running);
			};

			return {
				render: (width) => component.render(width),
				invalidate: () => component.invalidate(),
				handleInput: () => false, // Don't consume input - let it pass through
			};
		},
		{
			overlay: true,
			overlayOptions: {
				width: 35,
				minWidth: 30,
				maxWidth: 40,
				anchor: "right",
				margin: 0,
				visible: (termWidth, _termHeight) => termWidth >= 100, // Only show on wide terminals
			},
			onHandle: (handle) => {
				overlayHandle = handle;
			},
		},
	);
}

// Hide sidebar overlay
function hideSidebar(): void {
	if (overlayHandle) {
		overlayHandle.close();
		overlayHandle = null;
	}
	sidebarUpdateFn = null;
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
		showSidebar(ctx);
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
		hideSidebar();
		ctx.ui.setStatus("ralph-watch", undefined);
		ctx.ui.notify("Ralph watch disabled", "info");
	}

	persistState(ctx);
}

// Persist state to session
function persistState(ctx: ExtensionContext): void {
	// Access pi from closure, not ctx
	try {
		// This is a bit tricky - pi is in the outer scope
		// We'll use a different approach with session_manager
		ctx.sessionManager.appendCustomEntry("ralph-watch", {
			enabled: watchEnabled,
		});
	} catch {
		// If this fails, it's not critical
	}
}

// Restore state from session (only from current branch)
async function restoreState(ctx: ExtensionContext): Promise<void> {
	// Get entries in current branch only
	const branchEntries = ctx.sessionManager.getBranch();

	for (const entry of branchEntries) {
		if (entry.type === "custom" && entry.customType === "ralph-watch") {
			const state = entry.data as { enabled?: boolean };
			if (state.enabled) {
				watchEnabled = true;
				updateRalphData(ctx);
				showSidebar(ctx);
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
		description: "Toggle Ralph loop monitoring (sidebar panel on right)",
		handler: async (_args, ctx) => {
			toggleWatch(ctx);
		},
	});

	// Register keyboard shortcut
	pi.registerShortcut("ctrl+alt+r", {
		description: "Toggle Ralph watch sidebar",
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
		hideSidebar();
	});

	// Handle flag on startup
	pi.on("session_start", async (_event, ctx) => {
		if (!ctx.hasUI) return;
		if (pi.getFlag("--ralph-watch") && !watchEnabled) {
			toggleWatch(ctx);
		}
	});
}
