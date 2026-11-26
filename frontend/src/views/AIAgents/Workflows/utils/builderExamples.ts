import {
  BadgeCheck,
  GitFork,
  Languages,
  LifeBuoy,
  Newspaper,
  Package,
  Send,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

/**
 * Openers for the builder's empty chat: things people actually ask for, worded
 * so they can be sent as they are or edited first. The prompt is what goes in
 * the field; the label is the chip.
 */
export interface BuilderExample {
  label: string;
  prompt: string;
  icon: LucideIcon;
}

export const BUILDER_EXAMPLES: BuilderExample[] = [
  {
    label: "Support assistant",
    icon: LifeBuoy,
    prompt:
      "Build a customer support assistant that answers questions from our knowledge base, and opens a ticket with a short summary when it cannot help.",
  },
  {
    label: "Route by topic",
    icon: GitFork,
    prompt:
      "Classify each incoming message as billing, technical or sales and send it down a separate branch with its own reply for each, plus a default branch.",
  },
  {
    label: "Qualify leads",
    icon: BadgeCheck,
    prompt:
      "Talk to website visitors, collect their name, company and what they need, score the lead from 1 to 5 and post a summary to Slack.",
  },
  {
    label: "Telegram support bot",
    icon: Send,
    prompt:
      "Create a Telegram bot that answers questions about our products and hands over to a person when the customer asks for one.",
  },
  {
    label: "Summarize and translate",
    icon: Languages,
    prompt:
      "Take any message, summarize it in two sentences and translate the summary into English, Spanish and German.",
  },
  {
    label: "Approval before sending",
    icon: ShieldCheck,
    prompt:
      "Draft a reply email to the customer, show it to a person for approval, and send it with Gmail only once they approve.",
  },
  {
    label: "Order status lookup",
    icon: Package,
    prompt:
      "Let customers ask about their order: extract the order number, look it up with our orders API and reply with the status and delivery date.",
  },
  {
    label: "Daily digest",
    icon: Newspaper,
    prompt:
      "Search the web for news about our industry, pick the five most relevant items and write a short digest with links.",
  },
];

/** How many openers show before "See all". */
export const EXAMPLES_PREVIEW_COUNT = 4;

/** Openers for the empty chat; one is picked at random each time the panel starts fresh. */
export const BUILDER_GREETINGS: string[] = [
  "Describe it badly. I’ll figure it out.",
  "Let's automate our way out of this.",
  "Have you tried automating it?",
  "I was built for this. Literally.",
  "What should run while you’re at lunch?",
  "Another task? In this economy?",
];

/** A random opener, stable for the lifetime of the caller's state. */
export const pickBuilderGreeting = (): string =>
  BUILDER_GREETINGS[Math.floor(Math.random() * BUILDER_GREETINGS.length)];

/** Typed into the empty chat's field as its placeholder, one at random at a time. */
export const BUILDER_PLACEHOLDERS: readonly string[] = [
  "Build an agent that answers support questions from our docs",
  "Build an agent that summarizes every new ticket in one line",
  "Build an agent that sends me a daily report at 9 AM",
];

/** The field's placeholder once a conversation is under way. */
export const BUILDER_INLINE_PLACEHOLDER = "Ask GenAgent";
