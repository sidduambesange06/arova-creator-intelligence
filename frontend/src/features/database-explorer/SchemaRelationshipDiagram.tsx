import { useMemo, useRef, useState } from "react";
import type { DatabaseRelationships } from "../../services/api";

interface SchemaRelationshipDiagramProps {
  data: DatabaseRelationships;
  onInspectTable: (tableName: string, tab: "structure" | "rows") => void;
}

interface PositionedNode {
  table: DatabaseRelationships["tables"][number];
  x: number;
  y: number;
  w: number;
  h: number;
  fkCols: Set<string>;
}

const NODE_W = 228;
const NODE_H = 112;
const COL_GAP = 104;
const ROW_GAP = 26;
const PAD = 36;

export function SchemaRelationshipDiagram({
  data,
  onInspectTable,
}: SchemaRelationshipDiagramProps) {
  const [viewMode, setViewMode] = useState<"diagram" | "list">("diagram");
  const [showAllCategories, setShowAllCategories] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(
    null
  );
  const containerRef = useRef<HTMLDivElement | null>(null);

  const visibleTables = useMemo(
    () =>
      showAllCategories
        ? data.tables
        : data.tables.filter((t) => t.category === "application"),
    [data.tables, showAllCategories]
  );

  const visibleIdSet = useMemo(() => new Set(visibleTables.map((t) => t.id)), [visibleTables]);

  const visibleEdges = useMemo(
    () =>
      data.relationships.filter(
        (r) => visibleIdSet.has(r.source_table) && visibleIdSet.has(r.target_table)
      ),
    [data.relationships, visibleIdSet]
  );

  const inferredCount = useMemo(
    () => visibleEdges.filter((e) => Boolean(e.is_inferred)).length,
    [visibleEdges]
  );

  // Deterministic topological layered layout (parents left -> dependents right)
  const layout = useMemo(() => {
    const fkColsByTable = new Map<string, Set<string>>();
    const connectedIds = new Set<string>();
    const parentsOf = new Map<string, Set<string>>();

    for (const t of visibleTables) {
      fkColsByTable.set(t.id, new Set());
      parentsOf.set(t.id, new Set());
    }
    for (const edge of visibleEdges) {
      connectedIds.add(edge.source_table);
      connectedIds.add(edge.target_table);
      const colSet = fkColsByTable.get(edge.source_table);
      if (colSet) {
        for (const c of edge.source_columns) colSet.add(c);
      }
      if (edge.source_table !== edge.target_table) {
        parentsOf.get(edge.source_table)?.add(edge.target_table);
      }
    }

    const depth = new Map<string, number>();
    const computeDepth = (id: string, visiting: Set<string>): number => {
      if (depth.has(id)) return depth.get(id)!;
      if (visiting.has(id)) return 0;
      visiting.add(id);
      const parents = parentsOf.get(id) ?? new Set();
      let d = 0;
      for (const p of parents) {
        d = Math.max(d, computeDepth(p, visiting) + 1);
      }
      visiting.delete(id);
      depth.set(id, d);
      return d;
    };

    const connectedTables = visibleTables.filter((t) => connectedIds.has(t.id));
    const standaloneTables = visibleTables.filter((t) => !connectedIds.has(t.id));

    const layers = new Map<number, DatabaseRelationships["tables"]>();
    for (const t of connectedTables) {
      const d = computeDepth(t.id, new Set());
      const bucket = layers.get(d) ?? [];
      bucket.push(t);
      layers.set(d, bucket);
    }

    const nodes: PositionedNode[] = [];
    const nodeMap = new Map<string, PositionedNode>();
    let maxConnectedBottom = PAD;
    let maxRight = PAD + NODE_W;

    const sortedLayers = Array.from(layers.keys()).sort((a, b) => a - b);
    for (const layerIdx of sortedLayers) {
      const bucket = (layers.get(layerIdx) ?? []).slice().sort((a, b) => a.id.localeCompare(b.id));
      bucket.forEach((table, rowIdx) => {
        const x = PAD + layerIdx * (NODE_W + COL_GAP);
        const y = PAD + rowIdx * (NODE_H + ROW_GAP);
        const node: PositionedNode = {
          table,
          x,
          y,
          w: NODE_W,
          h: NODE_H,
          fkCols: fkColsByTable.get(table.id) ?? new Set(),
        };
        nodes.push(node);
        nodeMap.set(table.id, node);
        maxConnectedBottom = Math.max(maxConnectedBottom, y + NODE_H);
        maxRight = Math.max(maxRight, x + NODE_W);
      });
    }

    // Place standalone tables neatly in a bottom grid band
    const standaloneCols = Math.max(3, sortedLayers.length || 3);
    const standaloneStartY = connectedTables.length > 0 ? maxConnectedBottom + 56 : PAD;
    let maxBottom = maxConnectedBottom;
    standaloneTables
      .slice()
      .sort((a, b) => a.id.localeCompare(b.id))
      .forEach((table, idx) => {
        const col = idx % standaloneCols;
        const row = Math.floor(idx / standaloneCols);
        const x = PAD + col * (NODE_W + 44);
        const y = standaloneStartY + row * (NODE_H + ROW_GAP);
        const node: PositionedNode = {
          table,
          x,
          y,
          w: NODE_W,
          h: NODE_H,
          fkCols: fkColsByTable.get(table.id) ?? new Set(),
        };
        nodes.push(node);
        nodeMap.set(table.id, node);
        maxBottom = Math.max(maxBottom, y + NODE_H);
        maxRight = Math.max(maxRight, x + NODE_W);
      });

    return {
      nodes,
      nodeMap,
      width: Math.max(820, maxRight + PAD),
      height: Math.max(460, maxBottom + PAD),
      standaloneStartY: standaloneTables.length > 0 && connectedTables.length > 0 ? standaloneStartY - 24 : null,
    };
  }, [visibleTables, visibleEdges]);

  const handleFitToView = () => {
    const el = containerRef.current;
    if (!el) {
      setZoom(1);
      setPan({ x: 0, y: 0 });
      return;
    }
    const cw = Math.max(320, el.clientWidth - 24);
    const ch = Math.max(320, el.clientHeight - 24);
    const scale = Math.min(1.1, Math.max(0.35, Math.min(cw / layout.width, ch / layout.height)));
    setZoom(Number(scale.toFixed(2)));
    setPan({ x: 0, y: 0 });
  };

  const handleResetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setSelectedNodeId(null);
  };

  const selectedNode = selectedNodeId ? layout.nodeMap.get(selectedNodeId) ?? null : null;
  const selectedOutgoing = selectedNodeId
    ? visibleEdges.filter((e) => e.source_table === selectedNodeId)
    : [];
  const selectedIncoming = selectedNodeId
    ? visibleEdges.filter((e) => e.target_table === selectedNodeId)
    : [];

  if (visibleTables.length === 0) {
    return (
      <div className="p-8 rounded-xl border border-[#243149] bg-[#111827] text-center space-y-2">
        <p className="text-sm font-medium text-slate-200">No tables available for relationship mapping</p>
        <p className="text-xs text-slate-400">
          This database has no tables matching the active category filter.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="p-4 rounded-xl border border-[#243149] bg-[#111827] flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-[#F5F7FB]">
            Entity-Relationship Schema Visualization
          </h3>
          <p className="text-xs text-[#A2AEC0] mt-0.5">
            {visibleTables.length} tables · {visibleEdges.length} actual SQLite foreign keys
            {inferredCount > 0 ? ` · ${inferredCount} inferred` : " (0 inferred)"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-[#243149] bg-[#0B1019] p-0.5">
            <button
              type="button"
              onClick={() => setViewMode("diagram")}
              aria-pressed={viewMode === "diagram"}
              className={`px-2.5 py-1 text-xs font-mono rounded-md transition ${
                viewMode === "diagram"
                  ? "bg-[#9B8CFF] text-[#080B12] font-semibold"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              Visual Diagram
            </button>
            <button
              type="button"
              onClick={() => setViewMode("list")}
              aria-pressed={viewMode === "list"}
              className={`px-2.5 py-1 text-xs font-mono rounded-md transition ${
                viewMode === "list"
                  ? "bg-[#9B8CFF] text-[#080B12] font-semibold"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              Accessible List View
            </button>
          </div>

          <button
            type="button"
            onClick={() => setShowAllCategories((v) => !v)}
            className="px-2.5 py-1 text-xs font-mono rounded-lg border border-[#243149] bg-[#0B1019] text-slate-300 hover:text-white"
          >
            {showAllCategories ? "Showing: All Tables" : "Showing: App Tables"}
          </button>

          {viewMode === "diagram" && (
            <div className="inline-flex items-center gap-1 rounded-lg border border-[#243149] bg-[#0B1019] px-1.5 py-0.5 font-mono text-xs">
              <button
                type="button"
                aria-label="Zoom out"
                onClick={() => setZoom((z) => Math.max(0.35, Number((z - 0.15).toFixed(2))))}
                className="px-2 py-0.5 text-slate-300 hover:text-white"
              >
                -
              </button>
              <span className="text-[11px] text-slate-400 w-11 text-center">
                {Math.round(zoom * 100)}%
              </span>
              <button
                type="button"
                aria-label="Zoom in"
                onClick={() => setZoom((z) => Math.min(2, Number((z + 0.15).toFixed(2))))}
                className="px-2 py-0.5 text-slate-300 hover:text-white"
              >
                +
              </button>
              <button
                type="button"
                onClick={handleFitToView}
                className="px-2 py-0.5 text-[#51DCC8] hover:text-white border-l border-[#243149]"
              >
                Fit
              </button>
              <button
                type="button"
                onClick={handleResetView}
                className="px-2 py-0.5 text-slate-400 hover:text-white border-l border-[#243149]"
              >
                Reset
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 px-1 text-[11px] font-mono text-slate-400">
        <span className="inline-flex items-center gap-1.5">
          <span className="w-5 h-0.5 bg-[#51DCC8] inline-block" />
          Actual SQLite Foreign Key (Child → Parent)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="px-1 rounded bg-amber-950 text-amber-300 border border-amber-800 text-[9px]">
            PK
          </span>
          Primary Key
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="px-1 rounded bg-emerald-950 text-emerald-300 border border-emerald-800 text-[9px]">
            FK
          </span>
          Foreign Key Column
        </span>
        <span className="text-slate-500">Click any table node to highlight edges · Drag canvas to pan</span>
      </div>

      {viewMode === "diagram" ? (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
          {/* Interactive SVG Schema Canvas */}
          <div
            ref={containerRef}
            onMouseDown={(e) => {
              if ((e.target as HTMLElement).closest("[data-er-node]")) return;
              dragRef.current = { startX: e.clientX, startY: e.clientY, origX: pan.x, origY: pan.y };
            }}
            onMouseMove={(e) => {
              if (!dragRef.current) return;
              setPan({
                x: dragRef.current.origX + (e.clientX - dragRef.current.startX),
                y: dragRef.current.origY + (e.clientY - dragRef.current.startY),
              });
            }}
            onMouseUp={() => {
              dragRef.current = null;
            }}
            onMouseLeave={() => {
              dragRef.current = null;
            }}
            className="xl:col-span-3 h-[560px] rounded-xl border border-[#243149] bg-[#080B12] overflow-auto relative cursor-grab active:cursor-grabbing select-none"
            data-testid="er-diagram-canvas"
          >
            <svg
              role="img"
              aria-label={`Database Entity-Relationship Schema Diagram with ${visibleTables.length} tables and ${visibleEdges.length} foreign keys`}
              width={Math.round(layout.width * zoom)}
              height={Math.round(layout.height * zoom)}
              viewBox={`0 0 ${layout.width} ${layout.height}`}
              className="block"
            >
              <defs>
                <marker
                  id="er-arrow-default"
                  viewBox="0 0 10 10"
                  refX="9"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#51DCC8" fillOpacity="0.65" />
                </marker>
                <marker
                  id="er-arrow-active"
                  viewBox="0 0 10 10"
                  refX="9"
                  refY="5"
                  markerWidth="7"
                  markerHeight="7"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#9B8CFF" />
                </marker>
              </defs>

              <g transform={`translate(${pan.x / zoom}, ${pan.y / zoom})`}>
                {layout.standaloneStartY !== null && (
                  <g>
                    <line
                      x1={PAD}
                      y1={layout.standaloneStartY}
                      x2={layout.width - PAD}
                      y2={layout.standaloneStartY}
                      stroke="#243149"
                      strokeDasharray="6 6"
                    />
                    <text
                      x={PAD}
                      y={layout.standaloneStartY - 6}
                      fill="#64748B"
                      fontSize="10"
                      fontFamily="monospace"
                    >
                      STANDALONE TABLES (NO FOREIGN KEYS)
                    </text>
                  </g>
                )}

                {/* Foreign-Key Edges */}
                {visibleEdges.map((edge) => {
                  const src = layout.nodeMap.get(edge.source_table);
                  const dst = layout.nodeMap.get(edge.target_table);
                  if (!src || !dst) return null;

                  const isRelated =
                    selectedNodeId !== null &&
                    (edge.source_table === selectedNodeId || edge.target_table === selectedNodeId);
                  const isDimmed = selectedNodeId !== null && !isRelated;

                  const srcOnRight = src.x >= dst.x;
                  const x1 = srcOnRight ? src.x : src.x + src.w;
                  const y1 = src.y + src.h / 2;
                  const x2 = srcOnRight ? dst.x + dst.w : dst.x;
                  const y2 = dst.y + dst.h / 2;
                  const dx = Math.max(48, Math.abs(x2 - x1) * 0.45);
                  const c1x = srcOnRight ? x1 - dx : x1 + dx;
                  const c2x = srcOnRight ? x2 + dx : x2 - dx;
                  const pathD = `M ${x1} ${y1} C ${c1x} ${y1}, ${c2x} ${y2}, ${x2} ${y2}`;
                  const midX = (x1 + x2) / 2;
                  const midY = (y1 + y2) / 2;

                  return (
                    <g key={edge.id} opacity={isDimmed ? 0.18 : 1}>
                      <path
                        d={pathD}
                        fill="none"
                        stroke={isRelated ? "#9B8CFF" : "#51DCC8"}
                        strokeWidth={isRelated ? 2.4 : 1.5}
                        strokeOpacity={isRelated ? 1 : 0.6}
                        markerEnd={isRelated ? "url(#er-arrow-active)" : "url(#er-arrow-default)"}
                      >
                        <title>
                          {edge.source_table}.{edge.source_columns.join(",")} → {edge.target_table}.
                          {edge.target_columns.join(",")} (Actual SQLite FK)
                        </title>
                      </path>
                      {isRelated && (
                        <g>
                          <rect
                            x={midX - 66}
                            y={midY - 10}
                            width={132}
                            height={18}
                            rx={4}
                            fill="#0B1019"
                            stroke="#9B8CFF"
                            strokeWidth={1}
                          />
                          <text
                            x={midX}
                            y={midY + 3}
                            textAnchor="middle"
                            fill="#F5F7FB"
                            fontSize="9"
                            fontFamily="monospace"
                          >
                            {edge.source_columns.join(",")} → {edge.target_columns.join(",")}
                          </text>
                        </g>
                      )}
                    </g>
                  );
                })}

                {/* Table Nodes */}
                {layout.nodes.map((node) => {
                  const isSelected = selectedNodeId === node.table.id;
                  const isConnectedToSelected =
                    selectedNodeId !== null &&
                    visibleEdges.some(
                      (e) =>
                        (e.source_table === selectedNodeId && e.target_table === node.table.id) ||
                        (e.target_table === selectedNodeId && e.source_table === node.table.id)
                    );
                  const dimmed = selectedNodeId !== null && !isSelected && !isConnectedToSelected;

                  return (
                    <g
                      key={node.table.id}
                      data-er-node={node.table.id}
                      role="button"
                      tabIndex={0}
                      aria-label={`Table ${node.table.id}, ${node.table.row_count} rows, ${node.table.column_count} columns`}
                      onClick={() =>
                        setSelectedNodeId((prev) => (prev === node.table.id ? null : node.table.id))
                      }
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelectedNodeId((prev) => (prev === node.table.id ? null : node.table.id));
                        }
                      }}
                      transform={`translate(${node.x}, ${node.y})`}
                      opacity={dimmed ? 0.32 : 1}
                      className="cursor-pointer focus:outline-none"
                    >
                      <rect
                        width={node.w}
                        height={node.h}
                        rx={10}
                        fill={isSelected ? "#172235" : "#0F1726"}
                        stroke={isSelected ? "#9B8CFF" : isConnectedToSelected ? "#51DCC8" : "#243149"}
                        strokeWidth={isSelected ? 2 : 1.25}
                      />
                      <rect
                        width={node.w}
                        height={28}
                        rx={10}
                        fill={isSelected ? "#232F48" : "#152033"}
                      />
                      <text
                        x={10}
                        y={18}
                        fill="#F5F7FB"
                        fontSize="11"
                        fontWeight="600"
                        fontFamily="monospace"
                      >
                        {node.table.id.length > 20 ? `${node.table.id.slice(0, 19)}…` : node.table.id}
                      </text>
                      <text
                        x={node.w - 10}
                        y={18}
                        textAnchor="end"
                        fill="#51DCC8"
                        fontSize="10"
                        fontFamily="monospace"
                      >
                        {node.table.row_count}r
                      </text>

                      {node.table.columns.slice(0, 4).map((col, cIdx) => {
                        const isFk = node.fkCols.has(col.name);
                        const badge = col.primary_key ? "PK" : isFk ? "FK" : "";
                        return (
                          <g key={col.name} transform={`translate(10, ${44 + cIdx * 15})`}>
                            <text fill={col.primary_key ? "#F4BF69" : isFk ? "#51DCC8" : "#A2AEC0"} fontSize="10" fontFamily="monospace">
                              {col.name.length > 22 ? `${col.name.slice(0, 21)}…` : col.name}
                            </text>
                            {badge && (
                              <text
                                x={node.w - 20}
                                textAnchor="end"
                                fill={col.primary_key ? "#F4BF69" : "#51DCC8"}
                                fontSize="9"
                                fontWeight="700"
                                fontFamily="monospace"
                              >
                                {badge}
                              </text>
                            )}
                          </g>
                        );
                      })}
                      {node.table.columns.length > 4 && (
                        <text
                          x={10}
                          y={node.h - 6}
                          fill="#64748B"
                          fontSize="9"
                          fontFamily="monospace"
                        >
                          +{node.table.columns.length - 4} more columns
                        </text>
                      )}
                    </g>
                  );
                })}
              </g>
            </svg>
          </div>

          {/* Right Inspector Panel */}
          <div className="p-4 rounded-xl border border-[#243149] bg-[#111827] space-y-4 h-[560px] overflow-y-auto">
            {selectedNode ? (
              <>
                <div className="space-y-1 border-b border-[#243149] pb-3">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-sm font-mono font-bold text-[#F5F7FB] truncate">
                      {selectedNode.table.id}
                    </h4>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#0B1019] border border-[#243149] text-[#51DCC8]">
                      {selectedNode.table.row_count} rows
                    </span>
                  </div>
                  <p className="text-[11px] font-mono text-slate-400">
                    {selectedNode.table.column_count} columns · category: {selectedNode.table.category}
                  </p>
                  <div className="flex gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => onInspectTable(selectedNode.table.id, "structure")}
                      className="flex-1 px-2.5 py-1.5 text-xs font-mono rounded bg-[#172235] hover:bg-[#232f48] text-slate-200 border border-[#243149]"
                    >
                      Structure
                    </button>
                    <button
                      type="button"
                      onClick={() => onInspectTable(selectedNode.table.id, "rows")}
                      className="flex-1 px-2.5 py-1.5 text-xs font-mono rounded bg-[#51DCC8]/15 hover:bg-[#51DCC8]/25 text-[#51DCC8] border border-[#51DCC8]/40"
                    >
                      Browse Rows
                    </button>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <h5 className="text-[10px] font-mono uppercase text-slate-400">
                    Outgoing Foreign Keys ({selectedOutgoing.length})
                  </h5>
                  {selectedOutgoing.length === 0 ? (
                    <p className="text-xs text-slate-500 font-mono">None</p>
                  ) : (
                    <ul className="space-y-1.5 text-xs font-mono">
                      {selectedOutgoing.map((fk) => (
                        <li
                          key={fk.id}
                          className="p-2 rounded bg-[#0B1019] border border-[#243149] text-[#51DCC8]"
                        >
                          {fk.source_columns.join(", ")} →{" "}
                          <button
                            type="button"
                            onClick={() => setSelectedNodeId(fk.target_table)}
                            className="underline hover:text-white"
                          >
                            {fk.target_table}
                          </button>{" "}
                          ({fk.target_columns.join(", ")})
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="space-y-1.5">
                  <h5 className="text-[10px] font-mono uppercase text-slate-400">
                    Referenced By ({selectedIncoming.length})
                  </h5>
                  {selectedIncoming.length === 0 ? (
                    <p className="text-xs text-slate-500 font-mono">None</p>
                  ) : (
                    <ul className="space-y-1.5 text-xs font-mono">
                      {selectedIncoming.map((fk) => (
                        <li
                          key={fk.id}
                          className="p-2 rounded bg-[#0B1019] border border-[#243149] text-[#9B8CFF]"
                        >
                          <button
                            type="button"
                            onClick={() => setSelectedNodeId(fk.source_table)}
                            className="underline hover:text-white"
                          >
                            {fk.source_table}
                          </button>{" "}
                          ({fk.source_columns.join(", ")})
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="space-y-1.5">
                  <h5 className="text-[10px] font-mono uppercase text-slate-400">
                    All Columns ({selectedNode.table.columns.length})
                  </h5>
                  <ul className="space-y-1 text-[11px] font-mono">
                    {selectedNode.table.columns.map((c) => (
                      <li
                        key={c.name}
                        className="flex items-center justify-between px-2 py-1 rounded bg-[#0B1019]"
                      >
                        <span className="text-slate-200 truncate">{c.name}</span>
                        <span className="text-[10px] text-slate-400 shrink-0 ml-2">
                          {c.primary_key ? "PK · " : ""}
                          {c.type}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center space-y-2 px-3">
                <p className="text-xs font-semibold text-slate-200">Select a Table Node</p>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Click any table box in the SVG diagram to highlight its incoming and outgoing
                  SQLite foreign-key edges and inspect its columns.
                </p>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Accessible Table / List Alternative */
        <div className="rounded-xl border border-[#243149] bg-[#111827] overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300 font-mono">
            <thead className="bg-[#0B1019] text-slate-400 uppercase text-[10px] border-b border-[#243149]">
              <tr>
                <th className="px-4 py-3">Table</th>
                <th className="px-4 py-3">Rows</th>
                <th className="px-4 py-3">Primary Keys</th>
                <th className="px-4 py-3">Actual SQLite Foreign Keys (Child → Parent)</th>
                <th className="px-4 py-3 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#243149]">
              {visibleTables.map((t) => {
                const outgoing = visibleEdges.filter((r) => r.source_table === t.id);
                const pks = t.columns.filter((c) => c.primary_key).map((c) => c.name);
                return (
                  <tr key={t.id} className="hover:bg-[#172235]/50">
                    <td className="px-4 py-3 font-semibold text-[#F5F7FB]">{t.id}</td>
                    <td className="px-4 py-3">{t.row_count}</td>
                    <td className="px-4 py-3 text-amber-300">{pks.join(", ") || "None"}</td>
                    <td className="px-4 py-3">
                      {outgoing.length === 0 ? (
                        <span className="text-slate-500">None</span>
                      ) : (
                        <div className="space-y-0.5">
                          {outgoing.map((fk) => (
                            <div key={fk.id} className="text-[#51DCC8]">
                              {fk.source_columns.join(", ")} → {fk.target_table} (
                              {fk.target_columns.join(", ")})
                            </div>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => onInspectTable(t.id, "structure")}
                        className="px-2 py-1 rounded bg-[#172235] hover:bg-[#232f48] text-slate-200"
                      >
                        Structure
                      </button>
                      <button
                        type="button"
                        onClick={() => onInspectTable(t.id, "rows")}
                        className="px-2 py-1 rounded bg-[#51DCC8]/15 hover:bg-[#51DCC8]/25 text-[#51DCC8]"
                      >
                        Rows
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
