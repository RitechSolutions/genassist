import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ArrowUp, FileUp, Plus, ScanLine } from 'lucide-react';
import { LiveCallControl } from '../LiveCallControl';
import { VoiceInput } from '../VoiceInput';
import { UploadSheet } from './UploadSheet';
import { EmojiPicker } from './EmojiPicker';
import type { SpotlightController } from './types';
import { canCaptureScreen, captureScreenshot, screenshotAllowed } from '../../utils/screenshot';

const MAX_TEXTAREA_PX = 132;

interface ComposerAction {
  key: string;
  label: string;
  icon: React.ReactNode;
  run: () => void;
}

/**
 * The + button. With a single action it runs it directly (no point in a one-item menu);
 * with more it opens a popover above itself. Future attachments (screenshot, etc.) only
 * need to be appended to `actions`.
 */
const PlusButton: React.FC<{ ctl: SpotlightController; actions: ComposerAction[]; disabled: boolean }> = ({
  ctl,
  actions,
  disabled,
}) => {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent | TouchEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('touchstart', onPointerDown);
    document.addEventListener('keydown', onKey, true);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('touchstart', onPointerDown);
      document.removeEventListener('keydown', onKey, true);
    };
  }, [open]);

  if (actions.length === 0) return null;
  const single = actions.length === 1;
  const label = single ? actions[0].label : ctl.t('spotlight.attach', 'Attach');

  return (
    <div ref={wrapRef} style={{ position: 'relative', display: 'flex' }}>
      <button
        type="button"
        className="gas-icon-btn gas-plus"
        disabled={disabled}
        aria-label={label}
        title={label}
        aria-haspopup={single ? undefined : 'menu'}
        aria-expanded={single ? undefined : open}
        onClick={() => (single ? actions[0].run() : setOpen((o) => !o))}
      >
        <Plus size={19} />
      </button>
      {open && (
        <div
          className="gas-popover"
          role="menu"
          style={{ bottom: 'calc(100% + 10px)', left: -2, ['--gas-origin' as string]: 'bottom left' }}
        >
          {actions.map((a) => (
            <button
              key={a.key}
              type="button"
              role="menuitem"
              className="gas-menu-item"
              onClick={() => {
                setOpen(false);
                a.run();
              }}
            >
              {a.icon}
              <span className="gas-menu-item-label">{a.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

/** Pill composer plus the states that replace it (start, live voice) and the upload sheet. */
export const SpotlightComposer: React.FC<{ ctl: SpotlightController }> = ({ ctl }) => {
  const { t, themeParams } = ctl;
  const [fired, setFired] = useState(false);

  // Grow with the content up to ~5 lines, then scroll.
  useLayoutEffect(() => {
    const el = ctl.textAreaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_PX)}px`;
    el.style.overflowY = el.scrollHeight > MAX_TEXTAREA_PX ? 'auto' : 'hidden';
  }, [ctl.inputValue, ctl.textAreaRef]);

  const send = () => {
    if (ctl.isSendDisabled) return;
    setFired(true);
    ctl.onSubmit();
  };

  const openFilePicker = () => ctl.fileInputRef.current?.click();

  if (ctl.shouldShowStartButton) {
    return (
      <button type="button" className="gas-start" onClick={ctl.onStartConversation} disabled={ctl.isLoading}>
        {t('buttons.startConversation', 'Start Conversation')}
      </button>
    );
  }

  if (ctl.liveVoiceEnabled) {
    // Voice-only agent: the only way in is a live call.
    return (
      <div className="gas-composer">
        <span className="gas-voice-hint">
          {ctl.liveVoiceReady
            ? t('liveVoice.tapToStart', 'Tap to start a voice conversation')
            : t('liveVoice.unavailable', 'Voice is currently unavailable')}
        </span>
        <LiveCallControl
          status={ctl.liveVoiceStatus}
          isActive={ctl.liveVoiceActive}
          onStart={ctl.onStartLiveCall}
          onStop={ctl.onEndLiveCall}
          theme={ctl.theme}
          disabled={!ctl.agentId || !ctl.liveVoiceReady}
        />
      </div>
    );
  }

  const inputDisabled = !ctl.conversationId || ctl.isFinalized || ctl.hasPendingForm;
  const isEmpty = ctl.inputValue.trim() === '' && ctl.attachments.length === 0;
  const showMic = ctl.useAudio && isEmpty;

  const actions: ComposerAction[] = [];
  if (ctl.useFile) {
    actions.push({
      key: 'file',
      label: t('spotlight.sendFile', 'Send a file'),
      icon: <FileUp size={17} />,
      run: openFilePicker,
    });
  }
  if (ctl.useFile && ctl.allowScreenshot && canCaptureScreen() && screenshotAllowed(ctl.allowedExtensions)) {
    actions.push({
      key: 'screenshot',
      label: t('spotlight.addScreenshot', 'Add screenshot'),
      icon: <ScanLine size={17} />,
      run: () => {
        captureScreenshot()
          .then((file) => {
            if (file) ctl.onAddFiles([file]);
          })
          .catch(() => ctl.onFileError(t('spotlight.screenshotFailed', "Couldn't take the screenshot. Please try again.")));
      },
    });
  }

  return (
    <>
      {ctl.useFile && ctl.attachments.length > 0 && <UploadSheet ctl={ctl} onAddMore={openFilePicker} />}

      <form
        className={`gas-composer${inputDisabled ? ' gas-composer--disabled' : ''}`}
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <PlusButton ctl={ctl} actions={actions} disabled={inputDisabled} />
        {ctl.useFile && (
          <input
            ref={ctl.fileInputRef}
            type="file"
            multiple
            hidden
            onChange={ctl.onFileChange}
            accept={ctl.allowedExtensions.join(',') || '*/*'}
          />
        )}
        <textarea
          ref={ctl.textAreaRef}
          className="gas-textarea"
          rows={1}
          value={ctl.inputValue}
          placeholder={ctl.inputPlaceholder}
          disabled={inputDisabled}
          aria-label={ctl.inputPlaceholder}
          onChange={(e) => ctl.setInputValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        {ctl.showEmojiPicker && <EmojiPicker ctl={ctl} disabled={inputDisabled} />}
        {showMic ? (
          // VoiceInput positions itself absolutely inside the composer (mic over the send
          // slot; the recording bar covers the whole pill), so reserve the slot here.
          <>
            <span style={{ width: 36, height: 36, flexShrink: 0 }} aria-hidden="true" />
            <VoiceInput
              onAudioReady={(blob, format) => {
                void ctl.onSendAudio(blob, format);
              }}
              onError={ctl.onVoiceError}
              theme={{ ...ctl.theme, inputBackgroundColor: themeParams.inputBackgroundColor }}
              disabled={inputDisabled}
            />
          </>
        ) : (
          <button
            type="submit"
            className={`gas-send${fired ? ' gas-send--fired' : ''}`}
            disabled={ctl.isSendDisabled}
            aria-label={t('spotlight.send', 'Send message')}
            title={t('spotlight.send', 'Send message')}
            onAnimationEnd={() => setFired(false)}
          >
            <ArrowUp size={18} strokeWidth={2.6} />
          </button>
        )}
      </form>
    </>
  );
};
