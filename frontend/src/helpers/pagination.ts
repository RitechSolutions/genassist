export function getPageList(currentPage: number, totalPages: number): number[] {
  return Array.from({ length: totalPages }, (_, i) => i + 1);
}