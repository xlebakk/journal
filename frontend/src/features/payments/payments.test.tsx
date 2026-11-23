import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { mockApi } from "@/test/api-mock";
import { renderRoutes } from "@/test/render";

import { MyPaymentsPage } from "./MyPaymentsPage";
import { StudentPaymentsPage } from "./StudentPaymentsPage";

const CHARGE = {
  kind: "charge",
  id: "c1",
  date: "2026-11-01",
  amount: 450000,
  group_name: "11-М",
  full_amount: 500000,
  discount_percent: 10,
  method: "",
  comment: "",
};
const PAYMENT = {
  kind: "payment",
  id: "p1",
  date: "2026-11-05",
  amount: 200000,
  group_name: "",
  full_amount: null,
  discount_percent: null,
  method: "cash",
  comment: "за ноябрь",
};
const ADMIN = { voided: false, void_reason: "", author_name: "Каримова Д." };
const LEDGER = {
  student: "s1", full_name: "Алиев Фарход", login: "aliev.f", charged: 450000, paid: 200000,
  debt: 250000, discount_percent: 10,
  entries: [{ ...PAYMENT, ...ADMIN }, { ...CHARGE, ...ADMIN }],
}; // prettier-ignore

describe("StudentPaymentsPage", () => {
  it("shows the debt, takes a payment and voids an entry with a reason", async () => {
    const { calls } = mockApi({
      "GET /admin/payments/students/s1": { body: LEDGER },
      "POST /admin/payments/students/s1/payments": { status: 201, body: LEDGER },
      "POST /admin/payments/payments/p1/void": { status: 204 },
    });
    renderRoutes(
      [{ path: "/admin/payments/:id", element: <StudentPaymentsPage /> }],
      "/admin/payments/s1",
    );
    expect(await screen.findByRole("heading", { name: "Алиев Фарход" })).toBeInTheDocument();
    expect(screen.getByText(/250\s000 сомони/)).toHaveClass("debt");
    expect(screen.getByText(/Начисление за ноябрь 2026 г\. · 11-М/)).toBeInTheDocument();
    expect(screen.getByText(/500\s000 сомони со скидкой 10%/)).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Сумма"), "250000");
    await userEvent.click(screen.getByRole("button", { name: "принять оплату" }));
    expect(await screen.findByText("Оплата записана.")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")?.body).toMatchObject({
      amount: 250000,
      method: "cash",
    });

    await userEvent.click(screen.getAllByRole("button", { name: "аннулировать" })[0]!);
    const dialog = await screen.findByRole("dialog");
    const confirm = within(dialog).getByRole("button", { name: "аннулировать" });
    expect(confirm).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText("Причина"), "ошибка суммы");
    await userEvent.click(confirm);
    expect(calls.at(-2)).toMatchObject({
      path: "/admin/payments/payments/p1/void",
      body: { reason: "ошибка суммы" },
    });
  });
});

describe("MyPaymentsPage", () => {
  it("tells the student what is owed", async () => {
    mockApi({
      "GET /student/payments": {
        body: {
          charged: 450000,
          paid: 200000,
          debt: 250000,
          discount_percent: 10,
          entries: [PAYMENT, CHARGE],
        },
      },
    });
    renderRoutes([{ path: "/student/payments", element: <MyPaymentsPage /> }], "/student/payments");
    expect(
      await screen.findByText(/Задолженность за обучение: 250\s000 сомони/),
    ).toBeInTheDocument();
    expect(screen.getByText("Ваша скидка: 10%.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "аннулировать" })).not.toBeInTheDocument();
  });
});
