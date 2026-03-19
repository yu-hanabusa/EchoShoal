import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import NavBar from "./components/NavBar";
import HomePage from "./pages/HomePage";
import NewSimulationPage from "./pages/NewSimulationPage";
import SimulationPage from "./pages/SimulationPage";
import ReportPage from "./pages/ReportPage";
import BenchmarkListPage from "./pages/BenchmarkListPage";
import BenchmarkResultPage from "./pages/BenchmarkResultPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <NavBar />
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/new" element={<NewSimulationPage />} />
          <Route path="/simulation/:jobId" element={<SimulationPage />} />
          <Route path="/simulation/:jobId/report" element={<ReportPage />} />
          <Route path="/benchmarks" element={<BenchmarkListPage />} />
          <Route path="/benchmark/:jobId" element={<BenchmarkResultPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
