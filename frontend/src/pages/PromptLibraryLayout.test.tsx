import { render, screen } from "@testing-library/react";
import { MemoryRouter, Navigate, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import PromptLibraryLayout from "./PromptLibraryLayout";

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/prompt-library" element={<PromptLibraryLayout />}>
          <Route index element={<Navigate replace to="workbench" />} />
          <Route path="workbench" element={<h1>Prompt Workbench Screen</h1>} />
          <Route path="categories" element={<h1>分類管理 Screen</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("PromptLibraryLayout", () => {
  it("redirects the library root to the workbench", async () => {
    renderAt("/prompt-library");
    expect(await screen.findByRole("heading", { name: "Prompt Workbench Screen" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Prompt Workbench" })).toHaveAttribute("aria-current", "page");
  });

  it("keeps category management on a separate active route", () => {
    renderAt("/prompt-library/categories");
    expect(screen.getByRole("heading", { name: "分類管理 Screen" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Prompt Workbench Screen" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "分類管理" })).toHaveAttribute("aria-current", "page");
  });
});
