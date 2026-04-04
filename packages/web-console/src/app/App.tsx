import { AppLayout } from "./AppLayout";
import { AppStateProvider } from "./AppStateProvider";
import { ToastProvider } from "../components/shared/feedback";

export function App() {
  return (
    <ToastProvider>
      <AppStateProvider>
        <AppLayout />
      </AppStateProvider>
    </ToastProvider>
  );
}
