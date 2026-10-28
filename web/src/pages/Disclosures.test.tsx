import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test } from "vitest";
import { Disclosures } from "./Disclosures";

afterEach(cleanup);

test("the page names its sources, where data is stored and the AI position", () => {
  render(
    <MemoryRouter>
      <Disclosures />
    </MemoryRouter>,
  );
  expect(screen.getByText(/SEBI public issues/)).toBeTruthy();
  expect(screen.getByText(/Oracle Cloud's Mumbai region/)).toBeTruthy();
  expect(screen.getByText(/still call Anthropic's API/)).toBeTruthy();
  expect(screen.getByText(/pending legal review/)).toBeTruthy();
});
