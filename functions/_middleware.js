// Site-wide Pages middleware: Markdown content negotiation and agent-friendly 404s.
// The API under /api has its own handler (functions/api/[[path]].js).
import { handlePage } from "../edge/agent.js";

export const onRequest = ({ request, env, next }) => {
  const { pathname } = new URL(request.url);
  if (pathname === "/api" || pathname.startsWith("/api/")) return next();
  return handlePage(request, env, next);
};
