import { z } from "zod";

const chartSeriesSchema = z.object({
  dataKey: z.string().min(1),
  name: z.string().optional().default("Series"),
  color: z.string().optional(),
  type: z.string().optional(),
});

const chartAxisSchema = z.object({
  dataKey: z.string().optional(),
  label: z.string().optional(),
});

export const chartConfigSchema = z.object({
  chart_type: z.string().min(1),
  title: z.string().min(1),
  description: z.string().optional(),
  config: z
    .object({
      xAxis: chartAxisSchema.optional(),
      yAxis: z.object({ label: z.string().optional() }).optional(),
      nameKey: z.string().optional(),
      dataKey: z.string().optional(),
      columns: z.array(z.string()).optional(),
      series: z.array(chartSeriesSchema).optional(),
    })
    .passthrough(),
  data: z.array(z.record(z.any())),
});

export const alarmPayloadSchema = z.object({
  type: z.string().optional().default("revenue_alarm"),
  severity: z.enum(["warning", "critical"]).optional().default("warning"),
  message: z.string().optional().default(""),
  natural_message: z.string().optional(),
  current_revenue: z.number().or(z.string()).optional().default(0),
  previous_revenue: z.number().or(z.string()).optional().default(0),
  change_pct: z.number().or(z.string()).optional().default(0),
  timestamp: z.string().optional().default(""),
});

export type ParsedChartConfig = z.infer<typeof chartConfigSchema>;
