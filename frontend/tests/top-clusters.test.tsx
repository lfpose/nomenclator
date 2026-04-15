import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TopClustersTable } from "@/components/TopClustersTable";

describe("TopClustersTable", () => {
  const mockClusters = [
    {
      representative: "Jefe de Compras",
      member_count: 3,
      members: ["Jefe de Compras", "jefe de compras", "JEFE DE COMPRAS"],
    },
    {
      representative: "Ingeniero de Software",
      member_count: 2,
      members: ["Ingeniero de Software", "ingeniero software"],
    },
    {
      representative: "Director de Marketing",
      member_count: 1,
      members: ["Director de Marketing"],
    },
  ];

  it("renders one row per cluster", () => {
    render(<TopClustersTable clusters={mockClusters} />);

    // Check for representative values
    expect(screen.getByText("Jefe de Compras")).toBeInTheDocument();
    expect(screen.getByText("Ingeniero de Software")).toBeInTheDocument();
    expect(screen.getByText("Director de Marketing")).toBeInTheDocument();

    // Check for member counts
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("members hidden by default", () => {
    render(<TopClustersTable clusters={mockClusters} />);

    // Members should not be visible initially
    expect(screen.queryByText("jefe de compras")).not.toBeInTheDocument();
    expect(screen.queryByText("ingeniero software")).not.toBeInTheDocument();

    // All rows should have ChevronRight (collapsed state)
    const chevronRights = document.querySelectorAll(".lucide-chevron-right");
    expect(chevronRights).toHaveLength(3);

    // No ChevronDown (expanded state)
    const chevronDowns = document.querySelectorAll(".lucide-chevron-down");
    expect(chevronDowns).toHaveLength(0);
  });

  it("click expands members list", () => {
    render(<TopClustersTable clusters={mockClusters} />);

    // Click on first cluster row
    const firstRow = screen.getByText("Jefe de Compras").closest("tr");
    if (firstRow) {
      fireEvent.click(firstRow);
    }

    // Members should now be visible
    expect(screen.getByText("jefe de compras")).toBeInTheDocument();
    expect(screen.getByText("JEFE DE COMPRAS")).toBeInTheDocument();

    // Chevron should change to down
    const chevronDowns = document.querySelectorAll(".lucide-chevron-down");
    expect(chevronDowns).toHaveLength(1);

    const chevronRights = document.querySelectorAll(".lucide-chevron-right");
    expect(chevronRights).toHaveLength(2);
  });

  it("shows member count", () => {
    render(<TopClustersTable clusters={mockClusters} />);

    // Member counts should be displayed
    const counts = screen.getAllByText(/\d+/);
    const countValues = counts.map((el) => parseInt(el.textContent || "0"));

    expect(countValues).toContain(3);
    expect(countValues).toContain(2);
    expect(countValues).toContain(1);
  });
});
