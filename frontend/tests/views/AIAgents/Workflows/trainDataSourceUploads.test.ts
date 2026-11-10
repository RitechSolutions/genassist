import { describe, expect, it, vi } from 'vitest';
import {
  createDialogUploads,
  isCurrentUpload,
  UNMOUNTED_UPLOADER,
} from '@/views/AIAgents/Workflows/nodeDialogs/training/trainDataSourceUploads';

describe('createDialogUploads', () => {
  it('discards an upload from this dialog when it is replaced or removed', () => {
    const uploads = createDialogUploads();
    const discard = vi.fn();
    uploads.add('first');

    uploads.discard('first', discard);

    expect(discard).toHaveBeenCalledExactlyOnceWith('first');
  });

  it('never discards a file that was already saved on the node', () => {
    const uploads = createDialogUploads();
    const discard = vi.fn();

    uploads.discard('saved-before', discard);
    uploads.discardAllExcept(null, discard);

    expect(discard).not.toHaveBeenCalled();
  });

  it('discards a file only once', () => {
    const uploads = createDialogUploads();
    const discard = vi.fn();
    uploads.add('first');

    uploads.discard('first', discard);
    uploads.discard('first', discard);
    uploads.discardAllExcept(null, discard);

    expect(discard).toHaveBeenCalledTimes(1);
  });

  it('on cancel discards every upload of this dialog', () => {
    const uploads = createDialogUploads();
    const discard = vi.fn();
    uploads.add('first');
    uploads.add('second');

    uploads.discardAllExcept(null, discard);

    expect(discard.mock.calls.map(([id]) => id).sort()).toEqual(['first', 'second']);
  });

  it('on save keeps the saved file and discards the rest', () => {
    const uploads = createDialogUploads();
    const discard = vi.fn();
    uploads.add('first');
    uploads.add('kept');

    uploads.discardAllExcept('kept', discard);

    expect(discard).toHaveBeenCalledExactlyOnceWith('first');
  });

  it('after save the kept file counts as saved, so a later replace leaves it to the server', () => {
    const uploads = createDialogUploads();
    const discard = vi.fn();
    uploads.add('kept');
    uploads.discardAllExcept('kept', discard);

    uploads.discard('kept', discard);

    expect(discard).not.toHaveBeenCalled();
  });

  it('ignores empty ids', () => {
    const uploads = createDialogUploads();
    const discard = vi.fn();

    uploads.add(undefined);
    uploads.add(null);
    uploads.discard(null, discard);
    uploads.discardAllExcept(undefined, discard);

    expect(discard).not.toHaveBeenCalled();
  });
});

describe('isCurrentUpload', () => {
  it('accepts an upload that finishes in the same open dialog it started in', () => {
    expect(isCurrentUpload(3, 3, true)).toBe(true);
  });

  it('rejects an upload that finishes after Cancel or close', () => {
    expect(isCurrentUpload(3, 3, false)).toBe(false);
  });

  it('rejects an upload started before the dialog was closed and reopened', () => {
    expect(isCurrentUpload(3, 4, true)).toBe(false);
  });

  it('rejects an upload that finishes after the source type was switched', () => {
    expect(isCurrentUpload(4, 5, true)).toBe(false);
  });

  it('rejects an upload that finishes after the dialog unmounted while open', () => {
    expect(isCurrentUpload(3, UNMOUNTED_UPLOADER, true)).toBe(false);
  });
});
