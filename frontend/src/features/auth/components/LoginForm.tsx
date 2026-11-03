import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Button } from "../../../shared/components/ui/Button";
import { TextField } from "../../../shared/components/ui/TextField";
import {
  type LoginInput,
  type LoginValues,
  loginSchema,
} from "../lib/loginSchema";

type LoginFormProps = {
  onSubmit: (values: LoginValues) => void;
  /** 로그인 요청이 진행 중이면 같은 요청을 다시 보내지 않게 버튼을 막는다. */
  isPending?: boolean;
  /** 서버가 로그인을 거절한 문구 */
  errorMessage?: string;
};

export function LoginForm({
  onSubmit,
  isPending = false,
  errorMessage,
}: LoginFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginInput, unknown, LoginValues>({
    resolver: zodResolver(loginSchema),
    mode: "onSubmit",
    reValidateMode: "onSubmit",
    defaultValues: { email: "", password: "" },
  });

  return (
    <form
      noValidate
      // handleSubmit은 (값, 이벤트)를 넘기므로 값만 전달한다. 이벤트가 mutate의 options로 들어가지 않게 한다.
      onSubmit={handleSubmit((values) => onSubmit(values))}
      className="flex flex-col gap-5"
    >
      <TextField
        label="이메일"
        type="email"
        autoComplete="username"
        error={errors.email?.message}
        {...register("email")}
      />
      <TextField
        label="비밀번호"
        type="password"
        autoComplete="current-password"
        error={errors.password?.message}
        {...register("password")}
      />
      {errorMessage && (
        <p role="alert" className="text-body-sm text-red-600">
          {errorMessage}
        </p>
      )}
      <Button type="submit" disabled={isPending} className="w-full">
        로그인하기
      </Button>
    </form>
  );
}
