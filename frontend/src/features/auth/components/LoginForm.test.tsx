// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { LoginForm } from "./LoginForm";

afterEach(cleanup);

function renderForm(props: Partial<Parameters<typeof LoginForm>[0]> = {}) {
  const onSubmit = vi.fn();
  render(<LoginForm onSubmit={onSubmit} {...props} />);
  return {
    onSubmit,
    email: screen.getByLabelText("이메일"),
    password: screen.getByLabelText("비밀번호"),
    submit: screen.getByRole("button", { name: "로그인하기" }),
  };
}

test("비밀번호는 가려서 입력한다", () => {
  const { password } = renderForm();

  expect(password.getAttribute("type")).toBe("password");
});

test("입력하지 않고 제출하면 각 칸 아래에 무엇을 입력할지 알려 주고 제출하지 않는다", async () => {
  const { onSubmit, email, password, submit } = renderForm();

  fireEvent.click(submit);

  expect(await screen.findByText("이메일을 입력해 주세요.")).toBeDefined();
  expect(screen.getByText("비밀번호를 입력해 주세요.")).toBeDefined();
  expect(email.getAttribute("aria-invalid")).toBe("true");
  expect(password.getAttribute("aria-invalid")).toBe("true");
  expect(onSubmit).not.toHaveBeenCalled();
});

test("입력 중에는 오류를 띄우지 않고 제출할 때만 검사한다", async () => {
  const { email } = renderForm();

  fireEvent.change(email, { target: { value: "admin" } });
  fireEvent.blur(email);

  await Promise.resolve();
  expect(screen.queryByText("이메일 형식이 올바르지 않아요.")).toBeNull();
});

test("검증을 통과하면 정리된 값으로 제출한다", async () => {
  const { onSubmit, email, password, submit } = renderForm();

  fireEvent.change(email, { target: { value: " admin@patron.dev " } });
  fireEvent.change(password, { target: { value: "secret" } });
  fireEvent.click(submit);

  await vi.waitFor(() =>
    expect(onSubmit).toHaveBeenCalledWith({
      email: "admin@patron.dev",
      password: "secret",
    }),
  );
});

test("서버가 거절한 문구를 화면 낭독기가 바로 읽도록 alert로 보여 준다", () => {
  renderForm({ errorMessage: "이메일 또는 비밀번호가 올바르지 않습니다." });

  expect(screen.getByRole("alert").textContent).toBe(
    "이메일 또는 비밀번호가 올바르지 않습니다.",
  );
});

test("로그인 요청 중에는 버튼을 눌러도 다시 보내지 않는다", () => {
  const { submit } = renderForm({ isPending: true });

  expect(submit.hasAttribute("disabled")).toBe(true);
});
