import { Link, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function Layout() {
  const location = useLocation()
  const { user, logout } = useAuth()

  const navLinks = [
    { to: '/', label: 'Dashboard' },
    { to: '/new', label: 'New Request' },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center gap-8">
              <Link to="/" className="text-xl font-bold text-indigo-600">
                Peevinator
              </Link>
              <div className="flex gap-4">
                {navLinks.map((link) => (
                  <Link
                    key={link.to}
                    to={link.to}
                    className={`inline-flex items-center px-1 pt-1 text-sm font-medium border-b-2 ${
                      location.pathname === link.to
                        ? 'border-indigo-500 text-gray-900'
                        : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                    }`}
                  >
                    {link.label}
                  </Link>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-4">
              {user?.isAdmin && (
                <Link
                  to="/admin"
                  className={`text-xs font-medium px-2 py-1 rounded ${
                    location.pathname === '/admin'
                      ? 'bg-gray-200 text-gray-900'
                      : 'text-gray-400 hover:text-gray-600'
                  }`}
                >
                  Admin
                </Link>
              )}
              {user && (
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-600">{user.name}</span>
                  <button
                    onClick={logout}
                    className="text-xs text-gray-400 hover:text-gray-600"
                  >
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  )
}
