import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { register as registerApi } from "@/api/auth";
import { FormError, FormRow } from "@/components/shared/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthCard } from "./AuthCard";
import { useAuthMutation } from "./useAuthMutation";

const schema = z.object({
  email: z.string().email("请输入有效邮箱"),
  password: z.string().min(6, "密码至少 6 位"),
  name: z.string().optional(),
});
type Values = z.infer<typeof schema>;

export function RegisterPage() {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  const mutation = useAuthMutation<Values>(
    (v) => registerApi(v.email, v.password, v.name),
    () => "/",
  );

  return (
    <AuthCard
      title="注册"
      footer={
        <>
          已有账号？<Link to="/login" className="text-foreground underline">登录</Link>
        </>
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit((v) => mutation.mutate(v))} noValidate>
        <FormRow label="邮箱" htmlFor="email" error={errors.email?.message}>
          <Input id="email" type="email" autoComplete="email" {...register("email")} />
        </FormRow>
        <FormRow label="昵称(可选)" htmlFor="name">
          <Input id="name" type="text" autoComplete="nickname" {...register("name")} />
        </FormRow>
        <FormRow label="密码" htmlFor="password" error={errors.password?.message}>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            {...register("password")}
          />
        </FormRow>
        {mutation.isError && <FormError error={mutation.error} />}
        <Button type="submit" className="w-full" disabled={mutation.isPending}>
          {mutation.isPending ? "注册中…" : "注册"}
        </Button>
      </form>
    </AuthCard>
  );
}
