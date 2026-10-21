import { Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { accountsPath, withUsername } from './lib/shared';
import PublicLayout from './components/PublicLayout';
import AppShell from './components/AppShell';
import ScrollToTop from './components/ScrollToTop';
import { useAuth } from './state/AuthContext';
import { AdminAuthProvider, useAdminAuth } from './state/AdminAuthContext';

import Landing from './pages/public/Landing';
import Privacy from './pages/public/Privacy';
import Terms from './pages/public/Terms';
import RoleSelection from './pages/auth/RoleSelection';
import RegisterCreator from './pages/auth/RegisterCreator';
import RegisterBrand from './pages/auth/RegisterBrand';
import Login from './pages/auth/Login';
import ForgotPassword from './pages/auth/ForgotPassword';
import VerifyCode from './pages/auth/VerifyCode';
import ResetPassword from './pages/auth/ResetPassword';

import CreatorDashboard from './pages/creator/Dashboard';
import CreatorProfile from './pages/creator/Profile';
import EditCreatorProfile from './pages/creator/EditProfile';
import ConnectedAccounts from './pages/creator/ConnectedAccounts';
import BrandConnectedAccounts from './pages/brand/ConnectedAccounts';
import CampaignDiscovery from './pages/creator/CampaignDiscovery';
import CampaignDetail from './pages/creator/CampaignDetail';
import MyApplications from './pages/creator/MyApplications';
import ApplicationDetail from './pages/creator/ApplicationDetail';

import BrandDashboard from './pages/brand/Dashboard';
import BrandProfile from './pages/brand/Profile';
import EditBrandProfile from './pages/brand/EditProfile';
import CreatorDiscovery from './pages/brand/CreatorDiscovery';
import CreatorPublicProfile from './pages/brand/CreatorPublicProfile';
import CampaignList from './pages/brand/CampaignList';
import CreateCampaign from './pages/brand/CreateCampaign';
import EditCampaign from './pages/brand/EditCampaign';
import CampaignDetailBrand from './pages/brand/CampaignDetail';
import ProposalManagement from './pages/brand/ProposalManagement';
import ProposalDetail from './pages/brand/ProposalDetail';
import CampaignAnalytics from './pages/brand/CampaignAnalytics';

import NotificationsPage from './pages/shared/Notifications';
import Unauthorized from './pages/shared/Unauthorized';
import NotFound from './pages/shared/NotFound';
import VerifyEmailPage from './pages/shared/VerifyEmail';
import NotificationSettingsPage from './pages/shared/NotificationSettings';

import AdminApp from './pages/admin/App';
import AdminLogin from './pages/admin/Login';
import AdminOverview from './pages/admin/Overview';
import AdminUsers from './pages/admin/Users';
import AdminActions from './pages/admin/Actions';
import AdminPlatformReviews from './pages/admin/PlatformReviews';

function Protected({ role, children }: { role: 'creator' | 'brand'; children: JSX.Element }) {
  const { user, ready } = useAuth();
  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-mist-100">
        <div className="text-sm text-ink-500 font-mono">Loading…</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to="/unauthorized" replace />;
  return children;
}

/**
 * The backend sends the browser here after Google's consent screen
 * (`FRONTEND_URL/settings/connections?youtube=...`). Forward to the connected-accounts page,
 * which finishes the connection, keeping the query string.
 */
function ConnectionsRedirect() {
  const { search } = useLocation();
  const { user } = useAuth();
  // Brands and creators finish the Google sign-in on their own accounts page.
  if (!user) return <Navigate to="/login" replace />;
  const pathname = accountsPath(user.role === 'brand' ? 'brand' : 'creator', user.username);
  return <Navigate to={{ pathname, search }} replace />;
}

/**
 * Pages of a creator or brand live under /creator/<username>/... or /brand/<username>/....
 * Only the owner's own username works: anything else goes to the same page under their own name.
 */
function OwnerGuard({ role, children }: { role: 'creator' | 'brand'; children: JSX.Element }) {
  const { username } = useParams();
  const { pathname, search } = useLocation();
  const { user } = useAuth();
  if (!user) return null;
  const rest = pathname.split('/').slice(3).join('/');
  if (rest === '') {
    // /creator/imran goes to the dashboard. /creator/campaigns (an old address, no username) gets the name added.
    const to = username === user.username ? `${pathname.replace(/\/$/, '')}/dashboard` : withUsername(`/${role}/${username}`, user.username);
    return <Navigate to={{ pathname: to, search }} replace />;
  }
  if (username !== user.username) {
    return <Navigate to={{ pathname: withUsername(`/${role}/${rest}`, user.username), search }} replace />;
  }
  return children;
}

/** The old addresses without a username (/creator/dashboard, links in emails) go to the one with it. */
function LegacyRedirect() {
  const { pathname, search } = useLocation();
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  // Already under their own name but no such page (e.g. /creator/imran/nothing): do not add the name again.
  const parts = pathname.split('/').filter(Boolean);
  if (parts[1] === user.username) {
    return parts.length === 2 ? <Navigate to={`${pathname}/dashboard`} replace /> : <NotFound />;
  }
  return <Navigate to={{ pathname: withUsername(pathname, user.username), search }} replace />;
}

function AdminGuard({ children }: { children: JSX.Element }) {
  const { user, ready } = useAdminAuth();
  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-mist-100">
        <div className="text-sm text-ink-500 font-mono">Loading…</div>
      </div>
    );
  }
  if (!user || user.role !== 'admin') return <Navigate to="/admin/login" replace />;
  return children;
}

export default function App() {
  const { ready } = useAuth();
  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-mist-100">
        <div className="text-sm text-ink-500 font-mono">Loading…</div>
      </div>
    );
  }
  return (
    <>
      <ScrollToTop />
      <AdminAuthProvider>
      <Routes>
      <Route element={<PublicLayout />}>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register/role" element={<RoleSelection />} />
        <Route path="/register/creator" element={<RegisterCreator />} />
        <Route path="/register/brand" element={<RegisterBrand />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/verify-code" element={<VerifyCode />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />
        <Route path="/unauthorized" element={<Unauthorized />} />
      </Route>

      <Route path="/creator/:username" element={<Protected role="creator"><OwnerGuard role="creator"><AppShell /></OwnerGuard></Protected>}>
        <Route path="dashboard" element={<CreatorDashboard />} />
        <Route path="profile" element={<CreatorProfile />} />
        <Route path="profile/edit" element={<EditCreatorProfile />} />
        <Route path="accounts" element={<ConnectedAccounts />} />
        <Route path="campaigns" element={<CampaignDiscovery />} />
        <Route path="campaigns/:id" element={<CampaignDetail />} />
        <Route path="applications" element={<MyApplications />} />
        <Route path="applications/:id" element={<ApplicationDetail />} />
        <Route path="notifications" element={<NotificationsPage role="creator" />} />
        <Route path="settings/notifications" element={<NotificationSettingsPage />} />
      </Route>

      <Route path="/brand/:username" element={<Protected role="brand"><OwnerGuard role="brand"><AppShell /></OwnerGuard></Protected>}>
        <Route path="dashboard" element={<BrandDashboard />} />
        <Route path="profile" element={<BrandProfile />} />
        <Route path="profile/edit" element={<EditBrandProfile />} />
        <Route path="accounts" element={<BrandConnectedAccounts />} />
        <Route path="creators" element={<CreatorDiscovery />} />
        <Route path="creators/:id" element={<CreatorPublicProfile />} />
        <Route path="campaigns" element={<CampaignList />} />
        <Route path="campaigns/create" element={<CreateCampaign />} />
        <Route path="campaigns/:id" element={<CampaignDetailBrand />} />
        <Route path="campaigns/:id/analytics" element={<CampaignAnalytics />} />
        <Route path="campaigns/:id/edit" element={<EditCampaign />} />
        <Route path="campaigns/:id/proposals" element={<ProposalManagement />} />
        <Route path="proposals/:id" element={<ProposalDetail />} />
        <Route path="notifications" element={<NotificationsPage role="brand" />} />
        <Route path="settings/notifications" element={<NotificationSettingsPage />} />
      </Route>

      {/* Old addresses without a username. The static "settings/notifications" ones must beat :username. */}
      <Route path="/creator/settings/notifications" element={<LegacyRedirect />} />
      <Route path="/brand/settings/notifications" element={<LegacyRedirect />} />
      <Route path="/creator/*" element={<LegacyRedirect />} />
      <Route path="/brand/*" element={<LegacyRedirect />} />

      <Route path="/settings/connections" element={<ConnectionsRedirect />} />

      <Route path="/admin/login" element={<AdminLogin />} />
      <Route element={<AdminGuard><AdminApp /></AdminGuard>}>
        <Route path="/admin/overview" element={<AdminOverview />} />
        <Route path="/admin/users" element={<AdminUsers />} />
        <Route path="/admin/platform-reviews" element={<AdminPlatformReviews />} />
        <Route path="/admin/actions" element={<AdminActions />} />
      </Route>

      <Route path="*" element={<NotFound />} />
      </Routes>
      </AdminAuthProvider>
    </>
  );
}
