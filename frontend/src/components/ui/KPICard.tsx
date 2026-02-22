import type { LucideIcon } from 'lucide-react';
import { KPI_STYLES } from '../../lib/colors';

interface Props {
  label: string;
  value: string | number;
  icon: LucideIcon;
  color: string;
}

export default function KPICard({ label, value, icon: Icon, color }: Props) {
  const s = KPI_STYLES[color] || KPI_STYLES.blue;
  return (
    <div className={`${s.bg} rounded-xl border border-gray-800 p-5`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-400 mb-1">{label}</p>
          <p className={`text-2xl font-bold ${s.text}`}>{value}</p>
        </div>
        <Icon className={`w-10 h-10 ${s.icon} opacity-60`} />
      </div>
    </div>
  );
}
