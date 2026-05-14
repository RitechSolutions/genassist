'use strict';

const VITE_GENASSIST_CHAT_APIURL = null;
const VITE_GENASSIST_CHAT_APIKEY = null;

window.GENASSIST_CONFIG = {
  baseUrl: VITE_GENASSIST_CHAT_APIURL,
  apiKey: VITE_GENASSIST_CHAT_APIKEY,
  tenant: '',
  headerTitle: 'GenAssist Demo',
  mode: 'floating',
  floatingConfig: { position: 'bottom-right' },
  serverUnavailableMessage: 'Support is currently offline. Please try again later or contact us.',
  noColorAnimation: true,
  useWs: false,
  useFiles: false,
  usePoll: false,
  theme: {
    primaryColor: "#278900",
    secondaryColor: "#d7f3cc",
    backgroundColor: "#ffffff",
    textColor: "#000000",
    fontFamily: "Roboto, sans-serif",
    fontSize: "16px",
    fontWeight: 400
  }
};