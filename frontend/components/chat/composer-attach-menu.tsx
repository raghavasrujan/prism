'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { ChevronRight, Paperclip, Plug, Plus, Wrench } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { Switch } from '@/components/ui/switch';
import type { CustomTool, McpServer } from '@/lib/types';

type Props = {
  onAddFiles: () => void;
  tools: CustomTool[];
  enabledToolIds: Set<string>;
  onToggleTool: (id: string) => void;
  mcpServers: McpServer[];
  enabledMcpIds: Set<string>;
  onToggleMcp: (id: string) => void;
};

const contentClass = cn(
  'z-50 w-64 overflow-hidden rounded-lg border border-hairline bg-canvas p-1 shadow-popover',
  'data-[state=open]:animate-in data-[state=closed]:animate-out',
  'data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0',
  'data-[state=open]:zoom-in-95 data-[state=closed]:zoom-out-95',
  'duration-160 ease-out',
);

const subTriggerClass = cn(
  'flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm text-body outline-none',
  'transition-colors duration-120 ease-out',
  'data-[highlighted]:bg-surface-card data-[highlighted]:text-ink data-[state=open]:bg-surface-card data-[state=open]:text-ink',
);

function ToggleRow({
  title,
  subtitle,
  checked,
  onChange,
}: {
  title: string;
  subtitle?: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <DropdownMenu.Item
      onSelect={(e) => e.preventDefault()}
      className="flex cursor-pointer items-center justify-between gap-3 rounded-md px-3 py-2 outline-none transition-colors duration-120 ease-out data-[highlighted]:bg-surface-card"
    >
      <div className="min-w-0">
        <div className="truncate font-mono text-[13px] text-ink">{title}</div>
        {subtitle && <div className="truncate text-[11px] text-muted-soft">{subtitle}</div>}
      </div>
      <Switch checked={checked} onCheckedChange={onChange} className="shrink-0" />
    </DropdownMenu.Item>
  );
}

function EmptyRow({ label, href }: { label: string; href: string }) {
  return (
    <div className="px-3 py-4 text-center text-xs text-muted-soft">
      {label}{' '}
      <Link href={href} className="text-body underline hover:text-ink">
        Add one
      </Link>
    </div>
  );
}

/**
 * The composer's "+" menu — attachments entry point that also hosts the
 * per-conversation Tools and MCP server toggles (each tool/server listed
 * individually with its own on/off switch, nested under its own submenu).
 */
export function ComposerAttachMenu({
  onAddFiles,
  tools,
  enabledToolIds,
  onToggleTool,
  mcpServers,
  enabledMcpIds,
  onToggleMcp,
}: Props) {
  const toolCount = enabledToolIds.size;
  const mcpCount = enabledMcpIds.size;

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-hairline bg-canvas text-muted transition-[background-color,color,transform] duration-160 ease-out hover:bg-surface-card hover:text-ink active:scale-[0.94]"
          aria-label="Attach, tools, and MCP servers"
        >
          <Plus size={15} />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          side="top"
          align="start"
          sideOffset={8}
          style={{ transformOrigin: 'var(--radix-dropdown-menu-content-transform-origin)' }}
          className={contentClass}
        >
          <DropdownMenu.Item onSelect={onAddFiles} className={subTriggerClass}>
            <Paperclip size={14} className="shrink-0 text-muted" />
            <span className="flex-1">Add files or photos</span>
          </DropdownMenu.Item>

          <DropdownMenu.Separator className="my-1 h-px bg-hairline" />

          <DropdownMenu.Sub>
            <DropdownMenu.SubTrigger className={subTriggerClass}>
              <Wrench size={14} className="shrink-0 text-muted" />
              <span className="flex-1">Tools</span>
              {toolCount > 0 && <span className="text-xs text-teal">{toolCount}</span>}
              <ChevronRight size={13} className="shrink-0 text-muted-soft" />
            </DropdownMenu.SubTrigger>
            <DropdownMenu.Portal>
              <DropdownMenu.SubContent
                sideOffset={6}
                style={{ transformOrigin: 'var(--radix-dropdown-menu-content-transform-origin)' }}
                className={contentClass}
              >
                {tools.length === 0 ? (
                  <EmptyRow label="No tools configured yet." href="/app/settings/tools" />
                ) : (
                  tools.map((t) => (
                    <ToggleRow
                      key={t.id}
                      title={t.name}
                      subtitle={t.description}
                      checked={enabledToolIds.has(t.id)}
                      onChange={() => onToggleTool(t.id)}
                    />
                  ))
                )}
              </DropdownMenu.SubContent>
            </DropdownMenu.Portal>
          </DropdownMenu.Sub>

          <DropdownMenu.Sub>
            <DropdownMenu.SubTrigger className={subTriggerClass}>
              <Plug size={14} className="shrink-0 text-muted" />
              <span className="flex-1">MCP servers</span>
              {mcpCount > 0 && <span className="text-xs text-teal">{mcpCount}</span>}
              <ChevronRight size={13} className="shrink-0 text-muted-soft" />
            </DropdownMenu.SubTrigger>
            <DropdownMenu.Portal>
              <DropdownMenu.SubContent
                sideOffset={6}
                style={{ transformOrigin: 'var(--radix-dropdown-menu-content-transform-origin)' }}
                className={contentClass}
              >
                {mcpServers.length === 0 ? (
                  <EmptyRow label="No MCP servers configured yet." href="/app/settings/mcp" />
                ) : (
                  mcpServers.map((s) => (
                    <ToggleRow
                      key={s.id}
                      title={s.name}
                      subtitle={s.url}
                      checked={enabledMcpIds.has(s.id)}
                      onChange={() => onToggleMcp(s.id)}
                    />
                  ))
                )}
              </DropdownMenu.SubContent>
            </DropdownMenu.Portal>
          </DropdownMenu.Sub>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
