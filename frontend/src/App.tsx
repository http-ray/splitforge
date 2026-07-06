import { useEffect } from "react";
import Sidebar from "./components/Sidebar";
import Viewer from "./components/Viewer";
import { useStore } from "./store/useStore";
import { fetchPrinters } from "./api/client";

export default function App() {
  const setPrinters = useStore((s) => s.setPrinters);

  useEffect(() => {
    fetchPrinters()
      .then(setPrinters)
      .catch(() => {
        /* backend not up yet; sidebar still renders */
      });
  }, [setPrinters]);

  return (
    <div className="app">
      <Sidebar />
      <Viewer />
    </div>
  );
}
