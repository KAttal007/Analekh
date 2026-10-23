import { Navigate, Outlet, useLocation } from "react-router-dom";
import { ErrorNote, Loading } from "./ui";
import { rememberReturnPath, useMe } from "../lib/auth";

/** Everything inside needs a session. Signed out, the visitor goes to sign-in, and the page they
 * asked for (its path only) is remembered so signing in brings them back to it. */
export function RequireSignIn() {
  const me = useMe();
  const { pathname, search } = useLocation();
  if (me.isPending) return <Loading />;
  if (me.isError) return <ErrorNote error={me.error} />;
  if (me.data === null) {
    rememberReturnPath(pathname + search);
    return <Navigate to="/login" replace />;
  }
  // Still on the emailed first password: nothing else works until a new one is chosen.
  if (me.data?.must_change_password) return <Navigate to="/login" replace />;
  return <Outlet />;
}
