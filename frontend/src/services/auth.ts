import {
  PublicClientApplication,
  Configuration,
  InteractionRequiredAuthError,
} from "@azure/msal-browser";

const msalConfig: Configuration = {
  auth: {
    clientId: import.meta.env.VITE_AZURE_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_AZURE_TENANT_ID}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  },
};

export const msalInstance = new PublicClientApplication(msalConfig);
await msalInstance.initialize();

const loginRequest = {
  scopes: [`api://${import.meta.env.VITE_AZURE_CLIENT_ID}/kaats.user`],
};

export async function getAccessToken(): Promise<string> {
  const accounts = msalInstance.getAllAccounts();
  if (!accounts.length) throw new Error("No authenticated accounts found.");

  try {
    const result = await msalInstance.acquireTokenSilent({
      ...loginRequest,
      account: accounts[0],
    });
    return result.accessToken;
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) {
      const result = await msalInstance.acquireTokenPopup(loginRequest);
      return result.accessToken;
    }
    throw error;
  }
}

export { loginRequest };
