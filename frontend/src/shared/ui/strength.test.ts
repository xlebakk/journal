import { passwordStrength } from "./strength";

describe("passwordStrength", () => {
  it("is weak below 10 characters", () => {
    expect(passwordStrength("")).toBe(0);
    expect(passwordStrength("abc12")).toBe(1);
  });

  it("accepts a phrase of several words without symbols", () => {
    expect(passwordStrength("зелёный чай по утрам")).toBe(4);
  });

  it("penalises the login or name inside the password", () => {
    expect(passwordStrength("aliev.f-2026-summer", ["aliev.f"])).toBe(1);
  });

  it("penalises repeated characters and keyboard runs", () => {
    expect(passwordStrength("aaaaaaaaaaaa")).toBe(1);
    expect(passwordStrength("1234567890abc")).toBe(1);
  });
});
