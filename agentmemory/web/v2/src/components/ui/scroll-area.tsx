import * as React from 'react';
import { cn } from '@/utils/cn';

interface ScrollAreaProps extends React.HTMLAttributes<HTMLDivElement> {
  orientation?: 'vertical' | 'horizontal' | 'both';
}

const ScrollArea = React.forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ className, orientation = 'vertical', children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('relative overflow-auto', className)}
      style={{
        scrollbarWidth: orientation === 'horizontal' || orientation === 'both' ? 'thin' : 'auto',
        scrollbarColor: 'hsl(var(--muted-foreground) / 0.3) transparent',
      }}
      {...props}
    >
      {children}
    </div>
  )
);
ScrollArea.displayName = 'ScrollArea';

export { ScrollArea };
