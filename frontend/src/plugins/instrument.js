import * as Sentry from "@sentry/react";

const dsn = import.meta.env.VITE_SENTRY_DSN;
console.log("SENTRY_DSN", dsn, import.meta.env.MODE);
if (dsn) {
  Sentry.init({
    dsn,
    // Adds request headers and IP for users, for more info visit:
    // https://docs.sentry.io/platforms/javascript/guides/react/configuration/options/#sendDefaultPii
    sendDefaultPii: true,
    environment: import.meta.env.MODE,
    integrations: [Sentry.browserTracingIntegration(), Sentry.consoleLoggingIntegration({ levels: ["log", "warn", "error"] })],
    tracesSampleRate: 1.0,
    tracePropagationTargets: ["localhost", "app.dev.genassist.ritech.io", "app.test.genassist.ritech.io", "app.genassist.ai"],
    enableLogs: true,
  });
}
