/**
 * The training files the Train Data Source dialog uploaded while it was open.
 *
 * A file is uploaded as soon as it is picked, so one that is then replaced, removed
 * or cancelled would stay in File Manager. A file the preview rejects stays in the form
 * (a 400 can also mean a temporary storage error) until it is replaced, removed or
 * cancelled, which discards it like any other.
 *
 * Only uploads made in this dialog session are discarded here: a file that was already
 * saved on the node may still be used by a saved workflow version, and the server
 * refuses to delete it anyway.
 */
export type DiscardUpload = (fileId: string) => Promise<void> | void;

export const createDialogUploads = () => {
  const ids = new Set<string>();
  return {
    /** Record a file this dialog just uploaded. */
    add(fileId: string | null | undefined) {
      if (fileId) ids.add(fileId);
    },
    /** The file is no longer used: discard it if this dialog uploaded it. */
    discard(fileId: string | null | undefined, discardUpload: DiscardUpload) {
      if (fileId && ids.delete(fileId)) void discardUpload(fileId);
    },
    /** Save (keep the saved file) or Cancel (keep nothing): discard the rest and start over. */
    discardAllExcept(keepFileId: string | null | undefined, discardUpload: DiscardUpload) {
      for (const fileId of ids) {
        if (fileId !== keepFileId) void discardUpload(fileId);
      }
      ids.clear();
    },
  };
};

export type DialogUploads = ReturnType<typeof createDialogUploads>;

/** The uploader key once the dialog has unmounted; no upload was started under it. */
export const UNMOUNTED_UPLOADER = -1;

/**
 * An upload belongs in the form only if the dialog is still open on the same uploader it
 * was started from: not after Cancel, a reopening, a source type switch or an unmount.
 */
export const isCurrentUpload = (startedUnder: number, liveUploader: number, isOpen: boolean): boolean =>
  isOpen && startedUnder === liveUploader;
