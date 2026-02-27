import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import NewRequest from './pages/NewRequest'
import RequestDetail from './pages/RequestDetail'
import DeploymentDetail from './pages/DeploymentDetail'
import Admin from './pages/Admin'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/new" element={<NewRequest />} />
        <Route path="/request/:id" element={<RequestDetail />} />
        <Route path="/deployment/:id" element={<DeploymentDetail />} />
        <Route path="/admin" element={<Admin />} />
      </Route>
    </Routes>
  )
}
