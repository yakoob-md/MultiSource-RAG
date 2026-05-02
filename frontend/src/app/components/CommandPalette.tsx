"use client";

import * as React from "react";
import {
  Search,
  Command as CommandIcon,
  Sun,
  Moon,
  Monitor,
  Home,
  Settings,
  User,
  Mail,
  Bell,
  Copy,
  Share2,
  RefreshCw,
  Trash2,
  Clock,
  Bookmark,
  HelpCircle,
  FileText,
  Zap,
  Palette,
  Globe,
  Lock,
  Volume2,
  Smartphone,
  Printer,
  Camera,
  Wrench as ToolIcon,
  Maximize,
  Info,
  GitBranch,
  Twitter,
  Play,
  Terminal,
  Smartphone as Phone,
  MessageSquare,
  Database,
  History,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useNavigate } from "react-router";
import { fetchConversations, Conversation } from "../api";

const { useState, useEffect, useRef, useCallback } = React;

type CommandCategory =
  | "Navigation"
  | "System"
  | "Utility"
  | "Application"
  | "Social"
  | "Media"
  | "Development"
  | "Settings"
  | "Tools"
  | "History";

type CommandSection = "favorites" | "recents" | "suggestions" | "all";

type CommandItem = {
  id: string;
  title: string;
  description: string;
  category: CommandCategory;
  section: CommandSection;
  icon?: React.ReactNode;
  action?: () => void;
  shortcut?: string;
  keywords?: string[];
  tags?: string[];
};

export function CommandPalette({ onSelectHistory }: { onSelectHistory?: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [activeCategory, setActiveCategory] = useState<CommandCategory | "All">(
    "All"
  );
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const navigate = useNavigate();

  const ref = useRef<HTMLDivElement>(null);
  const itemsRef = useRef<(HTMLDivElement | null)[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [showAIPrompt, setShowAIPrompt] = useState(false);
  const [aiPrompt, setAiPrompt] = useState("");

  useEffect(() => {
    if (open) {
      fetchConversations().then(setConversations).catch(() => {});
    }
  }, [open]);

  const navigateTo = useCallback((url: string) => {
    navigate(url);
    setOpen(false);
  }, [navigate]);

  const showNotification = useCallback(
    (message: string, type: "success" | "error" | "info" = "info") => {
      const notification = document.createElement("div");
      notification.className = `fixed bottom-4 right-4 z-[9999] rounded-lg px-4 py-3 shadow-lg transition-all duration-300 transform translate-y-0 opacity-0 ${
        type === "success"
          ? "bg-green-500"
          : type === "error"
          ? "bg-red-500"
          : "bg-blue-500"
      } text-white`;
      notification.textContent = message;
      document.body.appendChild(notification);
      setTimeout(() => {
        notification.style.opacity = "1";
      }, 10);
      setTimeout(() => {
        notification.style.opacity = "0";
        notification.style.transform = "translateY(20px)";
        setTimeout(() => {
          if (document.body.contains(notification)) {
            document.body.removeChild(notification);
          }
        }, 300);
      }, 3000);
    },
    []
  );

  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch((err) => {
        showNotification(`Error: ${err.message}`, "error");
      });
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
    setOpen(false);
  }, [showNotification]);

  const allCommandItems: CommandItem[] = [
    {
      id: "nav-home",
      title: "InteleX Assistant",
      description: "Start a new conversation",
      category: "Navigation",
      section: "all",
      icon: <MessageSquare className="h-3 w-3" />,
      action: () => {
          window.dispatchEvent(new CustomEvent('new-chat'));
          navigateTo("/app");
      },
      shortcut: "Alt+N",
      keywords: ["home", "main", "chat", "ask", "new"],
    },
    {
        id: "nav-legal",
        title: "Legal AI",
        description: "Dual-mode legal search & reasoning",
        category: "Navigation",
        section: "favorites",
        icon: <Lock className="h-3 w-3" />,
        action: () => navigateTo("/app/legal"),
        shortcut: "Alt+L",
        keywords: ["legal", "law", "case", "court"],
    },
    {
        id: "nav-sources",
        title: "Resource Manager",
        description: "View knowledge statistics & upload files",
        category: "Navigation",
        section: "favorites",
        icon: <Database className="h-3 w-3" />,
        action: () => {
            window.dispatchEvent(new CustomEvent('open-sources'));
            setOpen(false);
        },
        shortcut: "Alt+R",
        keywords: ["sources", "files", "pdf", "youtube", "web", "kb", "knowledge"],
    },
    {
        id: "nav-history",
        title: "Chat History",
        description: "Open your previous conversations",
        category: "Navigation",
        section: "favorites",
        icon: <History className="h-3 w-3" />,
        action: () => {
            window.dispatchEvent(new CustomEvent('open-history'));
            setOpen(false);
        },
        shortcut: "Alt+H",
    },
    {
      id: "nav-settings",
      title: "Settings",
      description: "Configure InteleX preferences",
      category: "Settings",
      section: "all",
      icon: <Settings className="h-3 w-3" />,
      action: () => navigateTo("/app/settings"),
      shortcut: "Alt+S",
    },
    {
        id: "toggle-fullscreen",
        title: "Toggle Fullscreen",
        description: "Maximize your focus",
        category: "System",
        section: "all",
        icon: <Maximize className="h-3 w-3" />,
        action: toggleFullscreen,
        shortcut: "F11",
    },
    ...conversations.map(conv => ({
        id: `history-${conv.id}`,
        title: conv.title,
        description: "Previous conversation",
        category: "History" as CommandCategory,
        section: "all" as CommandSection,
        icon: <Clock className="h-3 w-3" />,
        action: () => {
            window.dispatchEvent(new CustomEvent('load-conversation', { detail: { id: conv.id } }));
            setOpen(false);
            navigateTo("/app");
        }
    }))
  ];

  const getFilteredCommands = useCallback(() => {
    const searchLower = searchTerm.toLowerCase();
    return allCommandItems.filter((cmd) => {
      if (activeCategory !== "All" && cmd.category !== activeCategory) return false;
      if (searchLower) {
        return cmd.title.toLowerCase().includes(searchLower) || 
               cmd.description.toLowerCase().includes(searchLower) ||
               cmd.keywords?.some(k => k.toLowerCase().includes(searchLower));
      }
      return true;
    });
  }, [searchTerm, activeCategory, allCommandItems]);

  const commandItemsList = getFilteredCommands();
  const categories = ["Navigation", "History", "System", "Settings", "Tools"];

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
        setSearchTerm("");
      }
      if (open) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setSelectedIndex(prev => Math.min(prev + 1, commandItemsList.length - 1));
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          setSelectedIndex(prev => Math.max(prev - 1, 0));
        } else if (e.key === "Enter") {
          e.preventDefault();
          const cmd = commandItemsList[selectedIndex];
          if (cmd?.action) cmd.action();
        } else if (e.key === "Escape") {
          setOpen(false);
        }
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [open, selectedIndex, commandItemsList]);

  useEffect(() => {
    if (open && itemsRef.current[selectedIndex]) {
      itemsRef.current[selectedIndex]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [selectedIndex, open]);

  return (
    <>
      {!open && (
        <motion.button
          onClick={() => setOpen(true)}
          className="fixed right-6 top-6 z-[100] flex h-10 w-10 items-center justify-center rounded-xl bg-white/5 text-white/40 shadow-2xl backdrop-blur-xl border border-white/10 hover:bg-white/10 hover:text-white transition-all"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <CommandIcon className="h-5 w-5" />
        </motion.button>
      )}

      <AnimatePresence>
        {open && (
          <div className="fixed inset-0 z-[1000] flex items-start justify-center pt-[15vh] px-4 bg-black/40 backdrop-blur-sm">
            <motion.div
              ref={ref}
              className="relative w-full max-w-2xl overflow-hidden rounded-2xl bg-[#1e1e2e] text-white shadow-2xl border border-white/10"
              initial={{ opacity: 0, scale: 0.95, y: -20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: -20 }}
            >
              <div className="flex items-center border-b border-white/5 px-4">
                <Search className="mr-3 h-4 w-4 shrink-0 text-white/40" />
                <input
                  className="h-14 w-full border-0 bg-transparent text-sm placeholder:text-white/20 focus:outline-none"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Search commands or chat history..."
                  autoFocus
                />
                <kbd className="hidden sm:inline-flex h-5 select-none items-center gap-1 rounded border border-white/10 bg-white/5 px-1.5 font-mono text-[10px] font-medium text-white/40">
                  ESC
                </kbd>
              </div>

              <div className="flex items-center gap-2 px-4 py-2 border-b border-white/5 overflow-x-auto scrollbar-hide no-scrollbar">
                <button
                  onClick={() => setActiveCategory("All")}
                  className={`flex items-center gap-1 rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-wider transition-colors ${
                    activeCategory === "All" ? "bg-[#6366F1] text-white" : "bg-white/5 text-white/40 hover:bg-white/10"
                  }`}
                >
                  All
                </button>
                {categories.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setActiveCategory(cat as CommandCategory)}
                    className={`flex items-center gap-1 rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-wider transition-colors ${
                      activeCategory === cat ? "bg-[#6366F1] text-white" : "bg-white/5 text-white/40 hover:bg-white/10"
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>

              <div className="max-h-[50vh] overflow-y-auto py-2 no-scrollbar">
                {commandItemsList.length === 0 ? (
                  <div className="py-12 text-center text-white/20 text-sm">No results found</div>
                ) : (
                  commandItemsList.map((item, idx) => (
                    <div
                      key={item.id}
                      ref={(el) => {
                        if (itemsRef.current) {
                          itemsRef.current[idx] = el;
                        }
                      }}
                      className={`mx-2 flex cursor-pointer items-center justify-between rounded-xl px-3 py-3 transition-all ${
                        selectedIndex === idx ? "bg-white/10 text-white scale-[1.01]" : "text-white/60 hover:bg-white/5"
                      }`}
                      onClick={() => item.action?.()}
                      onMouseEnter={() => setSelectedIndex(idx)}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`flex h-8 w-8 items-center justify-center rounded-lg border ${
                          selectedIndex === idx ? "border-white/20 bg-white/10" : "border-white/5 bg-white/5"
                        }`}>
                          {item.icon}
                        </div>
                        <div className="flex flex-col">
                          <span className="text-sm font-medium">{item.title}</span>
                          <span className="text-[10px] text-white/30 truncate max-w-[300px]">{item.description}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-[10px] font-bold uppercase tracking-widest text-white/20">{item.category}</span>
                        {item.shortcut && (
                          <kbd className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-white/40 font-mono">
                            {item.shortcut}
                          </kbd>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div className="flex items-center justify-between border-t border-white/5 p-4 bg-white/[0.02]">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-1.5">
                    <kbd className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-white/40">↑↓</kbd>
                    <span className="text-[10px] text-white/20 font-bold uppercase tracking-widest">Navigate</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <kbd className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-white/40">↵</kbd>
                    <span className="text-[10px] text-white/20 font-bold uppercase tracking-widest">Select</span>
                  </div>
                </div>
                <span className="text-[10px] text-white/20 font-bold uppercase tracking-widest">InteleX Palette</span>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
