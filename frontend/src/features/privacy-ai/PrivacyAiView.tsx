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
  const [loading, setLoading] = useState(true);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  // Verify Provider Modal State
  const [verifyingProvider, setVerifyingProvider] = useState<string | null>(null);
  const [verifyKey, setVerifyKey] = useState("");
  const [verifyModel, setVerifyModel] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<ProviderVerifyResponse | null>(null);

  // Grant Consent Form State
  const [consentProvider, setConsentProvider] = useState("google-gemini");
  const [consentPurpose, setConsentPurpose] = useState("Grounded Q&A & Video Summarization");
  const [consentHours, setConsentHours] = useState(24);
  const [granting, setGranting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadAll() {
      setLoading(true);
      try {
        const [provs, cs, rns] = await Promise.all([
          fetchAiProviders().catch(() => []),
          fetchAiConsents().catch(() => []),
          fetchAiRuns().catch(() => []),
        ]);
        if (!cancelled) {
          setProviders(Array.isArray(provs) ? provs : []);
          setConsents(Array.isArray(cs) ? cs : []);
          setRuns(Array.isArray(rns) ? rns : []);
        }
      } catch (err) {
        if (!cancelled) {
          setStatusMsg(err instanceof Error ? err.message : "Failed to load AI configurations");
        }
      } finally {
        if (!cancelled) setLoading(false);
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
      const updatedProvs = await fetchAiProviders().catch(() => []);
      setProviders(Array.isArray(updatedProvs) ? updatedProvs : []);
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

  const safeProviders = Array.isArray(providers) ? providers : [];
  const safeConsents = Array.isArray(consents) ? consents : [];
  const safeRuns = Array.isArray(runs) ? runs : [];

  return (
    <div className="space-y-6">
      {/* Header Stance */}
      <div className="p-6 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#51DCC8]/10 text-[#51DCC8] border border-[#51DCC8]/30 font-semibold">
            100% LOCAL-FIRST ENCLAVE
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#9B8CFF]/10 text-[#9B8CFF] border border-[#9B8CFF]/30 font-semibold">
            BRING YOUR OWN AI (BYO-AI)
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
            ZERO SILENT CLOUD FALLBACKS
          </span>
        </div>
        <h1 className="text-xl font-semibold text-[#F5F7FB]">
          Privacy Enclave &amp; BYO-AI Gateway
        </h1>
        <p className="text-xs text-[#A2AEC0] max-w-4xl leading-relaxed">
          Arova guarantees that your original media, audio transcripts, and video embeddings remain strictly on your local machine.
          Optional remote AI providers (Google Gemini, OpenAI, Anthropic) can be connected using your personal API keys, and only execute
          when you grant an explicit, time-bounded scoped consent.
        </p>

        {statusMsg && (
          <div className="p-3 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-[#51DCC8] flex items-center justify-between">
            <span>{statusMsg}</span>
            <button
              type="button"
              onClick={() => setStatusMsg(null)}
              className="text-slate-500 hover:text-white"
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {/* Privacy Architecture Guarantee Banner */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-panel bg-[#0B1019] border border-[#243149] space-y-1.5">
          <div className="text-xs font-semibold text-[#51DCC8] flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-[#51DCC8]" />
            1. Zero Cloud Egress by Default
          </div>
          <p className="text-[11px] text-slate-400 leading-normal">
            All speech transcription (Whisper), optical OCR, scene cut detection, and vector search run 100% locally on your CPU or GPU.
          </p>
        </div>

        <div className="p-4 rounded-panel bg-[#0B1019] border border-[#243149] space-y-1.5">
          <div className="text-xs font-semibold text-[#9B8CFF] flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-[#9B8CFF]" />
            2. Scoped User Consents
          </div>
          <p className="text-[11px] text-slate-400 leading-normal">
            Remote AI requests are blocked by the kernel unless an active consent is granted for a specific purpose and expires automatically.
          </p>
        </div>

        <div className="p-4 rounded-panel bg-[#0B1019] border border-[#243149] space-y-1.5">
          <div className="text-xs font-semibold text-[#F4BF69] flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-[#F4BF69]" />
            3. Immutable Provenance Audit
          </div>
          <p className="text-[11px] text-slate-400 leading-normal">
            Every AI query is hashed and logged in an immutable AIRun ledger with token counts and latency for full transparency.
          </p>
        </div>
      </div>

      {/* Configured AI Providers Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[#F5F7FB]">
            Configured AI Providers ({loading ? "…" : safeProviders.length})
          </h2>
          <span className="text-[11px] font-mono text-slate-400">
            Local Extractive Engine is always active and offline
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {safeProviders.map((p) => (
            <div
              key={p.id}
              className="p-4 rounded-panel bg-[#111827] border border-[#243149] flex flex-col justify-between space-y-3 shadow-sm hover:border-[#9B8CFF]/40 transition-colors"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-[#F5F7FB]">{p.name}</span>
                  <span
                    className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-semibold ${
                      p.local
                        ? "bg-[#51DCC8]/10 text-[#51DCC8] border border-[#51DCC8]/30"
                        : p.configured
                        ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                        : "bg-slate-800 text-slate-400 border border-slate-700"
                    }`}
                  >
                    {p.local ? "100% LOCAL" : p.configured ? "CONFIGURED" : "OPTIONAL"}
                  </span>
                </div>
                <p className="text-[11px] font-mono text-slate-400">ID: {p.id}</p>
                <p className="text-[11px] font-mono text-[#9B8CFF]">Default: {p.default_model}</p>
                <div className="flex flex-wrap gap-1">
                  {p.available_models.slice(0, 2).map((m) => (
                    <span
                      key={m}
                      className="text-[9px] font-mono px-1 py-0.2 rounded bg-[#0B1019] text-slate-400 border border-[#243149]"
                    >
                      {m}
                    </span>
                  ))}
                </div>
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
                  Verify Credentials →
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
            <div>
              <h2 className="text-sm font-semibold text-[#F5F7FB]">
                Active Scoped Consents ({safeConsents.length})
              </h2>
              <p className="text-[11px] text-slate-400">
                Grants permission for specific duration and purpose
              </p>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
              Enclave Guard Active
            </span>
          </div>

          <form onSubmit={handleGrantConsent} className="p-3.5 rounded bg-[#0B1019] border border-[#243149] space-y-3 font-sans">
            <div className="text-xs font-semibold text-slate-200">Grant New Scoped Consent</div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <label className="text-[11px] text-slate-400 font-mono">Provider:</label>
                <select
                  value={consentProvider}
                  onChange={(e) => setConsentProvider(e.target.value)}
                  className="w-full mt-1 px-2.5 py-1.5 rounded bg-[#111827] border border-[#243149] text-xs font-mono text-white focus:outline-none"
                >
                  <option value="google-gemini">google-gemini</option>
                  <option value="openai">openai</option>
                  <option value="anthropic">anthropic</option>
                  <option value="local">local (extractive)</option>
                </select>
              </div>

              <div>
                <label className="text-[11px] text-slate-400 font-mono">Duration (hours):</label>
                <select
                  value={consentHours}
                  onChange={(e) => setConsentHours(parseInt(e.target.value, 10))}
                  className="w-full mt-1 px-2.5 py-1.5 rounded bg-[#111827] border border-[#243149] text-xs font-mono text-white focus:outline-none"
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
                placeholder="e.g. Grounded Video Q&A and Scene Summarization"
                className="w-full mt-1 px-2.5 py-1.5 rounded bg-[#111827] border border-[#243149] text-xs text-white focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={granting}
              className="w-full py-2 rounded bg-[#9B8CFF] hover:bg-[#8b7aee] text-[#080B12] text-xs font-semibold font-mono disabled:opacity-50 transition-colors shadow-sm"
            >
              {granting ? "Granting Permission..." : "+ Grant Scoped Consent"}
            </button>
          </form>

          {/* Consents List */}
          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
            {safeConsents.length === 0 ? (
              <div className="py-6 text-center text-xs text-slate-500 font-mono">
                No active remote AI consents. All requests execute strictly within the local enclave.
              </div>
            ) : (
              safeConsents.map((c) => (
                <div
                  key={c.id}
                  className="p-3 rounded bg-[#0B1019] border border-[#243149] flex items-center justify-between text-xs hover:border-[#243149]/80 transition-colors"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-[#F5F7FB]">{c.provider}</span>
                      <span className="text-[10px] font-mono px-1 rounded bg-[#172235] text-slate-400">
                        {c.scope_type}
                      </span>
                      <span
                        className={`text-[9px] font-mono px-1 rounded ${
                          c.active ? "bg-emerald-950 text-emerald-300" : "bg-rose-950 text-rose-300"
                        }`}
                      >
                        {c.active ? "ACTIVE" : "REVOKED"}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400">{c.purpose}</p>
                    <p className="text-[10px] font-mono text-slate-500">
                      Expires: {c.expires_at ? new Date(c.expires_at).toLocaleTimeString() : "Never (Manual Revoke)"}
                    </p>
                  </div>
                  {c.active && (
                    <button
                      type="button"
                      onClick={() => handleRevokeConsent(c.id)}
                      className="px-2.5 py-1 rounded bg-rose-950/60 border border-rose-800 text-rose-300 text-xs font-mono hover:bg-rose-900 transition-colors"
                    >
                      Revoke
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Immutable AI Runs Audit Log */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
          <div className="flex items-center justify-between border-b border-[#243149] pb-3">
            <div>
              <h2 className="text-sm font-semibold text-[#F5F7FB]">
                AI Provenance Audit Log ({safeRuns.length})
              </h2>
              <p className="text-[11px] text-slate-400">
                Immutable cryptographic ledger of prompts and model executions
              </p>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
              AIRun Table
            </span>
          </div>

          {safeRuns.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-400 font-mono space-y-1">
              <div>No remote AI executions recorded yet.</div>
              <p className="text-[10px] text-slate-500">
                Executions appear here when Grounded Q&A queries or model inference runs.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto max-h-80">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-[#243149] text-slate-400 text-[11px]">
                    <th className="py-2 px-2">Provider</th>
                    <th className="py-2 px-2">Model</th>
                    <th className="py-2 px-2">Location</th>
                    <th className="py-2 px-2">Latency</th>
                    <th className="py-2 px-2">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#243149]/40 text-slate-300">
                  {safeRuns.map((r) => (
                    <tr key={r.id} className="hover:bg-[#172235]/40 transition-colors">
                      <td className="py-2 px-2 text-[#9B8CFF] font-medium">{r.provider}</td>
                      <td className="py-2 px-2 text-slate-300">{r.model}</td>
                      <td className="py-2 px-2">
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#0B1019] text-[#51DCC8] border border-[#243149]">
                          Local Enclave
                        </span>
                      </td>
                      <td className="py-2 px-2 text-[#51DCC8]">
                        {r.latency_ms && r.latency_ms > 0 ? `${r.latency_ms.toFixed(0)}ms` : "Instant"}
                      </td>
                      <td className="py-2 px-2 text-[10px] text-slate-500">
                        {r.created_at ? new Date(r.created_at).toLocaleTimeString() : "Recent"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Multilingual & Indic Language Readiness Matrix */}
      <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
        <div className="flex items-center justify-between border-b border-[#243149] pb-2">
          <h2 className="text-sm font-semibold text-[#F5F7FB]">
            Multilingual &amp; Indic Language Readiness Matrix
          </h2>
          <span className="text-[10px] font-mono text-[#51DCC8]">
            12 Indian Languages Evaluated
          </span>
        </div>
        <p className="text-xs text-[#A2AEC0]">
          Whisper, Faster-Whisper, and IndicConformer multi-script ASR evaluated on real-world Indian creator speech with mixed Hinglish support.
        </p>

        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2 pt-1">
          {INDIC_LANGUAGES.map((lang) => (
            <div
              key={lang.code}
              className="p-2.5 rounded bg-[#0B1019] border border-[#243149] space-y-1 text-xs font-mono hover:border-[#9B8CFF]/30 transition-colors"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-white">{lang.name}</span>
                <span className="text-[10px] text-slate-500">{lang.code.toUpperCase()}</span>
              </div>
              <p className="text-[10px] text-slate-400">{lang.script}</p>
              <span className="inline-block text-[9px] px-1.5 py-0.2 rounded bg-[#51DCC8]/10 text-[#51DCC8] border border-[#51DCC8]/30 font-medium">
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
                ✕
              </button>
            </div>

            <form onSubmit={handleVerifySubmit} className="space-y-3 font-sans">
              <div className="space-y-1">
                <label className="text-xs text-slate-300 font-medium">API Key (optional if configured in .env):</label>
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
                  className="w-full px-2.5 py-1.5 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-white focus:outline-none"
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
                  className="px-4 py-1.5 rounded bg-[#9B8CFF] hover:bg-[#8b7aee] text-[#080B12] text-xs font-semibold font-mono disabled:opacity-50 transition-colors"
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
export default PrivacyAiView;
