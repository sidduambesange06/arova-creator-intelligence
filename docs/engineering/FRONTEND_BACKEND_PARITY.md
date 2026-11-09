# Frontend / Backend Parity Matrix

**Document Version:** 1.0.0  
**Status:** Canonical Parity Audit  
**Backend Base URL:** `http://127.0.0.1:8000/api/v1`  
**Security Contract:** Deny-by-default filesystem, Local Enclave binding (`127.0.0.1`), Scoped Cloud AI Consents, Read-Only FastMCP Tools.

---

## 1. Complete API Route & UI Control Mapping

| Router | Method & Endpoint | Request Payload / Params | Response Model | Frontend Client Function | Frontend Screen & Interactive Control | Parity Status |
|---|---|---|---|---|---|---|
| **Core Health** | `GET /api/v1/health` | None | `HealthResponse` | `fetchHealth()` | `App.tsx` (TopBar badge, Sidebar status), `SystemHealthView.tsx` | **Verified** |
| **System** | `GET /api/v1/system/telemetry` | None | `SystemTelemetryResponse` | `fetchSystemTelemetry()` | `SystemHealthView.tsx`, `OverviewView.tsx` | **Verified** |
| **Videos** | `POST /api/v1/videos/import` | `VideoImportRequest` (`path`, `collection_id?`) | `VideoImportResponse` | `importVideos()` | `MediaLibraryView.tsx` & `OverviewView.tsx` (Modal) | **Verified** |
| **Videos** | `GET /api/v1/videos` | `collection_id?` | `list[VideoOut]` | `fetchVideos()` | `MediaLibraryView.tsx` (Asset grid), `VideoWorkstationView.tsx` | **Verified** |
| **Videos** | `GET /api/v1/videos/stats/summary` | None | `MediaLibraryStats` | `fetchMediaLibraryStats()` | `OverviewView.tsx` (6 KPI tiles), `McpConfigView.tsx` | **Verified** |
| **Videos** | `GET /api/v1/videos/{id}` | `video_id` path param | `VideoOut` | `fetchVideo()` | `MediaLibraryView.tsx` (Inspector pane), `VideoWorkstationView.tsx` | **Verified** |
| **Videos** | `GET /api/v1/videos/{id}/thumbnail` | `video_id` path param | JPEG image binary | `getVideoThumbnailUrl()` | `MediaLibraryView.tsx` (Thumbnails), `VideoWorkstationView.tsx` | **Verified** |
| **Videos** | `DELETE /api/v1/videos/{id}/index` | `video_id` path param | Status dict | `deleteVideoIndex()` | `MediaLibraryView.tsx` (Right Inspector -> Delete Index button) | **Verified** |
| **Videos** | `POST /api/v1/videos/{id}/process` | `sync=true/false` query | Job status dict | `processVideo()` | `MediaLibraryView.tsx` (Re-index button), `ProcessingJobsView.tsx` | **Verified** |
| **Videos** | `GET /api/v1/videos/{id}/transcript` | `video_id` path param | `TranscriptOut` | `fetchVideoTranscript()` | `MediaLibraryView.tsx`, `VideoWorkstationView.tsx` (Speech track) | **Verified** |
| **Videos** | `GET /api/v1/videos/{id}/scenes` | `video_id` path param | `list[VideoSceneOut]` | `fetchVideoScenes()` | `MediaLibraryView.tsx`, `VideoWorkstationView.tsx` (Scenes track) | **Verified** |
| **Videos** | `GET /api/v1/videos/{id}/stream` | Range header | Video chunk binary | `getVideoStreamUrl()` | `VideoWorkstationView.tsx`, `MediaLibraryView.tsx` (Player) | **Verified** |
| **Videos** | `POST /api/v1/videos/{id}/export-clip` | `ClipExportRequest` (`start_time`, `end_time`) | `ClipExportResponse` | `exportVideoClip()` | `VideoWorkstationView.tsx` & `HybridSearchView.tsx` (Export Clip) | **Verified** |
| **Videos** | `GET /api/v1/videos/clips/{filename}` | `clip_filename` path | Video MP4 binary | `getClipDownloadUrl()` | `VideoWorkstationView.tsx` (Download Link) | **Verified** |
| **Videos (Subtitles)** | `POST /api/v1/videos/{id}/subtitles` | `SubtitleIngestRequest` (`content`, `filename`, `language`) | `TranscriptOut` | `uploadVideoSubtitles()` | `OverviewView.tsx` (Import drawer), `VideoWorkstationView.tsx` | **Verified** |
| **Collections** | `GET /api/v1/collections` | None | `list[CollectionOut]` | `fetchCollections()` | `MediaLibraryView.tsx` (Filter pills), `StorageBackupView.tsx` | **Verified** |
| **Collections** | `POST /api/v1/collections` | `name`, `description?` | `CollectionOut` | `createCollection()` | `MediaLibraryView.tsx` (New collection modal) | **Verified** |
| **Collections** | `POST /api/v1/collections/{id}/videos` | `video_id` | `CollectionOut` | `addVideoToCollection()` | `MediaLibraryView.tsx` (Inspector -> Tag to Collection) | **Verified** |
| **Search & RAG** | `POST /api/v1/search/semantic` | `HybridSearchRequest` (`query`, `top_k`, `use_reranker`, `video_id?`) | `HybridSearchResponse` | `searchSemantic()` | `HybridSearchView.tsx` (Search bar, Cross-Encoder toggle) | **Verified** |
| **Search & RAG** | `POST /api/v1/search/transcripts` | `query`, `video_id?`, `limit?` | `list[TranscriptSearchResult]` | `searchTranscripts()` | `HybridSearchView.tsx` (Lexical mode toggle) | **Verified** |
| **Search & RAG** | `POST /api/v1/search/clips` | `query`, `top_k?` | `list[ClipResultItem]` | `searchClips()` | `HybridSearchView.tsx` (Visual matching results) | **Verified** |
| **Search & RAG** | `POST /api/v1/ai/summarize` | `video_id` | `SummarizeResponse` | `summarizeVideo()` | `VideoWorkstationView.tsx` (Summarize Tab) | **Verified** |
| **Search & RAG** | `POST /api/v1/ai/ask` | `query`, `video_id?`, `provider?` | `AskQuestionResponse` | `askVideoAi()` | `HybridSearchView.tsx` (Ask Archive console with citations) | **Verified** |
| **ML Eval** | `POST /api/v1/ml/eval/run` | None | `EvalBenchmarkReport` | `runEvalBenchmark()` | `HybridSearchView.tsx` (Run Benchmark suite button) | **Verified** |
| **ML Eval** | `GET /api/v1/ml/eval/report` | None | `EvalBenchmarkReport` | `fetchLatestEvalReport()` | `HybridSearchView.tsx` (MRR/NDCG comparison report table) | **Verified** |
| **Discovery (4B)** | `GET /api/v1/discovery/libraries` | None | `list[LibraryOut]` | `fetchDiscoveryLibraries()` | `DiscoverySourcesView.tsx` (Library selector) | **Verified** |
| **Discovery (4B)** | `POST /api/v1/discovery/libraries` | `name`, `device_id?` | `LibraryOut` | `createDiscoveryLibrary()` | `DiscoverySourcesView.tsx` (New library modal) | **Verified** |
| **Discovery (4B)** | `GET /api/v1/discovery/libraries/{id}/roots` | `library_id` path | `list[LibraryRootOut]` | `fetchDiscoveryRoots()` | `DiscoverySourcesView.tsx` (Active media roots table) | **Verified** |
| **Discovery (4B)** | `POST /api/v1/discovery/libraries/{id}/roots` | `path`, `policy`, `recursive` | `LibraryRootOut` | `registerDiscoveryRoot()` | `DiscoverySourcesView.tsx` (Register root form) | **Verified** |
| **Discovery (4B)** | `POST /api/v1/discovery/roots/{id}/scan` | `root_id` path | `ScanRunOut` | `scanDiscoveryRoot()` | `DiscoverySourcesView.tsx` (Scan Now button) | **Verified** |
| **Discovery (4B)** | `GET /api/v1/discovery/roots/{id}/scans` | `root_id` path | `list[ScanRunOut]` | `fetchScanRuns()` | `DiscoverySourcesView.tsx` (Scan Run history table) | **Verified** |
| **Jobs & DAG (4C)** | `GET /api/v1/jobs` | `status?`, `video_id?` | `list[ProcessingJobOut]` | `fetchJobs()` | `ProcessingJobsView.tsx` (Job list table) | **Verified** |
| **Jobs & DAG (4C)** | `GET /api/v1/jobs/{id}` | `job_id` path | `ProcessingJobOut` | `fetchJobDetails()` | `ProcessingJobsView.tsx` (Selected job header) | **Verified** |
| **Jobs & DAG (4C)** | `POST /api/v1/jobs/{id}/cancel` | `job_id` path | `ProcessingJobOut` | `cancelJob()` | `ProcessingJobsView.tsx` (Cancel Job button) | **Verified** |
| **Jobs & DAG (4C)** | `POST /api/v1/jobs/{id}/resume` | `job_id` path | `ProcessingJobOut` | `resumeJob()` | `ProcessingJobsView.tsx` (Resume / Retry button) | **Verified** |
| **Jobs & DAG (4C)** | `GET /api/v1/jobs/{id}/stages` | `job_id` path | `list[StageRunOut]` | `fetchJobStages()` | `ProcessingJobsView.tsx` (7-Stage DAG visualizer) | **Verified** |
| **Jobs & DAG (4C)** | `GET /api/v1/jobs/versions/{id}/artifacts` | `version_id` path | `list[ArtifactOut]` | `fetchJobArtifacts()` | `ProcessingJobsView.tsx` (Artifacts table with SHA-256) | **Verified** |
| **Portable (4D)** | `POST /api/v1/portable/export` | `video_ids`, `bundle_name`, options | `ExportSummary` | `exportPortableArchive()` | `StorageBackupView.tsx` (Export `.arova` wizard) | **Verified** |
| **Portable (4D)** | `POST /api/v1/portable/import/dry-run` | `archive_path` | `ImportDryRunReport` | `dryRunPortableImport()` | `StorageBackupView.tsx` (Dry-run preview table) | **Verified** |
| **Portable (4D)** | `POST /api/v1/portable/import` | `archive_path`, `conflict_policy` | `ImportResult` | `importPortableArchive()` | `StorageBackupView.tsx` (Import Archive button) | **Verified** |
| **Portable (4D)** | `GET /api/v1/versions/{id}/availability` | `version_id` path | `MediaAvailabilityOut` | `fetchMediaAvailability()` | `MediaLibraryView.tsx` & `StorageBackupView.tsx` | **Verified** |
| **Portable (4D)** | `POST /api/v1/versions/{id}/relink` | `new_file_path`, `expected_hash` | `RelinkResponse` | `relinkMediaAsset()` | `MediaLibraryView.tsx` & `StorageBackupView.tsx` (Relink modal) | **Verified** |
| **Portable (4D)** | `GET /api/v1/libraries/duplicates` | None | `list[DuplicateGroupOut]` | `fetchDuplicateMedia()` | `StorageBackupView.tsx` (Duplicate media table) | **Verified** |
| **Portable (4D)** | `GET /api/v1/annotations` | `video_id?` | `list[AnnotationOut]` | `fetchAnnotations()` | `VideoWorkstationView.tsx` (User notes track) | **Verified** |
| **Portable (4D)** | `POST /api/v1/annotations` | `video_id`, `start_time`, `text` | `AnnotationOut` | `createAnnotation()` | `VideoWorkstationView.tsx` (Add note at playhead) | **Verified** |
| **BYO-AI (Step 6)** | `GET /api/v1/ai/providers` | None | `list[AIProviderInfo]` | `fetchAiProviders()` | `PrivacyAiView.tsx` (Provider cards grid) | **Verified** |
| **BYO-AI (Step 6)** | `POST /api/v1/ai/providers/verify` | `provider_id`, `api_key?`, `model?` | `ProviderVerifyResponse` | `verifyAiProvider()` | `PrivacyAiView.tsx` (Verify Credentials button) | **Verified** |
| **BYO-AI (Step 6)** | `GET /api/v1/ai/consents` | `active_only=true/false` | `list[ConsentOut]` | `fetchAiConsents()` | `PrivacyAiView.tsx` (Active consents table) | **Verified** |
| **BYO-AI (Step 6)** | `POST /api/v1/ai/consents` | `provider_id`, `purpose`, `hours` | `ConsentOut` | `grantAiConsent()` | `PrivacyAiView.tsx` (Grant Scoped Consent form) | **Verified** |
| **BYO-AI (Step 6)** | `DELETE /api/v1/ai/consents/{id}` | `consent_id` path | Status dict | `revokeAiConsent()` | `PrivacyAiView.tsx` (Revoke Consent button) | **Verified** |
| **BYO-AI (Step 6)** | `GET /api/v1/ai/runs` | `limit=50` | `list[AIRunOut]` | `fetchAiRuns()` | `PrivacyAiView.tsx` (Immutable AIRun audit log) | **Verified** |
| **Smart Loop (Step 7)** | `GET /api/v1/tools` | None | `list[ToolDefinitionOut]` | `fetchSharedTools()` | `HybridSearchView.tsx` (Tool Explorer tab) | **Verified** |
| **Smart Loop (Step 7)** | `POST /api/v1/tools/execute` | `tool_name`, `arguments` | `ToolExecuteResponse` | `executeSharedTool()` | `HybridSearchView.tsx` (Execute Tool console) | **Verified** |
| **Smart Loop (Step 7)** | `POST /api/v1/agent/smart-loop` | `query`, `max_turns`, `provider?` | `SmartLoopResponse` | `runSmartLoopAgent()` | `HybridSearchView.tsx` (Smart Loop Agent Runner) | **Verified** |
| **DB Explorer** | `GET /api/v1/admin/database/overview` | Bearer Token | `DatabaseOverview` | `fetchDatabaseOverview()` | `DatabaseExplorerView.tsx` (Overview tab) | **Verified** |
| **DB Explorer** | `GET /api/v1/admin/database/tables` | Bearer Token, category? | `list[TableSummary]` | `fetchDatabaseTables()` | `DatabaseExplorerView.tsx` (Tables list tab) | **Verified** |
| **DB Explorer** | `GET /api/v1/admin/database/tables/{t}` | Bearer Token, table_name | `TableDetails` | `fetchTableDetails()` | `DatabaseExplorerView.tsx` (Table structure tab) | **Verified** |
| **DB Explorer** | `GET /api/v1/admin/database/tables/{t}/rows` | Bearer Token, limit, offset | `TableRowsResponse` | `fetchTableRows()` | `DatabaseExplorerView.tsx` (Paginated rows tab) | **Verified** |
| **DB Explorer** | `GET /api/v1/admin/database/migrations` | Bearer Token | `list[MigrationRevision]` | `fetchDatabaseMigrations()` | `DatabaseExplorerView.tsx` (Migrations history tab) | **Verified** |
| **DB Explorer** | `GET /api/v1/admin/database/relationships` | Bearer Token | `DatabaseRelationships` | `fetchDatabaseRelationships()` | `DatabaseExplorerView.tsx` (ER relationships tab) | **Verified** |

---

## 2. FastMCP Tool Contract vs Frontend Parity

All 12 FastMCP read-only tools and the 1 gated write tool (`export_video_clip`) are surfaced in two distinct frontend interfaces:
1. **MCP Configuration View (`McpConfigView.tsx`):**
   - Displays tool definitions, parameter schemas, read-only safety guarantees.
   - Provides ready-to-paste client configuration snippets for Claude Desktop, Cursor IDE, VS Code, and Antigravity.
2. **Shared Tool Execution Engine (`HybridSearchView.tsx` -> Tool Explorer Tab):**
   - Direct interactive invocation via `POST /api/v1/tools/execute`.
   - Form inputs generated from tool schemas with real parameter validation.
