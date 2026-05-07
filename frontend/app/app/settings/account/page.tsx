'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Moon, Sun } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';
import { useThemeStore } from '@/stores/theme';
import { PageTopBar } from '@/components/layout/page-top-bar';
import { Button } from '@/components/ui/button';
import { Input, Textarea } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardBody } from '@/components/ui/card';
import type { ProviderModel } from '@/lib/types';

type Tab = 'general' | 'billing' | 'api';

type MeResponse = {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  title_provider_model_id: string | null;
};

const AUTO_TITLE_MODEL = '__auto__';

export default function AccountPage() {
  const { user, logout } = useAuthStore();
  const { theme, toggle } = useThemeStore();
  const [tab, setTab] = useState<Tab>('general');
  const qc = useQueryClient();

  const me = useQuery<MeResponse>({
    queryKey: ['me'],
    queryFn: () => api('/auth/me'),
  });
  const models = useQuery<ProviderModel[]>({
    queryKey: ['models'],
    queryFn: () => api('/models'),
  });

  const [titleModelId, setTitleModelId] = useState<string>(AUTO_TITLE_MODEL);
  useEffect(() => {
    if (me.data) {
      setTitleModelId(me.data.title_provider_model_id ?? AUTO_TITLE_MODEL);
    }
  }, [me.data?.title_provider_model_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateTitleModel = useMutation({
    mutationFn: (nextId: string | null) =>
      api<MeResponse>('/auth/me', {
        method: 'PATCH',
        body: JSON.stringify({ title_provider_model_id: nextId }),
      }),
    onSuccess: (data) => {
      qc.setQueryData(['me'], data);
      toast.success('Title model updated');
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Could not update title model');
      // Roll the select back to the server's last-known value.
      setTitleModelId(me.data?.title_provider_model_id ?? AUTO_TITLE_MODEL);
    },
  });

  const activeModels = (models.data ?? []).filter((m) => m.is_active);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-canvas">
      <PageTopBar
        section="Settings"
        right={
          <>
            <Button
              variant="ghost"
              size="sm"
              onClick={toggle}
              title={theme === 'dark' ? 'Switch to light' : 'Switch to dark'}
            >
              {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
              <span className="hidden sm:inline">{theme === 'dark' ? 'Light' : 'Dark'}</span>
            </Button>
            <div className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary-active text-xs font-semibold text-white">
              {user?.display_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
            </div>
          </>
        }
      />

      <div className="mx-auto w-full max-w-[740px] px-4 py-8 sm:px-8 sm:py-10">
        <h1 className="mb-6 animate-fade-up font-serif text-[clamp(22px,4vw,28px)] font-medium tracking-tight text-ink">
          Settings
        </h1>

        <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
          <TabsList className="mb-8">
            <TabsTrigger value="general">General</TabsTrigger>
            <TabsTrigger value="billing">Plans &amp; Billing</TabsTrigger>
            <TabsTrigger value="api">API keys</TabsTrigger>
          </TabsList>

          <TabsContent value="general" className="mt-0 space-y-10">
            {/* Account */}
            <section>
              <h2 className="mb-4 font-serif text-xl font-medium tracking-tight text-ink">Account</h2>
              <div className="flex flex-col divide-y divide-hairline overflow-hidden rounded-lg border border-hairline">
                <SettingRow
                  label="Full name"
                  desc="Your real full name"
                  input={
                    <Input
                      type="text"
                      defaultValue={user?.display_name || ''}
                      placeholder="e.g. John Doe"
                      className="sm:w-64"
                    />
                  }
                />
                <SettingRow
                  label="Email"
                  desc="Your email address"
                  input={
                    <Input
                      type="email"
                      defaultValue={user?.email || ''}
                      placeholder="example@domain.com"
                      disabled
                      className="sm:w-64"
                    />
                  }
                />
              </div>
            </section>

            {/* Preferences */}
            <section>
              <h2 className="mb-4 font-serif text-xl font-medium tracking-tight text-ink">Preferences</h2>
              <div className="flex flex-col divide-y divide-hairline overflow-hidden rounded-lg border border-hairline">
                <SettingRow
                  label="Custom instructions"
                  desc="Give the AI any instructions or specify any preferences for the output"
                  input={
                    <Textarea
                      placeholder="Example: Give only concise responses"
                      className="min-h-[88px] sm:w-64"
                    />
                  }
                />
                <SettingRow
                  label="Chat title model"
                  desc="Model used to auto-generate chat names. Auto uses each conversation's own model."
                  input={
                    <Select
                      value={titleModelId}
                      onValueChange={(v) => {
                        setTitleModelId(v);
                        updateTitleModel.mutate(v === AUTO_TITLE_MODEL ? null : v);
                      }}
                      disabled={updateTitleModel.isPending || me.isPending}
                    >
                      <SelectTrigger className="sm:w-64">
                        <SelectValue placeholder="Auto" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={AUTO_TITLE_MODEL}>Auto (per-conversation model)</SelectItem>
                        {activeModels.map((m) => (
                          <SelectItem key={m.id} value={m.id}>
                            {m.name} — {m.model_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  }
                />
                <ToggleRow
                  label="Appearance"
                  desc="Switch between dark and light mode"
                  checked={theme === 'dark'}
                  onCheckedChange={toggle}
                />
                <ToggleRow label="Privacy mode" desc="Prevents training on your data" defaultChecked />
                <ToggleRow
                  label="Use memory"
                  desc="Remembers previous conversations and details you shared"
                  defaultChecked
                />
              </div>
            </section>

            {/* Danger zone */}
            <section>
              <h2 className="mb-4 font-serif text-xl font-medium tracking-tight text-ink">Danger zone</h2>
              <div className="flex flex-col divide-y divide-hairline overflow-hidden rounded-lg border border-hairline">
                <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="text-sm font-medium text-ink">Sign out</div>
                    <div className="mt-0.5 text-[13px] text-muted">Sign out of your account</div>
                  </div>
                  <Button variant="secondary" size="sm" onClick={logout} className="self-start sm:self-auto">
                    Sign out
                  </Button>
                </div>
                <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="text-sm font-medium text-danger">Delete account</div>
                    <div className="mt-0.5 text-[13px] text-muted">Permanently delete your account and all data</div>
                  </div>
                  <Button variant="danger" size="sm" className="self-start sm:self-auto">
                    Delete
                  </Button>
                </div>
              </div>
            </section>
          </TabsContent>

          <TabsContent value="billing" className="mt-0">
            <Card>
              <CardBody className="py-16 text-center">
                <div className="mb-2 text-lg text-ink">No active plan</div>
                <div className="text-sm text-muted">
                  You&apos;re using the free tier. No subscription needed for BYOM.
                </div>
              </CardBody>
            </Card>
          </TabsContent>

          <TabsContent value="api" className="mt-0">
            <Card>
              <CardBody className="py-16 text-center">
                <div className="mb-2 text-lg text-ink">API Keys</div>
                <div className="text-sm text-muted">Manage your API keys for external integrations.</div>
              </CardBody>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

function SettingRow({ label, desc, input }: { label: string; desc: string; input: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-ink">{label}</div>
        <div className="mt-0.5 text-[13px] text-muted">{desc}</div>
      </div>
      <div className="shrink-0">{input}</div>
    </div>
  );
}

function ToggleRow({
  label,
  desc,
  checked,
  defaultChecked,
  onCheckedChange,
}: {
  label: string;
  desc: string;
  checked?: boolean;
  defaultChecked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
}) {
  const [internalChecked, setInternalChecked] = useState(defaultChecked ?? false);
  const isControlled = checked !== undefined;
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-4">
      <div>
        <div className="text-sm font-medium text-ink">{label}</div>
        <div className="mt-0.5 text-[13px] text-muted">{desc}</div>
      </div>
      <Switch
        checked={isControlled ? checked : internalChecked}
        onCheckedChange={(v) => {
          if (onCheckedChange) onCheckedChange(v);
          else setInternalChecked(v);
        }}
      />
    </div>
  );
}
