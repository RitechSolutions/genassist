import { getPageItems } from "@/helpers/pagination";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { cn } from "@/lib/utils";

type PaginationBarProps = {
  total: number;
  currentPage: number;
  pageSize: number;
  pageItemCount?: number;
  onPageChange: (page: number) => void;
  className?: string;
  siblingCount?: number;
};

export function PaginationBar({
  total,
  currentPage,
  pageSize,
  pageItemCount,
  onPageChange,
  className,
  siblingCount = 1,
}: PaginationBarProps) {
  const safeTotal = Math.max(0, total);
  const safePageSize = Math.max(1, pageSize || 1);

  if (safeTotal <= 0) return null;

  const totalPages = Math.max(1, Math.ceil(safeTotal / safePageSize));
  const safePage = Math.min(Math.max(1, currentPage || 1), totalPages);
  const pageItems = getPageItems(safePage, totalPages, siblingCount);
  const itemsOnPage =
    typeof pageItemCount === "number" && pageItemCount >= 0
      ? pageItemCount
      : safePageSize;
  const displayStart =
    safeTotal === 0 || itemsOnPage === 0
      ? 0
      : Math.min((safePage - 1) * safePageSize + 1, safeTotal);
  const displayEnd =
    safeTotal === 0
      ? 0
      : Math.min((safePage - 1) * safePageSize + itemsOnPage, safeTotal);
  const disablePrev = safePage <= 1;
  const disableNext = safePage >= totalPages;

  return (
    <div
      className={cn(
        "px-2 md:px-3 pt-4 pb-2 flex items-center justify-between",
        className
      )}
    >
      <div className="text-sm text-muted-foreground">
        {`Showing ${displayStart} to ${displayEnd} of ${safeTotal} results`}
      </div>
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious
              href="#"
              onClick={(e) => {
                e.preventDefault();
                if (!disablePrev) onPageChange(safePage - 1);
              }}
              className={disablePrev ? "pointer-events-none opacity-50" : ""}
              aria-disabled={disablePrev}
              tabIndex={disablePrev ? -1 : undefined}
            />
          </PaginationItem>
          {pageItems.map((item, index) =>
            item === "ellipsis" ? (
              <PaginationItem key={`ellipsis-${index}`}>
                <PaginationEllipsis />
              </PaginationItem>
            ) : (
              <PaginationItem key={item}>
                <PaginationLink
                  href="#"
                  isActive={item === safePage}
                  onClick={(e) => {
                    e.preventDefault();
                    onPageChange(item);
                  }}
                >
                  {item}
                </PaginationLink>
              </PaginationItem>
            )
          )}
          <PaginationItem>
            <PaginationNext
              href="#"
              onClick={(e) => {
                e.preventDefault();
                if (!disableNext) onPageChange(safePage + 1);
              }}
              className={disableNext ? "pointer-events-none opacity-50" : ""}
              aria-disabled={disableNext}
              tabIndex={disableNext ? -1 : undefined}
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  );
}
