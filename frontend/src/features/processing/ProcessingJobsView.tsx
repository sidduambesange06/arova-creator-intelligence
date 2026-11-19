import { useEffect, useState } from "react";
import {
  cancelJob,
  fetchJobs,
  fetchJobStages,
  fetchVersionArtifacts,
  resumeJob,
  type ProcessingJob,
  type StageArtifact,
  type StageRun,
} from "../../services/api";

const CANONICAL_DAG_STAGES = [
  "metadata_probe",
  "scene_detection",
  "ocr_detection",
  "audio_extraction",
  "asr_transcription",
  "embedding_indexing",
  "summarization",
];

export function ProcessingJobsView() {
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string>("");
  const [stages, setStages] = useState<StageRun[]>([]);
  const [artifacts, setArtifacts] = useState<StageArtifact[]>([]);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const hasActiveJobs = jobs.some((j) =>
    ["running", "processing", "pending", "queued"].includes((j.status || "").toLowerCase())
  );

  useEffect(() => {
    let cancelled = false;
    async function loadJobs() {
      try {
        const j = await fetchJobs();
        if (!cancelled) {
          setJobs(j);
          setLoadError(null);
          setSelectedJobId((prev) => (prev || j[0]?.id || ""));
        }
      } catch (err) {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : "Failed to load processing jobs");
        }
      }
    }
    void loadJobs();
    if (!hasActiveJobs) {
      return () => {
        cancelled = true;
      };
    }
    const timer = setInterval(() => {
      void loadJobs();
    }, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [hasActiveJobs]);

  useEffect(() => {
    if (!selectedJobId) return;
    let cancelled = false;
    async function loadStagesAndArtifacts() {
      try {
        const st = await fetchJobStages(selectedJobId);
        if (!cancelled) setStages(st);
        if (st.length > 0) {
          const arts = await fetchVersionArtifacts(st[0].version_id).catch(() => []);
          if (!cancelled) setArtifacts(arts);
        } else if (!cancelled) {
          setArtifacts([]);
        }
      } catch {
        if (!cancelled) {
          setStages([]);
          setArtifacts([]);
        }
      }
    }
    void loadStagesAndArtifacts();
    return () => {
      cancelled = true;
    };
  }, [selectedJobId]);

  async function handleCancel(jobId: string) {
    try {
      const updated = await cancelJob(jobId);
      setActionMsg(`Job ${jobId.slice(0, 8)} ${updated.status}.`);
      setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, status: updated.status } : j)));
      const fresh = await fetchJobs().catch(() => null);
      if (fresh) setJobs(fresh);
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : "Cancel failed");
    }
  }

  async function handleResume(jobId: string) {
    try {
      const updated = await resumeJob(jobId);
      setActionMsg(`Job ${jobId.slice(0, 8)} resumed.`);
      setJobs((prev) => prev.map((j) => (j.id === jobId ? updated : j)));
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : "Resume failed");
    }
  }

  const selectedJob = jobs.find((j) => j.id === selectedJobId);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#9B8CFF]/10 text-[#9B8CFF] border border-[#9B8CFF]/30">
            TASK-4C RESUMABLE DAG
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
            7 DETERMINISTIC STAGES
          </span>
        </div>
        <h1 className="text-lg font-semibold text-[#F5F7FB]">
          Processing Pipeline &amp; Resumable DAG Execution
        </h1>
        <p className="text-xs text-[#A2AEC0]">
          Fault-tolerant DAG processing with atomic leases, stage SHA-256 fingerprints, and immutable artifacts.
        </p>

        {loadError && (
          <div role="alert" className="p-2 rounded bg-rose-950/40 border border-rose-900 text-xs font-mono text-rose-300">
            {loadError}
          </div>
        )}
        {actionMsg && (
          <div className="p-2 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-[#51DCC8]">
            {actionMsg}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Jobs List */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
          <h2 className="text-sm font-semibold text-[#F5F7FB]">
            Active &amp; Historical Jobs ({jobs.length})
          </h2>

          {jobs.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-400 font-mono">
              No processing jobs found.
            </div>
          ) : (
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {jobs.map((job) => {
                const isSelected = job.id === selectedJobId;
                return (
                  <div
                    key={job.id}
                    onClick={() => setSelectedJobId(job.id)}
                    className={`p-3 rounded-control border cursor-pointer transition-colors space-y-2 ${
                      isSelected
                        ? "bg-[#172235] border-[#9B8CFF]/50 text-[#F5F7FB]"
                        : "bg-[#0B1019] border-[#243149] text-slate-300 hover:bg-[#172235]/60"
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono font-medium truncate max-w-[140px]">
                        {job.id.slice(0, 10)}…
                      </span>
                      <span
                        className={`text-[10px] font-mono px-1.5 py-0.5 rounded uppercase ${
                          job.status === "completed"
                            ? "bg-emerald-950/60 text-emerald-400 border border-emerald-800"
                            : job.status === "running"
                            ? "bg-amber-950/60 text-amber-400 border border-amber-800 animate-pulse"
                            : job.status === "failed"
                            ? "bg-rose-950/60 text-rose-400 border border-rose-800"
                            : "bg-slate-800 text-slate-300"
                        }`}
                      >
                        {job.status}
                      </span>
                    </div>

                    <div className="w-full bg-[#080B12] rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-[#9B8CFF] h-1.5 rounded-full"
                        style={{ width: `${Math.round(job.progress * 100)}%` }}
                      />
                    </div>

                    <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                      <span>Video: {job.video_id.slice(0, 8)}…</span>
                      <span>{Math.round(job.progress * 100)}%</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right 2 Columns: Selected Job DAG Visualizer & Artifacts */}
        <div className="lg:col-span-2 space-y-6">
          {selectedJob ? (
            <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#243149] pb-3">
                <div>
                  <h2 className="text-sm font-semibold text-[#F5F7FB]">
                    Job DAG Execution: <span className="font-mono text-[#9B8CFF]">{selectedJob.id}</span>
                  </h2>
                  <p className="text-[11px] font-mono text-slate-400 mt-0.5">
                    Type: {selectedJob.job_type} · Target Video: {selectedJob.video_id}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  {selectedJob.status === "running" && (
                    <button
                      type="button"
                      onClick={() => handleCancel(selectedJob.id)}
                      className="px-3 py-1 rounded bg-rose-950/60 border border-rose-800 text-rose-300 text-xs font-mono hover:bg-rose-900"
                    >
                      Cancel Job
                    </button>
                  )}
                  {(selectedJob.status === "failed" || selectedJob.status === "cancelled") && (
                    <button
                      type="button"
                      onClick={() => handleResume(selectedJob.id)}
                      className="px-3 py-1 rounded bg-emerald-950/60 border border-emerald-800 text-emerald-300 text-xs font-mono hover:bg-emerald-900"
                    >
                      Resume / Retry Job
                    </button>
                  )}
                </div>
              </div>

              {/* 7 Canonical Stages */}
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-slate-300">7-Stage DAG Progress</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {CANONICAL_DAG_STAGES.map((stageName, idx) => {
                    const stageRun = stages.find((s) => s.stage === stageName);
                    const status = stageRun ? stageRun.status : "pending";
                    return (
                      <div
                        key={stageName}
                        className="p-2.5 rounded bg-[#0B1019] border border-[#243149] flex items-center justify-between text-xs font-mono"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-slate-500">{idx + 1}.</span>
                          <span className="text-[#F5F7FB]">{stageName}</span>
                        </div>
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded uppercase ${
                            status === "completed"
                              ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                              : status === "running"
                              ? "bg-amber-950 text-amber-400 border border-amber-800 animate-pulse"
                              : status === "failed"
                              ? "bg-rose-950 text-rose-400 border border-rose-800"
                              : status === "skipped"
                              ? "bg-slate-800 text-slate-400"
                              : "bg-[#172235] text-slate-500"
                          }`}
                        >
                          {status}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Detailed Stage Runs Table */}
              <div className="pt-2 border-t border-[#243149] space-y-2">
                <h3 className="text-xs font-semibold text-slate-300">Stage Leases &amp; Fingerprints</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead>
                      <tr className="border-b border-[#243149] text-slate-400">
                        <th className="py-1 px-2">Stage</th>
                        <th className="py-1 px-2">Attempt</th>
                        <th className="py-1 px-2">Fingerprint (SHA-256)</th>
                        <th className="py-1 px-2">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#243149]/40 text-slate-300">
                      {stages.map((st) => (
                        <tr key={st.id} className="hover:bg-[#172235]/40">
                          <td className="py-1.5 px-2 text-[#9B8CFF]">{st.stage}</td>
                          <td className="py-1.5 px-2">#{st.attempt}</td>
                          <td className="py-1.5 px-2 text-[10px] text-slate-400">
                            {st.fingerprint ? `${st.fingerprint.slice(0, 16)}…` : "--"}
                          </td>
                          <td className="py-1.5 px-2">{st.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Versioned Stage Artifacts Table */}
              {artifacts.length > 0 && (
                <div className="pt-2 border-t border-[#243149] space-y-2">
                  <h3 className="text-xs font-semibold text-slate-300">
                    Generated Versioned Artifacts ({artifacts.length})
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs font-mono">
                      <thead>
                        <tr className="border-b border-[#243149] text-slate-400">
                          <th className="py-1 px-2">Kind</th>
                          <th className="py-1 px-2">Producer Stage</th>
                          <th className="py-1 px-2">Trust</th>
                          <th className="py-1 px-2">Current</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#243149]/40 text-slate-300">
                        {artifacts.map((art) => (
                          <tr key={art.id} className="hover:bg-[#172235]/40">
                            <td className="py-1 px-2 text-[#51DCC8]">{art.kind}</td>
                            <td className="py-1 px-2">{art.producer_stage}</td>
                            <td className="py-1 px-2 text-[10px] text-slate-400">{art.trust}</td>
                            <td className="py-1 px-2">{art.is_current ? "YES" : "NO"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="p-8 rounded-panel bg-[#111827] border border-[#243149] text-center text-xs text-slate-400 font-mono">
              Select a processing job to inspect its 7-stage DAG execution.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
