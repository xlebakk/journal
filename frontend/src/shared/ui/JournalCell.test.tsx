import { render, screen } from "@testing-library/react";

import { JournalCell } from "./JournalCell";

describe("JournalCell", () => {
  it("marks low grades in red and keeps normal ones in ink", () => {
    render(<JournalCell grades={[49, 50]} lowBelow={50} />);
    expect(screen.getByText("49")).toHaveClass("low");
    expect(screen.getByText("50")).toHaveClass("grade");
  });

  it("shows absence as a letter, not only as colour", () => {
    render(<JournalCell attendance="absent" lowBelow={50} />);
    expect(screen.getByText("н")).toBeInTheDocument();
    expect(screen.getByText("отсутствовал")).toHaveClass("visually-hidden");
  });

  it("renders nothing visible for plain presence", () => {
    const { container } = render(<JournalCell lowBelow={50} />);
    expect(container).toHaveTextContent("");
  });
});
