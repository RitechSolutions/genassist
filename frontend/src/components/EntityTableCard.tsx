import { useCallback, useEffect, useRef, useState, isValidElement } from "react";
import type { ReactNode } from "react";
import { AxiosError } from "axios";
import { toast } from "react-hot-toast";
import { DataTable, Column, DataTableProps } from "@/components/ui/data-table";
import { LIST_PAGE_SIZE } from "@/constants/pagination";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ListEmptyState } from "@/components/ListEmptyState";

/** Helpers handed to a `columns` builder so custom cells can trigger the built-in delete flow. */
export interface EntityTableRenderHelpers<T> {
  /** Opens the built-in delete confirmation dialog for `item`. */
  requestDelete: (item: T) => void;
}

/** A flag that can be a constant or resolved per-row. */
type RowFlag<T> = boolean | ((item: T) => boolean);

/**
 * Declarative config for the standard trailing "Actions" column. When provided (and
 * `deleteFn` is set), an `<ActionButtons>` column is appended for you, with `onDelete`
 * wired to the built-in confirmation dialog. Omit this and instead build the column
 * yourself via the `columns` function form if you need a fully custom actions cell.
 */
export interface EntityRowActions<T> {
  onEdit?: (item: T) => void;
  onRevert?: (item: T) => void;
  editTitle?: string;
  deleteTitle?: string;
  revertTitle?: string;
  /** Defaults to `true` when `onEdit` is provided. */
  canEdit?: RowFlag<T>;
  /** Defaults to `true` when a `deleteFn` is provided. */
  canDelete?: RowFlag<T>;
  /** Defaults to `false`. */
  canRevert?: RowFlag<T>;
  /** Extra content rendered next to the standard buttons (e.g. a menu, a toggle). */
  extra?: (item: T) => ReactNode;
  /** Column header. Defaults to "Actions". */
  header?: ReactNode;
  /** Column key. Defaults to "actions". */
  key?: string;
  /** Extra classes for the actions body cell. */
  className?: string;
  /** Extra classes for the actions header cell (e.g. a fixed width). */
  headerClassName?: string;
}

/**
 * Structured empty state. Rendered through the shared `<ListEmptyState>`. Search-specific
 * copy is shown while a query is active, and `action` is hidden during search. Pass a raw
 * `ReactNode` to `emptyState` instead if you need something bespoke.
 */
export interface EntityEmptyState {
  icon?: ReactNode;
  title: string;
  description: string;
  /** Title shown when a search query is active. Falls back to `title`. */
  searchTitle?: string;
  /** Description shown when a search query is active. Falls back to `description`. */
  searchDescription?: string;
  /** Call-to-action (e.g. a "Create your first X" button). Hidden while searching. */
  action?: ReactNode;
}

/** DataTable passthrough props that are meaningful for a standard list card. */
type DataTablePassthrough<T> = Pick<
  DataTableProps<T>,
  | "onRowClick"
  | "groupBy"
  | "renderGroupHeader"
  | "renderSubRows"
  | "getRowProps"
>;

export interface EntityTableCardProps<T extends { id?: string | number }>
  extends DataTablePassthrough<T> {
  /**
   * Data column definitions. Pass a function to receive `{ requestDelete }` so a custom
   * cell can open the built-in delete dialog. The trailing actions column is added
   * separately via `rowActions` (or build your own here).
   */
  columns:
    | Column<T>[]
    | ((helpers: EntityTableRenderHelpers<T>) => Column<T>[]);

  // --- Data source: EITHER self-fetch (fetchFn) OR controlled (data) ---
  /** Self-fetch mode: called on mount and whenever `refreshKey` changes. */
  fetchFn?: () => Promise<T[]>;
  /** Bump from the parent (after create/edit) to re-run `fetchFn`. */
  refreshKey?: number;
  /** Self-fetch mode: optimistically patch a single edited item into the list. */
  updatedItem?: T | null;

  /** Controlled mode: rows owned by the parent. When set, `fetchFn` is ignored. */
  data?: T[];
  /** Controlled mode: loading flag from the parent. */
  loading?: boolean;
  /** Controlled mode: error message from the parent. */
  error?: string | null;

  // --- Delete ---
  /** Enables delete. Receives the row; should perform the delete request. */
  deleteFn?: (item: T) => Promise<void>;
  /** Human-readable name used in the confirm dialog + toasts. Defaults to `item.name`. */
  getItemName?: (item: T) => string;
  /** Custom confirm-dialog body. Defaults to a standard "cannot be undone" message. */
  deleteDescription?: (item: T) => string;
  /** Extra type-to-confirm guard passed through to `ConfirmDialog`. */
  requireConfirmText?: string;
  /** Called after a successful delete (both modes) — e.g. to invalidate other queries. */
  onDeleted?: (item: T) => void;

  // --- Search ---
  searchQuery?: string;
  /** Simple search: match if any of these fields contains the query (case-insensitive). */
  searchFields?: Array<keyof T>;
  /** Custom search predicate. Receives the raw (untrimmed) query. Wins over `searchFields`. */
  filterFn?: (item: T, query: string) => boolean;

  // --- Copy ---
  /** Singular entity noun (e.g. "role") used to derive default toast/dialog copy. */
  entityName?: string;
  /** Plural entity noun (e.g. "roles"). Defaults to `entityName + "s"`. */
  entityNamePlural?: string;
  fetchErrorMessage?: string;
  deleteSuccessMessage?: string;
  deleteErrorMessage?: string;

  // --- Error ---
  /** Heading above the error message in the error state. Defaults to "Couldn't load data". */
  errorTitle?: string;
  /**
   * Retry handler for the error state's "Try again" button. In self-fetch mode this
   * defaults to re-running `fetchFn`; pass a value to override, or in controlled mode
   * to supply the parent's refetch. Omit in controlled mode for no retry button.
   */
  onRetry?: () => void;

  // --- Empty / pagination ---
  emptyMessage?: string;
  notFoundMessage?: string;
  emptyState?: ReactNode | EntityEmptyState;
  pageSize?: number;

  /** Row actions column config. Appends a standard `<ActionButtons>` column. */
  rowActions?: EntityRowActions<T>;
  /** Override how a row's stable key/id is derived. Defaults to `item.id`. */
  getItemId?: (item: T) => string | number;
}

function resolveFlag<T>(
  flag: RowFlag<T> | undefined,
  item: T,
  fallback: boolean
): boolean {
  if (flag === undefined) return fallback;
  return typeof flag === "function" ? flag(item) : flag;
}

function capitalize(value: string): string {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
}

function isEntityEmptyState(value: unknown): value is EntityEmptyState {
  return (
    typeof value === "object" &&
    value !== null &&
    !isValidElement(value) &&
    "title" in value
  );
}

/**
 * Reusable list-card that collapses the fetch → filter → delete-confirm → empty-state →
 * `<DataTable>` boilerplate shared by the per-entity `<XxxCard>` components.
 *
 * Two data-source modes:
 *  - **Self-fetch** — pass `fetchFn` (+ `refreshKey`, `updatedItem`). The card owns the
 *    `data / loading / error` state and optimistically drops deleted rows.
 *  - **Controlled** — pass `data` (+ `loading`, `error`). The parent owns the list; deletes
 *    call `deleteFn` then `onDeleted` so the parent can refetch/invalidate.
 *
 * @example
 * <EntityTableCard<Role>
 *   entityName="role"
 *   searchQuery={searchQuery}
 *   searchFields={["name"]}
 *   refreshKey={refreshKey}
 *   updatedItem={updatedRole}
 *   fetchFn={getAllRoles}
 *   deleteFn={(role) => deleteRole(role.id)}
 *   getItemName={(role) => role.name}
 *   emptyMessage="No roles found"
 *   notFoundMessage="No roles found matching your search"
 *   columns={columns}
 *   rowActions={{
 *     onEdit: onEditRole,
 *     editTitle: "Edit Role",
 *     deleteTitle: "Delete Role",
 *     canEdit: (role) => !restrictedRoles.has(role.name),
 *     canDelete: (role) => !restrictedRoles.has(role.name),
 *   }}
 * />
 */
export function EntityTableCard<T extends { id?: string | number }>({
  columns,
  fetchFn,
  refreshKey = 0,
  updatedItem = null,
  data,
  loading: loadingProp,
  error: errorProp,
  deleteFn,
  getItemName,
  deleteDescription,
  requireConfirmText,
  onDeleted,
  searchQuery = "",
  searchFields,
  filterFn,
  entityName,
  entityNamePlural,
  fetchErrorMessage,
  deleteSuccessMessage,
  deleteErrorMessage,
  errorTitle,
  onRetry,
  emptyMessage,
  notFoundMessage,
  emptyState,
  pageSize = LIST_PAGE_SIZE,
  rowActions,
  getItemId = (item: T) => item.id as string | number,
  onRowClick,
  groupBy,
  renderGroupHeader,
  renderSubRows,
  getRowProps,
}: EntityTableCardProps<T>) {
  const isControlled = data !== undefined;

  const [items, setItems] = useState<T[]>([]);
  const [internalLoading, setInternalLoading] = useState(true);
  const [internalError, setInternalError] = useState<string | null>(null);

  const [itemToDelete, setItemToDelete] = useState<T | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Keep the latest fetchFn without making it a fetch-effect dependency (avoids
  // re-fetch loops when callers pass an inline function).
  const fetchFnRef = useRef(fetchFn);
  fetchFnRef.current = fetchFn;

  const pluralName = entityNamePlural ?? (entityName ? `${entityName}s` : "items");
  const resolvedFetchError =
    fetchErrorMessage ?? `Failed to fetch ${pluralName}.`;
  const resolvedDeleteSuccess =
    deleteSuccessMessage ??
    (entityName ? `${capitalize(entityName)} deleted successfully.` : "Deleted successfully.");
  const resolvedDeleteError =
    deleteErrorMessage ?? `Failed to delete ${entityName ?? "item"}.`;

  // Runs the self-fetch. Reused by the mount/refreshKey effect and the error retry.
  const runFetch = useCallback(async () => {
    try {
      setInternalLoading(true);
      const result = (await fetchFnRef.current?.()) ?? [];
      setItems(result);
      setInternalError(null);
    } catch (err) {
      setInternalError(err instanceof Error ? err.message : resolvedFetchError);
      toast.error(resolvedFetchError);
    } finally {
      setInternalLoading(false);
    }
  }, [resolvedFetchError]);

  // Self-fetch on mount and whenever refreshKey changes.
  useEffect(() => {
    if (isControlled) return;
    runFetch();
  }, [isControlled, refreshKey, runFetch]);

  // Optimistically patch an edited item into the self-fetched list.
  useEffect(() => {
    if (isControlled || !updatedItem) return;
    setItems((prev) =>
      prev.map((item) =>
        getItemId(item) === getItemId(updatedItem) ? updatedItem : item
      )
    );
    // getItemId is intentionally omitted: it is a stable id accessor.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [updatedItem, isControlled]);

  const displayItems = isControlled ? data! : items;
  const loading = isControlled ? loadingProp ?? false : internalLoading;
  const error = isControlled ? errorProp ?? null : internalError;
  // Self-fetch mode gets a built-in retry; controlled mode only retries if the
  // parent supplies one. An explicit `onRetry` always wins.
  const handleRetry = onRetry ?? (isControlled ? undefined : runFetch);

  const requestDelete = (item: T) => {
    setItemToDelete(item);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!itemToDelete || !deleteFn) return;
    try {
      setIsDeleting(true);
      await deleteFn(itemToDelete);
      toast.success(resolvedDeleteSuccess);
      if (!isControlled) {
        const deletedId = getItemId(itemToDelete);
        setItems((prev) => prev.filter((item) => getItemId(item) !== deletedId));
      }
      onDeleted?.(itemToDelete);
    } catch (err) {
      const axiosError = err as AxiosError<{ error?: string }>;
      const apiMessage = axiosError.response?.data?.error;
      toast.error(apiMessage ?? resolvedDeleteError);
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setItemToDelete(null);
    }
  };

  // Filtering.
  const query = searchQuery.trim();
  const filteredItems =
    query.length === 0
      ? displayItems
      : filterFn
        ? displayItems.filter((item) => filterFn(item, searchQuery))
        : searchFields
          ? displayItems.filter((item) =>
              searchFields.some((field) => {
                const value = item[field];
                return (
                  value != null &&
                  String(value).toLowerCase().includes(query.toLowerCase())
                );
              })
            )
          : displayItems;

  // Columns (+ optional standard actions column).
  const dataColumns =
    typeof columns === "function" ? columns({ requestDelete }) : columns;

  const actionsColumn: Column<T> | null =
    rowActions && deleteFn
      ? {
          header: rowActions.header ?? "Actions",
          key: rowActions.key ?? "actions",
          className: rowActions.className,
          headerClassName: rowActions.headerClassName,
          // Stop clicks/keys inside the actions cell from bubbling to the row's
          // onRowClick / onKeyDown handler (safe even when no row handler is set).
          cell: (item) => (
            <div
              className="flex items-center gap-2"
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => e.stopPropagation()}
            >
              <ActionButtons
                onEdit={() => rowActions.onEdit?.(item)}
                onDelete={() => requestDelete(item)}
                onRevert={
                  rowActions.onRevert ? () => rowActions.onRevert!(item) : undefined
                }
                editTitle={rowActions.editTitle}
                deleteTitle={rowActions.deleteTitle}
                revertTitle={rowActions.revertTitle}
                canEdit={resolveFlag(rowActions.canEdit, item, !!rowActions.onEdit)}
                canDelete={resolveFlag(rowActions.canDelete, item, true)}
                canRevert={resolveFlag(rowActions.canRevert, item, false)}
              />
              {rowActions.extra?.(item)}
            </div>
          ),
        }
      : null;

  const allColumns = actionsColumn ? [...dataColumns, actionsColumn] : dataColumns;

  // Empty state.
  const resolvedEmptyState: ReactNode | undefined = !emptyState
    ? undefined
    : isEntityEmptyState(emptyState)
      ? (
          <ListEmptyState
            icon={emptyState.icon ?? null}
            title={
              query.length > 0 && emptyState.searchTitle
                ? emptyState.searchTitle
                : emptyState.title
            }
            description={
              query.length > 0 && emptyState.searchDescription
                ? emptyState.searchDescription
                : emptyState.description
            }
            action={query.length > 0 ? undefined : emptyState.action}
          />
        )
      : emptyState;

  return (
    <>
      <DataTable
        data={filteredItems}
        columns={allColumns}
        loading={loading}
        error={error}
        errorTitle={errorTitle}
        onRetry={handleRetry}
        searchQuery={searchQuery}
        pageSize={pageSize}
        emptyMessage={emptyMessage}
        notFoundMessage={notFoundMessage}
        emptyState={resolvedEmptyState}
        keyExtractor={getItemId}
        onRowClick={onRowClick}
        groupBy={groupBy}
        renderGroupHeader={renderGroupHeader}
        renderSubRows={renderSubRows}
        getRowProps={getRowProps}
      />

      {deleteFn && (
        <ConfirmDialog
          isOpen={isDeleteDialogOpen}
          onOpenChange={setIsDeleteDialogOpen}
          onConfirm={handleDeleteConfirm}
          isInProgress={isDeleting}
          itemName={itemToDelete ? getItemName?.(itemToDelete) ?? "" : ""}
          description={
            itemToDelete && deleteDescription
              ? deleteDescription(itemToDelete)
              : undefined
          }
          requireConfirmText={requireConfirmText}
        />
      )}
    </>
  );
}
