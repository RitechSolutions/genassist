import * as Sentry from "@sentry/react";
import { SENTRY_CLIENT_ERROR_EVENT } from "./sentryErrorEvent";

const dsn = import.meta.env.VITE_SENTRY_DSN;
if (dsn) {
  Sentry.init({
    dsn,
    // Adds request headers and IP for users, for more info visit:
    // https://docs.sentry.io/platforms/javascript/guides/react/configuration/options/#sendDefaultPii
    sendDefaultPii: true,
    environment: import.meta.env.MODE,
    integrations: [Sentry.browserTracingIntegration(), Sentry.consoleLoggingIntegration({ levels: ["warn", "error"] })],
    tracesSampleRate: 1.0,
    tracePropagationTargets: ["localhost", "app.dev.genassist.ritech.io", "app.test.genassist.ritech.io", "app.genassist.ai"],
    enableLogs: true,
    beforeSend(event) {
      const hasException =
        event.exception?.values &&
        Array.isArray(event.exception.values) &&
        event.exception.values.length > 0;
      if (hasException && typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent(SENTRY_CLIENT_ERROR_EVENT));
      }

      // get user from isolation scope
      const user = Sentry.getIsolationScope().getUser();
      // show report dialog if in development mode
      if (import.meta.env.DEV) {
        Sentry.showReportDialog({ eventId: event.event_id, user: user });
        return null;
      }
    }
  });
}
