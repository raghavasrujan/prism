'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { BookOpen, Code, Globe, Lightbulb, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';
import type { Conversation, CustomTool, McpServer, ProviderModel } from '@/lib/types';
import { PageHamburger } from '@/components/layout/page-hamburger';
import { Logo } from '@/components/layout/logo';
import { ChatComposer } from '@/components/chat/chat-composer';

const EASE_OUT = [0.23, 1, 0.32, 1] as const;

const SUGGESTIONS = [
  { label: 'Learn', icon: BookOpen },
  { label: 'Build', icon: Code },
  { label: 'Get advice', icon: Lightbulb },
  { label: 'Generate image', icon: Sparkles },
  { label: 'Research', icon: Globe },
];

export default function NewChatPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const [modelId, setModelId] = useState('');
  const [enabledToolIds, setEnabledToolIds] = useState<Set<string>>(new Set());
  const [enabledMcpIds, setEnabledMcpIds] = useState<Set<string>>(new Set());
  const [prefill, setPrefill] = useState<string | undefined>(undefined);
  const creating = useRef(false);

  const models = useQuery<ProviderModel[]>({ queryKey: ['models'], queryFn: () => api('/models') });
  const tools = useQuery<CustomTool[]>({ queryKey: ['tools'], queryFn: () => api('/tools') });
  const mcp = useQuery<McpServer[]>({ queryKey: ['mcp'], queryFn: () => api('/mcp') });

  const activeModels = (models.data || []).filter((m) => m.is_active);
  const activeTools = (tools.data || []).filter((t) => t.is_active);
  const activeMcp = (mcp.data || []).filter((s) => s.is_active);

  useEffect(() => {
    if (!modelId && activeModels.length > 0) setModelId(activeModels[0].id);
  }, [activeModels, modelId]);

  useEffect(() => {
    if (activeTools.length > 0 && enabledToolIds.size === 0) {
      setEnabledToolIds(new Set(activeTools.map((t) => t.id)));
    }
  }, [activeTools, enabledToolIds.size]);

  useEffect(() => {
    if (activeMcp.length > 0 && enabledMcpIds.size === 0) {
      setEnabledMcpIds(new Set(activeMcp.map((s) => s.id)));
    }
  }, [activeMcp, enabledMcpIds.size]);

  const createAndSend = useMutation({
    mutationFn: async ({ text, attachmentIds }: { text: string; attachmentIds: string[] }) => {
      if (!modelId) throw new Error('Select a model first');
      if (creating.current) return;
      creating.current = true;
      const conv = await api<Conversation>('/conversations', {
        method: 'POST',
        body: JSON.stringify({
          provider_model_id: modelId,
          tool_ids: Array.from(enabledToolIds),
          mcp_server_ids: Array.from(enabledMcpIds),
        }),
      });
      sessionStorage.setItem('__pending_msg', JSON.stringify({ convId: conv.id, text, attachmentIds }));
      qc.invalidateQueries({ queryKey: ['conversations'] });
      router.push(`/app/c/${conv.id}`);
    },
    onError: (err: Error) => {
      creating.current = false;
      toast.error(err.message);
    },
  });

  function toggleTool(toolId: string) {
    setEnabledToolIds((prev) => {
      const next = new Set(prev);
      if (next.has(toolId)) next.delete(toolId);
      else next.add(toolId);
      return next;
    });
  }

  function toggleMcp(mcpId: string) {
    setEnabledMcpIds((prev) => {
      const next = new Set(prev);
      if (next.has(mcpId)) next.delete(mcpId);
      else next.add(mcpId);
      return next;
    });
  }

  const firstName = user?.display_name?.split(' ')[0] || user?.email?.split('@')[0] || 'there';

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-canvas">
      <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-hairline bg-canvas px-4 sm:px-5">
        <PageHamburger />
        <a href="/app">
          <Logo size={20} wordmarkClassName="hidden sm:inline" />
        </a>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto px-4 py-10">
        <div className="flex w-full max-w-[640px] flex-col items-center gap-6 sm:gap-8">
          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: EASE_OUT }}
            className="text-center font-serif text-[clamp(30px,6vw,52px)] font-medium leading-[1.12] tracking-tight text-ink"
          >
            <span className="sm:hidden">
              Hey <em className="italic text-primary">{firstName}</em>
            </span>
            <span className="hidden sm:inline">
              Hey <em className="italic text-primary">{firstName}</em>
              <br />
              What can I help you with today?
            </span>
          </motion.h1>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: 0.06, ease: EASE_OUT }}
            className="w-full"
          >
            <ChatComposer
              onSend={(text, attachmentIds) => createAndSend.mutate({ text, attachmentIds })}
              onCancel={() => {}}
              streaming={false}
              disabled={!modelId || createAndSend.isPending}
              prefill={prefill}
              activeTools={activeTools.filter((t) => enabledToolIds.has(t.id))}
              availableTools={activeTools}
              onToggleTool={toggleTool}
              activeMcp={activeMcp.filter((s) => enabledMcpIds.has(s.id))}
              availableMcp={activeMcp}
              onToggleMcp={toggleMcp}
              models={activeModels}
              modelId={modelId}
              onModelChange={setModelId}
            />
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: 0.12, ease: EASE_OUT }}
            className="flex flex-wrap justify-center gap-2"
          >
            {SUGGESTIONS.map(({ label, icon: Icon }) => (
              <button
                key={label}
                onClick={() => setPrefill(`${label} `)}
                className="inline-flex items-center gap-1.5 rounded-md border border-hairline bg-canvas px-3.5 py-2 text-[13px] text-body transition-colors duration-120 ease-out hover:bg-surface-card hover:text-ink"
              >
                <Icon size={13} />
                {label}
              </button>
            ))}
          </motion.div>

          {activeModels.length === 0 && !models.isPending && (
            <div className="text-center text-sm text-muted-soft">
              No models configured.{' '}
              <a href="/app/settings/models" className="text-body underline hover:text-ink">
                Add one
              </a>{' '}
              to start chatting.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
