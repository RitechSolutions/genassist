import type { CredentialSetupGuide } from './credentialSetupGuides';

interface CredentialSetupGuidePanelProps {
  guide: CredentialSetupGuide;
}

/**
 * Generic renderer for a {@link CredentialSetupGuide}. Purely data-driven — any
 * credential type that adds a guide entry renders here with consistent styling.
 */
export function CredentialSetupGuidePanel({ guide }: CredentialSetupGuidePanelProps) {
  return (
    <div className="space-y-3 text-sm text-muted-foreground">
      {guide.intro && <p className="leading-relaxed">{guide.intro}</p>}

      {guide.sections.map((section, index) => (
        <div key={index}>
          {section.title && <p className="font-medium text-foreground">{section.title}</p>}
          {section.body && <p className="mt-1 leading-relaxed">{section.body}</p>}
          {section.steps && section.steps.length > 0 && (
            <ol className="list-decimal ml-5 mt-1 space-y-1">
              {section.steps.map((step, i) => (
                <li key={i} className="leading-relaxed break-words">
                  {step}
                </li>
              ))}
            </ol>
          )}
          {section.bullets && section.bullets.length > 0 && (
            <ul className="list-disc ml-5 mt-1 space-y-1">
              {section.bullets.map((bullet, i) => (
                <li key={i} className="leading-relaxed break-words">
                  {bullet}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}

      {guide.note && <p className="text-xs">{guide.note}</p>}
    </div>
  );
}
