export function postLoginPath(from?: { pathname?: string; search?: string }): string {
  if (!from?.pathname || from.pathname === "/onboarding") return "/dashboard";
  return `${from.pathname}${from.search ?? ""}`;
}
