import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Truck, Brain, ChevronDown, ChevronRight, Clock, ShieldCheck, AlertTriangle, Gauge, Users, TrendingUp, Route, Building2, Settings } from 'lucide-react';
import { NAV_ITEMS } from '../../lib/constants';

const ML_SUBNAV = [
  { path: '/ml', label: 'ML Hub', icon: Brain, exact: true },
  { path: '/ml/eta', label: 'ETA Predictor', icon: Clock },
  { path: '/ml/sla', label: 'SLA Predictor', icon: ShieldCheck },
  { path: '/ml/anomaly', label: 'Anomaly Scanner', icon: AlertTriangle },
  { path: '/ml/driver-scorer', label: 'Driver Scorer', icon: Gauge },
  { path: '/ml/fatigue', label: 'Fatigue Monitor', icon: Brain },
  { path: '/ml/recommender', label: 'Driver Recommender', icon: Users },
  { path: '/ml/demand', label: 'Demand Forecast', icon: TrendingUp },
  { path: '/ml/route-optimizer', label: 'Route Optimizer', icon: Route },
  { path: '/ml/client-forecast', label: 'Client Forecast', icon: Building2 },
  { path: '/ml/models', label: 'Model Registry', icon: Settings },
];

export default function Sidebar() {
  const location = useLocation();
  const isMLActive = location.pathname.startsWith('/ml');
  const [mlExpanded, setMlExpanded] = useState(isMLActive);

  return (
    <aside className="w-60 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
      <div className="p-5 flex items-center gap-3 border-b border-gray-800">
        <div className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center">
          <Truck className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-base font-bold text-white leading-none">Smart-Truck</h1>
          <p className="text-[10px] text-gray-500 mt-0.5">Fleet Management</p>
        </div>
      </div>
      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(item => {
          // Special handling for ML Insights
          if (item.path === '/ml') {
            return (
              <div key={item.path}>
                <button
                  onClick={() => setMlExpanded(e => !e)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isMLActive
                      ? 'bg-blue-600/10 text-blue-400 border-l-2 border-blue-500'
                      : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                  }`}>
                  <div className="flex items-center gap-3">
                    <item.icon className="w-[18px] h-[18px]" />
                    {item.label}
                  </div>
                  {mlExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                </button>
                {/* ML Sub-navigation */}
                <div className={`overflow-hidden transition-all duration-300 ease-in-out ${mlExpanded ? 'max-h-[600px] opacity-100' : 'max-h-0 opacity-0'}`}>
                  <div className="ml-4 mt-1 space-y-0.5 border-l border-gray-800 pl-3">
                    {ML_SUBNAV.map(sub => (
                      <NavLink key={sub.path} to={sub.path} end={sub.exact}
                        className={({ isActive }) =>
                          `flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
                            isActive ? 'text-blue-400 bg-blue-600/10' : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800/50'
                          }`
                        }>
                        <sub.icon className="w-3.5 h-3.5" />
                        {sub.label}
                      </NavLink>
                    ))}
                  </div>
                </div>
              </div>
            );
          }

          return (
            <NavLink key={item.path} to={item.path} end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive ? 'bg-blue-600/10 text-blue-400 border-l-2 border-blue-500' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                }`
              }>
              <item.icon className="w-[18px] h-[18px]" />
              {item.label}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
