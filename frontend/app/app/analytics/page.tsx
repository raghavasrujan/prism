'use client';

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '@/lib/api';
import { cn, formatCost, formatDuration, formatTokens } from '@/lib/utils';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { PageTopBar } from '@/components/layout/page-top-bar';
import { useThemeStore } from '@/stores/theme';
import type { ModelUsageRow, UsageResponse } from '@/lib/types';

type Range = '7d' | '30d' | '90d';

// recharts renders raw SVG, so it needs literal hex strings — Tailwind classes don't
// apply inside stroke/fill/contentStyle props. These mirror the CSS vars in globals.css
// for light/dark so the charts stay legible in both themes.
const CHART_COLORS = {
  light: {
    grid: '#E6DFD8',
    axis: '#8E8B82',
    tooltipBg: '#FAF9F5',
    tooltipBorder: '#E6DFD8',
    tooltipText: '#141413',
    line: '#CC785C',
    series: ['#CC785C', '#5DB8A6', '#E8A55A', '#6C6A64', '#5DB872', '#C64545', '#D4A017', '#3D3D3A'],
  },
  dark: {
    grid: '#383530',
    axis: '#7D7A73',
    tooltipBg: '#181715',
    tooltipBorder: '#383530',
    tooltipText: '#FAF9F5',
    line: '#CC785C',
    series: ['#CC785C', '#6BC4B3', '#EDB275', '#A09D96', '#6BC77E', '#D96363', '#E0B23A', '#D8D5CE'],
  },
} as const;

export default function AnalyticsPage() {
  const [range, setRange] = useState<Range>('30d');
  const { theme } = useThemeStore();
  const palette = CHART_COLORS[theme === 'dark' ? 'dark' : 'light'];
  const days = range === '7d' ? 7 : range === '30d' ? 30 : 90;
  const from = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

  const byDay = useQuery<UsageResponse>({
    queryKey: ['analytics-daymodel', range],
    queryFn: () => api(`/analytics/usage?from=${encodeURIComponent(from)}&group_by=day,model`),
  });
  const byModel = useQuery<{ rows: ModelUsageRow[] }>({
    queryKey: ['analytics-models'],
    queryFn: () => api(`/analytics/models`),
  });

  const stackedData = useStackedByDay(byDay.data);
  const modelKeys = useModelKeys(byDay.data);

  const totalCost = byDay.data?.totals.cost_usd ?? 0;
  const totalRequests = byDay.data?.totals.request_count ?? 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-canvas">
      <PageTopBar section="Analytics" />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-[1120px] px-4 py-8 sm:px-6 sm:py-10">
          <div className="mb-8 flex flex-wrap items-end justify-between gap-4 animate-fade-up">
            <div className="min-w-0">
              <p className="mb-2 text-xs uppercase tracking-widest text-muted-soft">Analytics</p>
              <h1 className="font-serif text-[clamp(22px,4vw,28px)] font-medium tracking-tight text-ink">
                Usage &amp; cost
              </h1>
            </div>
            <div className="flex gap-1 rounded-md bg-surface-soft p-1">
              {(['7d', '30d', '90d'] as Range[]).map((r) => (
                <Button
                  key={r}
                  variant={range === r ? 'primary' : 'ghost'}
                  size="sm"
                  onClick={() => setRange(r)}
                >
                  {r}
                </Button>
              ))}
            </div>
          </div>

          <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Stat label="Total requests" value={totalRequests.toLocaleString()} stagger="stagger-0" />
            <Stat
              label="Total tokens"
              value={formatTokens((byDay.data?.totals.input_tokens ?? 0) + (byDay.data?.totals.output_tokens ?? 0))}
              stagger="stagger-1"
            />
            <Stat label="Total cost" value={formatCost(totalCost)} stagger="stagger-2" />
          </div>

          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Tokens per day by model</CardTitle>
            </CardHeader>
            <CardBody>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stackedData}>
                    <CartesianGrid strokeDasharray="1 4" stroke={palette.grid} vertical={false} />
                    <XAxis dataKey="day" stroke={palette.axis} fontSize={10} tickLine={false} axisLine={false} />
                    <YAxis stroke={palette.axis} fontSize={10} tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{
                        borderRadius: 8,
                        border: `1px solid ${palette.tooltipBorder}`,
                        background: palette.tooltipBg,
                        fontSize: 12,
                      }}
                      labelStyle={{ color: palette.tooltipText }}
                    />
                    {modelKeys.map((m, i) => (
                      <Bar
                        key={m}
                        dataKey={m}
                        stackId="tokens"
                        fill={palette.series[i % palette.series.length]}
                        radius={i === modelKeys.length - 1 ? [4, 4, 0, 0] : 0}
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardBody>
          </Card>

          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Cost over time</CardTitle>
            </CardHeader>
            <CardBody>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={stackedData}>
                    <CartesianGrid strokeDasharray="1 4" stroke={palette.grid} vertical={false} />
                    <XAxis dataKey="day" stroke={palette.axis} fontSize={10} tickLine={false} axisLine={false} />
                    <YAxis
                      stroke={palette.axis}
                      fontSize={10}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v) => `$${v}`}
                    />
                    <Tooltip
                      formatter={(v: number) => formatCost(v)}
                      contentStyle={{
                        borderRadius: 8,
                        border: `1px solid ${palette.tooltipBorder}`,
                        background: palette.tooltipBg,
                        fontSize: 12,
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="__cost__"
                      stroke={palette.line}
                      strokeWidth={1.5}
                      dot={{ r: 2 }}
                      name="Cost"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>By model — all time</CardTitle>
            </CardHeader>
            <CardBody className="overflow-x-auto p-0">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-widest text-muted-soft">
                    <th className="px-6 py-3 font-medium">Model</th>
                    <th className="px-4 py-3 text-right font-medium">Requests</th>
                    <th className="px-4 py-3 text-right font-medium">Input</th>
                    <th className="px-4 py-3 text-right font-medium">Output</th>
                    <th className="px-4 py-3 text-right font-medium">Cost</th>
                    <th className="px-6 py-3 text-right font-medium">Avg latency</th>
                  </tr>
                </thead>
                <tbody>
                  {byModel.isPending && (
                    <tr>
                      <td colSpan={6} className="px-6 py-10 text-center text-sm text-muted-soft">
                        Loading usage…
                      </td>
                    </tr>
                  )}
                  {byModel.isError && (
                    <tr>
                      <td colSpan={6} className="px-6 py-10 text-center text-sm text-danger">
                        Couldn&apos;t load usage by model.
                      </td>
                    </tr>
                  )}
                  {byModel.data?.rows.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-6 py-10 text-center text-sm text-muted-soft">
                        No usage yet.
                      </td>
                    </tr>
                  )}
                  {byModel.data?.rows.map((r) => (
                    <tr
                      key={r.provider_snapshot ?? 'unknown'}
                      className="border-t border-hairline transition-colors duration-160 ease-out hover:bg-surface-card"
                    >
                      <td className="truncate px-6 py-3 font-mono text-ink">
                        {r.provider_snapshot || 'unknown'}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-body">{r.request_count}</td>
                      <td className="px-4 py-3 text-right font-mono text-body">{formatTokens(r.input_tokens)}</td>
                      <td className="px-4 py-3 text-right font-mono text-body">{formatTokens(r.output_tokens)}</td>
                      <td className="px-4 py-3 text-right font-mono text-body">{formatCost(r.cost_usd)}</td>
                      <td className="px-6 py-3 text-right font-mono text-body">{formatDuration(r.avg_latency_ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, stagger }: { label: string; value: string; stagger?: string }) {
  return (
    <Card className={cn('animate-fade-up', stagger)}>
      <CardBody>
        <div className="text-xs uppercase tracking-widest text-muted-soft">{label}</div>
        <div className="mt-2 text-3xl font-semibold tracking-tight text-ink">{value}</div>
      </CardBody>
    </Card>
  );
}

function useStackedByDay(data: UsageResponse | undefined) {
  if (!data) return [];
  const byDay: Record<string, Record<string, string | number>> = {};
  for (const point of data.series) {
    if (!point.day) continue;
    const key = point.day;
    if (!byDay[key]) byDay[key] = { day: key.slice(5), __cost__: 0 };
    const modelKey = point.provider_snapshot || 'unknown';
    byDay[key][modelKey] =
      ((byDay[key][modelKey] as number | undefined) ?? 0) +
      point.input_tokens +
      point.output_tokens;
    byDay[key].__cost__ = ((byDay[key].__cost__ as number) ?? 0) + point.cost_usd;
  }
  return Object.values(byDay);
}

function useModelKeys(data: UsageResponse | undefined): string[] {
  if (!data) return [];
  const set = new Set<string>();
  for (const p of data.series) set.add(p.provider_snapshot || 'unknown');
  return Array.from(set);
}
