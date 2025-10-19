import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import VideoUpscaler from "./components/VideoUpscaler";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<VideoUpscaler />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
