'use strict';

const VITE_GENASSIST_CHAT_APIURL = null;
const VITE_GENASSIST_CHAT_APIKEY = null;

window.GENASSIST_CONFIG = {
  baseUrl: VITE_GENASSIST_CHAT_APIURL,
  apiKey: VITE_GENASSIST_CHAT_APIKEY,
  tenant: '',
  headerTitle: 'GenAssist Demo',
  placeholder: 'Ask anything...',
  mode: 'floating',
  floatingConfig: { position: 'bottom-right' },
  serverUnavailableMessage: 'Support is currently offline. Please try again later or contact us.',
  noColorAnimation: true,
  useWs: false,
  useFiles: false
};