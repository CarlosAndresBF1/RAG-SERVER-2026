export { auth as middleware } from "@/lib/auth";

export const config = {
  matcher: ["/((?!login|api/auth|_next|favicon|public).*)"],
};
