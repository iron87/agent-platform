import { AppLayout } from "./AppLayout";
import { AppStateProvider } from "./AppStateProvider";

export function App() {
  return (
    <AppStateProvider>
      <AppLayout />
    </AppStateProvider>
  );
}
