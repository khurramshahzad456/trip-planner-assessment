import { Navigate, Route, Routes } from 'react-router-dom'
import PlannerPage from './pages/PlannerPage.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<PlannerPage />} />
      <Route path="/trips/:tripId" element={<PlannerPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
