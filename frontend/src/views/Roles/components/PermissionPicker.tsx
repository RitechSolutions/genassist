import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Lock, Search } from "lucide-react";

import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Checkbox } from "@/components/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { cn } from "@/helpers/utils";
import { Permission } from "@/interfaces/permission.interface";
import {
  PermissionArea,
  PermissionEntry,
  buildPermissionAreas,
  collapsedAreasFor,
  summarizeCapabilities,
} from "@/views/Roles/permissionCatalog";

interface PermissionPickerProps {
  permissions: Permission[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  /** False for every role but the built-in admin, which this dialog cannot edit. */
  canAssignAdminOnly: boolean;
  disabled?: boolean;
}

type CheckedState = boolean | "indeterminate";

function checkedStateFor(selectedCount: number, total: number): CheckedState {
  if (total === 0 || selectedCount === 0) return false;
  return selectedCount === total ? true : "indeterminate";
}

export function PermissionPicker({
  permissions,
  selectedIds,
  onChange,
  canAssignAdminOnly,
  disabled = false,
}: PermissionPickerProps) {
  const [search, setSearch] = useState("");

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const areas = useMemo(() => buildPermissionAreas(permissions), [permissions]);

  // Areas the role already draws on start open; the rest stay collapsed so the
  // whole permission model is visible at a glance. Initial-only: collapsing an
  // area the moment its last permission is unticked would be hostile.
  const [collapsedAreas, setCollapsedAreas] = useState<Set<string>>(() =>
    collapsedAreasFor(areas, selectedIds)
  );

  const query = search.trim().toLowerCase();
  const isSearching = query.length > 0;

  // Areas reduced to the entries matching the search. Everything below reads
  // from this, so the counts, the toggles and the rows always agree.
  const visibleAreas = useMemo<PermissionArea[]>(() => {
    if (!isSearching) return areas;

    return areas
      .map((area) => {
        const areaMatches = area.label.toLowerCase().includes(query);
        const rows = area.rows
          .map((row) => {
            const rowMatches = areaMatches || row.label.toLowerCase().includes(query);
            const entries = rowMatches
              ? row.entries
              : row.entries.filter(
                  (entry) =>
                    entry.name.toLowerCase().includes(query) ||
                    entry.verbLabel.toLowerCase().includes(query)
                );
            return { ...row, entries };
          })
          .filter((row) => row.entries.length > 0);

        const entries = rows.flatMap((row) => row.entries);
        return {
          ...area,
          rows,
          permissionIds: entries.map((entry) => entry.id),
        };
      })
      .filter((area) => area.rows.length > 0);
  }, [areas, isSearching, query]);

  // Admin-reserved permissions are never assignable here, so they stay out of
  // every bulk toggle instead of being granted and then rejected by the API.
  const assignableIdsOf = (entries: PermissionEntry[]) =>
    entries
      .filter((entry) => canAssignAdminOnly || !entry.isAdminOnly)
      .map((entry) => entry.id);

  const assignableIdsIn = (area: PermissionArea) =>
    assignableIdsOf(area.rows.flatMap((row) => row.entries));

  const visibleAssignableIds = useMemo(
    () => visibleAreas.flatMap(assignableIdsIn),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [visibleAreas, canAssignAdminOnly]
  );

  const visibleSelectedCount = visibleAssignableIds.filter((id) =>
    selectedSet.has(id)
  ).length;

  const assignableIdSet = useMemo(
    () => new Set(areas.flatMap(assignableIdsIn)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [areas, canAssignAdminOnly]
  );

  // Counted over the same set as the total, so the two can never disagree. A
  // selection outside it is a permission the role may no longer hold, reported
  // separately rather than folded into the headline count.
  const selectedAssignableCount = selectedIds.filter((id) =>
    assignableIdSet.has(id)
  ).length;
  const reservedSelectedCount = selectedIds.length - selectedAssignableCount;

  const setSelection = (next: Set<string>) => onChange(Array.from(next));

  const toggleIds = (ids: string[], shouldSelect: boolean) => {
    const next = new Set(selectedSet);
    ids.forEach((id) => (shouldSelect ? next.add(id) : next.delete(id)));
    setSelection(next);
  };

  const toggleAll = (ids: string[]) => {
    const allSelected = ids.length > 0 && ids.every((id) => selectedSet.has(id));
    toggleIds(ids, !allSelected);
  };

  const toggleArea = (area: PermissionArea) => toggleAll(assignableIdsIn(area));

  const toggleAreaCollapsed = (key: string) => {
    setCollapsedAreas((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const capabilities = summarizeCapabilities(areas, selectedSet);
  const allVisibleSelected =
    visibleAssignableIds.length > 0 &&
    visibleSelectedCount === visibleAssignableIds.length;
  // Both actions are offered separately: from a part-expanded list each one is
  // a distinct, meaningful click, and a single toggle could only reach one.
  const collapsedCount = areas.filter((area) => collapsedAreas.has(area.key)).length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <Label>Permissions</Label>
        <span className="text-sm text-muted-foreground">
          {selectedAssignableCount} of {assignableIdSet.size} selected
        </span>
      </div>

      {reservedSelectedCount > 0 && (
        <p className="text-xs text-destructive">
          This role still holds {reservedSelectedCount} admin-reserved{" "}
          {reservedSelectedCount === 1 ? "permission" : "permissions"}. Untick{" "}
          {reservedSelectedCount === 1 ? "it" : "them"} below — saving is rejected
          while {reservedSelectedCount === 1 ? "it is" : "they are"} selected.
        </p>
      )}

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Search permissions..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          disabled={disabled}
          aria-label="Search permissions"
        />
      </div>

      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Checkbox
            id="permissions-select-all"
            checked={checkedStateFor(visibleSelectedCount, visibleAssignableIds.length)}
            onCheckedChange={() => toggleIds(visibleAssignableIds, !allVisibleSelected)}
            disabled={disabled || visibleAssignableIds.length === 0}
          />
          <label
            htmlFor="permissions-select-all"
            className="cursor-pointer text-sm font-medium"
          >
            {isSearching
              ? `Select all ${visibleAssignableIds.length} matching`
              : "Select all"}
          </label>
        </div>

        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            // Both are no-ops while searching, which forces every match open.
            disabled={disabled || isSearching || collapsedCount === 0}
            onClick={() => setCollapsedAreas(new Set())}
          >
            Expand all
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={disabled || isSearching || collapsedCount === areas.length}
            onClick={() => setCollapsedAreas(new Set(areas.map((area) => area.key)))}
          >
            Collapse all
          </Button>

          <span aria-hidden className="mx-1 h-4 w-px bg-border" />

          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={disabled || selectedIds.length === 0}
            onClick={() => onChange([])}
          >
            Clear all
          </Button>
        </div>
      </div>

      <div className="max-h-[42vh] min-h-[220px] overflow-y-auto rounded-md border">
        {visibleAreas.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">
            No permissions match &ldquo;{search.trim()}&rdquo;.
          </p>
        ) : (
          visibleAreas.map((area) => {
            const assignable = assignableIdsIn(area);
            const selectedInArea = assignable.filter((id) => selectedSet.has(id)).length;
            const isCollapsed = !isSearching && collapsedAreas.has(area.key);

            return (
              <div
                key={area.key}
                role="group"
                aria-label={area.label}
                className="border-b last:border-b-0"
              >
                <div className="flex items-center gap-2 bg-muted/40 px-3 py-2">
                  <Checkbox
                    checked={checkedStateFor(selectedInArea, assignable.length)}
                    onCheckedChange={() => toggleArea(area)}
                    disabled={disabled || assignable.length === 0}
                    aria-label={`Select all ${area.label} permissions`}
                  />
                  <button
                    type="button"
                    onClick={() => toggleAreaCollapsed(area.key)}
                    disabled={isSearching}
                    aria-expanded={!isCollapsed}
                    className="flex flex-1 items-center gap-1.5 text-left text-sm font-medium disabled:cursor-default"
                  >
                    {isCollapsed ? (
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    )}
                    {area.label}
                  </button>

                  {assignable.length === 0 ? (
                    <Badge variant="secondary" className="gap-1">
                      <Lock className="h-3 w-3" />
                      Admin only
                    </Badge>
                  ) : (
                    <span className="text-xs tabular-nums text-muted-foreground">
                      {selectedInArea}/{assignable.length}
                    </span>
                  )}
                </div>

                {!isCollapsed && (
                  <div className="divide-y">
                    {assignable.length === 0 && (
                      <p className="py-2 pl-9 pr-3 text-xs text-muted-foreground">
                        Reserved for the built-in <strong>admin</strong> role, which
                        is not editable here. These cannot be granted to any other
                        role.
                      </p>
                    )}
                    {area.rows.map((row) => {
                      const rowAssignable = assignableIdsOf(row.entries);
                      const rowSelected = rowAssignable.filter((id) =>
                        selectedSet.has(id)
                      ).length;
                      // A single-verb row is already its own toggle; a second
                      // checkbox beside it would just duplicate the first.
                      const showRowToggle = row.entries.length > 1;

                      return (
                      <div
                        key={row.key}
                        role="group"
                        aria-label={row.label}
                        // pl-9 lines each row's checkbox up under the area
                        // label, so the two levels read as parent and child
                        // rather than as peers on one vertical line.
                        className="flex flex-col gap-1.5 py-2 pl-9 pr-3 sm:flex-row sm:items-center sm:gap-3"
                      >
                        <div className="flex items-center gap-2 sm:w-44 sm:shrink-0">
                          {showRowToggle ? (
                            <Checkbox
                              checked={checkedStateFor(rowSelected, rowAssignable.length)}
                              onCheckedChange={() => toggleAll(rowAssignable)}
                              disabled={disabled || rowAssignable.length === 0}
                              aria-label={`Select all ${row.label} permissions`}
                            />
                          ) : (
                            <span className="h-4 w-4 shrink-0" />
                          )}
                          <span className="text-sm">{row.label}</span>
                        </div>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
                          {row.entries.map((entry) => {
                            const isSelected = selectedSet.has(entry.id);
                            const locked = entry.isAdminOnly && !canAssignAdminOnly;
                            // A locked permission that is somehow already granted
                            // stays unlockable so the admin can clear it —
                            // otherwise every save would be rejected with no way out.
                            return (
                              <div key={entry.id} className="flex items-center gap-1.5">
                                <Checkbox
                                  id={`permission-${entry.id}`}
                                  checked={isSelected}
                                  disabled={disabled || (locked && !isSelected)}
                                  // The visible label is just the verb, so the
                                  // resource has to come from here or every
                                  // checkbox announces identically.
                                  aria-label={`${row.label}: ${entry.verbLabel}${
                                    locked ? " (reserved for the admin role)" : ""
                                  }`}
                                  onCheckedChange={(checked) =>
                                    toggleIds([entry.id], checked === true)
                                  }
                                />
                                <label
                                  htmlFor={`permission-${entry.id}`}
                                  title={
                                    locked
                                      ? `${entry.name} — reserved for the admin role`
                                      : entry.name
                                  }
                                  className={cn(
                                    "cursor-pointer text-sm",
                                    locked && !isSelected &&
                                      "cursor-not-allowed text-muted-foreground"
                                  )}
                                >
                                  {entry.verbLabel}
                                </label>
                                {locked && (
                                  <Lock className="h-3 w-3 text-muted-foreground" />
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <p className="text-xs text-muted-foreground">
        {capabilities.length === 0
          ? "This role grants no permissions yet."
          : `This role can: ${capabilities.join(" · ")}.`}
      </p>
    </div>
  );
}
