import { NavLink } from 'react-router-dom';
import { Truck } from 'lucide-react';
import { NAV_ITEMS } from '../../lib/constants';

export default function Sidebar() {
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
      <nav className="flex-1 py-4 px-3 space-y-1">
        {NAV_ITEMS.map(item => (
          <NavLink key={item.path} to={item.path} end={item.path === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive ? 'bg-blue-600/10 text-blue-400 border-l-2 border-blue-500' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
              }`
            }>
            <item.icon className="w-[18px] h-[18px]" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
