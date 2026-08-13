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
  getWorkflowSchedules,
  getWorkflowSchedule,
  createWorkflowSchedule,
  updateWorkflowSchedule,
  deleteWorkflowSchedule,
  getWorkflowScheduleRuns,
  runWorkflowScheduleNow,
} from "@/services/workflowSchedules";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("workflowSchedules service", () => {
  describe("getWorkflowSchedules", () => {
    it("omits the query when isActive is undefined", async () => {
      const rows = [{ id: "s1" }];
      mockApiRequest.mockResolvedValue(rows as never);
      const result = await getWorkflowSchedules();
      expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/workflow-schedules");
      expect(result).toEqual(rows);
    });

    it("appends is_active=true", async () => {
      await getWorkflowSchedules(true);
      expect(mockApiRequest).toHaveBeenCalledWith(
        "GET",
        "genagent/workflow-schedules?is_active=true",
      );
    });

    it("appends is_active=false", async () => {
      await getWorkflowSchedules(false);
      expect(mockApiRequest).toHaveBeenCalledWith(
        "GET",
        "genagent/workflow-schedules?is_active=false",
      );
    });

    it("falls back to an empty array when the API returns null", async () => {
      mockApiRequest.mockResolvedValue(null as never);
      expect(await getWorkflowSchedules()).toEqual([]);
    });
  });

  describe("getWorkflowSchedule", () => {
    it("GETs a single schedule by id", async () => {
      const row = { id: "s2" };
      mockApiRequest.mockResolvedValue(row as never);
      const result = await getWorkflowSchedule("s2");
      expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/workflow-schedules/s2");
      expect(result).toEqual(row);
    });

    it("returns null when the API returns null", async () => {
      mockApiRequest.mockResolvedValue(null as never);
      expect(await getWorkflowSchedule("s2")).toBeNull();
    });
  });

  describe("createWorkflowSchedule", () => {
    it("POSTs to the base endpoint and returns the response", async () => {
      const payload = { name: "sched" };
      const created = { id: "s3" };
      mockApiRequest.mockResolvedValue(created as never);
      const result = await createWorkflowSchedule(payload as never);
      expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/workflow-schedules", payload);
      expect(result).toEqual(created);
    });

    it("throws when the API returns a falsy response", async () => {
      mockApiRequest.mockResolvedValue(null as never);
      await expect(createWorkflowSchedule({} as never)).rejects.toThrow(
        "Failed to create workflow schedule",
      );
    });
  });

  describe("updateWorkflowSchedule", () => {
    it("PUTs to the id endpoint and returns the response", async () => {
      const payload = { name: "renamed" };
      const updated = { id: "s4" };
      mockApiRequest.mockResolvedValue(updated as never);
      const result = await updateWorkflowSchedule("s4", payload as never);
      expect(mockApiRequest).toHaveBeenCalledWith(
        "PUT",
        "genagent/workflow-schedules/s4",
        payload,
      );
      expect(result).toEqual(updated);
    });

    it("throws when the API returns a falsy response", async () => {
      mockApiRequest.mockResolvedValue(null as never);
      await expect(updateWorkflowSchedule("s4", {} as never)).rejects.toThrow(
        "Failed to update workflow schedule",
      );
    });
  });

  it("deleteWorkflowSchedule DELETEs by id", async () => {
    await deleteWorkflowSchedule("s5");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "genagent/workflow-schedules/s5");
  });

  describe("getWorkflowScheduleRuns", () => {
    it("GETs runs with no query when no options are given", async () => {
      const rows = [{ id: "r1" }];
      mockApiRequest.mockResolvedValue(rows as never);
      const result = await getWorkflowScheduleRuns("s6");
      expect(mockApiRequest).toHaveBeenCalledWith(
        "GET",
        "genagent/workflow-schedules/s6/runs",
      );
      expect(result).toEqual(rows);
    });

    it("builds the query string from status, limit and offset", async () => {
      await getWorkflowScheduleRuns("s6", { status: "completed", limit: 10, offset: 5 });
      expect(mockApiRequest).toHaveBeenCalledWith(
        "GET",
        "genagent/workflow-schedules/s6/runs?run_status=completed&limit=10&offset=5",
      );
    });

    it("includes zero-valued limit and offset (checked with !== undefined)", async () => {
      await getWorkflowScheduleRuns("s6", { limit: 0, offset: 0 });
      expect(mockApiRequest).toHaveBeenCalledWith(
        "GET",
        "genagent/workflow-schedules/s6/runs?limit=0&offset=0",
      );
    });

    it("falls back to an empty array when the API returns null", async () => {
      mockApiRequest.mockResolvedValue(null as never);
      expect(await getWorkflowScheduleRuns("s6")).toEqual([]);
    });
  });

  describe("runWorkflowScheduleNow", () => {
    it("POSTs to the run-now endpoint and returns the response", async () => {
      const run = { id: "r2" };
      mockApiRequest.mockResolvedValue(run as never);
      const result = await runWorkflowScheduleNow("s7");
      expect(mockApiRequest).toHaveBeenCalledWith(
        "POST",
        "genagent/workflow-schedules/s7/run-now",
      );
      expect(result).toEqual(run);
    });

    it("throws when the API returns a falsy response", async () => {
      mockApiRequest.mockResolvedValue(null as never);
      await expect(runWorkflowScheduleNow("s7")).rejects.toThrow(
        "Failed to trigger workflow schedule run",
      );
    });
  });
});
