import { describe, expect, it } from "vitest";
import { detailToMessage } from "./api";

describe("detailToMessage", () => {
  it("passes a plain FastAPI detail string through", () => {
    expect(detailToMessage("Percentages must sum to 100")).toBe("Percentages must sum to 100");
  });

  it("keeps only the readable half of a Pydantic 422 body", () => {
    const detail = [
      {
        type: "greater_than",
        loc: ["body", "total_amount"],
        msg: "Input should be greater than 0",
        input: "0000.00",
        ctx: { gt: 0 },
      },
    ];
    expect(detailToMessage(detail)).toBe("Input should be greater than 0.");
  });

  it("joins several errors and drops duplicates", () => {
    const detail = [
      { loc: ["body", "splits", 0, "amount"], msg: "Input should be greater than 0" },
      { loc: ["body", "splits", 1, "amount"], msg: "Input should be greater than 0" },
      { loc: ["body", "currency"], msg: "String should match pattern" },
    ];
    expect(detailToMessage(detail)).toBe(
      "Input should be greater than 0. String should match pattern.",
    );
  });

  it("returns null when there is nothing readable, so the caller keeps its fallback", () => {
    expect(detailToMessage(undefined)).toBeNull();
    expect(detailToMessage("")).toBeNull();
    expect(detailToMessage([])).toBeNull();
    expect(detailToMessage([{ type: "greater_than", loc: ["body"] }])).toBeNull();
    expect(detailToMessage({ code: 42 })).toBeNull();
  });
});
