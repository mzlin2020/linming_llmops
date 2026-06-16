import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link, useLocation } from "react-router-dom";
import { z } from "zod";

import { login } from "@/api/auth";
import { FormError, FormRow } from "@/components/shared/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthCard } from "./AuthCard";
import { useAuthMutation } from "./useAuthMutation";

const schema = z.object({
  email: z.string().email("请输入有效邮箱"),
  password: z.string().min(1, "请输入密码"),
});
type Values = z.infer<typeof schema>;

export function LoginPage() {
  const location = useLocation() as { state?: { from?: { pathname?: string } } };
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  const mutation = useAuthMutation<Values>(
    (v) => login(v.email, v.password),
    () => location.state?.from?.pathname ?? "/",
  );

  return (
    <AuthCard
      title="登录"
      footer={
        <>
          还没有账号？<Link to="/register" className="text-foreground underline">注册</Link>
        </>
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit((v) => mutation.mutate(v))} noValidate>
        <FormRow label="邮箱" htmlFor="email" error={errors.email?.message}>
          <Input id="email" type="email" autoComplete="email" {...register("email")} />
        </FormRow>
        <FormRow label="密码" htmlFor="password" error={errors.password?.message}>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            {...register("password")}
          />
        </FormRow>
        {mutation.isError && <FormError error={mutation.error} />}
        <Button type="submit" className="w-full" disabled={mutation.isPending}>
          {mutation.isPending ? "登录中…" : "登录"}
        </Button>
      </form>
    </AuthCard>
  );
}
