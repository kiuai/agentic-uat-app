import { useMsal } from "@azure/msal-react";
import { loginRequest } from "@/services/auth";

export function LoginPage() {
  const { instance, inProgress } = useMsal();

  const handleLogin = () => {
    instance.loginRedirect(loginRequest);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-10 max-w-md w-full text-center">
        <div className="mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-600 text-white text-2xl font-bold mb-4">
            K
          </div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">KAATS</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1 text-sm">
            KIU AI Automated Test System
          </p>
        </div>

        <p className="text-sm text-gray-600 dark:text-gray-400 mb-8">
          Sign in with your corporate Microsoft account to access the platform.
        </p>

        <button
          onClick={handleLogin}
          disabled={inProgress !== "none"}
          className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-3"
        >
          <svg viewBox="0 0 21 21" className="h-5 w-5" fill="currentColor">
            <rect x="1" y="1" width="9" height="9" />
            <rect x="11" y="1" width="9" height="9" />
            <rect x="11" y="11" width="9" height="9" />
            <rect x="1" y="11" width="9" height="9" fill="#fff" fillOpacity="0.7" />
          </svg>
          {inProgress !== "none" ? "Signing in…" : "Sign in with Microsoft"}
        </button>
      </div>
    </div>
  );
}
