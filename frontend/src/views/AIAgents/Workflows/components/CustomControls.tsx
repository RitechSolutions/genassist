import React from "react";
import { useReactFlow } from "reactflow";
import { ZoomIn, ZoomOut, Maximize2, Lock, Unlock, Wand2 } from "lucide-react";
import ShortcutsHelp from "./ShortcutsHelp";

interface CustomControlsProps {
  nodesDraggable: boolean;
  nodesConnectable: boolean;
  elementsSelectable: boolean;
  onNodesDraggableChange: (draggable: boolean) => void;
  onNodesConnectableChange: (connectable: boolean) => void;
  onElementsSelectableChange: (selectable: boolean) => void;
  onAutoArrange: () => void;
}

const CustomControls: React.FC<CustomControlsProps> = ({
  nodesDraggable,
  nodesConnectable,
  elementsSelectable,
  onNodesDraggableChange,
  onNodesConnectableChange,
  onElementsSelectableChange,
  onAutoArrange,
}) => {
  const { zoomIn, zoomOut, fitView } = useReactFlow();

  const handleZoomIn = () => {
    zoomIn();
  };

  const handleZoomOut = () => {
    zoomOut();
  };

  const handleFitView = () => {
    fitView({ padding: 0.2, duration: 300 });
  };

  const isInteractive = nodesDraggable && nodesConnectable && elementsSelectable;

  const handleToggleInteractive = () => {
    const newState = !isInteractive;
    onNodesDraggableChange(newState);
    onNodesConnectableChange(newState);
    onElementsSelectableChange(newState);
  };

  return (
    // Positioning-only wrapper (no clipping) so the shortcuts popover can escape.
    <div className="react-flow__panel bottom left flex flex-col items-start gap-2">
      {/* Keyboard shortcuts button, stacked on top of the zoom controls */}
      <ShortcutsHelp />

      {/* Zoom / fit / lock controls pill */}
      <div className="wf-zoom-controls">
        <button
          type="button"
          className="react-flow__controls-button"
          onClick={handleZoomIn}
          title="Zoom in"
          aria-label="Zoom in"
        >
          <ZoomIn size={14} />
        </button>
        <button
          type="button"
          className="react-flow__controls-button"
          onClick={handleZoomOut}
          title="Zoom out"
          aria-label="Zoom out"
        >
          <ZoomOut size={14} />
        </button>
        <button
          type="button"
          className="react-flow__controls-button"
          onClick={handleFitView}
          title="Fit view"
          aria-label="Fit view"
        >
          <Maximize2 size={14} />
        </button>
        <button
          type="button"
          className="react-flow__controls-button"
          onClick={onAutoArrange}
          title="Arrange nodes"
          aria-label="Arrange nodes"
        >
          <Wand2 size={14} />
        </button>
        <button
          type="button"
          className="react-flow__controls-button"
          onClick={handleToggleInteractive}
          title={isInteractive ? "Lock view" : "Unlock view"}
          aria-label={isInteractive ? "Lock view" : "Unlock view"}
        >
          {isInteractive ? <Unlock size={14} /> : <Lock size={14} />}
        </button>
      </div>
    </div>
  );
};

export default CustomControls;
