import { renderIcon } from "../utils/iconUtils";

interface NodeAlertProps {
  missingFields: string[];
  onFix?: () => void;
  onTest?: () => void;
}

export const NodeAlert: React.FC<NodeAlertProps> = ({
  missingFields,
  onFix,
  onTest,
}) => {
  const hasMissingFields = missingFields && missingFields.length > 0;
  const message = hasMissingFields
    ? `Missing: ${missingFields.join(", ")}`
    : "Node not yet tested";
  const actionText = hasMissingFields ? "Add" : "Test";
  const handleClick = hasMissingFields ? onFix : onTest;

  return (
    <div className="flex items-center gap-3 p-4 mx-0.5 mb-0.5 mt-1 bg-red-600 rounded-sm text-white">
      <div className="flex items-center justify-center">
        {renderIcon("CircleAlert")}
      </div>
      <div className="flex-1 flex items-center">{message}</div>
      <div className="flex items-center justify-center">
        <span className="underline cursor-pointer" onClick={handleClick}>
          {actionText}
        </span>
      </div>
    </div>
  );
};
