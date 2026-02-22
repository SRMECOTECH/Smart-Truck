import { ResponsiveContainer, BarChart as RechartsBar, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';
import { CHART_COLORS } from '../../lib/colors';

interface Series { key: string; color: string; label: string; }
interface Props { data: any[]; xKey: string; series: Series[]; height?: number; }

export default function BarChart({ data, xKey, series, height = 300 }: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsBar data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
        <XAxis dataKey={xKey} tick={{ fill: '#9ca3af', fontSize: 12 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={{ backgroundColor: CHART_COLORS.tooltipBg, border: '1px solid #374151', borderRadius: 8, color: '#f3f4f6' }} />
        {series.map(s => (
          <Bar key={s.key} dataKey={s.key} name={s.label} fill={s.color} radius={[4,4,0,0]} />
        ))}
      </RechartsBar>
    </ResponsiveContainer>
  );
}
