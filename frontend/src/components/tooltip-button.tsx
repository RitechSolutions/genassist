import { Tooltip, TooltipTrigger, TooltipContent } from './RadixTooltip';

interface TooltipButtonProps {
  button: React.ReactNode;
  tooltipContent: React.ComponentProps<typeof TooltipContent>;
  className?: string;
  side?: 'top' | 'bottom' | 'left' | 'right';
  align?: 'start' | 'center' | 'end';
}

export function TooltipButton({
  button,
  tooltipContent,
  className,
  side = 'top',
  align = 'center',
}: TooltipButtonProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent className={className} side={side} align={align} {...tooltipContent} />
    </Tooltip>
  );
}
