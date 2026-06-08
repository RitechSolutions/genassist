import type { NodeHelpContent } from "../../types/nodes";

export const INTEGRATION_NODES_HELP_CONTENT: NodeHelpContent = {
  intro:
    "Integration nodes connect workflows to communication platforms, business tools, and external productivity systems. They are used when a workflow must send information out, create records, or react through connected services.",
  sections: [
    {
      title: "When To Use Integration Nodes",
      body: "Use integration nodes when you need to:",
      bullets: [
        "Send messages to communication channels",
        "Create tickets, tasks, or records in external systems",
        "Read data from connected business tools",
        "Trigger real-world actions from your workflow",
      ],
    },
    {
      title: "Summary",
      body: "Integration nodes are best suited for workflows that bridge automation logic with the systems your teams already use.",
    },
  ],
};

export const WHATSAPP_MESSENGER_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The WhatsApp Messenger node sends messages through WhatsApp as part of a workflow. It is useful for notifications, updates, support interactions, and customer-facing automations.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the WhatsApp Messenger node when you need to:",
      bullets: [
        "Send workflow notifications to WhatsApp",
        "Deliver customer updates",
        "Support messaging-based automation",
        "Trigger outbound communication from workflow events",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure WhatsApp Messenger dialog will open.",
        "Enter the Node Name.",
        "Select the optional Configuration Vars entry if you want to use a saved setup.",
        "Enter the Recipient Number in the expected phone-number format.",
        "Add the Message content to send.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const SLACK_MESSENGER_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Slack Messenger node sends messages to Slack channels or users directly from a workflow. It is ideal for alerts, updates, approvals, or internal team communication.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Slack Messenger node when you need to:",
      bullets: [
        "Send automated Slack messages",
        "Notify teams about workflow events",
        "Share updates into channels",
        "Support internal workflow communication",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Slack Messenger dialog will open.",
        "Enter the Node Name.",
        "Select the optional Configuration Vars value for the Slack setup.",
        "Enter the Channel ID or target user.",
        "Add the Message content.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const ZENDESK_TICKET_CREATOR_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Zendesk Ticket Creator node creates new Zendesk tickets from workflow data. It is useful for turning detected issues, requests, or support events into trackable support records.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Zendesk Ticket Creator node when you need to:",
      bullets: [
        "Create support tickets automatically",
        "Escalate workflow events to Zendesk",
        "Route customer requests into a ticketing system",
        "Standardize support operations",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Zendesk Ticket Creator dialog will open.",
        "Enter the Node Name.",
        "Select optional Configuration Vars for the Zendesk setup.",
        "Fill in the ticket Subject and Description.",
        "Add the requester details, tags, and any Custom Fields needed for the ticket.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const EMAIL_SENDER_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Email Sender node sends email messages from a workflow. It is useful for notifications, confirmations, reports, and outbound communication triggered by workflow events.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Email Sender node when you need to:",
      bullets: [
        "Send notification emails",
        "Deliver automated reports",
        "Confirm workflow actions to users",
        "Trigger outbound email communication",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Email Sender dialog will open.",
        "Enter the Node Name.",
        "Select the connector and choose the Operation.",
        "Add the recipients in the To, CC, and BCC fields as needed.",
        "Enter the Subject, Body, and any optional Attachments.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const EMAIL_READER_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Email Reader node reads incoming email content into a workflow. It can be used to trigger actions from mailbox events or process message content automatically.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Email Reader node when you need to:",
      bullets: [
        "Read inbox messages into a workflow",
        "Extract information from emails",
        "Automate responses to email-based requests",
        "Trigger downstream processing from email content",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Email Reader dialog will open.",
        "Enter the Node Name.",
        "Select the Gmail Data Source to read from.",
        "Configure filters such as sender, recipient, subject, label, or date range.",
        "Set the Max Results and any options such as attachments, unread-only, or a custom Gmail query.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const CALENDAR_SCHEDULER_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Calendar Scheduler node creates or manages calendar events from within a workflow. It is useful for booking meetings, scheduling follow-ups, or coordinating availability.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Calendar Scheduler node when you need to:",
      bullets: [
        "Schedule meetings automatically",
        "Create calendar events from workflow triggers",
        "Coordinate follow-ups or appointments",
        "Connect automation to team scheduling",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Calendar Scheduler dialog will open.",
        "Enter the Node Name.",
        "Select the calendar Connector.",
        "Add the event Summary and choose the calendar Operation.",
        "Fill in the Start, End, and any additional matching fields such as subject filters if required.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const JIRA_TASK_CREATOR_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Jira Task Creator node creates Jira issues from workflow data. It is useful for converting requests, detected work items, or process outcomes into tasks that engineering or operations teams can track.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Jira Task Creator node when you need to:",
      bullets: [
        "Create Jira tasks automatically",
        "Turn workflow outputs into actionable tickets",
        "Connect operational automation to project management",
        "Route work into existing team processes",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Jira Task Creator dialog will open.",
        "Enter the Node Name.",
        "Select optional Configuration Vars if a saved Jira setup is available.",
        "Enter the target Space Key.",
        "Fill in the Task Name and Task Description.",
        "Save the node configuration.",
      ],
    },
  ],
};
