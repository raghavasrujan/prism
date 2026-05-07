'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, Play, X, Zap, Pencil } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardBody } from '@/components/ui/card';
import { Tag } from '@/components/ui/tag';
import { Input, Label, Textarea, FieldHint } from '@/components/ui/input';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import type { CustomTool, ToolImplType, ToolTestResponse } from '@/lib/types';
import { PageTopBar } from '@/components/layout/page-top-bar';

// ── Starter templates ──────────────────────────────────────────────────────
// Each template pre-fills name, description, args_schema, and Python code so
// users can get started without knowing JSON Schema syntax.

const SCHEMA_EMPTY = JSON.stringify({ type: 'object', properties: {}, required: [] }, null, 2);

type Template = {
  label: string;
  emoji: string;
  name: string;
  description: string;
  schema: string;
  code: string;
  impl: ToolImplType;
};

const TEMPLATES: Template[] = [
  {
    label: 'No args',
    emoji: '⚡',
    name: 'get_time',
    description: 'Returns the current UTC date and time.',
    schema: SCHEMA_EMPTY,
    impl: 'python_inline',
    code: `def run(args: dict) -> dict:
    from datetime import datetime, timezone
    return {"utc": datetime.now(timezone.utc).isoformat()}
`,
  },
  {
    label: 'One string',
    emoji: '🔤',
    name: 'word_count',
    description: 'Counts words, characters, and lines in a text string.',
    schema: JSON.stringify(
      {
        type: 'object',
        properties: {
          text: { type: 'string', description: 'The text to analyse' },
        },
        required: ['text'],
      },
      null,
      2,
    ),
    impl: 'python_inline',
    code: `def run(args: dict) -> dict:
    text = args["text"]
    return {
        "words": len(text.split()),
        "chars": len(text),
        "lines": text.count("\\n") + 1,
    }
`,
  },
  {
    label: 'Calculator',
    emoji: '🧮',
    name: 'calculator',
    description: 'Performs basic arithmetic: add, sub, mul, div.',
    schema: JSON.stringify(
      {
        type: 'object',
        properties: {
          a: { type: 'number', description: 'First number' },
          b: { type: 'number', description: 'Second number' },
          op: {
            type: 'string',
            enum: ['add', 'sub', 'mul', 'div'],
            description: 'Operation to perform',
          },
        },
        required: ['a', 'b', 'op'],
      },
      null,
      2,
    ),
    impl: 'python_inline',
    code: `def run(args: dict) -> dict:
    a, b, op = args["a"], args["b"], args["op"]
    match op:
        case "add": return {"result": a + b}
        case "sub": return {"result": a - b}
        case "mul": return {"result": a * b}
        case "div":
            if b == 0:
                return {"error": "division by zero"}
            return {"result": a / b}
    return {"error": f"unknown op: {op}"}
`,
  },
  {
    label: 'HTTP GET',
    emoji: '🌐',
    name: 'fetch_url',
    description: 'Fetches a URL and returns the response body (first 2000 chars).',
    schema: JSON.stringify(
      {
        type: 'object',
        properties: {
          url: { type: 'string', description: 'URL to fetch' },
        },
        required: ['url'],
      },
      null,
      2,
    ),
    impl: 'python_inline',
    code: `def run(args: dict) -> dict:
    import urllib.request
    url = args["url"]
    with urllib.request.urlopen(url, timeout=10) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return {"status": resp.status, "body": body[:2000]}
`,
  },
  {
    label: 'JSON transform',
    emoji: '🔄',
    name: 'json_transform',
    description: 'Filters a list of objects by a key/value pair.',
    schema: JSON.stringify(
      {
        type: 'object',
        properties: {
          items: {
            type: 'array',
            items: { type: 'object' },
            description: 'List of objects to filter',
          },
          key: { type: 'string', description: 'Property name to filter on' },
          value: { description: 'Value to match' },
        },
        required: ['items', 'key', 'value'],
      },
      null,
      2,
    ),
    impl: 'python_inline',
    code: `def run(args: dict) -> dict:
    items = args["items"]
    key   = args["key"]
    value = args["value"]
    filtered = [i for i in items if i.get(key) == value]
    return {"count": len(filtered), "items": filtered}
`,
  },
  {
    label: 'Blank Python',
    emoji: '🐍',
    name: 'my_tool',
    description: 'Write your own tool from scratch.',
    schema: SCHEMA_EMPTY,
    impl: 'python_inline',
    code: `def run(args: dict) -> dict:
    # args contains whatever you declare in the schema above.
    # Return a JSON-serialisable dict.
    return {"result": "hello from my_tool"}
`,
  },
  {
    label: 'HTTP webhook',
    emoji: '🔗',
    name: 'my_webhook',
    description: 'Calls an external HTTP endpoint.',
    schema: JSON.stringify(
      {
        type: 'object',
        properties: {
          payload: { type: 'string', description: 'Data to send' },
        },
        required: ['payload'],
      },
      null,
      2,
    ),
    impl: 'http',
    code: '',
  },
];

const STAGGERS = ['stagger-0', 'stagger-1', 'stagger-2', 'stagger-3', 'stagger-4', 'stagger-5'];

export default function ToolsPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editTool, setEditTool] = useState<CustomTool | null>(null);
  const [impl, setImpl] = useState<ToolImplType>('python_inline');
  const [testFor, setTestFor] = useState<CustomTool | null>(null);

  const [form, setForm] = useState({
    name: '',
    description: '',
    args_schema: SCHEMA_EMPTY,
    timeout_ms: 30000,
    endpoint_url: '',
    method: 'POST',
    code: TEMPLATES[5].code, // Blank Python starter
    memory_limit_mb: 256,
    cpu_time_limit_s: 10,
    network_access: false,
  });

  function applyTemplate(t: Template) {
    setImpl(t.impl);
    setForm(f => ({
      ...f,
      name: t.name,
      description: t.description,
      args_schema: t.schema,
      code: t.code,
    }));
  }

  const tools = useQuery<CustomTool[]>({
    queryKey: ['tools'],
    queryFn: () => api('/tools'),
  });

  const create = useMutation({
    mutationFn: () => {
      let schema: unknown;
      try {
        schema = JSON.parse(form.args_schema);
      } catch {
        throw new Error('args_schema must be valid JSON');
      }
      const base = {
        name: form.name,
        description: form.description,
        args_schema: schema,
        timeout_ms: form.timeout_ms,
        impl_type: impl,
      };
      if (impl === 'http') {
        return api<CustomTool>('/tools', {
          method: 'POST',
          body: JSON.stringify({
            ...base,
            endpoint_url: form.endpoint_url,
            method: form.method,
          }),
        });
      }
      return api<CustomTool>('/tools', {
        method: 'POST',
        body: JSON.stringify({
          ...base,
          code: form.code,
          runtime: 'python3.14',
          memory_limit_mb: form.memory_limit_mb,
          cpu_time_limit_s: form.cpu_time_limit_s,
          network_access: form.network_access,
        }),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tools'] });
      setOpen(false);
      toast.success('Tool created');
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const update = useMutation({
    mutationFn: () => {
      if (!editTool) throw new Error('No tool selected');
      let schema: unknown;
      try {
        schema = JSON.parse(form.args_schema);
      } catch {
        throw new Error('args_schema must be valid JSON');
      }
      const base = {
        name: form.name,
        description: form.description,
        args_schema: schema,
        timeout_ms: form.timeout_ms,
        impl_type: impl,
      };
      if (impl === 'http') {
        return api<CustomTool>(`/tools/${editTool.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ ...base, endpoint_url: form.endpoint_url, method: form.method }),
        });
      }
      return api<CustomTool>(`/tools/${editTool.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          ...base,
          code: form.code,
          runtime: 'python3.14',
          memory_limit_mb: form.memory_limit_mb,
          cpu_time_limit_s: form.cpu_time_limit_s,
          network_access: form.network_access,
        }),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tools'] });
      setEditTool(null);
      toast.success('Tool updated');
    },
    onError: (err: Error) => toast.error(err.message),
  });

  function openEdit(t: CustomTool) {
    setImpl(t.impl_type);
    setForm({
      name: t.name,
      description: t.description,
      args_schema: JSON.stringify(t.args_schema, null, 2),
      timeout_ms: t.timeout_ms,
      endpoint_url: t.endpoint_url ?? '',
      method: t.method ?? 'POST',
      code: t.code ?? '',
      memory_limit_mb: t.memory_limit_mb,
      cpu_time_limit_s: t.cpu_time_limit_s,
      network_access: t.network_access,
    });
    setEditTool(t);
  }

  const remove = useMutation({
    mutationFn: (id: string) => api(`/tools/${id}`, { method: 'DELETE' }),
    onMutate: (id) => {
      const prev = qc.getQueryData<CustomTool[]>(['tools']);
      qc.setQueryData<CustomTool[]>(['tools'], (old) => (old ?? []).filter((t) => t.id !== id));
      return { prev };
    },
    onError: (err: Error, _id, ctx) => {
      qc.setQueryData(['tools'], ctx?.prev);
      toast.error(err.message || 'Failed to remove tool');
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tools'] });
      toast.success('Tool removed');
    },
  });

  return (
    <div className="flex-1 min-w-0 overflow-y-auto bg-canvas">
      <PageTopBar section="Tools" />
      <div className="mx-auto w-full max-w-[960px] px-4 py-8 sm:px-6 sm:py-10">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0 flex-1 animate-fade-up" style={{ flexBasis: 260 }}>
            <p className="mb-2 text-xs uppercase tracking-widest text-muted">Settings · Tools</p>
            <h1 className="font-serif text-[clamp(22px,4vw,28px)] font-medium tracking-tight text-ink">
              Custom tools
            </h1>
            <p className="mt-2 max-w-xl text-sm text-muted">
              HTTP webhooks or inline Python. Python tools run in a subprocess sandbox with CPU,
              memory, wall-clock, and network caps.
            </p>
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4" />
                Add tool
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-2xl">
              <DialogHeader>
                <DialogTitle>New tool</DialogTitle>
                <DialogDescription>
                  Snake_case name, JSON-Schema for args, and either an HTTP endpoint or a Python
                  function.
                </DialogDescription>
              </DialogHeader>

              <DialogBody className="space-y-4">
                {/* ── Template picker ─────────────────────────────────────── */}
                <div>
                  <Label>Start from a template</Label>
                  <div className="mt-2 grid grid-cols-2 gap-1.5 sm:grid-cols-4">
                    {TEMPLATES.map(t => (
                      <button
                        key={t.name}
                        type="button"
                        onClick={() => applyTemplate(t)}
                        className="group flex flex-col items-start gap-1 rounded-md border border-hairline px-2.5 py-2 text-left transition-colors duration-160 ease-out hover:border-muted-soft/50 hover:bg-surface-card active:scale-[0.97]"
                      >
                        <span className="text-base leading-none">{t.emoji}</span>
                        <span className="text-[11px] font-medium leading-tight text-body group-hover:text-ink">
                          {t.label}
                        </span>
                      </button>
                    ))}
                  </div>
                  <p className="mt-2 text-[11px] text-muted">
                    Click a template to pre-fill the form. You can edit everything after.
                  </p>
                </div>

                <div className="border-t border-hairline" />

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Name</Label>
                    <Input
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      placeholder="adder"
                      className="mt-1.5 font-mono"
                    />
                    <FieldHint>Snake_case; exposed to the model as a function name.</FieldHint>
                  </div>
                  <div>
                    <Label>Wall-clock timeout (ms)</Label>
                    <Input
                      type="number"
                      min={100}
                      max={600000}
                      value={form.timeout_ms}
                      onChange={(e) => setForm({ ...form, timeout_ms: Number(e.target.value) })}
                      className="mt-1.5 font-mono"
                    />
                  </div>
                </div>

                <div>
                  <Label>Description</Label>
                  <Textarea
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                    placeholder="Adds two numbers a + b."
                    className="mt-1.5 font-sans text-sm"
                  />
                </div>

                <div>
                  <Label>Arguments JSON-Schema</Label>
                  <Textarea
                    value={form.args_schema}
                    onChange={(e) => setForm({ ...form, args_schema: e.target.value })}
                    className="mt-1.5 min-h-[100px] font-mono"
                  />
                  <p className="mt-1.5 space-y-0.5 text-[11px] text-muted">
                    <span className="block">
                      Tells the model what to pass to{' '}
                      <code className="rounded-sm bg-surface-card px-1 font-mono">run(args)</code>.
                    </span>
                    <span className="block text-muted-soft">
                      Empty = no args (model calls the tool directly).{' '}
                      <code className="font-mono">&quot;required&quot;: [&quot;x&quot;]</code> = model must provide{' '}
                      <code className="font-mono">x</code>.
                    </span>
                  </p>
                </div>

                <Tabs value={impl} onValueChange={(v) => setImpl(v as ToolImplType)}>
                  <TabsList>
                    <TabsTrigger value="python_inline">Python inline</TabsTrigger>
                    <TabsTrigger value="http">HTTP webhook</TabsTrigger>
                  </TabsList>

                  <TabsContent value="python_inline" className="space-y-3">
                    <div>
                      <Label>Python code — must define run(args) → dict</Label>
                      <Textarea
                        value={form.code}
                        onChange={(e) => setForm({ ...form, code: e.target.value })}
                        className="mt-1.5 min-h-[180px] font-mono text-sm"
                        spellCheck={false}
                      />
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <Label>Memory (MB)</Label>
                        <Input
                          type="number"
                          min={32}
                          max={2048}
                          value={form.memory_limit_mb}
                          onChange={(e) =>
                            setForm({ ...form, memory_limit_mb: Number(e.target.value) })
                          }
                          className="mt-1.5 font-mono"
                        />
                      </div>
                      <div>
                        <Label>CPU (s)</Label>
                        <Input
                          type="number"
                          min={1}
                          max={120}
                          value={form.cpu_time_limit_s}
                          onChange={(e) =>
                            setForm({ ...form, cpu_time_limit_s: Number(e.target.value) })
                          }
                          className="mt-1.5 font-mono"
                        />
                      </div>
                      <label className="mt-6 flex cursor-pointer items-center justify-between rounded-md border border-hairline px-3 py-2 transition-colors duration-160 ease-out hover:bg-surface-card">
                        <span className="text-sm text-ink">Network</span>
                        <Switch
                          checked={form.network_access}
                          onCheckedChange={(v) => setForm({ ...form, network_access: v })}
                        />
                      </label>
                    </div>
                  </TabsContent>

                  <TabsContent value="http" className="space-y-3">
                    <div>
                      <Label>Endpoint URL</Label>
                      <Input
                        value={form.endpoint_url}
                        onChange={(e) => setForm({ ...form, endpoint_url: e.target.value })}
                        placeholder="https://your.api/tool"
                        className="mt-1.5 font-mono"
                      />
                    </div>
                    <div>
                      <Label>Method</Label>
                      <Input
                        value={form.method}
                        onChange={(e) => setForm({ ...form, method: e.target.value.toUpperCase() })}
                        className="mt-1.5 font-mono"
                      />
                    </div>
                  </TabsContent>
                </Tabs>
              </DialogBody>

              <DialogFooter>
                <Button variant="secondary" onClick={() => setOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={() => create.mutate()} disabled={create.isPending || !form.name}>
                  {create.isPending ? 'Saving…' : 'Save'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        <div className="space-y-3">
          {tools.isPending ? (
            <Card>
              <CardBody className="py-14 text-center text-sm text-muted">Loading tools…</CardBody>
            </Card>
          ) : tools.isError ? (
            <Card>
              <CardBody className="py-14 text-center text-sm text-danger">
                Couldn&apos;t load tools. Try refreshing the page.
              </CardBody>
            </Card>
          ) : tools.data?.length === 0 ? (
            <Card>
              <CardBody className="flex flex-col items-center gap-2 py-14 text-center">
                <Zap className="h-5 w-5 text-muted-soft" />
                <p className="text-sm text-muted">No tools yet.</p>
                <p className="text-xs text-muted-soft">
                  Add an HTTP webhook or inline Python function to give your models new abilities.
                </p>
              </CardBody>
            </Card>
          ) : (
            tools.data?.map((t, i) => (
              <Card
                key={t.id}
                className={`animate-fade-up ${STAGGERS[Math.min(i, STAGGERS.length - 1)]}`}
              >
                <CardBody className="flex flex-wrap items-start justify-between gap-4 sm:flex-nowrap sm:items-center">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="truncate font-mono text-sm text-ink">{t.name}</span>
                      <Tag tone={t.impl_type === 'python_inline' ? 'green' : 'blue'}>
                        {t.impl_type === 'python_inline' ? 'Python' : 'HTTP'}
                      </Tag>
                      {t.impl_type === 'python_inline' && (
                        <Tag tone="neutral">
                          {t.memory_limit_mb}MB · {t.cpu_time_limit_s}s
                          {t.network_access ? ' · net' : ''}
                        </Tag>
                      )}
                    </div>
                    <div className="mt-1 line-clamp-1 text-sm text-muted">{t.description}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={() => setTestFor(t)}>
                      <Play className="h-3.5 w-3.5" />
                      Test
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => openEdit(t)}>
                      <Pencil className="h-3.5 w-3.5" />
                      Edit
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Delete tool"
                      onClick={() => remove.mutate(t.id)}
                    >
                      <Trash2 className="h-4 w-4 text-muted" />
                    </Button>
                  </div>
                </CardBody>
              </Card>
            ))
          )}
        </div>

        <TestDrawer tool={testFor} onClose={() => setTestFor(null)} />

        {/* ── Edit tool dialog ─────────────────────────────────────── */}
        <Dialog open={!!editTool} onOpenChange={(o) => !o && setEditTool(null)}>
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>Edit tool</DialogTitle>
              <DialogDescription>
                Update the tool definition. Changes take effect immediately.
              </DialogDescription>
            </DialogHeader>

            <DialogBody className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Name</Label>
                  <Input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="mt-1.5 font-mono"
                  />
                  <FieldHint>Snake_case; exposed to the model as a function name.</FieldHint>
                </div>
                <div>
                  <Label>Wall-clock timeout (ms)</Label>
                  <Input
                    type="number"
                    min={100}
                    max={600000}
                    value={form.timeout_ms}
                    onChange={(e) => setForm({ ...form, timeout_ms: Number(e.target.value) })}
                    className="mt-1.5 font-mono"
                  />
                </div>
              </div>

              <div>
                <Label>Description</Label>
                <Textarea
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="mt-1.5 font-sans text-sm"
                />
              </div>

              <div>
                <Label>Arguments JSON-Schema</Label>
                <Textarea
                  value={form.args_schema}
                  onChange={(e) => setForm({ ...form, args_schema: e.target.value })}
                  className="mt-1.5 min-h-[100px] font-mono"
                />
              </div>

              <Tabs value={impl} onValueChange={(v) => setImpl(v as ToolImplType)}>
                <TabsList>
                  <TabsTrigger value="python_inline">Python inline</TabsTrigger>
                  <TabsTrigger value="http">HTTP webhook</TabsTrigger>
                </TabsList>

                <TabsContent value="python_inline" className="space-y-3">
                  <div>
                    <Label>Python code — must define run(args) → dict</Label>
                    <Textarea
                      value={form.code}
                      onChange={(e) => setForm({ ...form, code: e.target.value })}
                      className="mt-1.5 min-h-[180px] font-mono text-sm"
                      spellCheck={false}
                    />
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <Label>Memory (MB)</Label>
                      <Input
                        type="number"
                        min={32}
                        max={2048}
                        value={form.memory_limit_mb}
                        onChange={(e) =>
                          setForm({ ...form, memory_limit_mb: Number(e.target.value) })
                        }
                        className="mt-1.5 font-mono"
                      />
                    </div>
                    <div>
                      <Label>CPU (s)</Label>
                      <Input
                        type="number"
                        min={1}
                        max={120}
                        value={form.cpu_time_limit_s}
                        onChange={(e) =>
                          setForm({ ...form, cpu_time_limit_s: Number(e.target.value) })
                        }
                        className="mt-1.5 font-mono"
                      />
                    </div>
                    <label className="mt-6 flex cursor-pointer items-center justify-between rounded-md border border-hairline px-3 py-2 transition-colors duration-160 ease-out hover:bg-surface-card">
                      <span className="text-sm text-ink">Network</span>
                      <Switch
                        checked={form.network_access}
                        onCheckedChange={(v) => setForm({ ...form, network_access: v })}
                      />
                    </label>
                  </div>
                </TabsContent>

                <TabsContent value="http" className="space-y-3">
                  <div>
                    <Label>Endpoint URL</Label>
                    <Input
                      value={form.endpoint_url}
                      onChange={(e) => setForm({ ...form, endpoint_url: e.target.value })}
                      placeholder="https://your.api/tool"
                      className="mt-1.5 font-mono"
                    />
                  </div>
                  <div>
                    <Label>Method</Label>
                    <Input
                      value={form.method}
                      onChange={(e) => setForm({ ...form, method: e.target.value.toUpperCase() })}
                      className="mt-1.5 font-mono"
                    />
                  </div>
                </TabsContent>
              </Tabs>
            </DialogBody>

            <DialogFooter>
              <Button variant="secondary" onClick={() => setEditTool(null)}>
                Cancel
              </Button>
              <Button
                onClick={() => update.mutate()}
                disabled={update.isPending || !form.name}
              >
                {update.isPending ? 'Saving…' : 'Save changes'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}

function TestDrawer({ tool, onClose }: { tool: CustomTool | null; onClose: () => void }) {
  const [args, setArgs] = useState('{}');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ToolTestResponse | null>(null);

  async function run() {
    if (!tool) return;
    setRunning(true);
    setResult(null);
    try {
      const parsed = JSON.parse(args);
      const r = await api<ToolTestResponse>(`/tools/${tool.id}/test`, {
        method: 'POST',
        body: JSON.stringify({ args: parsed }),
      });
      setResult(r);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <Dialog open={!!tool} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            Test <span className="font-mono">{tool?.name}</span>
          </DialogTitle>
          <DialogDescription>
            Sends the args below through the same runtime the agent uses.
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-4">
          <div>
            <Label>Args JSON</Label>
            <Textarea
              value={args}
              onChange={(e) => setArgs(e.target.value)}
              className="mt-1.5 min-h-[100px] font-mono"
            />
          </div>

          <Button onClick={run} disabled={running}>
            <Play className="h-4 w-4" />
            {running ? 'Running…' : 'Run'}
          </Button>

          {result && (
            <div className="mt-2 space-y-3">
              <div className="flex items-center gap-2 text-xs">
                <Tag tone={result.ok ? 'green' : 'red'}>{result.ok ? 'ok' : 'error'}</Tag>
                <span className="font-mono text-muted">{result.duration_ms}ms</span>
                {result.status_code && (
                  <span className="font-mono text-muted">HTTP {result.status_code}</span>
                )}
              </div>
              {result.error && (
                <div className="whitespace-pre-wrap rounded-md border border-danger/25 bg-danger/8 p-2 font-mono text-xs text-danger">
                  {result.error}
                </div>
              )}
              {result.result != null && (
                <div>
                  <Label>Result</Label>
                  <pre className="mt-1.5 overflow-x-auto rounded-md border border-hairline bg-surface-card p-2 font-mono text-xs text-body">
                    {JSON.stringify(result.result, null, 2)}
                  </pre>
                </div>
              )}
              {result.stderr && (
                <div>
                  <Label>Stderr</Label>
                  <pre className="mt-1.5 max-h-40 overflow-x-auto rounded-md border border-hairline bg-surface-card p-2 font-mono text-xs text-body">
                    {result.stderr}
                  </pre>
                </div>
              )}
            </div>
          )}
        </DialogBody>

        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            <X className="h-4 w-4" />
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
