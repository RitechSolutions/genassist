import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/config/api", () => ({
  apiRequest: vi.fn(),
  getApiUrl: vi.fn(async () => "http://localhost/api/"),
  getApiUrlString: "http://localhost/api/",
  formatUploadOrNetworkError: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  API_DEFAULT_TIMEOUT_MS: 1000,
  API_UPLOAD_TIMEOUT_MS: 1000,
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), request: vi.fn() },
}));

import { apiRequest } from "@/config/api";
import {
  listSupportTickets,
  getSupportTicket,
  createSupportTicket,
  searchDuplicateTickets,
  listTicketComments,
  addTicketComment,
} from "@/services/helpCenter";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("listSupportTickets", () => {
  it("GETs the base endpoint with no query string when no params are given", async () => {
    const res = { items: [{ id: "1" }], total: 1 };
    mockApiRequest.mockResolvedValue(res as never);
    const result = await listSupportTickets();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "help-center/tickets");
    expect(result).toEqual(res);
  });

  it("builds the query string in order and includes skip=0", async () => {
    mockApiRequest.mockResolvedValue({ items: [], total: 0 } as never);
    await listSupportTickets({
      status: "open",
      ticket_type: "bug",
      skip: 0,
      limit: 20,
      mine_only: true,
    });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "help-center/tickets?status=open&ticket_type=bug&skip=0&limit=20&mine_only=true"
    );
  });

  it("omits mine_only when it is falsy", async () => {
    mockApiRequest.mockResolvedValue({ items: [], total: 0 } as never);
    await listSupportTickets({ status: "open", mine_only: false });
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "help-center/tickets?status=open");
  });

  it("falls back to an empty list when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await listSupportTickets()).toEqual({ items: [], total: 0 });
  });
});

describe("getSupportTicket", () => {
  it("GETs help-center/tickets/:id and returns the ticket", async () => {
    const ticket = { id: "9", title: "t" };
    mockApiRequest.mockResolvedValue(ticket as never);
    const result = await getSupportTicket("9");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "help-center/tickets/9");
    expect(result).toEqual(ticket);
  });

  it("returns null when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getSupportTicket("9")).toBeNull();
  });
});

describe("createSupportTicket", () => {
  it("POSTs the payload and returns the created ticket", async () => {
    const created = { id: "1", title: "t" };
    mockApiRequest.mockResolvedValue(created as never);
    const payload = { title: "t", ticket_type: "bug" };
    const result = await createSupportTicket(payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "help-center/tickets", payload);
    expect(result).toEqual(created);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(createSupportTicket({ title: "t" } as never)).rejects.toThrow(
      "Failed to create ticket"
    );
  });
});

describe("searchDuplicateTickets", () => {
  it("GETs the duplicates endpoint with title + default ticket_type", async () => {
    const candidates = [{ id: "1" }];
    mockApiRequest.mockResolvedValue(candidates as never);
    const result = await searchDuplicateTickets("crash");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "help-center/tickets/duplicates?title=crash&ticket_type=bug"
    );
    expect(result).toEqual(candidates);
  });

  it("uses the provided ticket_type and returns [] when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    const result = await searchDuplicateTickets("crash", "feature");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "help-center/tickets/duplicates?title=crash&ticket_type=feature"
    );
    expect(result).toEqual([]);
  });
});

describe("listTicketComments", () => {
  it("GETs the comments endpoint and returns the array", async () => {
    const comments = [{ id: "1", body: "hi" }];
    mockApiRequest.mockResolvedValue(comments as never);
    const result = await listTicketComments("9");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "help-center/tickets/9/comments");
    expect(result).toEqual(comments);
  });

  it("returns [] when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await listTicketComments("9")).toEqual([]);
  });
});

describe("addTicketComment", () => {
  it("POSTs the comment body and returns the created comment", async () => {
    const comment = { id: "1", body: "hi" };
    mockApiRequest.mockResolvedValue(comment as never);
    const result = await addTicketComment("9", "hi");
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "help-center/tickets/9/comments", {
      body: "hi",
    });
    expect(result).toEqual(comment);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(addTicketComment("9", "hi")).rejects.toThrow("Failed to add comment");
  });
});
