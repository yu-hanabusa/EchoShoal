import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import NavBar from "./components/NavBar";
import DocumentsPage from "./pages/DocumentsPage";
import GraphPage from "./pages/GraphPage";
import HomePage from "./pages/HomePage";
import SimulationPage from "./pages/SimulationPage";
import ReportPage from "./pages/ReportPage";

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
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/simulation/:jobId" element={<SimulationPage />} />
          <Route path="/simulation/:jobId/report" element={<ReportPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
