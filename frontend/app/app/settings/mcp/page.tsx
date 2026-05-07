'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, RefreshCw, Trash2, Pencil } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardBody } from '@/components/ui/card';
import { Tag } from '@/components/ui/tag';
import { Input, Label, FieldHint } from '@/components/ui/input';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { McpServer, McpTransport } from '@/lib/types';
import { PageTopBar } from '@/components/layout/page-top-bar';

export default function McpPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editServer, setEditServer] = useState<McpServer | null>(null);
  const [form, setForm] = useState({
    name: '',
    transport: 'http' as McpTransport,
    url: '',
    headers: '',
  });

  const servers = useQuery<McpServer[]>({
    queryKey: ['mcp'],
    queryFn: () => api('/mcp'),
  });

  const create = useMutation({
    mutationFn: async () => {
      let headers: Record<string, string> | null = null;
      if (form.headers.trim()) {
        try {
          headers = JSON.parse(form.headers) as Record<string, string>;
        } catch {
          throw new Error('Headers must be valid JSON');
        }
      }
      return api<McpServer>('/mcp', {
        method: 'POST',
        body: JSON.stringify({
          name: form.name,
          transport: form.transport,
          url: form.url,
          headers,
        }),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mcp'] });
      setOpen(false);
      setForm({ name: '', transport: 'http', url: '', headers: '' });
      toast.success('MCP server added');
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const update = useMutation({
    mutationFn: async () => {
      if (!editServer) throw new Error('No server selected');
      let headers: Record<string, string> | null = null;
      if (form.headers.trim()) {
        try {
          headers = JSON.parse(form.headers) as Record<string, string>;
        } catch {
          throw new Error('Headers must be valid JSON');
        }
      }
      return api<McpServer>(`/mcp/${editServer.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: form.name,
          transport: form.transport,
          url: form.url,
          headers,
        }),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mcp'] });
      setEditServer(null);
      setForm({ name: '', transport: 'http', url: '', headers: '' });
      toast.success('MCP server updated');
    },
    onError: (err: Error) => toast.error(err.message),
  });

  function openEdit(s: McpServer) {
    setForm({ name: s.name, transport: s.transport, url: s.url, headers: '' });
    setEditServer(s);
  }

  const refresh = useMutation({
    mutationFn: (id: string) => api(`/mcp/${id}/refresh`, { method: 'POST' }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['mcp'] });
      const tools = (data as { tools?: unknown[] })?.tools?.length ?? 0;
      toast.success(`Discovered ${tools} tools`);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api(`/mcp/${id}`, { method: 'DELETE' }),
    onMutate: (id) => {
      const prev = qc.getQueryData<McpServer[]>(['mcp']);
      qc.setQueryData<McpServer[]>(['mcp'], (old) => (old ?? []).filter((s) => s.id !== id));
      return { prev };
    },
    onError: (err: Error, _id, ctx) => {
      qc.setQueryData(['mcp'], ctx?.prev);
      toast.error(err.message || 'Failed to remove MCP server');
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mcp'] });
      toast.success('MCP server removed');
    },
  });

  return (
    <div className="flex-1 min-w-0 overflow-y-auto bg-canvas">
      <PageTopBar section="MCP Servers" />
      <div className="mx-auto w-full max-w-[960px] px-4 py-8 sm:px-8 sm:py-10">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4 animate-fade-up">
          <div className="min-w-0">
            <p className="mb-2 text-xs uppercase tracking-widest text-muted-soft">Settings · MCP</p>
            <h1 className="font-serif text-3xl font-medium tracking-tight text-ink">MCP servers</h1>
            <p className="mt-2 max-w-xl text-sm text-muted">
              Remote Model Context Protocol servers over HTTP or SSE. Their tools get merged in when
              attached to a conversation.
            </p>
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4" />
                Add MCP
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>New MCP server</DialogTitle>
                <DialogDescription>
                  Point at an MCP-compatible HTTP endpoint. Headers are encrypted at rest.
                </DialogDescription>
              </DialogHeader>

              <DialogBody className="space-y-4">
                <div>
                  <Label>Name</Label>
                  <Input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="filesystem"
                    className="mt-1.5"
                  />
                </div>

                <div>
                  <Label>Transport</Label>
                  <Select
                    value={form.transport}
                    onValueChange={(v) => setForm({ ...form, transport: v as McpTransport })}
                  >
                    <SelectTrigger className="mt-1.5">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="http">HTTP (POST)</SelectItem>
                      <SelectItem value="sse">SSE</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>URL</Label>
                  <Input
                    value={form.url}
                    onChange={(e) => setForm({ ...form, url: e.target.value })}
                    placeholder="https://mcp.example/rpc"
                    className="mt-1.5 font-mono text-xs"
                  />
                </div>

                <div>
                  <Label>Headers (optional JSON)</Label>
                  <Input
                    value={form.headers}
                    onChange={(e) => setForm({ ...form, headers: e.target.value })}
                    placeholder='{"authorization": "Bearer …"}'
                    className="mt-1.5 font-mono text-xs"
                  />
                  <FieldHint>Encrypted at rest.</FieldHint>
                </div>
              </DialogBody>

              <DialogFooter>
                <Button variant="secondary" onClick={() => setOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={() => create.mutate()}
                  disabled={create.isPending || !form.name || !form.url}
                >
                  {create.isPending ? 'Saving…' : 'Save'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        <div className="space-y-3">
          {servers.isPending ? (
            <Card>
              <CardBody className="py-14 text-center text-sm text-muted">
                Loading MCP servers…
              </CardBody>
            </Card>
          ) : servers.isError ? (
            <Card>
              <CardBody className="py-14 text-center text-sm text-danger">
                Couldn’t load MCP servers.
              </CardBody>
            </Card>
          ) : servers.data?.length === 0 ? (
            <Card>
              <CardBody className="py-14 text-center text-sm text-muted">
                No MCP servers yet.
              </CardBody>
            </Card>
          ) : (
            servers.data?.map((s, i) => (
              <Card
                key={s.id}
                className={`animate-fade-up ${i < 5 ? `stagger-${i}` : 'stagger-5'}`}
              >
                <CardBody className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="truncate font-medium text-ink">{s.name}</span>
                      <Tag tone="blue">{s.transport.toUpperCase()}</Tag>
                      {s.last_probe_ok === true && <Tag tone="green">Reachable</Tag>}
                      {s.last_probe_ok === false && <Tag tone="red">Error</Tag>}
                    </div>
                    <div className="mt-1 truncate font-mono text-sm text-muted">{s.url}</div>
                    {s.last_probe_error && (
                      <div className="mt-1 truncate font-mono text-xs text-danger">
                        {s.last_probe_error}
                      </div>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => refresh.mutate(s.id)}
                      disabled={refresh.isPending}
                    >
                      <RefreshCw
                        className={`h-3.5 w-3.5 ${refresh.isPending ? 'animate-spin' : ''}`}
                      />
                      Refresh
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => openEdit(s)}>
                      <Pencil className="h-3.5 w-3.5" />
                      Edit
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => remove.mutate(s.id)}>
                      <Trash2 className="h-4 w-4 text-muted" />
                    </Button>
                  </div>
                </CardBody>
              </Card>
            ))
          )}
        </div>
      </div>

      {/* ── Edit MCP server dialog ─────────────────────────────── */}
      <Dialog open={!!editServer} onOpenChange={(o) => !o && setEditServer(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit MCP server</DialogTitle>
            <DialogDescription>
              Update the server configuration. Headers are encrypted at rest.
            </DialogDescription>
          </DialogHeader>

          <DialogBody className="space-y-4">
            <div>
              <Label>Name</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="mt-1.5"
              />
            </div>

            <div>
              <Label>Transport</Label>
              <Select
                value={form.transport}
                onValueChange={(v) => setForm({ ...form, transport: v as McpTransport })}
              >
                <SelectTrigger className="mt-1.5">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="http">HTTP (POST)</SelectItem>
                  <SelectItem value="sse">SSE</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label>URL</Label>
              <Input
                value={form.url}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
                placeholder="https://mcp.example/rpc"
                className="mt-1.5 font-mono text-xs"
              />
            </div>

            <div>
              <Label>Headers (optional JSON)</Label>
              <Input
                value={form.headers}
                onChange={(e) => setForm({ ...form, headers: e.target.value })}
                placeholder='{"authorization": "Bearer …"}'
                className="mt-1.5 font-mono text-xs"
              />
              <FieldHint>
                {editServer?.has_headers
                  ? 'Server has existing headers. Enter new JSON to replace them, or leave blank to keep.'
                  : 'Encrypted at rest.'}
              </FieldHint>
            </div>
          </DialogBody>

          <DialogFooter>
            <Button variant="secondary" onClick={() => setEditServer(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => update.mutate()}
              disabled={update.isPending || !form.name || !form.url}
            >
              {update.isPending ? 'Saving…' : 'Save changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
