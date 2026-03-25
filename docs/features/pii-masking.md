# PII Masking

Protect sensitive personal information by automatically anonymizing user messages before they are processed by an AI model, then restoring the original values in the response.

## Why it matters

When a user sends a message that contains personal data — an email address, phone number, credit card, or government ID — that data is transmitted to the AI provider's infrastructure. Enabling PII Masking ensures the provider never sees the actual values, only anonymous placeholders. The original values are restored in the response before it reaches the user, so the conversation feels completely natural.

This helps organisations meet data minimisation requirements under GDPR, HIPAA, and similar regulations without any changes to the user experience.

## How to enable

PII Masking is a per-node setting available on **Language Model** and **Agent** nodes inside the Workflow Builder.

1. Open a workflow and select an LLM or Agent node.
2. In the node configuration panel, toggle **Enable PII Masking** on.
3. Save and publish the workflow.

That's it. No additional configuration is required.

## What gets masked

The following types of personal data are detected and anonymized automatically:

| Category | Examples |
|---|---|
| Email addresses | `alice@example.com` |
| Phone numbers | `+1 555 123 4567`, `+44 20 7946 0958` |
| Credit / debit cards | `4111 1111 1111 1111` |
| IP addresses | `192.168.1.1` |
| IBAN bank codes | `DE89 3704 0044 0532 0130 00` |
| US Social Security Numbers | `123-45-6789` |
| US Individual Taxpayer IDs | `912-34-5678` |
| US Passport numbers | `A12345678` |
| US Driver's licence numbers | — |
| UK NHS numbers | `943 476 5919` |
| Medical licence numbers | — |

Phone number detection works internationally, not just for US numbers.

## What does not get masked

- **System prompts** — these are written by the operator, not the end user, and are never modified.
- **File attachments and structured form data** — only free-text prompts are processed.

## End-to-end flow

```
User message  →  PII detected & replaced with tokens  →  AI provider receives anonymized text
                                                       ↓
User receives restored response  ←  tokens replaced with original values  ←  AI response
```

For example, if a user sends:

> *"My email is alice@example.com and my phone is +1 555 123 4567"*

The AI model receives:

> *"My email is \<EMAIL_ADDRESS_1\> and my phone is \<PHONE_NUMBER_1\>"*

And the response returned to the user has the real values restored, so the experience is seamless.

## Detection engine

PII detection is powered by **[Microsoft Presidio](https://microsoft.github.io/presidio/)**, an open-source data protection SDK maintained by Microsoft and widely used in enterprise compliance and privacy engineering.

Presidio uses a combination of pattern matching and contextual rules to identify personal data with high precision. It is the same engine used by organisations in financial services, healthcare, and government to meet regulatory requirements such as GDPR and HIPAA.

Running Presidio locally inside GenAssist means **no personal data is sent to a third-party detection service**. Detection happens entirely within your own infrastructure before the message ever leaves to the AI provider.


