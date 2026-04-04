import { Moon, Sun, Database, Trash2, Globe, Zap, Shield, Bell } from 'lucide-react';
import { useTheme } from '../ThemeProvider';

export function Settings() {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl text-gray-900 dark:text-[#F8FAFC] mb-2">Settings</h1>
          <p className="text-gray-600 dark:text-gray-400">
            Manage your preferences and system configuration
          </p>
        </div>

        <div className="space-y-6">
          {/* Appearance */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700">
            <div className="flex items-start gap-4 mb-4">
              {theme === 'light' ? (
                <Sun className="w-5 h-5 text-gray-600 dark:text-gray-400 mt-0.5" />
              ) : (
                <Moon className="w-5 h-5 text-gray-600 dark:text-gray-400 mt-0.5" />
              )}
              <div className="flex-1">
                <h3 className="text-lg text-gray-900 dark:text-[#F8FAFC] mb-1">Appearance</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  Customize the visual theme of the application
                </p>
                
                <div className="flex gap-3">
                  <button
                    onClick={() => theme === 'dark' && toggleTheme()}
                    className={`flex-1 px-4 py-3 rounded-xl border-2 transition-all ${
                      theme === 'light'
                        ? 'border-[#6366F1] bg-[#6366F1]/5 text-[#6366F1]'
                        : 'border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-[#6366F1]'
                    }`}
                  >
                    <Sun className="w-5 h-5 mx-auto mb-1" />
                    <span className="text-sm">Light</span>
                  </button>
                  <button
                    onClick={() => theme === 'light' && toggleTheme()}
                    className={`flex-1 px-4 py-3 rounded-xl border-2 transition-all ${
                      theme === 'dark'
                        ? 'border-[#6366F1] bg-[#6366F1]/5 text-[#6366F1]'
                        : 'border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-[#6366F1]'
                    }`}
                  >
                    <Moon className="w-5 h-5 mx-auto mb-1" />
                    <span className="text-sm">Dark</span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Language Settings */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700">
            <div className="flex items-start gap-4">
              <Globe className="w-5 h-5 text-gray-600 dark:text-gray-400 mt-0.5" />
              <div className="flex-1">
                <h3 className="text-lg text-gray-900 dark:text-[#F8FAFC] mb-1">Language Detection</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  Configure automatic language detection for ingested sources
                </p>
                
                <div className="space-y-3">
                  <SettingToggle
                    label="Auto-detect language"
                    description="Automatically identify the language of uploaded content"
                    enabled={true}
                  />
                  <SettingToggle
                    label="Multilingual search"
                    description="Enable cross-language semantic search"
                    enabled={true}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* RAG Settings */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700">
            <div className="flex items-start gap-4">
              <Zap className="w-5 h-5 text-gray-600 dark:text-gray-400 mt-0.5" />
              <div className="flex-1">
                <h3 className="text-lg text-gray-900 dark:text-[#F8FAFC] mb-1">RAG Configuration</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  Fine-tune retrieval and generation parameters
                </p>
                
                <div className="space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm text-gray-700 dark:text-gray-300">
                        Chunks per query
                      </label>
                      <span className="text-sm text-[#6366F1]">5</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="10"
                      defaultValue="5"
                      className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-[#6366F1]"
                    />
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm text-gray-700 dark:text-gray-300">
                        Similarity threshold
                      </label>
                      <span className="text-sm text-[#6366F1]">0.7</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      defaultValue="0.7"
                      className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-[#6366F1]"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Notifications */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700">
            <div className="flex items-start gap-4">
              <Bell className="w-5 h-5 text-gray-600 dark:text-gray-400 mt-0.5" />
              <div className="flex-1">
                <h3 className="text-lg text-gray-900 dark:text-[#F8FAFC] mb-1">Notifications</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  Manage notification preferences
                </p>
                
                <div className="space-y-3">
                  <SettingToggle
                    label="Ingestion complete"
                    description="Notify when source ingestion is completed"
                    enabled={true}
                  />
                  <SettingToggle
                    label="Processing errors"
                    description="Alert on failed ingestion or processing"
                    enabled={true}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Database */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700">
            <div className="flex items-start gap-4">
              <Database className="w-5 h-5 text-gray-600 dark:text-gray-400 mt-0.5" />
              <div className="flex-1">
                <h3 className="text-lg text-gray-900 dark:text-[#F8FAFC] mb-1">Vector Database</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  Manage your knowledge base storage
                </p>
                
                <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 mb-4">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-gray-500 dark:text-gray-400 mb-1">Total embeddings</p>
                      <p className="text-lg text-gray-900 dark:text-[#F8FAFC]">582</p>
                    </div>
                    <div>
                      <p className="text-gray-500 dark:text-gray-400 mb-1">Storage used</p>
                      <p className="text-lg text-gray-900 dark:text-[#F8FAFC]">24.3 MB</p>
                    </div>
                  </div>
                </div>

                <button className="w-full px-4 py-3 rounded-xl border-2 border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:border-[#6366F1] hover:text-[#6366F1] transition-all flex items-center justify-center gap-2">
                  <Database className="w-4 h-4" />
                  <span className="text-sm">Optimize Database</span>
                </button>
              </div>
            </div>
          </div>

          {/* Danger Zone */}
          <div className="p-6 rounded-2xl bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-900/30">
            <div className="flex items-start gap-4">
              <Shield className="w-5 h-5 text-red-600 dark:text-red-400 mt-0.5" />
              <div className="flex-1">
                <h3 className="text-lg text-red-900 dark:text-red-100 mb-1">Danger Zone</h3>
                <p className="text-sm text-red-700 dark:text-red-300 mb-4">
                  Irreversible actions that affect your entire knowledge base
                </p>
                
                <button className="px-4 py-3 rounded-xl bg-red-600 hover:bg-red-700 text-white transition-colors flex items-center gap-2">
                  <Trash2 className="w-4 h-4" />
                  <span className="text-sm">Clear All Data</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SettingToggle({ 
  label, 
  description, 
  enabled 
}: { 
  label: string; 
  description: string; 
  enabled: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex-1">
        <p className="text-sm text-gray-900 dark:text-gray-100 mb-0.5">{label}</p>
        <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
      </div>
      <button
        className={`relative w-11 h-6 rounded-full transition-colors ${
          enabled ? 'bg-[#6366F1]' : 'bg-gray-300 dark:bg-gray-700'
        }`}
      >
        <div
          className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
            enabled ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  );
}
