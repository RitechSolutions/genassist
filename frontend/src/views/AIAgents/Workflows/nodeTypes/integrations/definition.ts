import {
  CalendarEventToolNodeData,
  JiraNodeData,
  NodeData,
  NodeTypeDefinition,
  ReadMailsNodeData,
  SlackOutputNodeData,
  WhatsappNodeData,
  ZendeskTicketNodeData,
} from "../../types/nodes";
import GmailNode from "./gmailNode";
import { GmailNodeData } from "../../types/nodes";
import { NodeProps } from "reactflow";
import ZendeskTicketNode from "./zendeskTicketNode";
import SlackOutputNode from "./slackOutputNode";
import WhatsAppNode from "./whatsappNode";
import CalendarEventNode from "./calendarEventNode";
import ReadMailsNode from "./readMailsNode";
import JiraNode from "./jiraNode";

export const GMAIL_NODE_DEFINITION: NodeTypeDefinition<GmailNodeData> = {
  type: "gmailNode",
  label: "Email Sender",
  description: "Sends an email using a connected Gmail account.",
  shortDescription: "Send email via Gmail",
  configSubtitle:
    "Configure email settings, including recipients, subject, and body.",
  category: "integrations",
  icon: "Send",
  defaultData: {
    name: "Email Sender",
    dataSourceId: null,
    subject: "",
    body: "",
    to: "",
    cc: "",
    bcc: "",
    operation: "send_email",
    attachments: [],
    handlers: [
      {
        id: "input",
        type: "target",
        compatibility: "any",
        position: "left",
      },
      {
        id: "output",
        type: "source",
        compatibility: "any",
        position: "right",
      },
    ],
  },
  component: GmailNode as React.ComponentType<NodeProps<GmailNodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "gmailNode",
    position,
    data: {
      ...data,
    },
  }),
};

export const ZENDESK_TICKET_NODE_DEFINITION: NodeTypeDefinition<ZendeskTicketNodeData> =
  {
    type: "zendeskTicketNode",
    label: "Zendesk Ticket Creator",
    description:
      "Creates a new ticket in Zendesk with specified requester and ticket details.",
    shortDescription: "Create a Zendesk ticket",
    configSubtitle:
      "Configure Zendesk ticket fields, including requester details and tags.",
    category: "integrations",
    icon: "Zendesk",
    defaultData: {
      name: "Zendesk Ticket Creator",
      subject: "",
      description: "",
      requester_name: "",
      requester_email: "",
      tags: [],
      app_settings_id: undefined,
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "text",
          position: "left",
        },
        {
          id: "output",
          type: "source",
          compatibility: "any",
          position: "right",
        },
      ],
    },
    component: ZendeskTicketNode as React.ComponentType<
      NodeProps<ZendeskTicketNodeData>
    >,
    createNode: (id, position, data) => ({
      id,
      type: "zendeskTicketNode",
      position,
      data: {
        ...data,
      },
    }),
  };

export const SLACK_OUTPUT_NODE_DEFINITION: NodeTypeDefinition<SlackOutputNodeData> =
  {
    type: "slackMessageNode",
    label: "Slack Messenger",
    description: "Sends a message to a Slack user or channel.",
    shortDescription: "Send a Slack message",
    configSubtitle:
      "Configure Slack messaging settings, including channel and message content.",
    category: "integrations",
    icon: "Slack",
    defaultData: {
      name: "Slack Messenger",
      message: "",
      channel: "",
      app_settings_id: undefined,
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "any",
          position: "left",
        },
        {
          id: "output",
          type: "source",
          compatibility: "any",
          position: "right",
        },
      ],
    },
    component: SlackOutputNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "slackMessageNode",
      position,
      data: {
        ...data,
      },
    }),
  };

export const WHATSAPP_NODE_DEFINITION: NodeTypeDefinition<WhatsappNodeData> = {
  type: "whatsappToolNode",
  label: "WhatsApp Messenger",
  description: "Sends a WhatsApp message to a specified phone number.",
  shortDescription: "Send a WhatsApp message",
  configSubtitle:
    "Configure WhatsApp message settings, including recipient and content.",
  category: "integrations",
  icon: "Whatsapp",
  defaultData: {
    name: "WhatsApp Messenger",
    message: "",
    recipient_number: "",
    app_settings_id: undefined,
    handlers: [
      {
        id: "input",
        type: "target",
        compatibility: "any",
        position: "left",
      },
      {
        id: "output",
        type: "source",
        compatibility: "any",
        position: "right",
      },
    ],
  },
  component: WhatsAppNode as React.ComponentType<NodeProps<NodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "whatsappToolNode",
    position,
    data: {
      ...data,
    },
  }),
};

export const READ_MAILS_NODE_DEFINITION: NodeTypeDefinition<ReadMailsNodeData> =
  {
    type: "readMailsNode",
    label: "Email Reader",
    description:
      "Retrieves emails using customizable search filters from a connected email account.",
    shortDescription: "Retrieve emails",
    configSubtitle:
      "Configure email search filters, data source, and retrieval parameters.",
    category: "integrations",
    icon: "MailOpen",
    defaultData: {
      name: "Email Reader",
      dataSourceId: undefined,
      searchCriteria: {
        from: "",
        to: "",
        subject: "",
        has_attachment: false,
        is_unread: false,
        label: "",
        newer_than: "",
        older_than: "",
        custom_query: "",
        max_results: 10,
      },
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "any",
          position: "left",
        },
        {
          id: "output",
          type: "source",
          compatibility: "any",
          position: "right",
        },
      ],
    } as ReadMailsNodeData,
    component: ReadMailsNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "readMailsNode",
      position,
      data: {
        ...data,
      },
    }),
  };
export const CALENDAR_EVENT_NODE_DEFINITION: NodeTypeDefinition<CalendarEventToolNodeData> =
  {
    type: "calendarEventNode",
    label: "Calendar Scheduler",
    description:
      "Creates calendar events using extracted or user-provided scheduling details.",
    shortDescription: "Schedule a calendar event",
    configSubtitle:
      "Configure calendar event details, including timing, summary, and data source.",
    category: "integrations",
    icon: "Calendar",
    defaultData: {
      name: "Calendar Scheduler",
      summary: "",
      operation: "",
      start: "",
      end: "",
      dataSourceId: "",
      subjectContains: "",
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "any",
          position: "left",
        },
        {
          id: "output",
          type: "source",
          compatibility: "any",
          position: "right",
        },
      ],
    },
    component: CalendarEventNode as React.ComponentType<
      NodeProps<CalendarEventToolNodeData>
    >,
    createNode: (id, position, data) => ({
      id,
      type: "calendarEventNode",
      position,
      data: {
        ...data,
      },
    }),
  };

export const JIRA_NODE_DEFINITION: NodeTypeDefinition<JiraNodeData> = {
  type: "jiraNode",
  label: "Jira Task Creator",
  description:
    "Creates a new task in a Jira project space with configurable fields and metadata.",
  shortDescription: "Create a Jira task",
  configSubtitle:
    "Configure Jira task settings, including project space, name, and description.",
  category: "integrations",
  icon: "Jira",
  defaultData: {
    name: "Jira Task Creator",
    url: "",
    email: "",
    apiToken: "",
    spaceKey: "",
    taskName: "",
    taskDescription: "",
    app_settings_id: undefined,
    handlers: [
      {
        id: "input",
        type: "target",
        compatibility: "any",
        position: "left",
      },
      {
        id: "output",
        type: "source",
        compatibility: "any",
        position: "right",
      },
    ],
  },
  component: JiraNode as React.ComponentType<NodeProps<JiraNodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "jiraNode",
    position,
    data: {
      ...data,
    },
  }),
};
