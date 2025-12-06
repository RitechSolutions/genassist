import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

const sections = [
  { id: "introduction", title: "1. Introduction" },
  { id: "scope", title: "2. Scope of the Policy" },
  { id: "data-processed", title: "3. Data Processed by GenAssist" },
  { id: "security", title: "4. Security and Audit" },
  { id: "data-retention", title: "5. Data Retention" },
  { id: "customer-resp", title: "6. Customer Responsibilities" },
  { id: "liability", title: "7. Limitation of Liability" },
  { id: "changes", title: "8. Changes to This Policy" },
  { id: "contact", title: "9. Contact Information" },
];

const tocItemBase =
  "block rounded-xl px-4 py-2 text-sm text-gray-700 transition-colors hover:text-gray-900 hover:bg-gray-100";

const Privacy: React.FC = () => {
  const headingRefs = useMemo(
    () =>
      sections.reduce<Record<string, HTMLElement | null>>((acc, s) => {
        acc[s.id] = null;
        return acc;
      }, {}),
    []
  );

  const [activeId, setActiveId] = useState<string>(sections[0].id);
  const tocContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const id = entry.target.getAttribute("id");
          if (id && entry.isIntersecting) {
            setActiveId(id);
            const container = tocContainerRef.current;
            const activeEl = container?.querySelector<HTMLAnchorElement>(
              `a[href="#${id}"]`
            );
            if (activeEl && container) {
              const { top: ct, bottom: cb } = container.getBoundingClientRect();
              const { top: at, bottom: ab } = activeEl.getBoundingClientRect();
              if (at < ct || ab > cb) {
                activeEl.scrollIntoView({ block: "nearest" });
              }
            }
          }
        });
      },
      { rootMargin: "-40% 0px -55% 0px", threshold: [0, 1] }
    );

    Object.values(headingRefs).forEach((el) => {
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, [headingRefs]);

  const handleTocClick = (
    e: React.MouseEvent<HTMLAnchorElement>,
    id: string
  ) => {
    e.preventDefault();
    const target = document.getElementById(id);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      setActiveId(id);
      history.replaceState(null, "", `#${id}`);
    }
  };

  return (
    <div className="min-h-screen bg-white">
      <header className="sticky top-0 z-30 border-b bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-4">
            <img
              src="/genassist_logo.svg"
              alt="GenAssist"
              className="h-8 w-auto"
            />
            <span className="text-base text-gray-600">Privacy Policy</span>
          </div>
          <nav className="flex items-center gap-4">
            <Link
              to="/login"
              className="text-base text-gray-700 hover:text-gray-900"
            >
              Login
            </Link>
            <Link
              to="/register"
              className="rounded-full bg-gray-100 px-5 py-2 text-base font-medium text-gray-900 shadow-sm transition-colors hover:bg-gray-200"
            >
              Get Started
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl grid-cols-1 gap-10 px-6 py-10 md:grid-cols-[260px_1fr]">
        <aside className="sticky top-24 self-start">
          <div className="mb-3 text-sm font-semibold tracking-tight text-gray-800">
            Table of contents
          </div>
          <div
            ref={tocContainerRef}
            className="max-h-[calc(100vh-8rem)] space-y-2 overflow-auto pr-2"
          >
            {sections.map((s) => {
              const isActive = activeId === s.id;
              return (
                <a
                  key={s.id}
                  href={`#${s.id}`}
                  onClick={(e) => handleTocClick(e, s.id)}
                  aria-current={isActive ? "location" : undefined}
                  className={`${tocItemBase} ${isActive
                    ? "bg-gray-200 text-gray-900 shadow-sm"
                    : "bg-gray-50"
                    }`}
                >
                  {s.title.replace(/^\d+\.\s*/, "")}
                </a>
              );
            })}
          </div>
        </aside>

        <article className="prose prose-gray max-w-none leading-relaxed prose-h2:mt-10 prose-h2:mb-3 prose-li:my-1">
          <h1 className="mb-10 text-5xl font-extrabold tracking-tight text-gray-900">
            Privacy Policy
          </h1>
          <section
            id="introduction"
            ref={(el) => (headingRefs["introduction"] = el)}
            className="scroll-mt-28 mb-14 md:mb-16"
          >
            <h2 className="text-2xl font-semibold text-gray-900">
              1. Introduction
            </h2>
            <p className="mb-8 md:mb-10">
              This Privacy Policy (“Policy”) describes the manner in which [Vendor/Company Name] (“Vendor,” “we,” “our,” or “us”) provides the GenAssist software platform (“GenAssist” or the “Platform”) and outlines the respective responsibilities of Vendor and its customers (“Customer,” “you,” or “your”) with respect to personal data and other information processed through GenAssist.
            </p>
            <p>
              GenAssist is a software product deployed within the Customer’s infrastructure. The Vendor does not host, access, or control Customer Data processed by GenAssist. The Customer retains sole ownership and responsibility for all data processed through the Platform.
            </p>
          </section>
          <section
            id="scope"
            ref={(el) => (headingRefs["scope"] = el)}
            className="scroll-mt-28 mb-14 md:mb-16"
          >
            <h2 className="text-2xl font-semibold text-gray-900">
              2. Scope of the Policy
            </h2>
            <p>
              This Policy applies solely to the GenAssist software as delivered by the Vendor. It does not extend to:
            </p>
            <ul className="list-disc pl-6">
              <li>
                Customer’s internal policies or practices in managing data.
              </li>
              <li>
                Third-party services (e.g., remote large language models, cloud integrations) that the Customer elects to integrate with GenAssist.
              </li>
              <li>
                Customer’s use of GenAssist in a manner inconsistent with this Policy or applicable law.
              </li>
            </ul>
          </section>
          <section
            id="data-processed"
            ref={(el) => (headingRefs["data-processed"] = el)}
            className="scroll-mt-28 mb-14 md:mb-16"
          >
            <h2 className="text-2xl font-semibold text-gray-900">
              3. Data Processed by GenAssist
            </h2>
            <ul className="list-decimal pl-6 space-y-3">
              <li>
                <strong>Customer Data:</strong> “Customer Data” refers to all information, including but not limited to text, chat transcripts, voice transcriptions, documents, databases, and analytics, that is ingested, generated, or processed within the Customer’s deployment of GenAssist. All Customer Data remains under the exclusive control of the Customer.
              </li>
              <li>
                <strong>AI Model Processing</strong>
                <ul className="mt-2 list-disc pl-6">
                  <li>
                    <strong>Remote LLMs:</strong> GenAssist enables optional integration with third-party large language models (e.g., OpenAI, Gemini) for reasoning, sentiment analysis, and related tasks. Data transmitted to such providers is determined solely by Customer’s configuration. Vendor does not transmit data to third parties independently.
                  </li>
                  <li>
                    <strong>Local LLMs:</strong> GenAssist supports the use of models deployed within the Customer’s infrastructure (e.g., Ollama, Mistral). All processing occurs locally and is not transmitted outside the Customer’s environment.
                  </li>
                  <li>
                    <strong>Voice Transcription:</strong> GenAssist supports transcription of voice discussions via Whisper, executed locally within the Customer environment.
                  </li>
                </ul>
              </li>
              <li>
                <strong>Knowledge Base Content</strong> GenAssist may be configured to build and maintain knowledge bases from Customer’s internal systems, files, and databases. This content remains under Customer’s control and is not transmitted externally unless directed by Customer.
              </li>
              <li>
                <strong>Google User Data</strong> If a Customer elects to integrate GenAssist with Google services (such as Gmail, Google Drive, Calendar, or other APIs), the following applies:
                <ul className="mt-2 list-disc pl-6">
                  <li>
                    <strong>Data Accessed:</strong> Depending on Customer configuration, GenAssist may access email metadata and content, calendar events, drive files, or user profile details as permitted by OAuth 2.0 authentication. Access is strictly limited to the scopes the Customer explicitly authorizes.
                  </li>
                  <li>
                    <strong>Data Usage:</strong> GenAssist uses Google user data only to execute workflows defined by the Customer, such as retrieving documents, sending workflow results, or enabling AI-assisted tasks. GenAssist does not process Google user data for its own purposes.
                  </li>
                  <li>
                    <strong>Data Sharing:</strong> Google user data is not shared with any third parties by Vendor. Any sharing is initiated and controlled solely by the Customer through their configured workflows or integrations.
                  </li>
                  <li>
                    <strong>Data Storage & Protection:</strong> If the Customer configures authentication with Google APIs, GenAssist securely stores OAuth tokens, connection credentials, and API keys in encrypted form at rest. All data in transit is encrypted (TLS). Google user data itself remains within the Customer’s infrastructure unless the Customer explicitly transmits it to third-party services.
                  </li>
                </ul>
              </li>
              <li>
                <strong>Data Retention & Deletion</strong>
                <ul className="mt-2 list-disc pl-6">
                  <li>
                    OAuth tokens and connection details may be deleted by the Customer at any time through the GenAssist configuration interface.
                  </li>
                  <li>
                    Google user data (such as files or emails retrieved during workflows) is retained only as long as required to fulfill the Customer’s workflows and may be deleted, re-indexed, or removed entirely at the Customer’s discretion.
                  </li>
                  <li>
                    Vendor does not retain copies of Google user data.
                  </li>
                </ul>
              </li>
            </ul>
          </section>
          <section
            id="security"
            ref={(el) => (headingRefs["security"] = el)}
            className="scroll-mt-28 mb-14 md:mb-16"
          >
            <h2 className="text-2xl font-semibold text-gray-900">
              4. Security and Audit
            </h2>
            <ul className="list-decimal pl-6 space-y-2">
              <li>
                <strong>Audit Logs:</strong> ‍GenAssist records system activity, configuration changes, and usage events in audit logs for purposes of monitoring, compliance, and accountability.
              </li>
              <li>
                <strong>Encryption:</strong> Connection credentials and sensitive configuration parameters are stored in encrypted form within the Platform.
              </li>
              <li>
                <strong>Customer Control of Data Transmission:</strong> GenAssist does not initiate communication with external services without Customer’s configuration. Customers control whether data is sent, received, or both, with respect to any third-party integration.
              </li>
            </ul>
          </section>
          <section
            id="data-retention"
            ref={(el) => (headingRefs["data-retention"] = el)}
            className="scroll-mt-28 mb-14 md:mb-16"
          >
            <h2 className="text-2xl font-semibold text-gray-900">
              5. Data Retention
            </h2>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                <strong>No Access to Customer Data:</strong> ‍Vendor does not access, collect, or process Customer Data. All Customer Data remains within the Customer’s infrastructure unless Customer elects to transmit such data to external services.
              </li>
              <li>
                <strong>Support Services:</strong> Vendor provides support limited to the GenAssist software product itself. Support does not include accessing, reviewing, or handling Customer Data.
              </li>
            </ul>
          </section>
          <section
            id="customer-resp"
            ref={(el) => (headingRefs["customer-resp"] = el)}
            className="scroll-mt-28 mb-14 md:mb-16"
          >
            <h2 className="text-2xl font-semibold text-gray-900">
              6. Customer Responsibilities
            </h2>
            <p>The Customer acknowledges and agrees that:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                Customer is the data controller with respect to all Customer Data processed through GenAssist.
              </li>
              <li>
                Customer bears sole responsibility for configuring and managing integrations with third-party services, including determining what data, if any, is transmitted.
              </li>
              <li>
                Customer is responsible for ensuring compliance with all applicable data protection and privacy laws (e.g., GDPR, CCPA) and the terms and privacy policies of any third-party service providers integrated with GenAssist.
              </li>
              <li>
                Vendor shall not be liable for Customer’s misuse of the Platform or violations of third-party terms and conditions.
              </li>
            </ul>
          </section>
          <section
            id="liability"
            ref={(el) => (headingRefs["liability"] = el)}
            className="scroll-mt-28 mb-14 md:mb-16"
          >
            <h2 className="text-2xl font-semibold text-gray-900">
              7. Limitation of Liability
            </h2>
            <p>
              To the maximum extent permitted by law, Vendor disclaims any
              liability arising from:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>
                Customer’s decision to share Customer Data with third-party
                services.
              </li>
              <li>
                Customer’s failure to comply with applicable data protection
                obligations.
              </li>
              <li>
                Security incidents originating from Customer’s infrastructure
                outside the scope of the GenAssist software.
              </li>
            </ul>
          </section>
          <section
            id="changes"
            ref={(el) => (headingRefs["changes"] = el)}
            className="scroll-mt-28 mb-14 md:mb-16"
          >
            <h2 className="text-2xl font-semibold text-gray-900">
              8. Changes to This Policy
            </h2>
            <p>
              To the maximum extent permitted by law, Vendor disclaims any liability arising from:Vendor reserves the right to update or modify this Policy at any time to reflect changes in legal requirements, industry practices, or product functionality. Customers will be notified of material changes through appropriate communication channels. Continued use of GenAssist following such updates constitutes acceptance of the revised Policy.
            </p>
          </section>
          <section
            id="contact"
            ref={(el) => (headingRefs["contact"] = el)}
            className="scroll-mt-28 mb-14 md:mb-16"
          >
            <h2 className="text-2xl font-semibold text-gray-900">
              9. Contact Information
            </h2>
            <p>
              For questions regarding this Policy or Vendor’s role in relation
              to GenAssist, please contact:
            </p>
            <p>
              Ritech International AG
              <br />
              Dammstrasse 19
              <br />
              6300 Zug, Switzerland.
            </p>
          </section>
        </article>
      </main>
      <footer className="bg-neutral-900 text-gray-300">
        <div className="mx-auto flex max-w-6xl items-start justify-between gap-6 px-6 py-10">
          <div className="space-y-3">
            <p>
              GenAssist is a Trademark of {""}
              <a
                href="https://www.ritech.co/"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-white"
              >
                Ritech International AG
              </a>
              .
            </p>
            <p>Dammstrasse 19, 6300 Zug, Switzerland</p>
            <p>© Ritech International AG 2025</p>
          </div>
          <nav className="ml-auto flex gap-6">
            <Link to="/" className="underline hover:text-white">
              Home
            </Link>
            <Link to="/privacy" className="underline hover:text-white">
              Privacy Policy
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
};

export default Privacy;
