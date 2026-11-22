import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { withQuery } from "@/test/render";

import { UserForm } from "./UserForm";
import { toPayload } from "./userPayload";

describe("UserForm", () => {
  it("rejects a student combined with another role before calling the server", async () => {
    const onSubmit = vi.fn();
    withQuery(<UserForm submitLabel="создать" onSubmit={onSubmit} />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Фамилия"), "Алиев");
    await user.type(screen.getByLabelText("Имя"), "Фарход");
    await user.click(screen.getByLabelText("ученик"));
    await user.click(screen.getByLabelText("преподаватель"));
    await user.click(screen.getByRole("button", { name: "создать" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Роль «ученик» не совмещается с другими",
    );
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows student fields only for the student role and sends them", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    withQuery(<UserForm submitLabel="создать" onSubmit={onSubmit} />);
    const user = userEvent.setup();
    expect(screen.queryByLabelText("Телефон родителя")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Фамилия"), "Алиев");
    await user.type(screen.getByLabelText("Имя"), "Фарход");
    await user.click(screen.getByLabelText("ученик"));
    await user.type(screen.getByLabelText("Пароль"), "долгий пароль 2026");
    await user.selectOptions(screen.getByLabelText("Класс"), "11");
    await user.type(screen.getByLabelText("Телефон родителя"), "+998901112233");
    await user.click(screen.getByRole("button", { name: "создать" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0]?.[0];
    expect(payload.roles).toEqual(["student"]);
    expect(payload.student_profile.school_grade).toBe(11);
    expect(payload.student_profile.parent_phone).toBe("+998901112233");
    expect(payload.login).toBeUndefined();
    expect(payload.teacher_profile).toBeUndefined();
    expect(payload.password).toBe("долгий пароль 2026");
  });

  it("asks for a password of 10 characters before creating", async () => {
    const onSubmit = vi.fn();
    withQuery(<UserForm submitLabel="создать" onSubmit={onSubmit} />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Фамилия"), "Алиев");
    await user.type(screen.getByLabelText("Имя"), "Фарход");
    await user.click(screen.getByLabelText("ученик"));
    await user.type(screen.getByLabelText("Пароль"), "short");
    await user.click(screen.getByRole("button", { name: "создать" }));
    expect(await screen.findByText("Не короче 10 символов")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});

describe("toPayload", () => {
  it("lowercases an explicit login and drops profiles of other roles", () => {
    const payload = toPayload({
      last_name: "Ким",
      first_name: "Сергей",
      middle_name: "",
      login: "Kim.S",
      roles: ["teacher"],
      student: {
        phone: "",
        school: "x",
        school_grade: "",
        target: "",
        target_score: "",
        parent_name: "",
        parent_phone: "",
        admin_note: "",
      },
      teacher: { phone: "+998" },
      password: "",
      must_change_password: false,
      is_superadmin: false,
      admin_sections: [],
    });
    expect(payload).toEqual({
      last_name: "Ким",
      first_name: "Сергей",
      middle_name: "",
      login: "kim.s",
      roles: ["teacher"],
      must_change_password: false,
      teacher_profile: { phone: "+998" },
    });
  });
});
