'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, Pencil } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardBody } from '@/components/ui/card';
import { Tag } from '@/components/ui/tag';
import { FieldHint, Input, Label, Textarea } from '@/components/ui/input';
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
import { Switch } from '@/components/ui/switch';
import { PageTopBar } from '@/components/layout/page-top-bar';
import type { ProviderModel, ProviderType } from '@/lib/types';

const PROVIDER_LABELS: Record<ProviderType, string> = {
  openai: 'OpenAI',
  openai_compatible: 'OpenAI-compatible (Groq / vLLM / …)',
  azure: 'Azure OpenAI',
  anthropic: 'Anthropic',
  gemini: 'Google Gemini',
  ollama: 'Ollama',
};

const NEEDS_ENDPOINT: ProviderType[] = ['openai_compatible', 'ollama', 'azure'];
const NEEDS_API_VERSION: ProviderType[] = ['azure'];

const STAGGERS = ['stagger-0', 'stagger-1', 'stagger-2', 'stagger-3', 'stagger-4', 'stagger-5'];

export default function ModelsPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editModel, setEditModel] = useState<ProviderModel | null>(null);
  const [form, setForm] = useState<{
    name: string;
    provider_type: ProviderType;
    endpoint_url: string;
    model_name: string;
    api_version: string;
    api_key: string;
    default_system_prompt: string;
    supports_vision: boolean;
    supports_tools: boolean;
  }>({
    name: '',
    provider_type: 'openai',
    endpoint_url: '',
    model_name: '',
    api_version: '',
    api_key: '',
    default_system_prompt: '',
    supports_vision: false,
    supports_tools: true,
  });

  const models = useQuery<ProviderModel[]>({
    queryKey: ['models'],
    queryFn: () => api('/models'),
  });

  const create = useMutation({
    mutationFn: () =>
      api<ProviderModel>('/models', {
        method: 'POST',
        body: JSON.stringify({
          name: form.name,
          provider_type: form.provider_type,
          endpoint_url: form.endpoint_url || null,
          model_name: form.model_name,
          api_version: form.api_version || null,
          api_key: form.api_key || null,
          default_system_prompt: form.default_system_prompt || null,
          supports_vision: form.supports_vision,
          supports_tools: form.supports_tools,
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['models'] });
      setOpen(false);
      resetForm();
      toast.success('Model added');
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const update = useMutation({
    mutationFn: () => {
      if (!editModel) throw new Error('No model selected');
      return api<ProviderModel>(`/models/${editModel.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: form.name,
          provider_type: form.provider_type,
          endpoint_url: form.endpoint_url || null,
          model_name: form.model_name,
          api_version: form.api_version || null,
          ...(form.api_key ? { api_key: form.api_key } : {}),
          default_system_prompt: form.default_system_prompt || null,
          supports_vision: form.supports_vision,
          supports_tools: form.supports_tools,
        }),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['models'] });
      setEditModel(null);
      resetForm();
      toast.success('Model updated');
    },
    onError: (err: Error) => toast.error(err.message),
  });

  function openEdit(m: ProviderModel) {
    setForm({
      name: m.name,
      provider_type: m.provider_type,
      endpoint_url: m.endpoint_url ?? '',
      model_name: m.model_name,
      api_version: m.api_version ?? '',
      api_key: '',
      default_system_prompt: m.default_system_prompt ?? '',
      supports_vision: m.supports_vision,
      supports_tools: m.supports_tools,
    });
    setEditModel(m);
  }

  const remove = useMutation({
    mutationFn: (id: string) => api(`/models/${id}`, { method: 'DELETE' }),
    onMutate: (id) => {
      const prev = qc.getQueryData<ProviderModel[]>(['models']);
      qc.setQueryData<ProviderModel[]>(['models'], (old) => (old ?? []).filter((m) => m.id !== id));
      return { prev };
    },
    onError: (err: Error, _id, ctx) => {
      qc.setQueryData(['models'], ctx?.prev);
      toast.error(err.message || 'Failed to remove model');
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['models'] });
      toast.success('Model removed');
    },
  });

  function resetForm() {
    setForm({
      name: '',
      provider_type: 'openai',
      endpoint_url: '',
      model_name: '',
      api_version: '',
      api_key: '',
      default_system_prompt: '',
      supports_vision: false,
      supports_tools: true,
    });
  }

  const needsEndpoint = NEEDS_ENDPOINT.includes(form.provider_type);
  const needsApiVersion = NEEDS_API_VERSION.includes(form.provider_type);

  return (
    <div className="flex-1 min-w-0 overflow-y-auto bg-canvas">
      <PageTopBar section="Models" />
      <div className="mx-auto w-full max-w-[960px] px-4 py-8 sm:px-6 sm:py-10">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0 flex-1 animate-fade-up" style={{ flexBasis: 260 }}>
            <p className="mb-2 text-xs uppercase tracking-widest text-muted">Settings · Models</p>
            <h1 className="font-serif text-[clamp(22px,4vw,28px)] font-medium tracking-tight text-ink">
              Bring your own models
            </h1>
            <p className="mt-2 max-w-[480px] text-sm text-muted">
              Point at any OpenAI, Anthropic, Gemini, Ollama, or OpenAI-compatible endpoint. Keys are
              encrypted at rest.
            </p>
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4" />
                Add model
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>New model</DialogTitle>
                <DialogDescription>
                  All fields are stored per-user. Nothing here is shared with other accounts.
                </DialogDescription>
              </DialogHeader>

              <DialogBody className="space-y-4">
                <div>
                  <Label>Provider</Label>
                  <Select
                    value={form.provider_type}
                    onValueChange={(v) => setForm({ ...form, provider_type: v as ProviderType })}
                  >
                    <SelectTrigger className="mt-1.5">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.keys(PROVIDER_LABELS) as ProviderType[]).map((k) => (
                        <SelectItem key={k} value={k}>
                          {PROVIDER_LABELS[k]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <Label>Label</Label>
                    <Input
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      placeholder={
                        form.provider_type === 'azure' ? 'Azure GPT-4o EastUS2' : 'OpenAI Fast'
                      }
                      className="mt-1.5"
                    />
                  </div>
                  <div>
                    <Label>{form.provider_type === 'azure' ? 'Deployment name' : 'Model name'}</Label>
                    <Input
                      value={form.model_name}
                      onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                      placeholder={
                        form.provider_type === 'azure' ? 'gpt-4o-eastus2-rai' : 'gpt-4o-mini'
                      }
                      className="mt-1.5 font-mono"
                    />
                    {form.provider_type === 'azure' && (
                      <FieldHint>The Azure deployment ID, not the model family.</FieldHint>
                    )}
                  </div>
                </div>

                {needsEndpoint && (
                  <div>
                    <Label>{form.provider_type === 'azure' ? 'Azure resource URL' : 'Endpoint URL'}</Label>
                    <Input
                      value={form.endpoint_url}
                      onChange={(e) => setForm({ ...form, endpoint_url: e.target.value })}
                      placeholder={
                        form.provider_type === 'azure'
                          ? 'https://openai-eastus2-rai.openai.azure.com/'
                          : 'http://localhost:11434'
                      }
                      className="mt-1.5 font-mono text-xs"
                    />
                  </div>
                )}

                {needsApiVersion && (
                  <div>
                    <Label>API version</Label>
                    <Input
                      value={form.api_version}
                      onChange={(e) => setForm({ ...form, api_version: e.target.value })}
                      placeholder="2025-01-01-preview"
                      className="mt-1.5 font-mono text-xs"
                    />
                    <FieldHint>Azure OpenAI api-version query parameter.</FieldHint>
                  </div>
                )}

                <div>
                  <Label>API key</Label>
                  <Input
                    type="password"
                    value={form.api_key}
                    onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                    placeholder="sk-…"
                    className="mt-1.5 font-mono text-xs"
                    autoComplete="off"
                  />
                </div>

                <div>
                  <Label>Default system prompt</Label>
                  <Textarea
                    value={form.default_system_prompt}
                    onChange={(e) => setForm({ ...form, default_system_prompt: e.target.value })}
                    placeholder="You are a concise, careful assistant."
                    className="mt-1.5"
                  />
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <label className="flex cursor-pointer items-center justify-between rounded-md border border-hairline px-3 py-2 transition-colors duration-160 ease-out hover:bg-surface-card">
                    <span className="text-sm text-ink">Vision</span>
                    <Switch
                      checked={form.supports_vision}
                      onCheckedChange={(v) => setForm({ ...form, supports_vision: v })}
                    />
                  </label>
                  <label className="flex cursor-pointer items-center justify-between rounded-md border border-hairline px-3 py-2 transition-colors duration-160 ease-out hover:bg-surface-card">
                    <span className="text-sm text-ink">Tools</span>
                    <Switch
                      checked={form.supports_tools}
                      onCheckedChange={(v) => setForm({ ...form, supports_tools: v })}
                    />
                  </label>
                </div>
              </DialogBody>

              <DialogFooter>
                <Button variant="secondary" onClick={() => setOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={() => create.mutate()}
                  disabled={!form.name || !form.model_name || create.isPending}
                >
                  {create.isPending ? 'Saving…' : 'Save'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        <div className="space-y-3">
          {models.isPending ? (
            <Card>
              <CardBody className="py-14 text-center text-sm text-muted">Loading models…</CardBody>
            </Card>
          ) : models.isError ? (
            <Card>
              <CardBody className="py-14 text-center text-sm text-danger">
                Couldn&apos;t load models. Try refreshing the page.
              </CardBody>
            </Card>
          ) : models.data?.length === 0 ? (
            <Card>
              <CardBody className="py-14 text-center text-sm text-muted">
                No models configured yet.
              </CardBody>
            </Card>
          ) : (
            models.data?.map((m, i) => (
              <Card
                key={m.id}
                className={`animate-fade-up ${STAGGERS[Math.min(i, STAGGERS.length - 1)]}`}
              >
                <CardBody className="flex flex-wrap items-start justify-between gap-3 sm:flex-nowrap sm:items-center">
                  <div className="min-w-0 flex-1" style={{ flexBasis: 200 }}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="truncate font-medium text-ink">{m.name}</span>
                      <Tag tone="blue">{PROVIDER_LABELS[m.provider_type].split(' ')[0]}</Tag>
                      {m.has_api_key ? (
                        <Tag tone="green">Key set</Tag>
                      ) : (
                        <Tag tone="yellow">No key</Tag>
                      )}
                      {m.supports_vision && <Tag tone="neutral">Vision</Tag>}
                      {m.supports_tools && <Tag tone="neutral">Tools</Tag>}
                    </div>
                    <div className="mt-1 break-all font-mono text-sm text-muted">
                      {m.model_name}
                      {m.endpoint_url ? ` · ${m.endpoint_url}` : ''}
                      {m.api_version ? ` · api-version=${m.api_version}` : ''}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={() => openEdit(m)}>
                      <Pencil className="h-3.5 w-3.5" />
                      Edit
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Delete model"
                      onClick={() => remove.mutate(m.id)}
                    >
                      <Trash2 className="h-4 w-4 text-muted" />
                    </Button>
                  </div>
                </CardBody>
              </Card>
            ))
          )}
        </div>
      </div>

      {/* ── Edit model dialog ─────────────────────────────────────── */}
      <Dialog open={!!editModel} onOpenChange={(o) => { if (!o) { setEditModel(null); resetForm(); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit model</DialogTitle>
            <DialogDescription>
              All fields are stored per-user. Leave API key blank to keep the existing key.
            </DialogDescription>
          </DialogHeader>

          <DialogBody className="space-y-4">
            <div>
              <Label>Provider</Label>
              <Select
                value={form.provider_type}
                onValueChange={(v) => setForm({ ...form, provider_type: v as ProviderType })}
              >
                <SelectTrigger className="mt-1.5">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(Object.keys(PROVIDER_LABELS) as ProviderType[]).map((k) => (
                    <SelectItem key={k} value={k}>
                      {PROVIDER_LABELS[k]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <Label>Label</Label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="mt-1.5"
                />
              </div>
              <div>
                <Label>{form.provider_type === 'azure' ? 'Deployment name' : 'Model name'}</Label>
                <Input
                  value={form.model_name}
                  onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                  className="mt-1.5 font-mono"
                />
              </div>
            </div>

            {NEEDS_ENDPOINT.includes(form.provider_type) && (
              <div>
                <Label>{form.provider_type === 'azure' ? 'Azure resource URL' : 'Endpoint URL'}</Label>
                <Input
                  value={form.endpoint_url}
                  onChange={(e) => setForm({ ...form, endpoint_url: e.target.value })}
                  className="mt-1.5 font-mono text-xs"
                />
              </div>
            )}

            {NEEDS_API_VERSION.includes(form.provider_type) && (
              <div>
                <Label>API version</Label>
                <Input
                  value={form.api_version}
                  onChange={(e) => setForm({ ...form, api_version: e.target.value })}
                  placeholder="2025-01-01-preview"
                  className="mt-1.5 font-mono text-xs"
                />
                <FieldHint>Azure OpenAI api-version query parameter.</FieldHint>
              </div>
            )}

            <div>
              <Label>API key</Label>
              <Input
                type="password"
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                placeholder={editModel?.has_api_key ? '(leave blank to keep existing key)' : 'sk-…'}
                className="mt-1.5 font-mono text-xs"
                autoComplete="off"
              />
              {editModel?.has_api_key && (
                <FieldHint>A key is already set. Enter a new one to replace it.</FieldHint>
              )}
            </div>

            <div>
              <Label>Default system prompt</Label>
              <Textarea
                value={form.default_system_prompt}
                onChange={(e) => setForm({ ...form, default_system_prompt: e.target.value })}
                className="mt-1.5"
              />
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="flex cursor-pointer items-center justify-between rounded-md border border-hairline px-3 py-2 transition-colors duration-160 ease-out hover:bg-surface-card">
                <span className="text-sm text-ink">Vision</span>
                <Switch
                  checked={form.supports_vision}
                  onCheckedChange={(v) => setForm({ ...form, supports_vision: v })}
                />
              </label>
              <label className="flex cursor-pointer items-center justify-between rounded-md border border-hairline px-3 py-2 transition-colors duration-160 ease-out hover:bg-surface-card">
                <span className="text-sm text-ink">Tools</span>
                <Switch
                  checked={form.supports_tools}
                  onCheckedChange={(v) => setForm({ ...form, supports_tools: v })}
                />
              </label>
            </div>
          </DialogBody>

          <DialogFooter>
            <Button variant="secondary" onClick={() => { setEditModel(null); resetForm(); }}>
              Cancel
            </Button>
            <Button
              onClick={() => update.mutate()}
              disabled={!form.name || !form.model_name || update.isPending}
            >
              {update.isPending ? 'Saving…' : 'Save changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
