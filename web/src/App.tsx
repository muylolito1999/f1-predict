import { useHashRoute } from "./proposals/useHashRoute";
import Gallery from "./proposals/Gallery";
import Paddock from "./proposals/Paddock";
import Telemetry from "./proposals/Telemetry";
import Circuit from "./proposals/Circuit";
import Nocturne from "./proposals/Nocturne";
import Slipstream from "./proposals/Slipstream";
import Official from "./proposals/Official";

const ROUTES: Record<string, () => React.ReactNode> = {
  live: () => <Official />,
  official: () => <Official />,
  paddock: () => <Paddock />,
  telemetry: () => <Telemetry />,
  circuit: () => <Circuit />,
  nocturne: () => <Nocturne />,
  slipstream: () => <Slipstream />,
};

export default function App() {
  const [route] = useHashRoute();
  const render = ROUTES[route];
  if (render) return <>{render()}</>;
  return <Gallery />;
}
