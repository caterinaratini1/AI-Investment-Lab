import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { demoDashboardData } from "../lib/demo-data";
import { DashboardView } from "./dashboard-view";

vi.mock("./performance-chart", () => ({
  PerformanceChart: () => <div data-testid="performance-chart">Chart</div>,
}));

afterEach(cleanup);

describe("DashboardView", () => {
  it("makes preview status and the primary comparison immediately visible", () => {
    render(<DashboardView data={demoDashboardData} />);

    expect(screen.getByRole("heading", { level: 1, name: /AI versus the world/i })).toBeVisible();
    expect(screen.getByText("Illustrative preview")).toBeVisible();
    expect(screen.getByRole("heading", { name: /invested with AI vs IWDA/i })).toBeVisible();
    expect(screen.getByTestId("performance-chart")).toBeVisible();
  });

  it("renders holdings as a semantic, labelled table", () => {
    render(<DashboardView data={demoDashboardData} />);

    const table = screen.getByRole("table");
    expect(within(table).getByRole("columnheader", { name: "Asset" })).toBeVisible();
    expect(within(table).getByRole("rowheader", { name: /ASML Holding/i })).toBeVisible();
    expect(within(table).getAllByRole("row")).toHaveLength(5);
  });

  it("keeps future risk analytics visibly unpublished", () => {
    render(<DashboardView data={demoDashboardData} />);

    expect(screen.getByText("Maximum drawdown")).toBeVisible();
    expect(screen.getAllByText("Phase 5")).toHaveLength(2);
  });
});
