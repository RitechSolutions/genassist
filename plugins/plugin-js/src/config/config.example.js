 const GENASSIST_CONFIG = {
    baseUrl: 'https://api.test.genassist.ritech.io',
    apiKey: 'genagent123',
    tenant: '',
    headerTitle: 'GenAssist',
    agentName: 'GenAssist',
    description: 'Your Virtual Assistant',
    // logoUrl: 'https://www.lausanne-tourisme.ch/app/uploads/2025/06/pay-by-phone.png',
    placeholder: 'Ask anything...',
    mode: 'floating',
    floatingConfig: { position: 'bottom-right' },
    serverUnavailableMessage: 'Support is currently offline. Please try again later or contact us.',
    noColorAnimation: true,
    useWs: false,
    useFiles: false,
    theme: {
        primaryColor: "#4F46E5",
        secondaryColor: "#f5f5f5",
        backgroundColor: "#ffffff",
        textColor: "#000000",
        fontFamily: "Roboto, Arial, sans-serif",
        fontSize: "14px",
    },
};

// inject the config into the window object
window.GENASSIST_CONFIG = GENASSIST_CONFIG;