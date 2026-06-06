import { z } from "zod";

export const signInSchema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(1, "Password is required."),
});

export type SignInValues = z.infer<typeof signInSchema>;

export const signUpSchema = z.object({
  name: z.string().trim().max(120, "Name is too long.").optional(),
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(8, "Password must be at least 8 characters."),
});

export type SignUpValues = z.infer<typeof signUpSchema>;
