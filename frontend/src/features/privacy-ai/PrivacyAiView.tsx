import { useEffect, useState } from "react";
import {
  fetchAiConsents,
  fetchAiProviders,
  fetchAiRuns,
  grantAiConsent,
  revokeAiConsent,
  verifyAiProvider,
  type AIProviderInfo,
  type AIRunItem,
  type ConsentItem,
  type ProviderVerifyResponse,
} from "../../services/api";

const INDIC_LANGUAGES = [
  { code: "hi", name: "Hindi", script: "Devanagari", status: "Verified Local ASR" },
  { code: "kn", name: "Kannada", script: "Kannada", status: "Verified Local ASR" },
  { code: "ta", name: "Tamil", script: "Tamil", status: "Verified Local ASR" },
  { code: "te", name: "Telugu", script: "Telugu", status: "Verified Local ASR" },
  { code: "mr", name: "Marathi", script: "Devanagari", status: "Supported" },
  { code: "bn", name: "Bengali", script: "Bengali", status: "Supported" },
  { code: "ml", name: "Malayalam", script: "Malayalam", status: "Supported" },
  { code: "gu", name: "Gujarati", script: "Gujarati", status: "Supported" },
  { code: "pa", name: "Punjabi", script: "Gurmukhi", status: "Supported" },
  { code: "or", name: "Odia", script: "Odia", status: "Supported" },
  { code: "as", name: "Assamese", script: "Bengali-Assamese", status: "Supported" },
  { code: "ur", name: "Urdu", script: "Perso-Arabic", status: "Supported" },
];

export function PrivacyAiView() {
  const [providers, setProviders] = useState<AIProviderInfo[]>([]);
  const [consents, setConsents] = useState<ConsentItem[]>([]);
  const [runs, setRuns] = useState<AIRunItem[]>([]);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  // Verify Provider Modal State
  const [verifyingProvider, setVerifyingProvider] = useState<string | null>(null);
  const [verifyKey, setVerifyKey] = useState("");
  const [verifyModel, setVerifyModel] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<ProviderVerifyResponse | null>(null);

  // Grant Consent Form State
  const [consentProvider, setConsentProvider] = useState("google-gemini");
  const [consentPurpose, setConsentPurpose] = useState("Research and Grounded Q&A");
  const [consentHours, setConsentHours] = useState(24);
  const [granting, setGranting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadAll() {
      try {
        const [provs, cs, rns] = await Promise.all([
          fetchAiProviders().catch(() => []),
          fetchAiConsents().catch(() => []),
          fetchAiRuns().catch(() => []),
        ]);
        if (!cancelled) {
          setProviders(provs);
          setConsents(cs);
          setRuns(rns);
        }
      } catch {
        // Handled
      }
    }
    void loadAll();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleVerifySubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!verifyingProvider) return;
    setVerifying(true);
    setVerifyResult(null);
    try {
      const res = await verifyAiProvider({
        provider: verifyingProvider,
        api_key: verifyKey.trim() || undefined,
        model: verifyModel.trim() || undefined,
      });
      setVerifyResult(res);
      // Refresh providers
      const updatedProvs = await fetchAiProviders();
      setProviders(updatedProvs);
    } catch (err) {
      setVerifyResult({
        provider: verifyingProvider,
        status: "error",
        model: verifyModel || "unknown",
        message: err instanceof Error ? err.message : "Verification failed",
        latency_ms: 0,
      });
    } finally {
      setVerifying(false);
    }
  }

  async function handleGrantConsent(e: React.FormEvent) {
    e.preventDefault();
    if (!consentProvider || !consentPurpose.trim()) return;
    setGranting(true);
    setStatusMsg(null);
    try {
      const item = await grantAiConsent({
        provider: consentProvider,
        purpose: consentPurpose.trim(),
        duration_hours: consentHours,
      });
      setConsents((prev) => [item, ...prev]);
      setStatusMsg(`Consent granted for provider ${consentProvider} (${consentHours}h duration).`);
    } catch (err) {
      setStatusMsg(err instanceof Error ? err.message : "Failed to grant consent");
    } finally {
      setGranting(false);
    }
  }

  async function handleRevokeConsent(consentId: string) {
    try {
      await revokeAiConsent(consentId);
      setConsents((prev) => prev.filter((c) => c.id !== consentId));
      setStatusMsg("Consent revoked successfully.");
    } catch (err) {
      setStatusMsg(err instanceof Error ? err.message : "Failed to revoke consent");
    }
  }

  return (
    <div className="space-y-6">
      {/* Header Stance */}
      <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#51DCC8]/10 text-[#51DCC8] border border-[#51DCC8]/30">
            LOCAL-FIRST ENCLAVE
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#9B8CFF]/10 text-[#9B8CFF] border border-[#9B8CFF]/30">
            BYO-AI GATEWAY
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
            STEP 6 IMPLEMENTED
          </span>
        </div>
        <h1 className="text-lg font-semibold text-[#F5F7FB]">
          Privacy, BYO-AI Gateway &amp; Consent Management
        </h1>
        <p className="text-xs text-[#A2AEC0] max-w-3xl leading-relaxed">
          Arova runs completely offline by default. No data or media ever leaves your machine without
          an active, user-granted scoped consent. Bring your own API keys for optional remote intelligence.
        </p>

        {statusMsg && (
          <div className="p-2 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-[#51DCC8]">
            {statusMsg}
          </div>
        )}
      </div>

      {/* Provider Cards Grid */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-[#F5F7FB]">Configured AI Providers ({providers.length})</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {providers.map((p) => (
            <div
              key={p.id}
              className="p-4 rounded-panel bg-[#111827] border border-[#243149] flex flex-col justify-between space-y-3"
            >
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-[#F5F7FB]">{p.name}</span>
                  <span
                    className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                      p.local
                        ? "bg-[#51DCC8]/10 text-[#51DCC8] border border-[#51DCC8]/30"
                        : p.configured
                        ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                        : "bg-slate-800 text-slate-400"
                    }`}
                  >
                    {p.local ? "100% LOCAL" : p.configured ? "CONFIGURED" : "NOT SET"}
                  </span>
                </div>
                <p className="text-[11px] font-mono text-slate-400">ID: {p.id}</p>
                <p className="text-[11px] font-mono text-[#9B8CFF]">Default: {p.default_model}</p>
              </div>

              <div className="pt-2 border-t border-[#243149]">
                <button
                  type="button"
                  onClick={() => {
                    setVerifyingProvider(p.id);
                    setVerifyModel(p.default_model);
                    setVerifyResult(null);
                  }}
                  className="w-full py-1.5 rounded-control bg-[#172235] hover:bg-[#232f48] text-xs font-mono text-[#F5F7FB] border border-[#243149] transition-colors"
                >
                  Verify Credentials â†’
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Two Column Layout: Consent Manager & AIRun Audit Log */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Scoped Consents */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
          <div className="flex items-center justify-between border-b border-[#243149] pb-3">
            <h2 className="text-sm font-semibold text-[#F5F7FB]">
              Active Scoped Consents ({consents.length})
            </h2>
            <span className="text-[10px] font-mono text-slate-400">Zero Cloud Egress Barrier</span>
          </div>

          <form onSubmit={handleGrantConsent} className="p-3 rounded bg-[#0B1019] border border-[#243149] space-y-3 font-sans">
            <div className="text-xs font-semibold text-slate-200">Grant Scoped Consent</div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <label className="text-[11px] text-slate-400 font-mono">Provider:</label>
                <select
                  value={consentProvider}
                  onChange={(e) => setConsentProvider(e.target.value)}
                  className="w-full mt-0.5 px-2 py-1 rounded bg-[#111827] border border-[#243149] text-xs font-mono text-white"
                >
                  <option value="google-gemini">google-gemini</option>
                  <option value="openai">openai</option>
                  <option value="anthropic">anthropic</option>
                </select>
              </div>

              <div>
                <label className="text-[11px] text-slate-400 font-mono">Duration (hours):</label>
                <select
                  value={consentHours}
                  onChange={(e) => setConsentHours(parseInt(e.target.value, 10))}
                  className="w-full mt-0.5 px-2 py-1 rounded bg-[#111827] border border-[#243149] text-xs font-mono text-white"
                >
                  <option value={1}>1 Hour</option>
                  <option value={8}>8 Hours</option>
                  <option value={24}>24 Hours</option>
                  <option value={72}>72 Hours</option>
                </select>
              </div>
            </div>

            <div>
              <label className="text-[11px] text-slate-400 font-mono">Purpose Description:</label>
              <input
                type="text"
                required
                value={consentPurpose}
                onChange={(e) => setConsentPurpose(e.target.value)}
                placeholder="e.g. Grounded Video Q&A"
                className="w-full mt-0.5 px-2 py-1 rounded bg-[#111827] border border-[#243149] text-xs text-white"
              />
            </div>

            <button
              type="submit"
              disabled={granting}
              className="w-full py-1.5 rounded bg-[#9B8CFF] text-[#080B12] text-xs font-semibold font-mono disabled:opacity-50"
            >
              {granting ? "Granting..." : "+ Grant Scoped Consent"}
            </button>
          </form>

          {/* Consents List */}
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {consents.length === 0 ? (
              <div className="py-4 text-center text-xs text-slate-500 font-mono">
                No active remote AI consents. All requests stay strictly local.
              </div>
            ) : (
              consents.map((c) => (
                <div
                  key={c.id}
                  className="p-2.5 rounded bg-[#0B1019] border border-[#243149] flex items-center justify-between text-xs"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-[#F5F7FB]">{c.provider}</span>
                      <span className="text-[10px] font-mono px-1 rounded bg-[#172235] text-slate-400">
                        {c.scope_type}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400">{c.purpose}</p>
                    <p className="text-[10px] font-mono text-slate-500">
                      Expires: {c.expires_at ? new Date(c.expires_at).toLocaleTimeString() : "Never"}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRevokeConsent(c.id)}
                    className="px-2 py-1 rounded bg-rose-950/60 border border-rose-800 text-rose-300 text-xs font-mono hover:bg-rose-900"
                  >
                    Revoke
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Immutable AI Runs Audit Log */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
          <div className="flex items-center justify-between border-b border-[#243149] pb-3">
            <h2 className="text-sm font-semibold text-[#F5F7FB]">
              AI Provenance Audit Log ({runs.length})
            </h2>
            <span className="text-[10px] font-mono text-slate-400">AIRun Ledger</span>
          </div>

          {runs.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-400 font-mono">
              No remote AI executions recorded yet.
            </div>
          ) : (
            <div className="overflow-x-auto max-h-80">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-[#243149] text-slate-400">
                    <th className="py-1 px-2">Provider</th>
                    <th className="py-1 px-2">Model</th>
                    <th className="py-1 px-2">Tokens (In/Out)</th>
                    <th className="py-1 px-2">Latency</th>
                    <th className="py-1 px-2">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#243149]/40 text-slate-300">
                  {runs.map((r) => (
                    <tr key={r.id} className="hover:bg-[#172235]/40">
                      <td className="py-1.5 px-2 text-[#9B8CFF]">{r.provider}</td>
                      <td className="py-1.5 px-2 text-slate-300">{r.model}</td>
                      <td className="py-1.5 px-2">
                        {r.prompt_tokens}/{r.completion_tokens}
                      </td>
                      <td className="py-1.5 px-2 text-[#51DCC8]">{r.latency_ms.toFixed(0)}ms</td>
                      <td className="py-1.5 px-2 text-[10px] text-slate-500">
                        {new Date(r.created_at).toLocaleTimeString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Indic Speech & Text Language Readiness Matrix */}
      <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
        <h2 className="text-sm font-semibold text-[#F5F7FB]">
          Multilingual &amp; Indic Language Readiness Matrix
        </h2>
        <p className="text-xs text-[#A2AEC0]">
          Whisper, Faster-Whisper, and IndicConformer multi-script ASR evaluated on real-world Indian creator speech.
        </p>

        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
          {INDIC_LANGUAGES.map((lang) => (
            <div
              key={lang.code}
              className="p-2.5 rounded bg-[#0B1019] border border-[#243149] space-y-1 text-xs font-mono"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-white">{lang.name}</span>
                <span className="text-[10px] text-slate-500">{lang.code.toUpperCase()}</span>
              </div>
              <p className="text-[10px] text-slate-400">{lang.script}</p>
              <span className="inline-block text-[9px] px-1.5 py-0.2 rounded bg-[#51DCC8]/10 text-[#51DCC8] border border-[#51DCC8]/30">
                {lang.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Verify Provider Modal */}
      {verifyingProvider && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md bg-[#111827] border border-[#243149] rounded-panel p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#243149] pb-2">
              <h3 className="text-xs font-semibold text-[#F5F7FB]">
                Verify Provider: {verifyingProvider}
              </h3>
              <button
                type="button"
                onClick={() => setVerifyingProvider(null)}
                className="text-slate-400 hover:text-white text-sm"
              >
                âœ•
              </button>
            </div>

            <form onSubmit={handleVerifySubmit} className="space-y-3 font-sans">
              <div className="space-y-1">
                <label className="text-xs text-slate-300 font-medium">API Key (optional if in .env):</label>
                <input
                  type="password"
                  value={verifyKey}
                  onChange={(e) => setVerifyKey(e.target.value)}
                  placeholder="Enter API key to test..."
                  className="w-full px-2.5 py-1.5 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-white focus:outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-300 font-medium">Model ID:</label>
                <input
                  type="text"
                  value={verifyModel}
                  onChange={(e) => setVerifyModel(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-white"
                />
              </div>

              {verifyResult && (
                <div
                  className={`p-2.5 rounded text-xs font-mono border ${
                    verifyResult.status === "verified"
                      ? "bg-emerald-950/60 text-emerald-300 border-emerald-800"
                      : "bg-rose-950/60 text-rose-300 border-rose-800"
                  }`}
                >
                  <p className="font-semibold uppercase">{verifyResult.status}</p>
                  <p className="text-[11px] mt-0.5">{verifyResult.message}</p>
                  <p className="text-[10px] text-slate-400 mt-1">
                    Latency: {verifyResult.latency_ms.toFixed(1)}ms
                  </p>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setVerifyingProvider(null)}
                  className="px-3 py-1.5 rounded bg-[#172235] text-xs text-slate-300"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={verifying}
                  className="px-4 py-1.5 rounded bg-[#9B8CFF] text-[#080B12] text-xs font-semibold font-mono disabled:opacity-50"
                >
                  {verifying ? "Testing Connectivity..." : "Run Test Probe"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
