import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { readFileSync } from "fs";
import { join } from "path";

describe("globals.css defines CSS variables", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark");
  });

  afterEach(() => {
    document.documentElement.classList.remove("dark");
  });

  it("defines --background variable in :root", () => {
    const cssPath = join(__dirname, "../src/styles/globals.css");
    const cssContent = readFileSync(cssPath, "utf-8");
    
    // Check that the :root section defines the --background variable
    expect(cssContent).toContain(":root");
    expect(cssContent).toContain("--background: 0 0% 98%;");
  });

  it("dark mode overrides --background", () => {
    const cssPath = join(__dirname, "../src/styles/globals.css");
    const cssContent = readFileSync(cssPath, "utf-8");
    
    // Check that the .dark section overrides the --background variable
    expect(cssContent).toContain(".dark");
    expect(cssContent).toContain("--background: 0 0% 4%;");
  });

  it("tailwind config has custom font families", () => {
    const configPath = join(__dirname, "../tailwind.config.ts");
    const configContent = readFileSync(configPath, "utf-8");
    
    // Check that the config defines custom font families
    expect(configContent).toContain("fontFamily");
    expect(configContent).toContain("Inter Variable");
    expect(configContent).toContain("Fraunces Variable");
    expect(configContent).toContain("JetBrains Mono");
  });
});
