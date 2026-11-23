import { useEffect, useState } from "react";

export interface CommandItem {
  id: string;
  title: string;
  subtitle: string;
  category: "Navigation" | "Action";
  shortcut?: string;
  onSelect: () => void;
}

interface CommandPaletteModalProps {
  isOpen: boolean;
  onClose: () => void;
  commands: CommandItem[];
}

export function CommandPaletteModal({ isOpen, onClose, commands }: CommandPaletteModalProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  const filtered = commands.filter(
    (cmd) =>
      cmd.title.toLowerCase().includes(query.toLowerCase()) ||
      cmd.subtitle.toLowerCase().includes(query.toLowerCase()) ||
      cmd.category.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (!isOpen) return;
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (filtered.length ? (prev + 1) % filtered.length : 0));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) =>
          filtered.length ? (prev - 1 + filtered.length) % filtered.length : 0
        );
      } else if (e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault();
        filtered[selectedIndex].onSelect();
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, filtered, selectedIndex, onClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command Palette"
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-100"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl bg-[#111827] border border-[#243149] rounded-panel shadow-2xl overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center px-4 py-3 border-b border-[#243149] bg-[#0B1019]">
          <span className="text-slate-400 font-mono text-xs mr-3">Ctrl+K</span>
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or search views..."
            className="w-full bg-transparent text-sm text-[#F5F7FB] placeholder-slate-500 focus:outline-none font-sans"
          />
          <button
            type="button"
            onClick={onClose}
            className="text-xs font-mono text-slate-400 hover:text-slate-200 px-2 py-0.5 rounded bg-[#172235]"
          >
            ESC
          </button>
        </div>

        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filtered.length === 0 ? (
            <div className="px-4 py-6 text-center text-xs text-slate-400 font-mono">
              No matching commands found.
            </div>
          ) : (
            filtered.map((item, index) => {
              const isSelected = index === selectedIndex;
              return (
                <div
                  key={item.id}
                  onClick={() => {
                    item.onSelect();
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={`flex items-center justify-between px-3 py-2 rounded-control text-xs cursor-pointer transition-colors ${
                    isSelected
                      ? "bg-[#172235] text-[#F5F7FB] border border-[#9B8CFF]/40"
                      : "text-slate-300 hover:bg-[#172235]/60"
                  }`}
                >
                  <div className="flex flex-col min-w-0 pr-2">
                    <span className="font-medium truncate text-[#F5F7FB]">{item.title}</span>
                    <span className="text-[11px] text-slate-400 truncate">{item.subtitle}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#0B1019] text-slate-400 border border-[#243149]">
                      {item.category}
                    </span>
                    {item.shortcut && (
                      <span className="text-[10px] font-mono text-[#9B8CFF]">
                        {item.shortcut}
                      </span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div className="px-4 py-2 bg-[#0B1019] border-t border-[#243149] flex items-center justify-between text-[11px] text-slate-400 font-mono">
          <span>↑↓ to navigate</span>
          <span>↵ to select</span>
        </div>
      </div>
    </div>
  );
}
