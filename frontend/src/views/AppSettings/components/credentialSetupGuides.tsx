import type { AppSetting } from '@/interfaces/app-setting.interface';

/**
 * Data-driven "How to get these values" guidance for the credential
 * (Configuration Vars) create/edit modal, rendered generically by
 * {@link CredentialSetupGuidePanel}.
 *
 * To add a guide for another credential type, add one entry keyed by that
 * `AppSetting['type']` — no component/JSX changes required.
 */
export interface CredentialSetupSection {
  /** Optional sub-heading for the section. */
  title?: string;
  /** Optional lead paragraph. */
  body?: string;
  /** Rendered as an ordered (numbered) list. */
  steps?: string[];
  /** Rendered as an unordered (bulleted) list. */
  bullets?: string[];
}

export interface CredentialSetupGuide {
  /** Collapsible panel heading. Defaults to "How to get these values". */
  title?: string;
  /** Optional intro paragraph above the sections. */
  intro?: string;
  sections: CredentialSetupSection[];
  /** Optional footnote (rendered muted/small). */
  note?: string;
}

export const CREDENTIAL_SETUP_GUIDES: Partial<Record<AppSetting['type'], CredentialSetupGuide>> = {
  Salesforce: {
    title: 'How to get these values',
    intro:
      'The Salesforce node authenticates with the OAuth2 client-credentials flow (app-level — no username/password). You need an Instance URL, a Client ID, and a Client Secret from a Salesforce Connected / External Client App.',
    sections: [
      {
        title: '1. Create the app (Setup)',
        steps: [
          'Setup → Quick Find → "External Client App Manager" → New External Client App (older orgs: App Manager → New Connected App).',
          'Enter a name + contact email; leave Distribution State = Local.',
          'Expand "API (Enable OAuth Settings)": enable OAuth, set any HTTPS callback URL (e.g. https://login.salesforce.com/services/oauth2/callback), add the scopes "api" and "refresh_token", and check "Enable Client Credentials Flow". Create.',
        ],
      },
      {
        title: '2. Set the Run As user',
        steps: [
          'Open the app → Policies → Edit → OAuth Policies: confirm "Enable Client Credentials Flow", then set "Run As" to an integration user (Cases are created as this user). Save.',
        ],
      },
      {
        title: '3. Copy the field values',
        bullets: [
          'Instance URL → your My Domain URL, e.g. https://myorg.my.salesforce.com. Use the .my.salesforce.com host — NOT the .my.salesforce-setup.com Setup host.',
          'Client ID / Client Secret → app → Settings → OAuth Settings → Consumer Key and Secret → Reveal (a.k.a. Consumer Key / Consumer Secret).',
        ],
      },
    ],
    note: 'New apps and policy changes can take a few minutes to propagate. If Test Connection fails right after setup, wait ~5 minutes and retry.',
  },
};
