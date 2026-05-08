import { useMsal } from "@azure/msal-react";
import { loginRequest } from "@/services/auth";

export function LoginPage() {
  const { instance, inProgress } = useMsal();

  const handleLogin = () => {
    instance.loginRedirect(loginRequest);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
      <div className="bg-white rounded-xl shadow-lg p-10 max-w-md w-full text-center">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">KAATS</h1>
          <p className="text-gray-500 mt-1">KIU AI Automated Test System</p>
        </div>
        <p className="text-sm text-gray-600 mb-8">
          Sign in with your corporate Microsoft account to access the platform.
        </p>
        <button
          onClick={handleLogin}
          disabled={inProgress !== "none"}
          className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-3"
        >
          <svg viewBox="0 0 21 21" className="h-5 w-5" fill="currentColor">
            <path d="M0 0h10v10H0zm11 0h10v10H11zm0 11h10v10H11zM0 11h10v10H0z" />
          </svg>
          Sign in with Microsoft
        </button>
      </div>
    </div>
  );
}
