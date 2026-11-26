import React, { useMemo, useRef } from 'react';
import { AlertCircle, ArrowDown } from 'lucide-react';
import DynamicFormMessage from '../DynamicFormMessage';
import { CSS_KEYFRAMES, getFloatingContainerStyle } from '../../styles/genAgentChatStyles';
import { SPOTLIGHT_CSS } from './spotlightStyles';
import { buildSpotlightVars } from './spotlightTheme';
import { SpotlightHeader } from './SpotlightHeader';
import { SpotlightMenu } from './SpotlightMenu';
import { SpotlightConversation } from './SpotlightConversation';
import { SpotlightComposer } from './SpotlightComposer';
import { SpotlightLauncher } from './SpotlightLauncher';
import type { SpotlightController } from './types';
import { GenAssistWordmark } from './GenAssistWordmark';

const SpotlightPanel: React.FC<{ ctl: SpotlightController }> = ({ ctl }) => {
  const { t, themeParams } = ctl;
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  return (
    <div className={`gas-panel${ctl.isFullscreen ? ' gas-panel--full' : ''}`}>
      <SpotlightHeader ctl={ctl} menuButtonRef={menuButtonRef} />

      <div className="gas-scroll" ref={ctl.chatContainerRef}>
        {ctl.languageSelector}
        <SpotlightConversation ctl={ctl} />
        <div ref={ctl.setBottomSentinelRef} />
        <div ref={ctl.spacerRef} style={{ flexShrink: 0 }} />
      </div>

      <div className="gas-footer">
        {ctl.showScrollButton && (
          <button
            type="button"
            className="gas-jump"
            style={{ top: -44 }}
            onClick={() => ctl.scrollToLatest()}
            aria-label={t('spotlight.jumpToLatest', 'Jump to latest')}
            title={t('spotlight.jumpToLatest', 'Jump to latest')}
          >
            <ArrowDown size={17} />
          </button>
        )}

        {ctl.fileErrorToast && (
          <div className="gas-toast" role="alert">
            <AlertCircle size={17} style={{ flexShrink: 0 }} />
            <span>{ctl.fileErrorToast}</span>
          </div>
        )}
        {ctl.liveVoiceNotice && (
          <div className="gas-toast" role="alert">
            <AlertCircle size={17} style={{ flexShrink: 0 }} />
            <span>{ctl.liveVoiceNotice}</span>
          </div>
        )}

        <SpotlightComposer ctl={ctl} />

        {ctl.disclaimerHtml && (
          <div className="gas-meta" dangerouslySetInnerHTML={{ __html: ctl.disclaimerHtml }} />
        )}
        {/* The agent's own disclaimer takes this slot; the credit only shows without one. */}
        {ctl.showPoweredBy && !ctl.disclaimerHtml && (
          <div className="gas-meta">
            <span className="gas-powered">
              {t('spotlight.poweredBy', 'Powered by')}
              <GenAssistWordmark height={11} />
            </span>
          </div>
        )}
      </div>

      {ctl.showMenu && <SpotlightMenu ctl={ctl} anchorRef={menuButtonRef} />}

      {ctl.pendingForm && ctl.formDisplay !== 'inline' && (
        <div className="gas-form-overlay">
          <DynamicFormMessage
            schema={ctl.pendingForm.schema}
            onSubmit={(data) => ctl.onFormSubmit(data, ctl.pendingForm!.index)}
            onCancel={() => ctl.onFormCancel(ctl.pendingForm!.index)}
            isSubmitting={ctl.submittingFormIndex === ctl.pendingForm.index}
            isSubmitted={false}
            primaryColor={themeParams.primaryColor}
            fontFamily={themeParams.fontFamily}
            backgroundColor={themeParams.backgroundColor}
            textColor={themeParams.textColor}
            borderColor={themeParams.borderColor}
            mutedTextColor={themeParams.mutedTextColor}
            inputBackgroundColor={themeParams.inputBackgroundColor}
            variant="fullscreen"
            title={ctl.agentName || undefined}
          />
        </div>
      )}

      {ctl.showResetConfirm && (
        <div className="gas-overlay" onClick={ctl.onCancelReset}>
          <div
            className="gas-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="gas-reset-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="gas-reset-title">{t('dialog.resetConversation.title', 'Reset Conversation')}</h3>
            <p>{t('dialog.resetConversation.message')}</p>
            <div className="gas-dialog-actions">
              <button type="button" className="gas-btn gas-btn--ghost" onClick={ctl.onCancelReset}>
                {t('buttons.cancel', 'Cancel')}
              </button>
              <button type="button" className="gas-btn gas-btn--danger" onClick={ctl.onConfirmReset} autoFocus>
                {t('buttons.reset', 'Reset')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * mode="spotlight": a floating launcher that opens a redesigned panel. Same chat engine
 * as every other mode (state lives in GenAgentChat); only the presentation differs.
 */
export const SpotlightChat: React.FC<{ ctl: SpotlightController }> = ({ ctl }) => {
  const vars = useMemo(() => buildSpotlightVars(ctl.themeParams), [ctl.themeParams]);
  const isClosing = ctl.isPanelMounted && !ctl.isOpen;

  const containerStyle = getFloatingContainerStyle({
    mode: 'floating',
    isFullscreen: ctl.isFullscreen,
    windowWidth: ctl.windowWidth,
    windowHeight: ctl.windowHeight,
    position: ctl.position,
    offsetX: ctl.offsetX,
    offsetY: ctl.offsetY,
    isExpanded: ctl.isExpanded,
    keyboard: ctl.keyboard,
  });

  return (
    <div className="gas-root" style={vars} data-genassist-root="true">
      <style>{CSS_KEYFRAMES}</style>
      <style>{SPOTLIGHT_CSS}</style>

      {!ctl.isPanelMounted && <SpotlightLauncher ctl={ctl} />}

      {ctl.isPanelMounted && (
        <div
          style={containerStyle}
          className={isClosing ? 'gas-panel-out' : 'gas-panel-in'}
          onAnimationEnd={(e) => {
            // Only the container's own close animation unmounts it, not bubbled child ones.
            if (e.target !== e.currentTarget) return;
            if (isClosing) ctl.onPanelClosed();
          }}
          data-genassist-container="spotlight"
        >
          <SpotlightPanel ctl={ctl} />
        </div>
      )}
    </div>
  );
};
