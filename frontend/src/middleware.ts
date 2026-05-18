import { NextResponse, type NextRequest } from "next/server";

/**
 * Frontend route guard.
 *
 * Backend SSO/local-login callbacks set the HttpOnly `access_token` cookie on
 * the API origin; when the frontend is served behind the same nginx, that
 * cookie is also visible here. If the deployment splits domains, set the
 * cookie domain on the backend to the shared parent.
 *
 * Auth is mandatory in every environment — there is no dev-bypass on the
 * frontend. Sign in once with the seeded admin and the cookie persists.
 */
const PUBLIC_PATHS = [
  "/login",
  "/change-password",
  // Next internals + static assets
  "/_next",
  "/favicon",
  "/robots.txt",
];

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

export function middleware(req: NextRequest) {
  const { pathname, search } = req.nextUrl;

  if (isPublic(pathname)) {
    return NextResponse.next();
  }

  const token = req.cookies.get("access_token")?.value;
  if (token) {
    return NextResponse.next();
  }

  const loginUrl = req.nextUrl.clone();
  loginUrl.pathname = "/login";
  loginUrl.search = `?next=${encodeURIComponent(pathname + (search || ""))}`;
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    /*
     * Run on every path EXCEPT:
     * - /_next/* (Next assets)
     * - /api/* (proxied API calls)
     * - common static files
     */
    "/((?!_next/static|_next/image|api/|favicon.ico|robots.txt).*)",
  ],
};
