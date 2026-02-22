import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/layout/Sidebar';
import Spinner from './components/ui/Spinner';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const DriverList = lazy(() => import('./pages/DriverList'));
const DriverDetail = lazy(() => import('./pages/DriverDetail'));
const TripList = lazy(() => import('./pages/TripList'));
const TripDetail = lazy(() => import('./pages/TripDetail'));
const RouteList = lazy(() => import('./pages/RouteList'));
const RouteDetailPage = lazy(() => import('./pages/RouteDetail'));
const VehicleList = lazy(() => import('./pages/VehicleList'));
const VehicleDetail = lazy(() => import('./pages/VehicleDetail'));
const MLInsights = lazy(() => import('./pages/MLInsights'));
const Migration = lazy(() => import('./pages/Migration'));

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-gray-950 text-gray-100">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6">
          <Suspense fallback={<Spinner />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/drivers" element={<DriverList />} />
              <Route path="/drivers/:id" element={<DriverDetail />} />
              <Route path="/trips" element={<TripList />} />
              <Route path="/trips/:id" element={<TripDetail />} />
              <Route path="/routes" element={<RouteList />} />
              <Route path="/routes/:origin/:destination" element={<RouteDetailPage />} />
              <Route path="/vehicles" element={<VehicleList />} />
              <Route path="/vehicles/:id" element={<VehicleDetail />} />
              <Route path="/ml" element={<MLInsights />} />
              <Route path="/migration" element={<Migration />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </BrowserRouter>
  );
}
