import React from "react";
import { useReactFlow } from "reactflow";
import { ZoomIn, ZoomOut, Maximize2, Lock, Unlock } from "lucide-react";

interface CustomControlsProps {
  nodesDraggable: boolean;
  nodesConnectable: boolean;
  elementsSelectable: boolean;
  onNodesDraggableChange: (draggable: boolean) => void;
  onNodesConnectableChange: (connectable: boolean) => void;
  onElementsSelectableChange: (selectable: boolean) => void;
}

const CustomControls: React.FC<CustomControlsProps> = ({
  nodesDraggable,
  nodesConnectable,
  elementsSelectable,
  onNodesDraggableChange,
  onNodesConnectableChange,
  onElementsSelectableChange,
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
    <div className="react-flow__panel react-flow__controls bottom left">
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
        onClick={handleToggleInteractive}
        title={isInteractive ? "Lock view" : "Unlock view"}
        aria-label={isInteractive ? "Lock view" : "Unlock view"}
      >
        {isInteractive ? (
          <Unlock size={14} />
        ) : (
          <Lock size={14} />
        )}
      </button>
    </div>
  );
};

export default CustomControls;
