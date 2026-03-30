import { LayoutDashboard, Users, MapPin, Route, Truck, Brain, Database, Building2 } from 'lucide-react';

export const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/drivers', label: 'Drivers', icon: Users },
  { path: '/trips', label: 'Trips', icon: MapPin },
  { path: '/routes', label: 'Routes', icon: Route },
  { path: '/vehicles', label: 'Vehicles', icon: Truck },
  { path: '/clients', label: 'Clients', icon: Building2 },
  { path: '/ml', label: 'ML Insights', icon: Brain },
  { path: '/migration', label: 'Migration', icon: Database },
];

export const SEVERITY_STYLES: Record<string, string> = {
  critical: 'bg-red-900/40 text-red-400 border border-red-800',
  high: 'bg-red-900/40 text-red-400 border border-red-800',
  warning: 'bg-amber-900/40 text-amber-400 border border-amber-800',
  medium: 'bg-amber-900/40 text-amber-400 border border-amber-800',
  info: 'bg-blue-900/40 text-blue-400 border border-blue-800',
  low: 'bg-emerald-900/40 text-emerald-400 border border-emerald-800',
};
