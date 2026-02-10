import React from 'react';
import { ChatContentBlock, DynamicChatItem, FileItem, ScheduleItem } from '../types';
import { getFileIcon } from './FileTypeIcon';
import { X } from 'lucide-react';

// Utility function to parse markdown bold syntax (**text**) and convert to React elements
export const parseBoldText = (input: string): React.ReactNode[] => {
  const parts: React.ReactNode[] = [];
  const boldRegex = /\*\*(.*?)\*\*/g;
  let lastIndex = 0;
  let match;
  let key = 0;

  while ((match = boldRegex.exec(input)) !== null) {
    // Add text before the match
    if (match.index > lastIndex) {
      parts.push(input.slice(lastIndex, match.index));
    }
    
    // Add bold text
    parts.push(
      <strong key={key++} style={{ fontWeight: 700 }}>
        {match[1]}
      </strong>
    );
    
    lastIndex = match.index + match[0].length;
  }

  // Add remaining text after the last match
  if (lastIndex < input.length) {
    parts.push(input.slice(lastIndex));
  }

  // If no matches found, return the original text
  return parts.length > 0 ? parts : [input];
};

interface InteractiveContentProps {
  blocks: ChatContentBlock[];
  primaryColor: string;
  textColor: string;
  isActionable: boolean;
  onQuickAction?: (text: string) => void;
  onScheduleConfirm?: (schedule: ScheduleItem) => void;
}

export const InteractiveContent: React.FC<InteractiveContentProps> = ({
  blocks,
  primaryColor,
  textColor,
  isActionable,
  onQuickAction,
  onScheduleConfirm,
}) => {
  if (!blocks.length) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {blocks.map((block, index) => {
        
        switch (block.kind) {
          case 'file':
            const fileData = block.data;
            if (fileData && fileData.type && fileData.type.startsWith('image')) {
              return <ImageBlock key={index} imageData={fileData} />;
            } else {
              return <FileBlock key={index} fileData={fileData} />;
            }
          case 'text':
            return <TextBlock key={index} text={block.text} />;
          case 'options':
            return (
              <QuickOptions
                key={index}
                options={block.options}
                primaryColor={primaryColor}
                isActionable={isActionable}
                onQuickAction={onQuickAction}
              />
            );
          case 'items':
            return (
              <DynamicItemsList
                key={index}
                items={block.items}
                primaryColor={primaryColor}
                textColor={textColor}
                isActionable={isActionable}
                onSelect={onQuickAction}
              />
            );
          case 'schedule':
            return (
              <ScheduleBlock
                key={index}
                schedule={block.schedule}
                primaryColor={primaryColor}
                textColor={textColor}
                isActionable={isActionable}
                onQuickAction={onQuickAction}
                onConfirm={onScheduleConfirm}
              />
            );
          default:
            return null;
        }
      })}
    </div>
  );
};

const TextBlock: React.FC<{ text: string }> = ({ text }) => {
  return (
    <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
      {parseBoldText(text)}
    </div>
  );
};

interface QuickOptionsProps {
  options: string[];
  primaryColor: string;
  isActionable: boolean;
  onQuickAction?: (text: string) => void;
}

const QuickOptions: React.FC<QuickOptionsProps> = ({
  options,
  primaryColor,
  isActionable,
  onQuickAction,
}) => {
  const [visibleOptions, setVisibleOptions] = React.useState(options);

  React.useEffect(() => {
    setVisibleOptions(options);
  }, [options]);

  if (!visibleOptions.length) return null;

  return (
    <div
      style={{
        display: 'flex',
        gap: 8,
        flexWrap: 'wrap',
      }}
    >
      {visibleOptions.map((option, idx) => (
        <button
          key={`${option}-${idx}`}
          type="button"
          disabled={!isActionable}
          onClick={() => {
            if (!isActionable) return;
            setVisibleOptions([]);
            onQuickAction?.(option);
          }}
          style={{
            borderRadius: 99,
            border: 'none',
            backgroundColor: primaryColor,
            padding: '12px 12px',
            cursor: isActionable ? 'pointer' : 'not-allowed',
            fontWeight: 500,
            fontSize: 14,
            color: '#ffffff',
            whiteSpace: 'nowrap',
            transition: 'transform 0.12s ease, opacity 0.12s ease',
            opacity: isActionable ? 1 : 0.6,
            boxShadow: '0 2px 6px rgba(0,0,0,0.12)',
          }}
        >
          {option}
        </button>
      ))}
    </div>
  );
};

interface DynamicItemsListProps {
  items: DynamicChatItem[];
  primaryColor: string;
  textColor: string;
  isActionable: boolean;
  onSelect?: (text: string) => void;
}

const DynamicItemsList: React.FC<DynamicItemsListProps> = ({
  items,
  primaryColor,
  textColor,
  isActionable,
  onSelect,
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {items.map((item) => (
        <DynamicItemCard
          key={item.id}
          item={item}
          primaryColor={primaryColor}
          textColor={textColor}
          isActionable={isActionable}
          onSelect={() => isActionable && onSelect?.(item.name)}
        />
      ))}
    </div>
  );
};

interface DynamicItemCardProps {
  item: DynamicChatItem;
  primaryColor: string;
  textColor: string;
  isActionable: boolean;
  onSelect?: () => void;
  onSlotSelect?: (slot: string) => void;
  onRemove?: () => void;
}

const DynamicItemCard: React.FC<DynamicItemCardProps> = ({
  item,
  primaryColor,
  textColor,
  isActionable,
  onSelect,
  onSlotSelect,
  onRemove,
}) => {
  const [expanded, setExpanded] = React.useState(false);
  const hasSlots = Array.isArray(item.slots) && item.slots.length > 0;

  const handleCardClick = () => {
    setExpanded((prev) => !prev);
    onSelect?.();
  };

  return (
    <div
      onClick={handleCardClick}
      style={{
        display: 'flex',
        gap: 12,
        padding: 12,
        borderRadius: 12,
        border: '1px solid #e5e7eb',
        backgroundColor: '#f8fafc',
        cursor: isActionable ? 'pointer' : 'default',
        boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
      }}
    >
      {item.image && (
        <img
          src={item.image}
          alt={item.name}
          style={{ width: 64, height: 64, borderRadius: 8, objectFit: 'cover' }}
        />
      )}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
          <div style={{ fontWeight: 700, color: textColor, fontSize: 15, flex: 1 }}>
            {item.name}
          </div>
          {onRemove && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onRemove();
              }}
              style={{
                background: '#f1f5f9',
                borderRadius: 9999,
                border: '1px solid #e2e8f0',
                width: 28,
                height: 28,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
              }}
            >
              <X size={16} />
            </button>
          )}
        </div>
        {item.category && (
          <div style={{ color: '#6b7280', fontSize: 13, fontWeight: 500 }}>
            {item.category}
          </div>
        )}
        {item.description && (
          <div
            style={{
              color: '#374151',
              fontSize: 13,
              lineHeight: 1.5,
              display: '-webkit-box',
              WebkitLineClamp: expanded ? 'unset' : 3,
              WebkitBoxOrient: 'vertical',
              overflow: expanded ? 'visible' : 'hidden',
            }}
          >
            {item.description}
          </div>
        )}
        {hasSlots && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 4 }}>
            {item.slots!.map((slot) => {
              const isSelected = item.selectedSlot === slot;
              return (
                <button
                  key={slot}
                  type="button"
                  disabled={!isActionable}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (!isActionable) return;
                    onSlotSelect?.(slot);
                  }}
                  style={{
                    borderRadius: 9999,
                    border: `1px solid ${isSelected ? primaryColor : '#e5e7eb'}`,
                    backgroundColor: isSelected ? primaryColor : '#ffffff',
                    color: isSelected ? '#ffffff' : '#111827',
                    padding: '6px 12px',
                    cursor: isActionable ? 'pointer' : 'not-allowed',
                    fontSize: 13,
                    fontWeight: 600,
                  }}
                >
                  {slot}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

interface ScheduleBlockProps {
  schedule: ScheduleItem;
  primaryColor: string;
  textColor: string;
  isActionable: boolean;
  onQuickAction?: (text: string) => void;
  onConfirm?: (schedule: ScheduleItem) => void;
}

const ScheduleBlock: React.FC<ScheduleBlockProps> = ({
  schedule,
  primaryColor,
  textColor,
  isActionable,
  onQuickAction,
  onConfirm,
}) => {
  const [currentSchedule, setCurrentSchedule] = React.useState<ScheduleItem>(schedule);

  React.useEffect(() => {
    setCurrentSchedule(schedule);
  }, [schedule]);

  const updateRestaurant = (id: string, updater: (item: DynamicChatItem) => DynamicChatItem) => {
    setCurrentSchedule((prev) => ({
      ...prev,
      restaurants: prev.restaurants.map((restaurant) =>
        restaurant.id === id ? updater(restaurant) : restaurant
      ),
    }));
  };

  const removeRestaurant = (id: string) => {
    setCurrentSchedule((prev) => ({
      ...prev,
      restaurants: prev.restaurants.filter((restaurant) => restaurant.id !== id),
    }));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div
        style={{
          padding: 12,
          borderRadius: 12,
          backgroundColor: '#f8fafc',
          border: '1px solid #e5e7eb',
          fontWeight: 700,
          color: textColor,
        }}
      >
        {currentSchedule.title || 'Schedule'}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {currentSchedule.restaurants.map((restaurant) => (
          <DynamicItemCard
            key={restaurant.id}
            item={restaurant}
            primaryColor={primaryColor}
            textColor={textColor}
            isActionable={isActionable}
            onSelect={() => isActionable && onQuickAction?.(restaurant.name)}
            onSlotSelect={(slot) =>
              updateRestaurant(restaurant.id, (item) => ({ ...item, selectedSlot: slot }))
            }
            onRemove={isActionable ? () => removeRestaurant(restaurant.id) : undefined}
          />
        ))}
      </div>

      {isActionable && currentSchedule.restaurants.length > 0 && (
        <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
          <button
            type="button"
            onClick={() => onConfirm?.(currentSchedule)}
            style={{
              backgroundColor: primaryColor,
              color: '#ffffff',
              border: 'none',
              borderRadius: 10,
              padding: '10px 16px',
              fontWeight: 700,
              cursor: 'pointer',
              boxShadow: '0 1px 4px rgba(0,0,0,0.12)',
            }}
          >
            Confirm
          </button>
        </div>
      )}
    </div>
  );
};

const ImageBlock: React.FC<{ imageData: FileItem }> = ({ imageData }) => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }} onClick={() => window.open(imageData.url, '_blank')}>
      <img src={imageData.url} alt="Image" style={{ width: 80, height: 64, borderRadius: 8, objectFit: 'cover' }} />
    </div>
  );
};

const FileBlock: React.FC<{ fileData: FileItem }> = ({ fileData }) => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }} onClick={() => window.open(fileData.url, '_blank')}>
      {getFileIcon(fileData.type)}
      <span className="text-xs text-muted-foreground">{fileData.name}</span>
    </div>
  );
};